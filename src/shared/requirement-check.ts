/**
 * 需求检查工作室的结构化产物 schema 与校验。
 *
 * 直译自 grasp（thirdparties/grasp/server/internal/mcp/structured/doc.go 与
 * server/internal/mcp/plan.go、plan_coverage.go）的需求处理机制，按需求检查
 * 工作室语义裁剪： clarified 需求规格（SRS 子集，无排期无技术设计）、两级
 * 检查计划（大目标→小目标叶子）、检查结果（验收点叶子全覆盖核验）。
 *
 * 差异（有意为之）： grasp 的校验是单条短路报错，这里改为收集全部错误一次
 * 返回——工具调用失败会把错误文本回给 agent，一次报全能让 agent 单次重试
 * 修复所有问题。
 */

/** 功能需求：每条必须有 detail 与至少 1 条可验证的验收标准。 */
export interface RequirementFuncReq {
  id: string;
  title: string;
  detail: string;
  priority: "must" | "should" | "could";
  acceptanceCriteria: string[];
  scenarioIds: string[];
}

export interface RequirementScenario {
  id: string;
  name: string;
  actor: string;
  trigger: string;
  flow: string;
  outcome: string;
}

/** 需求规格：ISO/IEC/IEEE 29148 SRS 裁剪子集（无排期、无技术选型）。 */
export interface RequirementSpec {
  title: string;
  summary: string;
  background: string;
  workKind: "bug" | "feature" | "other" | "";
  /** workKind 为 bug 时必填：问题根因（grasp 的 root_cause 产物，简化为字段）。 */
  rootCause: string;
  goals: string[];
  successMetrics: string[];
  inScope: string[];
  outOfScope: string[];
  scenarios: RequirementScenario[];
  functionalRequirements: RequirementFuncReq[];
  assumptions: string[];
  dependencies: string[];
  constraints: string[];
  openQuestions: string[];
}

/** 计划小目标（叶子）：id 形如 g1.2，不带子级。 */
export interface CheckPlanSubgoal {
  id: string;
  title: string;
  detail: string;
}

/** 计划大目标：id 形如 g1；无小目标时自身即叶子。 */
export interface CheckPlanGoal {
  id: string;
  title: string;
  detail: string;
  subgoals: CheckPlanSubgoal[];
}

/** 检查计划：严格两级，小目标不得再嵌套。 */
export interface CheckPlan {
  title: string;
  goals: CheckPlanGoal[];
}

/** 一个验收点（计划叶子）的核查结论。 */
export interface CheckCoverageItem {
  planId: string;
  title: string;
  passed: boolean;
  evidence: string;
  cases: string[];
}

export interface CheckCase {
  name: string;
  status: "passed" | "failed" | "skipped";
  detail: string;
}

export interface CheckFinding {
  title: string;
  severity: "blocker" | "major" | "minor" | "info";
  detail: string;
}

/** 检查结果：必须全覆盖计划叶子，发现的问题记 findings。 */
export interface CheckResult {
  summary: string;
  cases: CheckCase[];
  coverage: CheckCoverageItem[];
  findings: CheckFinding[];
  assessment: string;
}

export interface RequirementSpecValidation {
  spec: RequirementSpec | null;
  errors: string[];
}

const WORK_KINDS = new Set(["bug", "feature", "other", ""]);
const FUNC_PRIORITIES = new Set(["must", "should", "could"]);
const SEVERITIES = new Set(["blocker", "major", "minor", "info"]);

function trim(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function trimList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => trim(item)).filter((item) => item !== "")
    : [];
}

function bool(value: unknown): boolean {
  return value === true;
}

/**
 * 校验需求规格（对应 grasp ParseClarifiedRequirement）：
 * 必填段非空、每条功能需求有 detail 与 >=1 条验收标准、priority 合法
 * （缺省 must）、scenarioIds 只保留已存在的场景。通过时补齐稳定编号
 * （场景 s1、需求 f1）并返回归一化结果；不通过时 errors 收集全部问题。
 */
