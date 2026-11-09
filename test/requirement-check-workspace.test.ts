import { describe, expect, it } from "vitest";
import { artifactStage, leafCoverage, REQUIREMENT_SPEC_PATH, CHECK_PLAN_PATH, CHECK_RESULT_PATH } from "../src/renderer/requirement-check-workspace.js";

describe("artifactStage", () => {
  it("done when the artifact file exists", () => {
    expect(artifactStage(true, false)).toBe("done");
    expect(artifactStage(true, true)).toBe("done");
  });

  it("working when missing but the agent is running", () => {
    expect(artifactStage(false, true)).toBe("working");
  });

  it("idle when missing and no agent run", () => {
    expect(artifactStage(false, false)).toBe("idle");
  });
});

describe("leafCoverage", () => {
  const result = {
    coverage: [
      { planId: "g1.1", passed: true },
      { planId: "g1.2", passed: false },
    ],
  };

  it("joins verdicts by planId", () => {
    expect(leafCoverage(result, "g1.1")).toEqual({ passed: true });
    expect(leafCoverage(result, "g1.2")).toEqual({ passed: false });
  });

  it("missing when the leaf is absent from the result", () => {
    expect(leafCoverage(result, "g2.1")).toEqual({ missing: true });
  });

  it("missing when there is no result yet", () => {
    expect(leafCoverage(null, "g1.1")).toEqual({ missing: true });
  });
});

describe("artifact paths", () => {
  it("match the daemon tool output locations", () => {
    expect(REQUIREMENT_SPEC_PATH).toBe("requirements/requirement-spec.json");
    expect(CHECK_PLAN_PATH).toBe("requirements/check-plan.json");
    expect(CHECK_RESULT_PATH).toBe("check/check-result.json");
  });
});
