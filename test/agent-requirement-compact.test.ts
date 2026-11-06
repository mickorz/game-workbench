import { describe, expect, it } from "vitest";
import { toolArguments } from "../src/daemon/agent.js";

/** 超过 MAX_GENERIC_TOOL_ARGUMENTS（2000 字符）的完整规格参数（compact 前的原始形态）。 */
const fullSpec = {
  title: "深色模式",
  summary: "设置页支持深色模式切换，切换立即生效",
  background: "x".repeat(600),
  workKind: "feature",
  goals: ["深色模式"],
  inScope: ["设置页切换"],
  outOfScope: ["主题自定义"],
  functionalRequirements: [
    {
      title: "深色切换",
      detail: "y".repeat(600),
      priority: "must",
      acceptanceCriteria: ["切换立即生效，无需刷新"],
      scenarioIds: [],
    },
  ],
  assumptions: ["无额外假设"],
  dependencies: ["主题服务"],
  constraints: ["默认跟随系统"],
  openQuestions: [],
};

describe("toolArguments compacts requirement-check artifacts for the timeline", () => {
  it("keeps card fields and drops detail text for set_requirement_spec", () => {
    const compact = toolArguments("set_requirement_spec", fullSpec) as Record<string, unknown>;
    expect(typeof compact).toBe("object");
    expect(compact.title).toBe("深色模式");
    expect(compact.workKind).toBe("feature");
    const requirements = compact.functionalRequirements as Array<Record<string, unknown>>;
    expect(requirements).toHaveLength(1);
    expect(requirements[0].title).toBe("深色切换");
    expect(requirements[0].priority).toBe("must");
    expect((requirements[0].acceptanceCriteria as string[])[0]).toContain("立即生效");
    // detail 大文本被丢弃，summary/background 等卡片不需要的字段不保留
    expect(requirements[0].detail).toBeUndefined();
    expect(compact.summary).toBeUndefined();
    expect(compact.background).toBeUndefined();
    // inScope/outScope 卡片渲染保留
    expect(compact.inScope).toEqual(["设置页切换"]);
    expect(compact.outOfScope).toEqual(["主题自定义"]);
  });

  it("caps rootCause length for bug specs", () => {
    const compact = toolArguments("set_requirement_spec", { ...fullSpec, workKind: "bug", rootCause: "r".repeat(500) }) as Record<string, unknown>;
    expect((compact.rootCause as string).length).toBeLessThanOrEqual(200);
  });

  it("keeps only the two-level tree for set_check_plan", () => {
    const compact = toolArguments("set_check_plan", {
      title: "计划",
      goals: [
        {
          title: "切换行为",
          detail: "d".repeat(800),
          subgoals: [{ title: "切换立即生效", detail: "s".repeat(800) }, { title: "无需刷新" }],
        },
        { title: "独立项" },
      ],
    }) as Record<string, unknown>;
    const goals = compact.goals as Array<Record<string, unknown>>;
    expect(goals[0].title).toBe("切换行为");
    expect(goals[0].detail).toBeUndefined();
    expect(goals[0].subgoals).toEqual(["切换立即生效", "无需刷新"]);
    expect(goals[1].subgoals).toEqual([]);
  });

  it("keeps coverage verdicts with capped evidence and compact findings for set_check_result", () => {
    const compact = toolArguments("set_check_result", {
      summary: "s".repeat(600),
      cases: [{ name: "用例A", status: "passed", detail: "c".repeat(600) }],
      coverage: [
        { planId: "g1.1", title: "立即生效", passed: true, evidence: "e".repeat(500), cases: ["用例A"] },
        { planId: "g2", passed: false, evidence: "未通过证据", cases: ["用例A"] },
      ],
      findings: [{ title: "发现一", severity: "major", detail: "f".repeat(600) }],
      assessment: "a".repeat(600),
    }) as Record<string, unknown>;
    const coverage = compact.coverage as Array<Record<string, unknown>>;
    expect(coverage[0].planId).toBe("g1.1");
    expect(coverage[0].passed).toBe(true);
    expect((coverage[0].evidence as string).length).toBeLessThanOrEqual(160);
    expect(coverage[1].passed).toBe(false);
    expect((compact.findings as Array<Record<string, unknown>>)[0].severity).toBe("major");
    // cases/summary/assessment 卡片不渲染，全部丢弃
    expect(compact.cases).toBeUndefined();
    expect(compact.summary).toBeUndefined();
    expect(compact.assessment).toBeUndefined();
  });

  it("still returns the generic bounded value for other tools", () => {
    const compact = toolArguments("bash", { command: "echo hi", timeout: 5000 }) as Record<string, unknown>;
    expect(compact.command).toBe("echo hi");
    expect(compact.timeout).toBe(5000);
  });
});
