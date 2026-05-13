import os
import io
import sys
import json
import socket
import struct
import traceback
from qgis.core import *
from qgis.gui import *
from qgis.PyQt.QtCore import QObject, pyqtSignal, QTimer, Qt, QSize
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QVBoxLayout, QLabel, QPushButton, QSpinBox, QWidget
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.utils import active_plugins

_HEADER_STRUCT = struct.Struct(">I")

class QgisMCPServer(QObject):
    """Server class to handle socket connections and execute QGIS commands"""

    def __init__(self, host='localhost', port=9876, iface=None):
        super().__init__()
        self.host = host
        self.port = port
        self.iface = iface
        self.running = False
        self.socket = None
        self.client = None
        self.buffer = b''
        self.expected_len = None
        self.timer = None

    def start(self):
        """Start the server"""
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            self.socket.setblocking(False)

            self.timer = QTimer()
            self.timer.timeout.connect(self.process_server)
            self.timer.start(100)

            QgsMessageLog.logMessage(f"QGIS MCP server started on {self.host}:{self.port}", "QGIS MCP")
            return True
        except Exception as e:
            QgsMessageLog.logMessage(f"Failed to start server: {str(e)}", "QGIS MCP", Qgis.Critical)
            self.stop()
            return False

    def stop(self):
        """Stop the server"""
        self.running = False

        if self.timer:
            self.timer.stop()
            self.timer = None

        if self.socket:
            self.socket.close()
        if self.client:
            self.client.close()

        self.socket = None
        self.client = None
        self.buffer = b''
        self.expected_len = None
        QgsMessageLog.logMessage("QGIS MCP server stopped", "QGIS MCP")

    def process_server(self):
        """Process server operations (called by timer)"""
        if not self.running:
            return

        try:
            if not self.client and self.socket:
                try:
                    self.client, address = self.socket.accept()
                    self.client.setblocking(False)
                    QgsMessageLog.logMessage(f"Connected to client: {address}", "QGIS MCP")
                except BlockingIOError:
                    pass
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error accepting connection: {str(e)}", "QGIS MCP", Qgis.Warning)

            if self.client:
                try:
                    try:
                        data = self.client.recv(8192)
                        if data:
                            self.buffer += data
                            while True:
                                if self.expected_len is None:
                                    if len(self.buffer) < 4:
                                        break
                                    self.expected_len = _HEADER_STRUCT.unpack(self.buffer[:4])[0]
                                    self.buffer = self.buffer[4:]

                                if len(self.buffer) < self.expected_len:
                                    break

                                message = self.buffer[:self.expected_len]
                                self.buffer = self.buffer[self.expected_len:]
                                self.expected_len = None

                                command = json.loads(message.decode('utf-8'))
                                response = self.execute_command(command)
                                response_data = json.dumps(response).encode('utf-8')
                                self.client.sendall(_HEADER_STRUCT.pack(len(response_data)) + response_data)
                        else:
                            QgsMessageLog.logMessage("Client disconnected", "QGIS MCP")
                            self.client.close()
                            self.client = None
                            self.buffer = b''
                            self.expected_len = None
                    except BlockingIOError:
                        pass
                    except Exception as e:
                        QgsMessageLog.logMessage(f"Error receiving data: {str(e)}", "QGIS MCP", Qgis.Warning)
                        self.client.close()
                        self.client = None
                        self.buffer = b''
                        self.expected_len = None
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error with client: {str(e)}", "QGIS MCP", Qgis.Warning)
                    if self.client:
                        self.client.close()
                        self.client = None
                    self.buffer = b''
                    self.expected_len = None
        except Exception as e:
            QgsMessageLog.logMessage(f"Server error: {str(e)}", "QGIS MCP", Qgis.Critical)

    def execute_command(self, command):
        """Execute a command"""
        try:
            cmd_type = command.get("type")
            params = command.get("params", {})

            handlers = {
                "ping": self.ping,
                "get_qgis_info": self.get_qgis_info,
                "load_project": self.load_project,
                "get_project_info": self.get_project_info,
                "execute_code": self.execute_code,
                "add_vector_layer": self.add_vector_layer,
                "add_raster_layer": self.add_raster_layer,
                "get_layers": self.get_layers,
                "remove_layer": self.remove_layer,
                "zoom_to_layer": self.zoom_to_layer,
                "get_layer_features": self.get_layer_features,
                "execute_processing": self.execute_processing,
                "save_project": self.save_project,
                "render_map": self.render_map,
                "create_new_project": self.create_new_project,
            }

            handler = handlers.get(cmd_type)
            if handler:
                try:
                    QgsMessageLog.logMessage(f"Executing handler for {cmd_type}", "QGIS MCP")
                    result = handler(**params)
                    QgsMessageLog.logMessage("Handler execution complete", "QGIS MCP")
                    return {"status": "success", "result": result}
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error in handler: {str(e)}", "QGIS MCP", Qgis.Critical)
                    traceback.print_exc()
                    return {"status": "error", "message": str(e)}
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}
        except Exception as e:
            QgsMessageLog.logMessage(f"Error executing command: {str(e)}", "QGIS MCP", Qgis.Critical)
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def ping(self, **kwargs):
        """Simple ping command"""
        return {"pong": True}

    def get_qgis_info(self, **kwargs):
        """Get basic QGIS information"""
        return {
            "qgis_version": Qgis.version(),
            "profile_folder": QgsApplication.qgisSettingsDirPath(),
            "plugins_count": len(active_plugins)
        }

    def get_project_info(self, **kwargs):
        """Get information about the current QGIS project"""
        project = QgsProject.instance()
        info = {
            "filename": project.fileName(),
            "title": project.title(),
            "layer_count": len(project.mapLayers()),
            "crs": project.crs().authid(),
            "layers": []
        }

        layers = list(project.mapLayers().values())
        for i, layer in enumerate(layers):
            if i >= 10:
                break
            layer_info = {
                "id": layer.id(),
                "name": layer.name(),
                "type": self._get_layer_type(layer),
                "visible": layer.isValid() and project.layerTreeRoot().findLayer(layer.id()).isVisible()
            }
            info["layers"].append(layer_info)

        return info

    def _get_layer_type(self, layer):
        """Helper to get layer type as string"""
        if layer.type() == QgsMapLayer.VectorLayer:
            return f"vector_{layer.geometryType()}"
        if layer.type() == QgsMapLayer.RasterLayer:
            return "raster"
        return str(layer.type())

    def execute_code(self, code, **kwargs):
        """Execute arbitrary PyQGIS code"""
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        try:
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture
            namespace = {
                "qgis": Qgis,
                "QgsProject": QgsProject,
                "iface": self.iface,
                "QgsApplication": QgsApplication,
                "QgsVectorLayer": QgsVectorLayer,
                "QgsRasterLayer": QgsRasterLayer,
                "QgsCoordinateReferenceSystem": QgsCoordinateReferenceSystem
            }
            exec(code, namespace)
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            return {
                "executed": True,
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue()
            }
        except Exception as e:
            error_traceback = traceback.format_exc()
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            return {
                "executed": False,
                "error": str(e),
                "traceback": error_traceback,
                "stdout": stdout_capture.getvalue(),
                "stderr": stderr_capture.getvalue()
            }

    def add_vector_layer(self, path, name=None, provider="ogr", **kwargs):
        """Add a vector layer to the project"""
        if not name:
            name = os.path.basename(path)
        layer = QgsVectorLayer(path, name, provider)
        if not layer.isValid():
            raise Exception(f"Layer is not valid: {path}")
        QgsProject.instance().addMapLayer(layer)
        return {
            "id": layer.id(),
            "name": layer.name(),
            "type": self._get_layer_type(layer),
            "feature_count": layer.featureCount()
        }

    def add_raster_layer(self, path, name=None, provider="gdal", **kwargs):
        """Add a raster layer to the project"""
        if not name:
            name = os.path.basename(path)
        layer = QgsRasterLayer(path, name, provider)
        if not layer.isValid():
            raise Exception(f"Layer is not valid: {path}")
        QgsProject.instance().addMapLayer(layer)
        return {
            "id": layer.id(),
            "name": layer.name(),
            "type": "raster",
            "width": layer.width(),
            "height": layer.height()
        }

    def get_layers(self, **kwargs):
        """Get all layers in the project"""
        project = QgsProject.instance()
        layers = []
        for layer_id, layer in project.mapLayers().items():
            layer_info = {
                "id": layer_id,
                "name": layer.name(),
                "type": self._get_layer_type(layer),
                "visible": project.layerTreeRoot().findLayer(layer_id).isVisible()
            }
            if layer.type() == QgsMapLayer.VectorLayer:
                layer_info.update({
                    "feature_count": layer.featureCount(),
                    "geometry_type": layer.geometryType()
                })
            elif layer.type() == QgsMapLayer.RasterLayer:
                layer_info.update({
                    "width": layer.width(),
                    "height": layer.height()
                })
            layers.append(layer_info)
        return layers

    def remove_layer(self, layer_id, **kwargs):
        """Remove a layer from the project"""
        project = QgsProject.instance()
        if layer_id in project.mapLayers():
            project.removeMapLayer(layer_id)
            return {"removed": layer_id}
        raise Exception(f"Layer not found: {layer_id}")

    def zoom_to_layer(self, layer_id, **kwargs):
        """Zoom to a layer's extent"""
        project = QgsProject.instance()
        if layer_id in project.mapLayers():
            layer = project.mapLayer(layer_id)
            self.iface.setActiveLayer(layer)
            self.iface.zoomToActiveLayer()
            return {"zoomed_to": layer_id}
        raise Exception(f"Layer not found: {layer_id}")

    def get_layer_features(self, layer_id, limit=10, **kwargs):
        """Get features from a vector layer"""
        project = QgsProject.instance()
        if layer_id not in project.mapLayers():
            raise Exception(f"Layer not found: {layer_id}")

        layer = project.mapLayer(layer_id)
        if layer.type() != QgsMapLayer.VectorLayer:
            raise Exception(f"Layer is not a vector layer: {layer_id}")

        features = []
        for i, feature in enumerate(layer.getFeatures()):
            if i >= limit:
                break
            attrs = {}
            for field in layer.fields():
                attrs[field.name()] = feature.attribute(field.name())
            geom = None
            if feature.hasGeometry():
                geom = {
                    "type": feature.geometry().type(),
                    "wkt": feature.geometry().asWkt(precision=4)
                }
            features.append({
                "id": feature.id(),
                "attributes": attrs,
                "geometry": geom
            })

        return {
            "layer_id": layer_id,
            "feature_count": layer.featureCount(),
            "features": features,
            "fields": [field.name() for field in layer.fields()]
        }

    def execute_processing(self, algorithm, parameters, **kwargs):
        """Execute a processing algorithm"""
        try:
            import processing
            result = processing.run(algorithm, parameters)
            return {
                "algorithm": algorithm,
                "result": {k: str(v) for k, v in result.items()}
            }
        except Exception as e:
            raise Exception(f"Processing error: {str(e)}")

    def save_project(self, path=None, **kwargs):
        """Save the current project"""
        project = QgsProject.instance()
        if not path and not project.fileName():
            raise Exception("No project path specified and no current project path")
        save_path = path if path else project.fileName()
        if project.write(save_path):
            return {"saved": save_path}
        raise Exception(f"Failed to save project to {save_path}")

    def load_project(self, path, **kwargs):
        """Load a project"""
        project = QgsProject.instance()
        if project.read(path):
            self.iface.mapCanvas().refresh()
            return {
                "loaded": path,
                "layer_count": len(project.mapLayers())
            }
        raise Exception(f"Failed to load project from {path}")

    def create_new_project(self, path, **kwargs):
        """Create a new QGIS project and save it at the specified path."""
        project = QgsProject.instance()
        if project.fileName():
            project.clear()
        project.setFileName(path)
        self.iface.mapCanvas().refresh()
        if project.write():
            return {
                "created": f"Project created and saved successfully at: {path}",
                "layer_count": len(project.mapLayers())
            }
        raise Exception(f"Failed to save project to {path}")

    def render_map(self, path, width=800, height=600, **kwargs):
        """Render the current map view to an image"""
        try:
            ms = QgsMapSettings()
            layers = list(QgsProject.instance().mapLayers().values())
            ms.setLayers(layers)
            rect = self.iface.mapCanvas().extent()
            ms.setExtent(rect)
            ms.setOutputSize(QSize(width, height))
            ms.setBackgroundColor(QColor(255, 255, 255))
            ms.setOutputDpi(96)
            render = QgsMapRendererParallelJob(ms)
            render.start()
            render.waitForFinished()
            img = render.renderedImage()
            if img.save(path):
                return {
                    "rendered": True,
                    "path": path,
                    "width": width,
                    "height": height
                }
            raise Exception(f"Failed to save rendered image to {path}")
        except Exception as e:
            raise Exception(f"Render error: {str(e)}")


