# NOTICE

本插件包的能力层文件收编自开源项目 [fairygui-agent-bridge](https://github.com/wingcd/fairygui-agent-bridge)
（MIT License，锁定 commit `4b3abc1`），随本仓库 `thirdparties/fairygui-agent-bridge` 子模块保留上游参照。

收编文件与本地改动：

| 文件 | 来源 | 本地改动 |
|---|---|---|
| `mcp/server.mjs` | `mcp/server.mjs` | import 路径 `../cli/instances.mjs` → `./instances.mjs`（目录结构调整） |
| `mcp/fgui.mjs` | `cli/fgui.mjs` | 无 |
| `mcp/instances.mjs` | `cli/instances.mjs` | 无 |
| `editor-plugin/main.js` | `plugin/main.js` | 六个补丁（在 dev-examples/fairygui-test-project 实测验证）；分发目录已从 agent-bridge 更名为 **xc-link-plugin**（`thirdparties/xc-link-plugin/` 为源，目标工程用 junction/link 安装，修改即同步；`~/.fgui-agent-bridge` 全局注册表目录为 MCP/CLI 发现协议约定，保留不改）：① `itemInfo` 空目录 children 判空（否则真实工程 list_items 递归崩溃）；② `App.add_onUpdate` + `CS.FairyGUI.Timers.inst.Add(0.1, 0, onUpdate)` 双泵与心跳日志；③ `onUpdate` 每帧重设 `Application.runInBackground`（编辑器切后台会反复覆盖此值，只设一次会导致桥长时间挂起——FairyGUI-MCP 同款坑）；④ `startServer()` 同时绑定 `localhost` 与 `127.0.0.1` 前缀（宿主 CSP 只放行 `127.0.0.1:*`，且 localhost 前缀仅绑 IPv6 回环，浏览器 fetch 会被双重挡住）；⑤ 新增 `capture_component` 命令：`doc.content.displayObject.GetScreenShot`（注意在 DisplayObject 上调，不在 GComponent 上）+ `EncodeToPNG` 返回 base64——编辑器内置 ScreenCapture 被裁后的引擎级保真截图，供设计页渲染组件用；⑥ 新增 `focus_component` 命令：HasUnsavedDocuments→SaveAllDocuments→CloseAllDocuments→OpenDocument，实现编辑器「同时只开一个组件」的单一工作目标语义（设计页切换选中时调用） |
| `editor-plugin/package.json` | `plugin/package.json` | 无 |
| `scripts/install.bat` / `install.sh` | 同名文件 | 源目录 `plugin/` → `editor-plugin/` |
| `scripts/lint_components.mjs` | 同名文件 | 无 |

实测环境：FairyGUI-Editor 6.1.4（Windows）。结论详见
`dev-docs/progress/FairyGUI工作室-P0-探活记录.md` 与 `dev-docs/experience/fairygui-agent-bridge-local-patches.md`。

上游已知限制（6.1.4 实测）：`screenshot` 的 Unity `ScreenCapture` 被裁剪不可用；
`open_doc` 可用。规范正文 `STANDARDS.md` 的要点已翻译进 `skills/fairygui-ui/SKILL.md`。
