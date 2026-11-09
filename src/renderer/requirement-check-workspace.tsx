import { useEffect, useState, type ReactNode } from "react";
import type { ProjectState } from "../shared/contracts.js";
import { getWorkspaceFile, listWorkspaceFiles } from "./api.js";
import { LoaderCircle } from "./icons.js";
import { t } from "./i18n.js";

// 需求检查工作区：专属产物面板。
// 阶段不依赖引擎状态机，由三份产物文件的齐全度推断（见可行性分析）：
//   requirements/requirement-spec.json  -> 需求规格已产出
//   requirements/check-plan.json        -> 检查计划已产出
//   check/check-result.json             -> 检查结果已产出
// agent 落盘后 workspaceRevision 变化驱动重新加载。

/** 需求检查三份产物的工作区相对路径。 */
export const REQUIREMENT_SPEC_PATH = "requirements/requirement-spec.json";
export const CHECK_PLAN_PATH = "requirements/check-plan.json";
export const CHECK_RESULT_PATH = "check/check-result.json";

export type ArtifactStage = "idle" | "working" | "done";

/** 产物阶段推断：文件已落盘为 done；缺失但 agent 正在跑为 working；否则 idle。 */
export function artifactStage(present: boolean, agentBusy: boolean): ArtifactStage {
  if (present) return "done";
  return agentBusy ? "working" : "idle";
}

interface RequirementCheckWorkspaceProps {
  project: ProjectState;
  agentBusy: boolean;
  workspaceRevision: number;
  onHome: () => void;
  homeLabel?: string;
}

type Artifact = Record<string, unknown> | null;

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function list(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null) : [];
}

async function readArtifact(projectId: string, path: string): Promise<Record<string, unknown>> {
  const file = await getWorkspaceFile(projectId, path);
  return JSON.parse(file.content ?? "") as Record<string, unknown>;
}

export function RequirementCheckWorkspace({ project, agentBusy, workspaceRevision }: RequirementCheckWorkspaceProps) {
  const [spec, setSpec] = useState<Artifact>(null);
  const [plan, setPlan] = useState<Artifact>(null);
  const [result, setResult] = useState<Artifact>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const files = await listWorkspaceFiles(project.id);
        const paths = new Set(files.map((file) => file.path));
        if (paths.has(REQUIREMENT_SPEC_PATH)) {
          const doc = await readArtifact(project.id, REQUIREMENT_SPEC_PATH);
          if (!cancelled) setSpec(doc);
        } else if (!cancelled) setSpec(null);
        if (paths.has(CHECK_PLAN_PATH)) {
          const doc = await readArtifact(project.id, CHECK_PLAN_PATH);
          if (!cancelled) setPlan(doc);
        } else if (!cancelled) setPlan(null);
        if (paths.has(CHECK_RESULT_PATH)) {
          const doc = await readArtifact(project.id, CHECK_RESULT_PATH);
          if (!cancelled) setResult(doc);
        } else if (!cancelled) setResult(null);
        if (!cancelled) setError(null);
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : String(cause));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [project.id, workspaceRevision]);

  const specStage = artifactStage(spec !== null, agentBusy);
  const planStage = artifactStage(plan !== null, agentBusy);
  const resultStage = artifactStage(result !== null, agentBusy);

  return (
    <section className="requirement-panel" data-testid="requirement-panel">
      <header className="requirement-panel-header">
        <div className="requirement-panel-title">{t("requirementPanel.title")}</div>
        <div className="requirement-panel-stages">
          <StageChip label={t("requirementPanel.stageSpec")} stage={specStage} />
          <StageChip label={t("requirementPanel.stagePlan")} stage={planStage} />
          <StageChip label={t("requirementPanel.stageResult")} stage={resultStage} />
        </div>
      </header>
      {error ? (
        <div className="requirement-panel-error">{t("requirementPanel.loadError") + ": " + error}</div>
      ) : (
        <div className="requirement-panel-body">
          <SpecView stage={specStage} spec={spec} />
          <PlanView stage={planStage} plan={plan} result={result} />
          <ResultView stage={resultStage} result={result} />
        </div>
      )}
    </section>
  );
}

const stageStateLabels: Record<ArtifactStage, string> = {
  idle: t("requirementPanel.state.idle"),
  working: t("requirementPanel.state.working"),
  done: t("requirementPanel.state.done"),
};

function StageChip({ label, stage }: { label: string; stage: ArtifactStage }) {
  return (
    <span className={"requirement-stage requirement-stage-" + stage}>
      {stage === "working" ? <LoaderCircle className="spin" size={12} /> : null}
      {label}
      <em className="requirement-stage-state">{stageStateLabels[stage]}</em>
    </span>
  );
}