class QgisMCPDockWidget(QDockWidget):
    """Dock widget for the QGIS MCP plugin"""
    closed = pyqtSignal()

    def __init__(self, iface):
        super().__init__("QGIS MCP")
        self.iface = iface
        self.server = None
        self.setup_ui()

    def setup_ui(self):
        """Set up the dock widget UI"""
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)

        layout.addWidget(QLabel("Server Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setMinimum(1024)
        self.port_spin.setMaximum(65535)
        self.port_spin.setValue(9876)
        layout.addWidget(self.port_spin)

        self.start_button = QPushButton("Start Server")
        self.start_button.clicked.connect(self.start_server)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Server")
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)
        layout.addWidget(self.stop_button)

        self.status_label = QLabel("Server: Stopped")
        layout.addWidget(self.status_label)
        self.setWidget(widget)

    def start_server(self):
        """Start the server"""
        if not self.server:
            port = self.port_spin.value()
            self.server = QgisMCPServer(port=port, iface=self.iface)

        if self.server.start():
            self.status_label.setText(f"Server: Running on port {self.server.port}")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.port_spin.setEnabled(False)

    def stop_server(self):
        """Stop the server"""
        if self.server:
            self.server.stop()
            self.server = None

        self.status_label.setText("Server: Stopped")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.port_spin.setEnabled(True)

    def closeEvent(self, event):
        """Stop server on dock close"""
        self.stop_server()
        self.closed.emit()
        super().closeEvent(event)


class QgisMCPPlugin:
    """Main plugin class for QGIS MCP"""

    def __init__(self, iface):
        self.iface = iface
        self.dock_widget = None
        self.action = None

    def initGui(self):
        """Initialize GUI"""
        self.action = QAction(
            "QGIS MCP",
            self.iface.mainWindow()
        )
        self.action.setCheckable(True)
        self.action.triggered.connect(self.toggle_dock)
        self.iface.addPluginToMenu("QGIS MCP", self.action)
        self.iface.addToolBarIcon(self.action)

    def toggle_dock(self, checked):
        """Toggle the dock widget"""
        if checked:
            if not self.dock_widget:
                self.dock_widget = QgisMCPDockWidget(self.iface)
                self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
                self.dock_widget.closed.connect(self.dock_closed)
            else:
                self.dock_widget.show()
        else:
            if self.dock_widget:
                self.dock_widget.hide()

    def dock_closed(self):
        """Handle dock widget closed"""
        self.action.setChecked(False)

    def unload(self):
        """Unload plugin"""
        if self.dock_widget:
            self.dock_widget.stop_server()
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget = None
        self.iface.removePluginMenu("QGIS MCP", self.action)
        self.iface.removeToolBarIcon(self.action)


def classFactory(iface):
    return QgisMCPPlugin(iface)
