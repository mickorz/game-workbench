# 协议名与标识符说明

XC-UI-Flow 从开源项目
[ohmygame](https://github.com/WhiteTowerAI/ohmygame) fork 而来并完成品牌化。
所有**用户可见**的名称现在都是 XC-UI-Flow，但一批协议名与标识符**刻意保留**
旧的 `ohmygame` 拼写。本页逐条记录它们是什么、为什么冻结、改动代价。

## 为什么冻结

协议名只有在两端一致时才有意义。存量安装、已保存工程、已安装插件、外部
agent 注册信息里都已经带着这些字符串落在磁盘上。改名会让所有存量工程与
插件失效，除非同时发布「读旧名」的迁移逻辑——风险高，用户价值为零。

## 冻结清单

| 标识符 | 位置 | 冻结原因 |
| --- | --- | --- |
| `.ohmygame-plugin/` | `plugins/` 与已装插件归档里的旧名插件清单目录 | 作为发现回退永久保留：存量已装插件与为上游 ohmygame 生态写的插件都带此目录。写入已迁移 `.xcflow-plugin/`（2026-11-03）；两者都在 `PLUGIN_MANIFEST_PATHS` 里，新名优先。类似 `.git`，目录名对已发布物是契约。 |
| `ohmygame-godot` | `src/shared/mcp.ts` 的 `GODOT_MCP_SERVER_ID` | MCP 服务 id，daemon 与插件两端字符串匹配。 |
| `ohmygame` | `src/shared/plugins.ts` 的插件市场索引 id | 插件目录查询按此 id 寻址。 |
| `ohmygame-studio` | 外部 MCP 服务名（`EXTERNAL_MCP_SERVER_NAME`）与 `integrations/skills/xcflow-studio/SKILL.md` 里技能的 `name` | 外部 CLI 注册进 `~/.claude.json` 的名字、MCP 握手名，也是用户机器上的安装目录 `~/.claude/skills/ohmygame-studio`。改名会让存量注册孤儿化。仓库内源目录已改 `integrations/skills/xcflow-studio`，仅协议名保留。 |
| `ohmygame:*` | Electron IPC 通道名（`src/desktop/main.ts`、`preload.cts`） | 渲染进程与主进程约定的字符串；保存的会话与测试都在引用。 |
| `ohMyGameDesktop` | `preload.cts` 的 `contextBridge` 暴露键 | 同 IPC 通道契约，暴露给网页游戏页面。 |
| `OHMYGAME_*` 环境变量 | `OHMYGAME_RENDERER_URL`、旧 `OHMYGAME_FFMPEG_PATH`、daemon token/数据目录变量 | 由用户或外部启动器配置，不在我们控制内。新变量用 `XCUIFLOW_` 前缀，读取处保留 `OHMYGAME_` fallback（见 `.env.example`、`src/daemon/project-process.ts`）。 |
| `ohmygame-*` URL 参数 | 网页故事运行时（`src/story-web/runtime.ts`，如 `ohmygame-policy`、`ohmygame-save`） | 已发布故事与运行时之间的 query 协议。 |
| `ohmygame-pruned.json`、`ohmygame-workspace-`、`ohmygame-checkpoint*` | `.data/` 下检查点文件与临时目录前缀 | 磁盘存量数据按名寻址。 |
| `ohmygame-check-process.cmd` | `build/` 安装器脚本 | 安装器内部件，改了要重打安装器且无收益。 |
| `~/.fgui-agent-bridge/` | FairyGUI 桥插件注册表（见 `thirdparties/xc-link-plugin/`） | 沿用上游 `fairygui-agent-bridge` fork 的 MCP/CLI 发现约定。 |

## 政策

- 新标识符一律用新品牌（`XCUIFLOW_` 环境变量前缀；必要时 `xcflow-` 符号前缀）。
- 旧名是**兼容面**，不是技术债。不要在清理 PR 里顺手改名。
- 若将来确需改名，必须同版本配套「读旧名 fallback + 数据迁移」，单独一个
  release 发布。

fork 出处与 FairyGUI 桥的逐文件补丁记录见
[`plugins/fairygui/assets/NOTICE.md`](../plugins/fairygui/assets/NOTICE.md)。
英文版见 [protocol-names.md](../protocol-names.md)。
