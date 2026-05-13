# Contributing to QGIS MCP

Thank you for your interest in contributing.

## Getting Started

1. Fork and clone the repository.
2. Install QGIS 3.x, Python 3.10 or newer, `uv`, and an MCP-compatible chat client.
3. Link or copy `qgis_mcp_plugin` into your active QGIS profile plugin directory.
4. Configure your MCP client to run `src/qgis_mcp/qgis_mcp_server.py`.

## Development Notes

- Keep changes focused.
- Update docs when behavior changes.
- Be careful with `execute_code`; it runs arbitrary PyQGIS code in the local QGIS process.
- Avoid committing local paths, credentials, generated data, or private project files.