function SectionShell({ stage, title, children }: { stage: ArtifactStage; title: string; children?: ReactNode }) {
  return (
    <section className={"requirement-doc requirement-doc-" + stage} data-stage={stage}>
      <h2 className="requirement-doc-title">{title}</h2>
      {stage === "done" ? (
        children
      ) : stage === "working" ? (
        <div className="requirement-doc-empty">
          <LoaderCircle className="spin" size={16} />
          <span>{t("requirementPanel.working")}</span>
        </div>
      ) : (
        <div className="requirement-doc-empty">{t("requirementPanel.pending")}</div>
      )}
    </section>
  );
}

function Chiplist({ label, items, tone }: { label: string; items: string[]; tone: "ok" | "muted" }) {
  if (!items.length) return null;
  return (
    <div className="requirement-doc-section">
      <div className="requirement-card-section-label">{label}</div>
      <div className="requirement-chips">
        {items.map((item, index) => (
          <span key={index} className={"requirement-chip requirement-chip-" + tone}>{item}</span>
        ))}
      </div>
    </div>
  );
}

function SpecView({ stage, spec }: { stage: ArtifactStage; spec: Artifact }) {
  return (
    <SectionShell stage={stage} title={t("requirementPanel.specTitle")}>
      {spec ? (
        <div className="requirement-card">
          <div className="requirement-card-head">
            <div className="requirement-card-title">{text(spec.title) || text(spec.summary)}</div>
            {typeof spec.workKind === "string" ? (
              <span className={"requirement-badge requirement-kind-" + spec.workKind}>{spec.workKind}</span>
            ) : null}
          </div>
          {text(spec.summary) ? <p className="requirement-doc-summary">{text(spec.summary)}</p> : null}
          {text(spec.background) ? (
            <div className="requirement-doc-section">
              <div className="requirement-card-section-label">{t("requirementPanel.specBackground")}</div>
              <p className="requirement-doc-text">{text(spec.background)}</p>
            </div>
          ) : null}
          {text(spec.rootCause) ? (
            <div className="requirement-doc-section">
              <div className="requirement-card-section-label">{t("timeline.detail.reqRootCause")}</div>
              <p className="requirement-doc-text">{text(spec.rootCause)}</p>
            </div>
          ) : null}
          <Chiplist label={t("timeline.detail.reqInScope")} items={stringList(spec.inScope)} tone="ok" />
          <Chiplist label={t("timeline.detail.reqOutScope")} items={stringList(spec.outOfScope)} tone="muted" />
          {stringList(spec.goals).length ? (
            <Chiplist label={t("requirementPanel.specGoals")} items={stringList(spec.goals)} tone="muted" />
          ) : null}
          {list(spec.functionalRequirements).length ? (
            <div className="requirement-doc-section">
              <div className="requirement-card-section-label">{t("timeline.detail.reqFr")}</div>
              <ol className="requirement-fr-list">
                {list(spec.functionalRequirements).map((requirement, index) => (
                  <li key={index} className="requirement-fr">
                    <div className="requirement-fr-head">
                      <span className="requirement-fr-id">f{index + 1}</span>
                      <span className="requirement-fr-title">{text(requirement.title)}</span>
                      {typeof requirement.priority === "string" ? (
                        <span className={"requirement-badge requirement-priority-" + requirement.priority}>{requirement.priority}</span>
                      ) : null}
                    </div>
                    {text(requirement.detail) ? <p className="requirement-doc-text">{text(requirement.detail)}</p> : null}
                    {stringList(requirement.acceptanceCriteria).length ? (
                      <ul className="requirement-criteria">
                        {stringList(requirement.acceptanceCriteria).map((criterion, cIndex) => (
                          <li key={cIndex}>{criterion}</li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
          {stringList(spec.assumptions).length ? (
            <Chiplist label={t("requirementPanel.specAssumptions")} items={stringList(spec.assumptions)} tone="muted" />
          ) : null}
          {stringList(spec.constraints).length ? (
            <Chiplist label={t("requirementPanel.specConstraints")} items={stringList(spec.constraints)} tone="muted" />
          ) : null}
          {stringList(spec.openQuestions).length ? (
            <div className="requirement-doc-section">
              <div className="requirement-card-section-label requirement-open-label">{t("requirementPanel.specOpenQuestions")}</div>
              <ul className="requirement-criteria">
                {stringList(spec.openQuestions).map((question, index) => (
                  <li key={index}>{question}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </SectionShell>
  );
}

/** 叶子覆盖状态：从检查结果按 planId 关联，未出现在结果里视为未覆盖。 */
export function leafCoverage(result: Artifact, planId: string): { passed: boolean } | { missing: true } {
  for (const entry of list(result?.coverage)) {
    if (text(entry.planId) === planId) return { passed: entry.passed === true };
  }
  return { missing: true };
}

function PlanView({ stage, plan, result }: { stage: ArtifactStage; plan: Artifact; result: Artifact }) {
  const goals = list(plan?.goals);
  const leaves = goals.reduce((count, goal) => count + list(goal.subgoals).length, 0);
  return (
    <SectionShell stage={stage} title={t("requirementPanel.planTitle")}>
      {plan ? (
        <div className="requirement-card">
          <div className="requirement-card-head">
            <div className="requirement-card-title">{text(plan.title)}</div>
            <span className="requirement-card-meta">{t("requirementPanel.planLeavesCount", { n: leaves })}</span>
          </div>
          {goals.map((goal, gIndex) => (
            <div key={gIndex} className="requirement-plan-goal">
              <div className="requirement-plan-goal-title">
                <span className="requirement-plan-id">g{gIndex + 1}</span>
                {text(goal.title)}
              </div>
              <ul className="requirement-plan-leaves">
                {list(goal.subgoals).map((leaf) => {
                  const id = text(leaf.id);
                  const coverage = result && id ? leafCoverage(result, id) : { missing: true as const };
                  const coverageClass = "missing" in coverage ? "requirement-unknown" : coverage.passed ? "requirement-pass" : "requirement-fail";
                  const coverageLabel =
                    "missing" in coverage ? t("requirementPanel.coverageMissing") : coverage.passed ? t("timeline.detail.checkPassed") : t("timeline.detail.checkNotPassed");
                  return (
                    <li key={id || gIndex + "." + list(goal.subgoals).indexOf(leaf)} className="requirement-plan-leaf">
                      <span className="requirement-plan-id">{id}</span>
                      <span className="requirement-plan-leaf-title">{text(leaf.title)}</span>
                      {result ? <span className={"requirement-badge " + coverageClass}>{coverageLabel}</span> : null}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      ) : null}
    </SectionShell>
  );
}

function ResultView({ stage, result }: { stage: ArtifactStage; result: Artifact }) {
  const coverage = list(result?.coverage);
  const passedCount = coverage.filter((entry) => entry.passed === true).length;
  const total = coverage.length;
  const passPct = total > 0 ? Math.round((passedCount / total) * 100) : 0;
  const findings = list(result?.findings);
  return (
    <SectionShell stage={stage} title={t("requirementPanel.resultTitle")}>
      {result ? (
        <div className="requirement-card">
          <div className="requirement-stats">
            <div className="requirement-stats-bar">
              <div className="requirement-stats-fill" style={{ width: passPct + "%" }} />
            </div>
            <div className="requirement-stats-nums">
              <span className="requirement-stats-num requirement-stats-pass">{passedCount}</span>
              <span className="requirement-stats-denom">{"/ " + total}</span>
              <span className="requirement-stats-pct">{passPct + "%"}</span>
            </div>
          </div>
          {text(result.summary) ? <p className="requirement-doc-summary">{text(result.summary)}</p> : null}
          {coverage.length ? (
            <div className="requirement-doc-section">
              <div className="requirement-card-section-label">{t("timeline.detail.checkCoverage")}</div>
              <ul className="requirement-coverage-list">
                {coverage.map((entry, index) => (
                  <li key={index} className="requirement-coverage-row">
                    <span className="requirement-plan-id">{text(entry.planId)}</span>
                    <span className="requirement-plan-leaf-title">{text(entry.title)}</span>
                    <span className={"requirement-badge " + (entry.passed === true ? "requirement-pass" : "requirement-fail")}>
                      {entry.passed === true ? t("timeline.detail.checkPassed") : t("timeline.detail.checkNotPassed")}
                    </span>
                    {text(entry.evidence) ? <span className="requirement-coverage-evidence">{text(entry.evidence)}</span> : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {findings.length ? (
            <div className="requirement-doc-section">
              <div className="requirement-card-section-label">{t("timeline.detail.checkFindings")}</div>
              <ul className="requirement-findings-list">
                {findings.map((finding, index) => (
                  <li key={index} className="requirement-finding">
                    {typeof finding.severity === "string" ? (
                      <span className={"requirement-badge requirement-severity-" + finding.severity}>{finding.severity}</span>
                    ) : null}
                    <span className="requirement-finding-title">{text(finding.title)}</span>
                    {text(finding.detail) ? <p className="requirement-doc-text">{text(finding.detail)}</p> : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </SectionShell>
  );
}