export function validateRequirementSpec(input: Record<string, unknown>): RequirementSpecValidation {
  const errors: string[] = [];
  const requireList = (name: string, value: string[]): string[] => {
    if (value.length === 0) errors.push(`${name} 至少需要 1 条`);
    return value;
  };

  const title = trim(input.title);
  const summary = trim(input.summary);
  const background = trim(input.background);
  if (title === "") errors.push("title 不能为空");
  if (summary === "") errors.push("summary 不能为空");
  if (background === "") errors.push("background 不能为空");

  const workKind = trim(input.workKind) as RequirementSpec["workKind"];
  if (!WORK_KINDS.has(workKind)) errors.push("workKind 须为 bug、feature 或 other");
  const rootCause = trim(input.rootCause);
  if (workKind === "bug" && rootCause === "") errors.push("workKind 为 bug 时 rootCause（问题根因）不能为空");

  const goals = requireList("goals", trimList(input.goals));
  const inScope = requireList("inScope", trimList(input.inScope));
  const outOfScope = requireList("outScope", trimList(input.outOfScope));
  const assumptions = requireList("assumptions", trimList(input.assumptions));
  const dependencies = requireList("dependencies", trimList(input.dependencies));
  const constraints = requireList("constraints", trimList(input.constraints));

  const scenarioNames = new Set<string>();
  const scenarioIds = new Set<string>();
  const scenarios: RequirementScenario[] = [];
  let scenarioIndex = 0;
  for (const raw of Array.isArray(input.scenarios) ? input.scenarios : []) {
    const name = trim((raw as Record<string, unknown>).name);
    if (name === "") continue;
    scenarioIndex += 1;
    const id = `s${scenarioIndex}`;
    scenarios.push({
      id,
      name,
      actor: trim((raw as Record<string, unknown>).actor),
      trigger: trim((raw as Record<string, unknown>).trigger),
      flow: trim((raw as Record<string, unknown>).flow),
      outcome: trim((raw as Record<string, unknown>).outcome),
    });
    scenarioNames.add(name);
    scenarioIds.add(id);
  }

  const functionalRequirements: RequirementFuncReq[] = [];
  let requirementIndex = 0;
  for (const raw of Array.isArray(input.functionalRequirements) ? input.functionalRequirements : []) {
    const item = raw as Record<string, unknown>;
    const itemTitle = trim(item.title);
    if (itemTitle === "") continue;
    requirementIndex += 1;
    const detail = trim(item.detail);
    if (detail === "") errors.push(`functionalRequirements[${itemTitle}] detail 不能为空`);
    const acceptanceCriteria = trimList(item.acceptanceCriteria);
    if (acceptanceCriteria.length === 0) {
      errors.push(`functionalRequirements[${itemTitle}] acceptanceCriteria 至少需要 1 条`);
    }
    let priority = trim(item.priority) || "must";
    if (!FUNC_PRIORITIES.has(priority)) {
      errors.push(`functionalRequirements[${itemTitle}] priority 无效（须为 must、should 或 could）`);
      priority = "must";
    }
    const scenarioRefs = trimList(item.scenarioIds).filter((id) => scenarioIds.has(id));
    functionalRequirements.push({
      id: `f${requirementIndex}`,
      title: itemTitle,
      detail,
      priority: priority as RequirementFuncReq["priority"],
      acceptanceCriteria,
      scenarioIds: scenarioRefs,
    });
  }
  if (functionalRequirements.length === 0) errors.push("functionalRequirements 至少需要 1 条");

  if (errors.length > 0) return { spec: null, errors };
  return {
    spec: {
      title,
      summary,
      background,
      workKind,
      rootCause,
      goals,
      successMetrics: trimList(input.successMetrics),
      inScope,
      outOfScope,
      scenarios,
      functionalRequirements,
      assumptions,
      dependencies,
      constraints,
      openQuestions: trimList(input.openQuestions),
    },
    errors: [],
  };
}

