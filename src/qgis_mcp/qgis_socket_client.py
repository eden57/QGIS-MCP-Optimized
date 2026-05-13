#!/usr/bin/env python3
"""
QGIS MCP Client - Simple client to connect to the QGIS MCP server
"""

import socket
import struct
import json

_HEADER_STRUCT = struct.Struct(">I")

class QgisMCPClient:
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

    def ping(self):
        return self.send_command("ping")

    def get_qgis_info(self):
        return self.send_command("get_qgis_info")

    def get_project_info(self):
        return self.send_command("get_project_info")

    def execute_code(self, code):
        return self.send_command("execute_code", {"code": code})

    def add_vector_layer(self, path, name=None, provider="ogr"):
        params = {"path": path, "provider": provider}
        if name:
            params["name"] = name
        return self.send_command("add_vector_layer", params)

    def add_raster_layer(self, path, name=None, provider="gdal"):
        params = {"path": path, "provider": provider}
        if name:
            params["name"] = name
        return self.send_command("add_raster_layer", params)

    def get_layers(self):
        return self.send_command("get_layers")

    def remove_layer(self, layer_id):
        return self.send_command("remove_layer", {"layer_id": layer_id})

    def zoom_to_layer(self, layer_id):
        return self.send_command("zoom_to_layer", {"layer_id": layer_id})

    def get_layer_features(self, layer_id, limit=10):
        return self.send_command("get_layer_features", {"layer_id": layer_id, "limit": limit})

    def execute_processing(self, algorithm, parameters):
        return self.send_command("execute_processing", {"algorithm": algorithm, "parameters": parameters})

    def save_project(self, path=None):
        params = {}
        if path:
            params["path"] = path
        return self.send_command("save_project", params)

    def load_project(self, path):
        return self.send_command("load_project", {"path": path})

    def render_map(self, path, width=800, height=600):
        return self.send_command("render_map", {"path": path, "width": width, "height": height})

def print_json(data):
    print(json.dumps(data, indent=2))

def main():
    client = QgisMCPClient(host='localhost', port=9876)
    if not client.connect():
        print("No se pudo conectar al servidor QGIS MCP")
        return

    try:
        print("Verificando conexión...")
        response = client.ping()
        if response and response.get("status") == "success":
            print("Conexión exitosa")
        else:
            print("Error de conexión")
            return

        print("\nInformación de QGIS:")
        print_json(client.get_qgis_info())

        print("\nInformación del proyecto:")
        print_json(client.get_project_info())
    except Exception:
        print("Error ejecutando comandos")

if __name__ == "__main__":
    main()
