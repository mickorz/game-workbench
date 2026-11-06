# 需求检查工作区 grasp 化改造 - P1 执行报告

- 阶段：P1 MVP（纯会话内闭环，结构化产物 + 门禁 + 提示词）
- 日期：2026-11-07
- 分支：`feat/requirement-check-grasp`（commit `206dc7e`）
- 设计依据：`dev-docs/design/需求检查工作区grasp化改造-可行性分析.md`
- 机制来源：`dev-docs/research/2026-11-07-grasp-需求处理机制分析.md`

## 需求

把 grasp（`thirdparties/grasp`）的需求处理机制迁入需求检查工作室：
一句话 → 澄清（questionnaire 拍板）→ 结构化需求规格（SRS 子集）→
两级检查计划 → 检查结果（验收点叶子全覆盖核验），全程带门禁。
P1 范围：纯会话内闭环，无新 UI 组件。

## 交付清单

| 文件 | 内容 |
|---|---|
| `src/shared/requirement-check.ts`（新） | schema 与校验直译：`validateRequirementSpec`（必填段非空、FR 每条 detail + ≥1 验收标准、priority 枚举缺省 must、workKind=bug 时 rootCause 必填、稳定编号 f1/s1）、`validateCheckPlan`（严格两级、g1/g1.2 编号、嵌套即驳回）、`validateCheckResult`（叶子全覆盖恰好一条、evidence 非空、引用用例存在）、`requirementOpenQuestions`/`checkPlanLeaves` |
| `src/daemon/agent-tools.ts` | `requirement-check` 条件分支注册三工具（仅该类型可见）：`set_requirement_spec` / `set_check_plan` / `set_check_result`；校验不过 throw（错误文本回给 agent 驱动重试，即 grasp 的提交驳回）；openQuestions 非空不准提交（先 questionnaire 拍板）；产物落盘 `requirements/requirement-spec.json`、`requirements/check-plan.json`、`check/check-result.json` |
| `src/daemon/agent-prompts.ts` | `REQUIREMENT_CHECK_INSTRUCTIONS` 八条：每轮一个小问题、真实分歧才 questionnaire、workKind 直判、管线顺序、三份产物各自的自检清单（grasp clarify/plan-checklist 要点直译）、如实上报失败 |
| `test/requirement-check.test.ts`（新） | 15 用例锁校验行为 |
| `test/agent-tools.test.ts` | 注册断言：三工具仅 `requirement-check` 类型注册，`general` 不注册 |

## 与 grasp 的有意差异

1. **错误收集式**：grasp 校验单条短路，这里收集全部错误一次返回——工具失败文本
   回给 agent，一次报全可让 agent 单次重试修复所有问题。
2. **passed=false 是合法结果**：grasp 的 PlanCoverageOK 要求全部 passed 才过测试门禁
   （挡实现流转）；需求检查工作室的产出就是检查结论——叶子未通过时如实
   passed=false + findings 记录 + assessment 结论即放行，门禁只拦「报告不完整」
   （缺叶子条目、evidence 空、引用用例不存在、重复/未知 planId）。
3. **rootCause 简化为 spec 字段**：grasp 是独立产物 root_cause.json，P1 并入 spec
   的 `rootCause` 字段（workKind=bug 时必填）。

## 验证记录

1. `bun run typecheck`：0 错误。
2. `bun run vitest run test/requirement-check.test.ts`：15/15 过。
3. `bun run vitest run test/agent-prompts.test.ts test/requirement-check.test.ts`：23/23 过。
4. `bun run vitest run test/agent-tools.test.ts`：37 passed / 2 failed——2 个失败为
   **既有基线失败**（`git stash` 后基线同 2 失败，逐条比对一致，与本改动无关）；
   新增注册断言过。
5. daemon 重启（杀 43110 监听 PID + 后台 `bun run dev:daemon`），`/health` ok。
6. 浏览器实测说明：P1 无 renderer 改动（工具卡片渲染走既有通用机制），验证全走
   程序化（注册断言 + 提示词注入测试）；端到端对话实测（模型驱动的
   questionnaire/set 工具链）留给 P2 确认门卡片时一并做实机验收。

## 经验与坑

1. **`python - <<'EOF'` heredoc 改代码有隐形转义坑**：多段拼接字符串（含反引号模板
   串 + `\n` 转义）在 quoted heredoc 里偶发匹配 0 次，同样的串写进 `.py` 脚本文件
   就能匹配。教训：改代码的脚本一律写成临时 `.py` 文件执行（write 工具落地，
   零转义层），跑完即删；heredoc 只用于跑简单只读命令。
2. **`python -c` 多步替换中途失败会把半改状态写盘**：`sub()` 逐条改内存 `t`、最后
   一次性 `write_text` 的写法才安全；一旦按步写盘，assert 失败会留下 head 已改
   body 未改的残缺文件（本次实际发生，靠独立修复脚本收尾）。
3. **TS 对跨函数边界的 `never` 收窄不可靠**：`const reject = (...) => { throw ... }`
   标了 `: never` 调用处仍不收窄（`'spec' is possibly 'null'`）。可靠写法：
   reject 改为返回错误文本的普通函数，调用处 `throw new Error(rejection(errors))`
   原生控制流必收窄。
4. **TypeBox `Type.Optional` 不收第二参**：options 要给内层（如 `Type.Union([...], { description })`），
   写成 `Type.Optional(Type.Union([...]), { description })` 报 TS2554。
5. **edit 工具偶发匹配不上 grep 可见的行**：同一行 sed/grep 可见、edit 的 oldText
   却找不到（疑似不可见字符/行尾差异）；此时退到临时 python 脚本按行号或子串
   替换最稳。

## 后续（P2+）

- P2：确认门卡片（chat-text-action 机制）+ spec 验收点表格渲染 + 端到端实机验收
- P3（可选）：`create-workspace` 建 RequirementCheckWorkspace（阶段条 + 验收点面板）
- 后置：leftover 遗留清单、page.html 页面稿对比、跨会话产物复用