/** 读取已落盘需求规格中未决的 openQuestions（解析失败视为无）。 */
export function requirementOpenQuestions(content: string): string[] {
  try {
    return trimList((JSON.parse(content) as Record<string, unknown>).openQuestions);
  } catch {
    return [];
  }
}

/** 读取已落盘需求规格的 workKind（解析失败视为空）。 */
export function requirementWorkKind(content: string): RequirementSpec["workKind"] {
  try {
    const kind = trim((JSON.parse(content) as Record<string, unknown>).workKind);
    return (WORK_KINDS.has(kind) ? kind : "") as RequirementSpec["workKind"];
  } catch {
    return "";
  }
}

export interface CheckPlanValidation {
  plan: CheckPlan | null;
  errors: string[];
}

/**
 * 校验检查计划（对应 grasp parsePlan）：严格两级（小目标不得再嵌套）、
 * title 非空、稳定编号 g1 / g1.2。
 */
export function validateCheckPlan(input: Record<string, unknown>): CheckPlanValidation {
  const errors: string[] = [];
  const goals: CheckPlanGoal[] = [];
  const rawGoals = Array.isArray(input.goals) ? input.goals : [];
  if (rawGoals.length === 0) errors.push("goals 不能为空");

  rawGoals.forEach((rawGoal, goalIndex) => {
    const goal = rawGoal as Record<string, unknown>;
    const goalTitle = trim(goal.title);
    if (goalTitle === "") {
      errors.push(`第 ${goalIndex + 1} 个大目标缺少 title`);
      return;
    }
    const subgoals: CheckPlanSubgoal[] = [];
    const rawSubs = Array.isArray(goal.subgoals) ? goal.subgoals : [];
    rawSubs.forEach((rawSub, subIndex) => {
      const sub = rawSub as Record<string, unknown>;
      if (Array.isArray(sub.subgoals) && sub.subgoals.length > 0) {
        errors.push("计划最多支持两级（大目标→小目标），小目标下不能再有子目标");
        return;
      }
      const subTitle = trim(sub.title);
      if (subTitle === "") {
        errors.push(`大目标 g${goalIndex + 1} 的第 ${subIndex + 1} 个小目标缺少 title`);
        return;
      }
      subgoals.push({
        id: `g${goalIndex + 1}.${subIndex + 1}`,
        title: subTitle,
        detail: trim(sub.detail),
      });
    });
    goals.push({
      id: `g${goalIndex + 1}`,
      title: goalTitle,
      detail: trim(goal.detail),
      subgoals,
    });
  });

  if (errors.length > 0) return { plan: null, errors };
  return { plan: { title: trim(input.title), goals }, errors: [] };
}

/** 计划叶子：无小目标的大目标自身即叶子，否则每个小目标是一个叶子。 */
export function checkPlanLeaves(plan: CheckPlan): Array<{ id: string; title: string }> {
  const leaves: Array<{ id: string; title: string }> = [];
  for (const goal of plan.goals) {
    if (goal.subgoals.length === 0) leaves.push({ id: goal.id, title: goal.title });
    else for (const sub of goal.subgoals) leaves.push({ id: sub.id, title: sub.title });
  }
  return leaves;
}

export interface CheckResultValidation {
  result: CheckResult | null;
  errors: string[];
}

/**
 * 校验检查结果（对应 grasp PlanCoverageOK + TestVerdict 的需求检查版）：
 * - cases / coverage / findings 逐项归一化（status 三态、severity 四级）
 * - 全覆盖核验：每个计划叶子在 coverage 中恰好一条、passed=true、
 *   evidence 非空、引用的 case 存在且真实 passed
 * - 未知或重复的 planId 报错
 */
