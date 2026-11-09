# 需求检查工作区 grasp 化改造 - P3 执行报告

- 阶段：P3 专属产物面板 + 进度统计 + 确认门链接化
- 日期：2026-11-09
- 分支：`feat/requirement-check-grasp`（commit `4952fb2`）
- 前置：P2 报告 `dev-docs/progress-result/需求检查grasp化-P2-执行报告.md`；差距分析 `dev-docs/research/2026-11-09-grasp渲染效果差异分析.md`

## 交付清单

| 文件 | 内容 |
|---|---|
| `src/renderer/requirement-check-workspace.tsx`（新） | 专属工作区：阶段条（三产物 idle/working/done，文件齐全度 + agentBusy 推断）+ 三段全量文档视图（规格含 FR detail + 验收点 + 范围 chip + 待澄清警示；计划两级树叶子带覆盖徽章——与检查结果按 planId join，未出现在结果里为「未覆盖」；结果头部通过率进度条 + passed/total 大数字 + findings 严重度）；`workspaceRevision` 驱动 agent 落盘后刷新 |
| `src/renderer/project-shell.tsx` | `requirement-check` 分支接入（fairygui 之后、排除法之前），agentBusy + workspaceRevision 透传 |
| `src/renderer/markdown-content.tsx` | `requirement-check://confirm/` 协议：`urlTransform` 放行 + `a:` 分支拦截成按钮；`onConfirmAction` prop（fgui 组件链接先例） |
| `src/renderer/agent-timeline.tsx` + `project-shell.tsx` | `onConfirmAction` 透传链；点击 → `requestPrompt` 预填输入框（accept 预填确认文案 / revise 预填「需要修改：」），仅 requirement-check 类型启用 |
| `src/daemon/agent-prompts.ts` | 确认门指令追加：结尾必须带两个 markdown 链接（确认通过 / 需要修改），由 app 渲染成可点按钮 |
| `src/renderer/styles.css` | `.requirement-panel` 系列样式（阶段胶囊/文档卡/chip/统计条/确认链接按钮）；徽标复用 P2 `.requirement-badge` 色系 |
| `test/requirement-check-workspace.test.ts`（新） | `artifactStage`（三态推断）/ `leafCoverage`（join + missing）/ 产物路径常量，7 用例 |

## 与 grasp 的对齐程度（对照差异分析文档第五节）

| 差距项 | P3 落地 |
|---|---|
| 专属产物面板（优先级 1） | 已落地：阶段条 + 三段全量文档视图，不复刻 grasp 20+ 分节（spec 渲染 FR detail + 验收点 + 范围 + 假设/约束/待澄清） |
| 计划进度 + 结果统计（优先级 2） | 已落地：叶子覆盖徽章（通过/未通过/未覆盖三态）+ 通过率进度条 + passed/total 大数字 |
| 确认流 UI 化（优先级 3） | 已落地：确认链接按钮 + 点击预填 composer；保留 questionnaire（复杂拍板点仍走问卷） |
| 字段级标注（优先级 4） | 未做（差异分析定位为收益递减项，待评估） |

## 端到端实机验收（真实模型对话）

| 环节 | 结果 |
|---|---|
| 面板替换 | requirement-check 项目会话页右侧不再落 CodingWorkspace 空画布，渲染 `.requirement-panel` |
| 旧产物渲染 | 三段全 done：5 FR（含 detail + must 徽标）、15 叶子全部带「通过」徽章、15/15 通过率 + 满格进度条（DOM 断言 + 截图看图双验证） |
| 新对话链路 | 「设置页深色模式切换」→ 3 FR / 9 验收点 / 9 叶子新产物落盘，面板随 revision 刷新 |
| 确认链接 | agent 结尾输出两个链接，渲染成「确认通过」「需要修改」按钮（href 为 `requirement-check://confirm/*` 完整值，非空串）；点击 accept → composer 预填「确认通过这份检查结果，请结束流程。」 |
| 回归无泄漏 | fairygui 项目会话页 `.requirement-panel` 计数 0、时间线正常 |
| 截图存档 | `dev-examples/browser-selftest-shots/06-p3-panel.png`（409KB）、`07-p3-plan.png` |

## 验证汇总

- typecheck 0 错误
- `requirement-check-workspace.test.ts` 7/7；`requirement-check + agent-prompts + agent-tools` 44 passed（agent-tools 2 failed 为既有环境基线，与前两阶段记录一致）
- daemon 由 `--watch --watch-path=./src` 自动热载（agent-prompts.ts 在 src 内）

## 发现并修复的问题

1. **daemon watch 重启 EADDRINUSE 卡死（新坑，已记 `dev-docs/experience/daemon-watch-kills-agent-session.md`）**：开发期改 daemon 侧 src 文件触发 watch 重启时，旧子进程因活跃 SSE 连接未退干净占着 43110，新进程 EADDRINUSE 直接死，watcher 卡在「Failed running. Waiting for file changes」不再自愈。修法：杀整链（watcher 父 + 子，`taskkill //F //T //PID <watcher>`）重起。**触发条件：跑着 agent 会话时改 daemon 代码**——开发流程注意：改 daemon 代码前先停会话或接受重启杀会话。
2. locales 块插入位置：新命名空间块加进了 `timeline` 内层（缩进层级判断失误）——i18n key 解析不到；用 python 脚本按缩进移出到顶层。
3. i18n `t()` 的 ParseKeys 强类型不接受动态拼接 key——动态文案改静态映射表 / 传翻译后的节点。

## 遗留与后续

- 字段级标注（AnnotateBtn + jsonPath 回填聊天）未做——P3 后评估收益
- 面板 spec 视图未渲染 scenarios / workKind 之外的全部 grasp 分节（数据实体/业务规则/边界等）——schema 未要求这些字段，按需再加
- 确认链接依赖模型输出格式（prompt 指令约束）——若模型漏输出链接，仍可走 questionnaire 确认（双通道兜底）

## 经验与坑（新增）

1. **node --watch 开发期 EADDRINUSE 卡死链**：见上「发现并修复的问题 1」，完整排查过程已并入 experience 文档。
2. **chrome-use screenshot 偶发 CDP 超时**：报「command did not finish before deadline」时先 `status` + 简单 eval 探活，不要重启浏览器；重试 screenshot 即可成功。
