# QGIS MCP Plugin

让 Reasonix（或任何支持 MCP 协议的工具）直接操控本地 QGIS 插件。
为了能够实战使用，修改了原作者的代码版本。

## 架构

```
Reasonix ←→ MCP Bridge (Python) ←→ TCP :9876 ←→ 本插件 (QGIS 内部)
```

- **本插件**（`qgis_mcp_plugin/`）：运行在 QGIS 内部，监听 TCP 9876 端口，接收 JSON 命令后执行 PyQGIS 代码
- **MCP Bridge**（`src/qgis_mcp/qgis_mcp_server.py`）：独立 Python 进程，将 MCP 协议转为 TCP 命令
- **Reasonix**：通过 MCP 协议调用 Bridge 提供的工具（`qgis_ping`、`qgis_execute_code`、`qgis_render_map` 等）

## 安装

```bash
# macOS
cp -r qgis_mcp_plugin/ \
  ~/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins/

# Windows
xcopy qgis_mcp_plugin\ "%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\qgis_mcp_plugin\" /E

# Linux
cp -r qgis_mcp_plugin/ \
  ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
```

## 在 QGIS 中激活

1. 打开 QGIS
2. 菜单 → **Plugins → Manage and Install Plugins**
3. 切换到 **Installed** 标签
4. 搜索 "QGIS MCP" → 勾选启用
5. 右侧会出现 **QGIS MCP** 停靠面板，底部状态栏显示 `QGIS MCP server started on localhost:9876`

## 在 Reasonix 中配置

编辑 `~/.reasonix/config.json`，在 `mcp` 数组中添加：

```json
{
  "mcp": [
    "qgis=uv --directory \"/path/to/QGIS-MCP-main/src/qgis_mcp\" run qgis_mcp_server.py"
  ]
}
```

重启 Reasonix 后生效。

## 支持的 PyQGIS 命令

插件通过 TCP 接收 JSON 命令（`{type: "command_name", params: {...}}`），支持的命令：

| 命令 | 说明 |
|:-----|:-----|
| `ping` | 检查连通性 |
| `get_qgis_info` | 获取 QGIS 版本信息 |
| `get_project_info` | 获取当前工程信息 |
| `load_project` | 加载 .qgs 工程 |
| `create_new_project` | 新建工程 |
| `save_project` | 保存工程 |
| `get_layers` | 列出所有图层 |
| `add_vector_layer` | 加矢量层 |
| `add_raster_layer` | 加栅格层 |
| `remove_layer` | 删除图层 |
| `zoom_to_layer` | 缩放到图层范围 |
| `get_layer_features` | 获取图层要素 |
| `execute_processing` | 运行 Processing 算法 |
| `execute_code` | **执行任意 PyQGIS 代码** ⭐ |
| `render_map` | 渲染画布为 PNG |

## 调试

插件日志在 QGIS 的 **Log Messages** 面板（View → Panels → Log Messages），标签页为 "QGIS MCP"。

如果 Reasonix 连不上：
1. 确认 QGIS 中插件已启用（Plugins 菜单中勾选）
2. 确认状态栏显示 `localhost:9876` 已启动
3. 确认 MCP Bridge 进程正在运行
4. 确认 `config.json` 中 `--directory` 路径正确

## 已知限制

- `execute_code` 超时 60 秒——大文件处理需缩小范围或增大像素
- QGIS API 是 C++ 绑定，枚举值必须传 enum 类型而非 int
- 图层树 `findLayer()` 不递归搜索子组——需手写遍历
- Print Layout 导出时需显式设置 `m.setLayers([...])`

## 版本

- v1.0 — 初始版本
- 修改于 2026-06-02 — 移除 `transport="stdio"` 参数以兼容当前 FastMCP 版本
