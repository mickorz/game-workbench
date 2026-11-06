# 需求检查工作区 grasp 化改造 - P2 执行报告

- 阶段：P2 确认门 + 产物卡片渲染 + 端到端实机验收
- 日期：2026-11-07
- 分支：`feat/requirement-check-grasp`（commit `ba45836`）
- 前置：P1 报告 `dev-docs/progress-result/需求检查grasp化-P1-执行报告.md`

## 交付清单

| 文件 | 内容 |
|---|---|
| `src/renderer/agent-timeline.tsx` | 三张产物卡片：`RequirementSpecDetails`（标题 + workKind 徽标 + FR 列表 f1/priority/验收点 + 范围边界）、`CheckPlanDetails`（两级树 g1/g1.1）、`CheckResultDetails`（覆盖表 通过/未通过 徽标 + passed/total 计数 + findings 严重度徽标）；`ToolDetails` 按 tool 名分发（web_search/bash 先例），失败调用保留通用错误视图 |
| `src/daemon/agent.ts` | `toolArguments` 加 set_* 特例（bash/read 的 compactRecord 先例）：compact 到卡片所需字段（丢 detail/summary/cases 等大文本、rootCause 截 200、evidence 截 160）再走通用 boundedValue——修「超 2000 字符被截断成字符串导致卡片拿不到对象」；导出供测试 |
| `src/daemon/agent-prompts.ts` | 确认门纪律：`set_check_result` 落盘后 questionnaire 让用户确认（确认/驳回），驳回按意见修正重落盘再确认；未确认不得结束 |
| `src/renderer/styles.css` + 双语 locales | 卡片样式与 9 条文案（zh/en 同步） |
| `test/agent-requirement-compact.test.ts`（新） | 5 用例锁 compact：字段保留/丢弃、rootCause/evidence 截断、其他工具不受影响 |

## 端到端实机验收（第一个对话，真实模型）

一句话「登录页手机号验证码登录，60 秒送达，5 分钟有效」→ 全链路真实跑通：

| 环节 | 实测结果 |
|---|---|
| todo 管线 | 4 步卡片（梳理→保存规格→制定计划→执行检查），agent 主动用 todo_write |
| 三工具调用 | set_requirement_spec → set_check_plan → set_check_result 全调用，产物落盘 `requirements/`+`check/`（文件树可见三个 JSON，+409 行） |
| 产物结构 | 6 FR / 10 验收准则 / 5 组 10 叶子一一对应 / 严格两级（check-result.json 内容实机核对） |
| 如实上报 | 运行时叶子无实现环境 → 全部如实 passed=false + 6 findings（1 blocker/2 major/2 minor/1 info）——门禁只拦报告不完整，失败即产出 |
| 确认门 | 结尾抛出两个待拍板点（60 秒语义、未绑定手机号处理）+「请确认这份检查结果（确认/需要修改）」 |
| 卡片渲染 | 工具卡展开后 `.requirement-card` 出现在 DOM（渲染分支工作） |

截图存档：`dev-examples/browser-selftest-shots/03-grasp-p2-session.png`（334KB）+ zai 看图断言（布局/文件树/覆盖结构 5 项全过）。

## 发现并修复的问题

1. **工具卡 arguments 被 boundedValue 截断成字符串**（超 2000 字符）→ 卡片拿不到对象、FR 空。修：`toolArguments` 给 set_* 加 compact 特例（单测锁 5 用例）。
   - 注意：历史会话的 items 是持久化的，compact 只对新工具调用生效——首个对话的工具卡仍是旧数据（文档记录，不做迁移）。
2. **折叠工具卡被输入区遮挡带盖住**（chrome-use 报 element_occluded）→ 滚动会话流离开遮挡带后真实点击成功；`--allow-dom` 的 DOM click 不触发 React 折叠状态，无效。

## 未竟事项（外部因素，非代码问题）

- 第二个对话（验证 compact 后新数据卡片）两次卡在「思考中」——模型网关挂起（首个对话同模型跑通，外部服务不稳）。compact 数据路径已由单测覆盖，模型恢复后可在新对话复验卡片全量渲染。
- 观察点（后续调优，不阻塞）：agent 把待拍板点写在结尾文本而非 questionnaire 工具（规格 openQuestions 为空、分歧记入 assumptions 的灰色路径）——提示词已要求 questionnaire，靠模型遵循度；P3 若做专属工作区可把确认门做成显式 UI。

## 验证汇总

- typecheck 0 错误
- `agent-requirement-compact.test.ts` 5/5、`requirement-check + agent-prompts` 28/28、agent-tools 注册断言过（2 既有基线失败与本改动无关，stash 比对一致）
- agent-timeline / i18n-ui 渲染测试在本机基线即全挂（stash 前后一致），渲染验证以实机为准（CLAUDE.md 硬性标准）
- daemon 双重启 + 浏览器实机：全链路对话 + 卡片 DOM + 截图看图断言
- 测试项目已清理（DELETE 204）、chrome tab 已关

## 经验与坑（新增）

1. **edit 工具写含反引号模板串的 JSX 会丢字符**（本次丢闭合反引号致 17 个连锁语法错；P1 丢 `\n` 转义）——含反引号/`${}` 的行一律用临时 python 脚本按行号重写，esbuild 单文件 build 可秒定位真实语法错因（tsc 连锁错的首因行不可靠）。
2. **esbuild/bun build 单文件解析是定位 JSX 语法错的捷径**：`bun build src/xx.tsx --outfile tmp` 直接给出精确行列，比 tsc 的连锁报错好读。

## 后续（P3，可选）

- `create-workspace` 建 RequirementCheckWorkspace：阶段条（产物齐全度推断）+ 验收点面板 + 检查结果视图
- 确认门显式 UI（chat-text-action 确认链接）替代纯提示词纪律
- 历史会话 items 的 compact 迁移（如需要）
