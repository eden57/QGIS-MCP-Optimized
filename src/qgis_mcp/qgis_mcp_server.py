#!/usr/bin/env python3
"""
QGIS MCP Client - Simple client to connect to the QGIS MCP server
"""

import logging
from contextlib import asynccontextmanager
import socket
import struct
import json
from typing import AsyncIterator, Dict, Any
from mcp.server.fastmcp import FastMCP, Context

_HEADER_STRUCT = struct.Struct(">I")

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("QgisMCPServer")

class QgisMCPServer:
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.socket = None

    def connect(self):
        """Connect to the QGIS MCP server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            return True
        except Exception as e:
            print(f"Error connecting to server: {str(e)}")
            return False

    def disconnect(self):
        """Disconnect from the server"""
        if self.socket:
            self.socket.close()
            self.socket = None

    def send_command(self, command_type, params=None):
        """Send a length-prefixed command to the server and get the response"""
        if not self.socket:
            print("Not connected to server")
            return None

        command = {"type": command_type, "params": params or {}}

        try:
            data = json.dumps(command).encode('utf-8')
            self.socket.sendall(_HEADER_STRUCT.pack(len(data)) + data)

            header_buf = b''
            while len(header_buf) < 4:
                chunk = self.socket.recv(4 - len(header_buf))
                if not chunk:
                    return None
                header_buf += chunk

            msg_len = _HEADER_STRUCT.unpack(header_buf)[0]

            response_data = b''
            while len(response_data) < msg_len:
                chunk = self.socket.recv(min(65536, msg_len - len(response_data)))
                if not chunk:
                    break
                response_data += chunk

            return json.loads(response_data.decode('utf-8'))

        except Exception as e:
            print(f"Error sending command: {str(e)}")
            return None

_qgis_connection = None

def get_qgis_connection():
    """Get or create a persistent Qgis connection"""
    global _qgis_connection

    if _qgis_connection is not None:
        try:
            _qgis_connection.socket.sendall(b'')
            return _qgis_connection
        except Exception as e:
            logger.warning(f"Existing connection is no longer valid: {str(e)}")
            try:
                _qgis_connection.disconnect()
            except Exception:
                pass
            _qgis_connection = None

    if _qgis_connection is None:
        _qgis_connection = QgisMCPServer(host="localhost", port=9876)
        if not _qgis_connection.connect():
            logger.error("Failed to connect to Qgis")
            _qgis_connection = None
            raise Exception("Could not connect to Qgis. Make sure the Qgis plugin is running.")
        logger.info("Created new persistent connection to Qgis")

    return _qgis_connection

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle"""
    try:
        logger.info("QgisMCPServer server starting up")
        try:
            get_qgis_connection()
            logger.info("Successfully connected to Qgis on startup")
        except Exception as e:
            logger.warning(f"Could not connect to Qgis on startup: {str(e)}")
            logger.warning("Make sure the Qgis addon is running before using Qgis resources or tools")
        yield {}
    finally:
        global _qgis_connection
        if _qgis_connection:
            logger.info("Disconnecting from Qgis on shutdown")
            _qgis_connection.disconnect()
            _qgis_connection = None
        logger.info("QgisMCPServer server shut down")

mcp = FastMCP(
    "Qgis_mcp",
    description="Qgis integration through the Model Context Protocol",
    lifespan=server_lifespan
)

@mcp.tool()
def ping(ctx: Context) -> str:
    """Simple ping command to check server connectivity"""
    qgis = get_qgis_connection()
    result = qgis.send_command("ping")
    return json.dumps(result, indent=2)

@mcp.tool()
def get_qgis_info(ctx: Context) -> str:
    """Get QGIS information"""
    qgis = get_qgis_connection()
    result = qgis.send_command("get_qgis_info")
    return json.dumps(result, indent=2)