export function validateCheckResult(input: Record<string, unknown>, plan: CheckPlan): CheckResultValidation {
  const errors: string[] = [];
  const summary = trim(input.summary);
  if (summary === "") errors.push("summary 不能为空");

  const normStatus = (value: unknown): CheckCase["status"] => {
    const status = trim(value).toLowerCase();
    if (status === "passed" || status === "pass" || status === "ok") return "passed";
    if (status === "skipped" || status === "skip") return "skipped";
    return "failed";
  };
  const cases: CheckCase[] = [];
  for (const raw of Array.isArray(input.cases) ? input.cases : []) {
    const item = raw as Record<string, unknown>;
    const name = trim(item.name);
    if (name === "") continue;
    cases.push({ name, status: normStatus(item.status), detail: trim(item.detail) });
  }
  const caseStatus = new Map(cases.map((item) => [item.name, item.status]));

  const coverage: CheckCoverageItem[] = [];
  const seenPlanIds = new Set<string>();
  const rawCoverage = Array.isArray(input.coverage) ? input.coverage : [];
  if (rawCoverage.length === 0) errors.push("有计划叶子时 coverage 至少需要 1 条");
  for (const raw of rawCoverage) {
    const item = raw as Record<string, unknown>;
    const planId = trim(item.planId);
    if (planId === "") continue;
    if (seenPlanIds.has(planId)) {
      errors.push(`coverage[${planId}] 重复：每个计划叶子恰好一条`);
      continue;
    }
    seenPlanIds.add(planId);
    const refs = trimList(item.cases).filter((name) => caseStatus.has(name));
    const dropped = trimList(item.cases).filter((name) => !caseStatus.has(name));
    if (dropped.length > 0) {
      errors.push(`coverage[${planId}] 引用的用例不存在：${dropped.join("、")}`);
    }
    coverage.push({
      planId,
      title: trim(item.title),
      passed: bool(item.passed),
      evidence: trim(item.evidence),
      cases: refs,
    });
  }

  const leaves = checkPlanLeaves(plan);
  const leafIds = new Set(leaves.map((leaf) => leaf.id));
  const leafTitle = new Map(leaves.map((leaf) => [leaf.id, leaf.title]));
  for (const leaf of leaves) {
    const item = coverage.find((entry) => entry.planId === leaf.id);
    if (!item) {
      errors.push(`计划叶子 ${leaf.id}（${leaf.title}）缺少 coverage 条目`);
      continue;
    }
    if (item.evidence === "") errors.push(`计划叶子 ${leaf.id}（${leaf.title}）evidence 不能为空`);
    if (item.cases.length === 0) errors.push(`计划叶子 ${leaf.id}（${leaf.title}）须引用至少 1 个已执行的用例`);
    // passed=false（含引用未通过用例佐证）是合法检查结果：如实上报失败并记 findings 即可，
    // 不驳回；门禁只拦报告不完整（缺条目、无证据、无引用）。
    if (leafTitle.get(leaf.id) && item.title === "") item.title = leafTitle.get(leaf.id) ?? "";
  }
  for (const item of coverage) {
    if (!leafIds.has(item.planId)) errors.push(`coverage[${item.planId}] 不是本计划的叶子（planId 须为 gN 或 gN.M）`);
  }

  const findings: CheckFinding[] = [];
  for (const raw of Array.isArray(input.findings) ? input.findings : []) {
    const item = raw as Record<string, unknown>;
    const findingTitle = trim(item.title);
    if (findingTitle === "") continue;
    let severity = trim(item.severity) || "info";
    if (!SEVERITIES.has(severity)) {
      errors.push(`findings[${findingTitle}] severity 须为 blocker、major、minor 或 info`);
      severity = "info";
    }
    findings.push({ title: findingTitle, severity: severity as CheckFinding["severity"], detail: trim(item.detail) });
  }

  if (errors.length > 0) return { result: null, errors };
  return { result: { summary, cases, coverage, findings, assessment: trim(input.assessment) }, errors: [] };
}
