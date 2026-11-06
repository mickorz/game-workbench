import { describe, expect, it } from "vitest";
import {
  checkPlanLeaves,
  validateCheckPlan,
  validateCheckResult,
  validateRequirementSpec,
} from "../src/shared/requirement-check.js";

/** 最小合法的需求规格输入（其余用例在此之上做增删）。 */
const validSpec = {
  title: "登录页验证码登录",
  summary: "支持邮箱验证码登录",
  background: "现有账号密码登录缺少验证码方式",
  workKind: "feature",
  goals: ["完成邮箱验证码登录"],
  inScope: ["登录页验证码发送与校验"],
  outOfScope: ["注册流程改造"],
  functionalRequirements: [
    {
      title: "发送验证码",
      detail: "用户输入邮箱后可请求验证码",
      priority: "must",
      acceptanceCriteria: ["输入合法邮箱时 60 秒内收到验证码"],
      scenarioIds: [],
    },
  ],
  assumptions: ["无额外假设（已与用户确认）"],
  dependencies: ["邮件服务可用"],
  constraints: ["验证码 5 分钟有效"],
  openQuestions: [],
};

describe("validateRequirementSpec", () => {
  it("accepts a minimal valid spec and assigns stable ids", () => {
    const { spec, errors } = validateRequirementSpec(validSpec);
    expect(errors).toEqual([]);
    expect(spec?.functionalRequirements[0].id).toBe("f1");
    expect(spec?.functionalRequirements[0].priority).toBe("must");
  });

  it("defaults priority to must and drops unknown scenario ids", () => {
    const { spec, errors } = validateRequirementSpec({
      ...validSpec,
      functionalRequirements: [
        { title: "发送验证码", detail: "d", acceptanceCriteria: ["a"], scenarioIds: ["s9"] },
      ],
    });
    expect(errors).toEqual([]);
    expect(spec?.functionalRequirements[0].priority).toBe("must");
    expect(spec?.functionalRequirements[0].scenarioIds).toEqual([]);
  });

  it("collects every missing required section at once", () => {
    const { spec, errors } = validateRequirementSpec({ ...validSpec, goals: [], assumptions: [], summary: " " });
    expect(spec).toBeNull();
    expect(errors).toContain("summary 不能为空");
    expect(errors).toContain("goals 至少需要 1 条");
    expect(errors).toContain("assumptions 至少需要 1 条");
    expect(errors.length).toBeGreaterThanOrEqual(3);
  });

  it("rejects a functional requirement without detail or acceptance criteria", () => {
    const { errors } = validateRequirementSpec({
      ...validSpec,
      functionalRequirements: [{ title: "发送验证码", detail: "", acceptanceCriteria: [] }],
    });
    expect(errors).toContain("functionalRequirements[发送验证码] detail 不能为空");
    expect(errors).toContain("functionalRequirements[发送验证码] acceptanceCriteria 至少需要 1 条");
  });

  it("rejects empty functional requirements and invalid priority", () => {
    const noRequirements = validateRequirementSpec({ ...validSpec, functionalRequirements: [] });
    expect(noRequirements.errors).toContain("functionalRequirements 至少需要 1 条");
    const badPriority = validateRequirementSpec({
      ...validSpec,
      functionalRequirements: [{ title: "t", detail: "d", acceptanceCriteria: ["a"], priority: "wish" }],
    });
    expect(badPriority.errors).toContain("functionalRequirements[t] priority 无效（须为 must、should 或 could）");
  });

  it("requires rootCause for bug work kind only", () => {
    const bugWithoutRootCause = validateRequirementSpec({ ...validSpec, workKind: "bug" });
    expect(bugWithoutRootCause.errors).toContain("workKind 为 bug 时 rootCause（问题根因）不能为空");
    const bugWithRootCause = validateRequirementSpec({ ...validSpec, workKind: "bug", rootCause: "会话过期未跳转" });
    expect(bugWithRootCause.errors).toEqual([]);
    const featureWithRootCause = validateRequirementSpec({ ...validSpec, rootCause: "多余" });
    expect(featureWithRootCause.errors).toEqual([]);
  });

  it("rejects invalid work kind", () => {
    const { errors } = validateRequirementSpec({ ...validSpec, workKind: "chore" });
    expect(errors).toContain("workKind 须为 bug、feature 或 other");
  });
});