@mcp.tool()
def load_project(ctx: Context, path: str) -> str:
    """Load a QGIS project from the specified path."""
    qgis = get_qgis_connection()
    result = qgis.send_command("load_project", {"path": path})
    return json.dumps(result, indent=2)

@mcp.tool()
def create_new_project(ctx: Context, path: str) -> str:
    """Create a new project and save it."""
    qgis = get_qgis_connection()
    result = qgis.send_command("create_new_project", {"path": path})
    return json.dumps(result, indent=2)

@mcp.tool()
def get_project_info(ctx: Context) -> str:
    """Get current project information"""
    qgis = get_qgis_connection()
    result = qgis.send_command("get_project_info")
    return json.dumps(result, indent=2)

@mcp.tool()
def add_vector_layer(ctx: Context, path: str, provider: str = "ogr", name: str = None) -> str:
    """Add a vector layer to the project."""
    qgis = get_qgis_connection()
    params = {"path": path, "provider": provider}
    if name:
        params["name"] = name
    result = qgis.send_command("add_vector_layer", params)
    return json.dumps(result, indent=2)

@mcp.tool()
def add_raster_layer(ctx: Context, path: str, provider: str = "gdal", name: str = None) -> str:
    """Add a raster layer to the project."""
    qgis = get_qgis_connection()
    params = {"path": path, "provider": provider}
    if name:
        params["name"] = name
    result = qgis.send_command("add_raster_layer", params)
    return json.dumps(result, indent=2)

@mcp.tool()
def get_layers(ctx: Context) -> str:
    """Retrieve all layers in the current project."""
    qgis = get_qgis_connection()
    result = qgis.send_command("get_layers")
    return json.dumps(result, indent=2)

@mcp.tool()
def remove_layer(ctx: Context, layer_id: str) -> str:
    """Remove a layer from the project by its ID."""
    qgis = get_qgis_connection()
    result = qgis.send_command("remove_layer", {"layer_id": layer_id})
    return json.dumps(result, indent=2)

@mcp.tool()
def zoom_to_layer(ctx: Context, layer_id: str) -> str:
    """Zoom to the extent of a specified layer."""
    qgis = get_qgis_connection()
    result = qgis.send_command("zoom_to_layer", {"layer_id": layer_id})
    return json.dumps(result, indent=2)

@mcp.tool()
def get_layer_features(ctx: Context, layer_id: str, limit: int = 10) -> str:
    """Retrieve features from a vector layer with an optional limit."""
    qgis = get_qgis_connection()
    result = qgis.send_command("get_layer_features", {"layer_id": layer_id, "limit": limit})
    return json.dumps(result, indent=2)

@mcp.tool()
def execute_processing(ctx: Context, algorithm: str, parameters: dict) -> str:
    """Execute a processing algorithm with the given parameters."""
    qgis = get_qgis_connection()
    result = qgis.send_command("execute_processing", {"algorithm": algorithm, "parameters": parameters})
    return json.dumps(result, indent=2)

@mcp.tool()
def save_project(ctx: Context, path: str = None) -> str:
    """Save the current project to the given path, or to the current project path if not specified."""
    qgis = get_qgis_connection()
    params = {}
    if path:
        params["path"] = path
    result = qgis.send_command("save_project", params)
    return json.dumps(result, indent=2)

@mcp.tool()
def render_map(ctx: Context, path: str, width: int = 800, height: int = 600) -> str:
    """Render the current map view to an image file with the specified dimensions."""
    qgis = get_qgis_connection()
    result = qgis.send_command("render_map", {"path": path, "width": width, "height": height})
    return json.dumps(result, indent=2)

@mcp.tool()
def execute_code(ctx: Context, code: str) -> str:
    """Execute arbitrary PyQGIS code provided as a string."""
    qgis = get_qgis_connection()
    result = qgis.send_command("execute_code", {"code": code})
    return json.dumps(result, indent=2)

def main():
    """Run the MCP server"""
    mcp.run()

if __name__ == "__main__":
    main()
