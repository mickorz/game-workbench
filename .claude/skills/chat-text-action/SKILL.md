---
name: chat-text-action
version: 1.0.0
display_name: 聊天文本点击扩展
display_name_en: Chat Text Action
description: >
  Add clickable behavior to chat message text in the xc-ui-flow app: turn text
  patterns in agent replies (component names, file paths, identifiers) into
  links that trigger in-app actions such as opening a design page, filtering a
  list, or calling a local service. Use when the user asks to make text in chat
  replies clickable, add inline links with custom actions, extend the markdown
  rendering of the agent timeline, or wire chat text to app navigation.
description_zh: >-
  在 xc-ui-flow 应用的会话消息文本里新增可点击行为：把 agent 回复中的文本模式
  （组件名、文件路径、标识符）变成链接，点击触发应用内动作（打开设计页、过滤
  列表、调用本地服务等）。用户说「让回复里的 XX 可以点击 / 聊天文本加链接 /
  扩展时间线 markdown 渲染 / 文本点击跳转」时使用。
description_en: >-
  Add clickable behavior to chat message text in the xc-ui-flow app: turn text
  patterns in agent replies into links that trigger in-app actions. Use when
  asked to make text in chat replies clickable or extend the agent timeline
  markdown rendering with custom link actions.
---

# 聊天文本点击扩展（chat-text-action）

让 agent 回复里的特定文本模式（组件名、路径、ID 等标识符）变成可点击链接，
点击触发应用内动作（打开某个视图、选中某个对象、调本地服务），而不是新开浏览器标签。

**核心模式一句话**：markdown 预处理把文本模式替换为自定义协议伪链接（`xxx://`），
react-markdown 的 `a:` 组件分支拦截并转成可点击元素，`urlTransform` 放行自定义协议，
点击回调经 props/context 链传到 shell 层执行动作。

## 何时用 / 何时不用

| 用 | 不用 |
|---|---|
| 回复文本中的标识符要触发应用内动作 | 只是展示富文本（直接写 markdown 即可） |
| 点击后跳视图/选中对象/调服务 | 目标是外部网页（remark-gfm autolink 就够） |
| 模式来自 agent 回复的不可控输出 | 内容是我们自己生成的受控 UI（直接写组件） |

## 输入

| 输入 | 例 | 缺省策略 |
|---|---|---|
| 文本模式（正则） | 反引号/链接里的组件名 | 问用户或从样例回复归纳 |
| 点击动作 | 打开设计页并选中组件 | 问用户；涉及跨视图传参时用「状态提升 + 视图切换」模式 |
| 定位方式 | 本地服务搜索 / 纯前端路由 | 有本地服务（桥/daemon）时先搜后跳 |
| 生效范围 | 仅某项目类型 / 全局 | 有类型上下文时按类型开关 |

## 边界

- **做**：markdown-content 的 linkify 与拦截、timeline 的回调透传、shell 层动作、
  （若需）本地服务的搜索命令、单测脚本。
- **不做**：agent 侧提示词改动（除非模式必须由 agent 输出）、普通 markdown 功能、
  会话存储格式。

## 主流程

进入 `references/chat-text-action-flow.md`，按 6 步执行。流程内含：

- 完整代码模板（linkify 正则、a: 拦截、urlTransform、回调透传链、状态提升）
- **5 个必踩坑**（urlTransform 清洗、捕获组错位、链接形态多样、代码块跳过、
  shell 反引号污染）——每坑有现象/根因/修法
- 验收清单（typecheck + 单测脚本 + 浏览器端到端）

## 关键规则

1. **自定义协议必须配 `urlTransform`**：react-markdown v9 默认把非 http 协议
   清洗成空串，没有它点击就是开空白新标签。
2. **linkify 输入是 agent 的不可控输出**：至少覆盖裸反引号、带反引号链接、
   空链接三种形态；围栏代码块必须跳过；正则要防误伤（文件路径、图片链接白名单）。
3. **回调参数与捕获组一一对齐**：正则有几个捕获组，回调就几个参数；
   写完立即用 `dev-examples/test-*.mjs` 单测脚本验证输出形态（不经 shell 生成，
   用 write 工具写脚本，避免反引号转义污染）。
4. **点击动作失败要静默降级**（如本地服务不通时 return），不能打断会话阅读。
5. 完成后按仓库 CLAUDE.md 约定更新进度文档。

## 参照物（全部技能内自包含）

| 文件 | 内容 |
|---|---|
| `references/chat-text-action-flow.md` | 6 步流程 + 代码模板 + 坑清单 + 验收 |
| `references/case-fgui-component-link.md` | 完整实战案例（组件名点击 → 设计页），含所有踩坑细节 |
