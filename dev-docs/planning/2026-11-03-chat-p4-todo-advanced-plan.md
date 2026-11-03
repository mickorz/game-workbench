# 对话框增强 P4 细化方案（todo 进阶）

- 日期：2026-11-03
- 依据：`dev-docs/planning/2026-11-03-chat-dialog-enhancement-plan.md` 第 P4 节（「本计划只定边界，实施前另行细化」）
- 范围决策（用户确认）：reconcile + todo_write 系统提示引导 + 用户加 todo（含 nudge）+ 分组；**不做**侧栏 todo 面板；R2~R6 借鉴项维持需求池不启动（R4 排队条经核实已存在于 `MessageQueue`，需求文档记录过时）。

## 范围与落点

| 项 | 落点 | 说明 |
|---|---|---|
| reconcile | `src/daemon/agent.ts` 纯函数 | agent 重写快照时：同 group+title 旧 done 保持 done；旧 origin=user 条目身份保持；旧 user 条目未被新快照收录时原样追加（agent 重写不能删用户条目）。实时路径与历史重建路径共用 |
| 引导 | `src/daemon/agent-prompts.ts` COMMON_AGENT_INSTRUCTIONS | 追加一行：多步工作用 todo_write 维护清单（写前建、做中标、做完标、重写保持最新）；与 update_plan（跨 turn 计划）措辞区分 |
| 用户加 todo | `POST /projects/:pId/conversations/:cId/todos` + `AgentManager.addUserTodo` | 无活动 turn 抛错（409）；追加 `{title, status:"pending", origin:"user"}`（同 group+title 已存在则不重复追加）；随后 `session.steer(nudge)` 注入引导提示 |
| nudge 前缀 | `src/shared/contracts.ts` `TODO_NUDGE_PREFIX = "[xc-ui-flow:todo-nudge] "` | daemon 注入与 renderer 过滤共用；仿 thinkrail `isControlMessage`：nudge 用户消息不渲染成气泡 |
| 分组 | `TodoSnapshotItem.group?: string`（max 40）+ todo_write schema + 卡片渲染 | 组按首次出现顺序分块，无组条目为首块（无标题）；组内仍三段式（进行中/待办/已完成）；计数保持全局 |
| 渲染入口 | `agent-timeline.tsx` `TodoActionsContext` | 仿 `WorkspaceLinkContext`：context 传 `{ turnId: 活动turnId, add }`，卡内仅当 `item.turnId === turnId` 时显示添加入口（避免旧 turn 卡上加新 todo 的错位）；TurnArticle memo 不受影响 |

## 明确不做（留需求池）

- 侧栏 todo 面板、用户删/改 todo、todo 完成小结（summary）、R2 虚拟列表、R3 工具卡注册表、R5 子代理转写、R6 会话统计条。

## 验证

- `bun run typecheck` / 针对性 vitest（agent / agent-timeline / turn-display / renderer-state / app / external-mcp / agent-tools）/ `bun run build:renderer`
- 全量测试仅对比基线 diff（2 个环境失败）
