#!/usr/bin/env python3
"""
QGIS MCP Client - Optimized for speed and stability
"""

import logging
import sys
from contextlib import asynccontextmanager
import socket
import struct
import json
from typing import AsyncIterator, Dict, Any
from mcp.server.fastmcp import FastMCP, Context

_HEADER_STRUCT = struct.Struct(">I")
# 增大接收缓冲区到1MB，大幅提升大消息传输速度
_RECV_BUFFER_SIZE = 4 * 1048576  # 从1MB增大到4MB

# 强制所有日志输出到stderr，绝对禁止任何stdout输出
logging.basicConfig(
    level=logging.ERROR,  # 只输出错误，完全禁用info和warning
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # 显式指定stderr，这是核心修复
)
logger = logging.getLogger("QgisMCPServer")

# 新增：禁用所有第三方库的日志，彻底消除隐性输出
logging.getLogger("mcp").setLevel(logging.CRITICAL)
logging.getLogger("fastmcp").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

class QgisMCPServer:
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.socket = None
        # 添加连接超时，防止卡死
        self.timeout = 120 # 从10秒增加到2分钟

    def connect(self):
        """Connect to the QGIS MCP server with timeout"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            # 禁用Nagle算法，减少延迟
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 0)
            self.socket.connect((self.host, self.port))
            return True
        except Exception as e:
            logger.error(f"Error connecting to server: {str(e)}")
            self.disconnect()
            return False

    def disconnect(self):
        """Disconnect from the server safely"""
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def is_connected(self):
        """
        macOS兼容的100%可靠连接检测
        解决了send(b'')不抛异常和select检测失效的双重bug
        """
        if not self.socket:
            return False
        
        try:
            # 步骤1：先尝试发送一个1字节的无效探测包
            # 注意：这个包会被QGIS服务器忽略，但会触发TCP栈的连接状态检查
            self.socket.send(b'\x00')
            
            # 步骤2：立即尝试读取，使用非阻塞模式
            # 如果连接已关闭，recv会立即返回空字节串
            self.socket.setblocking(False)
            data = self.socket.recv(1, socket.MSG_PEEK)
            self.socket.setblocking(True)
            
            # 如果recv返回空，说明连接已关闭
            if data == b'':
                return False
            
            return True
            
        except BlockingIOError:
            # 这是正常情况：连接正常，没有数据可读
            self.socket.setblocking(True)
            return True
            
        except Exception:
            # 任何其他异常（BrokenPipe, ConnectionReset等）都说明连接已断开
            self.socket.setblocking(True)
            return False

    def send_command(self, command_type, params=None):
        """优化后的命令发送，大幅提升大消息速度"""
        if not self.is_connected():
            #logger.warning("Connection lost, reconnecting...")
            self.disconnect()
            if not self.connect():
                raise Exception("Could not connect to QGIS server")

        command = {"type": command_type, "params": params or {}}

        try:
            data = json.dumps(command, ensure_ascii=False).encode('utf-8')
            self.socket.sendall(_HEADER_STRUCT.pack(len(data)) + data)

            # 一次性读取完整头部
            header_buf = self.socket.recv(4, socket.MSG_WAITALL)
            if len(header_buf) != 4:
                raise Exception("Incomplete header received")
            
            msg_len = _HEADER_STRUCT.unpack(header_buf)[0]

            # 一次性读取完整消息，使用大缓冲区
            response_data = b''
            while len(response_data) < msg_len:
                remaining = msg_len - len(response_data)
                chunk = self.socket.recv(min(_RECV_BUFFER_SIZE, remaining))
                if not chunk:
                    raise Exception("Connection closed prematurely")
                response_data += chunk

            # 直接返回Python对象，不再转JSON字符串
            return json.loads(response_data.decode('utf-8'))

        except Exception as e:
            logger.error(f"Error sending command: {str(e)}")
            self.disconnect()
            raise Exception(f"Command failed: {str(e)}")

_qgis_connection = None

def get_qgis_connection():
    """Get or create a persistent QGIS connection"""
    global _qgis_connection

    if _qgis_connection is not None and _qgis_connection.is_connected():
        return _qgis_connection

    # 连接无效，清理旧连接
    if _qgis_connection:
        try:
            _qgis_connection.disconnect()
        except Exception:
            pass
        _qgis_connection = None

    # 创建新连接
    _qgis_connection = QgisMCPServer(host="localhost", port=9876)
    if not _qgis_connection.connect():
        _qgis_connection = None
        raise Exception("Could not connect to Qgis. Make sure the Qgis plugin is running.")
    
    logger.info("Created new persistent connection to Qgis")
    return _qgis_connection

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    try:
        # 启动时不尝试连接，避免启动失败和日志输出
        yield {}
    finally:
        global _qgis_connection
        if _qgis_connection:
            _qgis_connection.disconnect()
            _qgis_connection = None

mcp = FastMCP(
    "Qgis_mcp",
    lifespan=server_lifespan,
)

@mcp.tool()
def ping(ctx: Context) -> dict:
    """Simple ping command to check server connectivity"""
    qgis = get_qgis_connection()
    return qgis.send_command("ping")

@mcp.tool()
def get_qgis_info(ctx: Context) -> dict:
    """Get QGIS information"""
    qgis = get_qgis_connection()
    return qgis.send_command("get_qgis_info")

@mcp.tool()
def load_project(ctx: Context, path: str) -> dict:
    """Load a QGIS project from the specified path."""
    qgis = get_qgis_connection()
    return qgis.send_command("load_project", {"path": path})

@mcp.tool()
def create_new_project(ctx: Context, path: str) -> dict:
    """Create a new project and save it."""
    qgis = get_qgis_connection()
    return qgis.send_command("create_new_project", {"path": path})

@mcp.tool()
def get_project_info(ctx: Context) -> dict:
    """Get current project information"""
    qgis = get_qgis_connection()
    return qgis.send_command("get_project_info")

@mcp.tool()
def add_vector_layer(ctx: Context, path: str, provider: str = "ogr", name: str = None) -> dict:
    """Add a vector layer to the project."""
    qgis = get_qgis_connection()
    params = {"path": path, "provider": provider}
    if name:
        params["name"] = name
    return qgis.send_command("add_vector_layer", params)

@mcp.tool()
def add_raster_layer(ctx: Context, path: str, provider: str = "gdal", name: str = None) -> dict:
    """Add a raster layer to the project."""
    qgis = get_qgis_connection()
    params = {"path": path, "provider": provider}
    if name:
        params["name"] = name
    return qgis.send_command("add_raster_layer", params)

@mcp.tool()
def get_layers(ctx: Context) -> dict:
    """Retrieve all layers in the current project."""
    qgis = get_qgis_connection()
    return qgis.send_command("get_layers")

@mcp.tool()
def remove_layer(ctx: Context, layer_id: str) -> dict:
    """Remove a layer from the project by its ID."""
    qgis = get_qgis_connection()
    return qgis.send_command("remove_layer", {"layer_id": layer_id})

@mcp.tool()
def zoom_to_layer(ctx: Context, layer_id: str) -> dict:
    """Zoom to the extent of a specified layer."""
    qgis = get_qgis_connection()
    return qgis.send_command("zoom_to_layer", {"layer_id": layer_id})

@mcp.tool()
def get_layer_features(ctx: Context, layer_id: str, limit: int = 10) -> dict:
    """Retrieve features from a vector layer with an optional limit."""
    qgis = get_qgis_connection()
    return qgis.send_command("get_layer_features", {"layer_id": layer_id, "limit": limit})

@mcp.tool()
def execute_processing(ctx: Context, algorithm: str, parameters: dict) -> dict:
    """Execute a processing algorithm with the given parameters."""
    qgis = get_qgis_connection()
    return qgis.send_command("execute_processing", {"algorithm": algorithm, "parameters": parameters})

@mcp.tool()
def save_project(ctx: Context, path: str = None) -> dict:
    """Save the current project to the given path, or to the current project path if not specified."""
    qgis = get_qgis_connection()
    params = {}
    if path:
        params["path"] = path
    return qgis.send_command("save_project", params)

@mcp.tool()
def render_map(ctx: Context, path: str, width: int = 800, height: int = 600) -> dict:
    """Render the current map view to an image file with the specified dimensions."""
    qgis = get_qgis_connection()
    return qgis.send_command("render_map", {"path": path, "width": width, "height": height})

@mcp.tool()
def execute_code(ctx: Context, code: str) -> dict:
    """Execute arbitrary PyQGIS code provided as a string."""
    qgis = get_qgis_connection()
    return qgis.send_command("execute_code", {"code": code})

def main():
    """Run the MCP server with unbuffered output"""
    # 强制禁用Python输出缓冲，确保消息立即发送
    sys.stdout.reconfigure(line_buffering=False)
    sys.stderr.reconfigure(line_buffering=False)
    
    # 再次显式指定stdio传输，双重保险
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
