# QGIS MCP

QGIS MCP connects QGIS to chat clients that support the Model Context Protocol (MCP). It lets an assistant inspect and control a local QGIS session through a QGIS plugin plus a Python MCP server.

## Features

- Two-way communication between the MCP server and QGIS through a local socket.
- Create, load and save QGIS projects.
- Add and remove vector or raster layers.
- List layers and inspect vector features.
- Execute QGIS Processing algorithms.
- Render the current map view to an image file.
- Execute PyQGIS code from the chat client.

## Components

- `qgis_mcp_plugin/`: QGIS plugin that opens a local socket server inside QGIS.
- `src/qgis_mcp/qgis_mcp_server.py`: MCP server that exposes QGIS tools to the chat client.
- `src/qgis_mcp/qgis_socket_client.py`: simple socket client for direct tests.

## Requirements

- QGIS 3.x
- Python 3.10 or newer
- `uv` package manager
- An MCP-compatible chat client

## Install

Clone the repository:

```bash
git clone https://github.com/lpochettino-gis/QGIS-MCP.git
```

Install `uv` if needed:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Copy `qgis_mcp_plugin` into your active QGIS profile plugin folder. In QGIS, open `Settings > User Profiles > Open Active Profile Folder`, then copy the folder into `python/plugins`.

On Windows the plugin folder is commonly:

```text
C:\Users\USER\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins
```

Restart QGIS, open `Plugins > Manage and Install Plugins`, search for `QGIS MCP`, and enable it.

## MCP Client Configuration

Example configuration:

```json
{
  "mcpServers": {
    "qgis": {
      "command": "uv",
      "args": [
        "--directory",
        "C:\\path\\to\\QGIS-MCP\\src\\qgis_mcp",
        "run",
        "qgis_mcp_server.py"
      ]
    }
  }
}
```

## Usage

1. Open QGIS.
2. Start the plugin from `Plugins > QGIS MCP > QGIS MCP`.
3. Click `Start Server`.
4. Start or reload your MCP chat client.
5. Use the exposed QGIS tools from chat.

## Tools

- `ping`
- `get_qgis_info`
- `load_project`
- `create_new_project`
- `get_project_info`
- `add_vector_layer`
- `add_raster_layer`
- `get_layers`
- `remove_layer`
- `zoom_to_layer`
- `get_layer_features`
- `execute_processing`
- `save_project`
- `render_map`
- `execute_code`

## Security

This MCP can execute arbitrary PyQGIS code and modify local projects. Use it only with trusted prompts and local files. Do not expose the QGIS socket server outside `localhost`.
