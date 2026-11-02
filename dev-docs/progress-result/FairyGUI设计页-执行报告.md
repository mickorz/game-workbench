# FairyGUI 自定义设计页执行报告

- 日期：2026-11-02
- 状态：**完成并经用户实测验收**（组件树浏览、编辑器选中联动、截图渲染）
- 依据：`dev-docs/design/设计页面机制分析与自定义指南.md` 方案 B（只读预览版 MVP）

## 交付清单

| 文件 | 内容 |
|---|---|
| `src/renderer/fairygui-design-workspace.tsx` | 设计页：左组件树（按包懒加载）+ 右渲染截图 + XML 源码（可折叠）+ 选中组件注入设计上下文 chip + 返回工作区按钮 |
| `src/renderer/fairygui-design.css` | 布局与状态样式 |
| `src/renderer/project-shell.tsx` | 第四向分支：`type === "fairygui" && designOpen` 渲染新设计页；`CodingWorkspace` 的 designOpen 对 fairygui 恒 false |
| `src/renderer/locales/{zh-CN,en}.ts` | `fairyguiDesign.*` 双语文案 |
| `plugins/fairygui/editor-plugin/main.js` | 桥新增 `capture_component` 命令（补丁 5） |
| `dev-docs/experience/fairygui-agent-bridge-local-patches.md` | 补丁 5 坑点记录 |

## 技术要点

1. **渲染路线**：放弃 Web 运行时（npm 无官方 fairygui-js、Web 版绑死 LayaAir），改用桥的
   `open_doc` + `displayObject.GetScreenShot` 引擎级保真截图，base64 直出，零新依赖。
2. **懒加载**：组件树初始只拉 `list_packages`，点开包才拉 `list_items`——避免挂载时串行
   打满桥的单线程队列，导致会话里 agent 的桥调用排队超时。
3. **上下文联动**：选中组件作为 `PromptContext`（kind `canvas-board`）注入会话，
   agent 能感知用户正在看哪个组件。
4. **用户实测发现**：设计页点组件，FairyGUI 编辑器里同步切换选中状态——open_doc 的天然副作用，成为「设计页 ↔ 编辑器」联动的免费能力。

## 已知边界

- 只读预览：修改仍走会话 agent（MCP `set_property` 等）。
- 截图的是编辑器当前打开文档的画布，首次点组件需等 open_doc + 截图（约 1~2 秒）。
- 检查器面板不跟随选中（上游已验证的死路，见可行性分析）。

## 追加（2026-11-02）：单一工作目标

需求：设计页/会话链接切换选中组件时，编辑器里只保留当前组件文档（此前 open_doc 只开不关，标签堆积）。
实现：桥新增 `focus_component`（补丁 6）：HasUnsavedDocuments→SaveAllDocuments→CloseAllDocuments→OpenDocument；
设计页选中流程 open_doc → focus_component。探查确认 docView 有 CloseAllDocuments/HasUnsavedDocuments/
SaveAllDocuments/FindDocument 等 API（for-in 枚举可得，官方 API 语义可靠）。agent 侧 open_doc 保持原多开语义。

## 遗留 / 后续

- 多态截图（switch_controller 逐态）——MCP 侧有 action，设计页未接。
- 可视化编辑（点选节点改属性回写）——按指南建议后置，需处理 agent 并发冲突。