describe("validateCheckPlan", () => {
  it("accepts two levels and assigns g1/g1.2 ids", () => {
    const { plan, errors } = validateCheckPlan({
      goals: [
        { title: "验证码发送", subgoals: [{ title: "合法邮箱收到验证码" }, { title: "频控生效" }] },
        { title: "独立项" },
      ],
    });
    expect(errors).toEqual([]);
    expect(plan?.goals[0].subgoals.map((sub) => sub.id)).toEqual(["g1.1", "g1.2"]);
    expect(plan?.goals[1].id).toBe("g2");
  });

  it("rejects nesting beyond two levels, empty goals and missing titles", () => {
    const nested = validateCheckPlan({ goals: [{ title: "g", subgoals: [{ title: "s", subgoals: [{ title: "x" }] }] }] });
    expect(nested.errors).toContain("计划最多支持两级（大目标→小目标），小目标下不能再有子目标");
    const empty = validateCheckPlan({ goals: [] });
    expect(empty.errors).toContain("goals 不能为空");
    const missingTitle = validateCheckPlan({ goals: [{ title: " " }] });
    expect(missingTitle.errors).toContain("第 1 个大目标缺少 title");
  });
});

describe("checkPlanLeaves", () => {
  it("treats a goal without subgoals as its own leaf", () => {
    const { plan } = validateCheckPlan({
      goals: [{ title: "a", subgoals: [{ title: "a1" }] }, { title: "b" }],
    });
    expect(plan && checkPlanLeaves(plan).map((leaf) => leaf.id)).toEqual(["g1.1", "g2"]);
  });
});

describe("validateCheckResult", () => {
  const plan = validateCheckPlan({
    goals: [{ title: "验证码", subgoals: [{ title: "收到验证码" }] }, { title: "频控" }],
  }).plan!;

  const validResult = {
    summary: "两项通过",
    cases: [{ name: "用例A", status: "passed", detail: "收到验证码" }],
    coverage: [
      { planId: "g1.1", passed: true, evidence: "实际发送验证码并收到", cases: ["用例A"] },
      { planId: "g2", passed: true, evidence: "频控日志确认", cases: ["用例A"] },
    ],
    findings: [],
    assessment: "通过",
  };

  it("accepts full coverage with passed evidence and referenced cases", () => {
    const { result, errors } = validateCheckResult(validResult, plan);
    expect(errors).toEqual([]);
    expect(result?.coverage.length).toBe(2);
  });

  it("rejects a missing leaf and an unknown planId", () => {
    const { errors } = validateCheckResult({
      ...validResult,
      coverage: [{ planId: "g9", passed: true, evidence: "e", cases: ["用例A"] }],
    }, plan);
    expect(errors).toContain("计划叶子 g1.1（收到验证码）缺少 coverage 条目");
    expect(errors).toContain("计划叶子 g2（频控）缺少 coverage 条目");
    expect(errors).toContain("coverage[g9] 不是本计划的叶子（planId 须为 gN 或 gN.M）");
  });

  it("rejects duplicate leaf coverage and evidence-free entries", () => {
    const { errors } = validateCheckResult({
      ...validResult,
      coverage: [
        { planId: "g1.1", passed: true, evidence: "e", cases: ["用例A"] },
        { planId: "g1.1", passed: true, evidence: "e", cases: ["用例A"] },
        { planId: "g2", passed: true, evidence: " ", cases: ["用例A"] },
      ],
    }, plan);
    expect(errors).toContain("coverage[g1.1] 重复：每个计划叶子恰好一条");
    expect(errors).toContain("计划叶子 g2（频控）evidence 不能为空");
  });

  it("rejects references to cases that do not exist but allows failed ones as honest evidence", () => {
    const missingCase = validateCheckResult({
      ...validResult,
      coverage: validResult.coverage.map((item) => ({ ...item, cases: ["用例B"] })),
    }, plan);
    expect(missingCase.errors.some((line) => line.includes("引用的用例不存在"))).toBe(true);
    const failedCase = validateCheckResult({
      ...validResult,
      cases: [{ name: "用例A", status: "failed" }],
    }, plan);
    expect(failedCase.errors).toEqual([]);
  });

  it("allows a failed leaf when reported honestly", () => {
    const { errors } = validateCheckResult({
      ...validResult,
      coverage: [
        { planId: "g1.1", passed: false, evidence: "验证码未在 60 秒内到达", cases: ["用例A"] },
        { planId: "g2", passed: true, evidence: "频控确认", cases: ["用例A"] },
      ],
      cases: [{ name: "用例A", status: "failed" }],
      findings: [{ title: "验证码超时", severity: "blocker", detail: "60 秒未到达" }],
    }, plan);
    // passed=false 的叶子引用了 failed 用例是如实上报，只要求 evidence 与用例引用存在。
    expect(errors).toEqual([]);
  });
});
