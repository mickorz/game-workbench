import { Check } from "./icons.js";
import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import type { ThreadItem } from "../shared/contracts.js";
import { InlineAnswer } from "./inline-answer.js";
import { t } from "./i18n.js";

interface QuestionnaireCardProps {
  request: Extract<ThreadItem, { type: "userInputRequest" }>;
  onSubmit: (answers: Array<{ questionId: string; value: string }>) => Promise<boolean>;
  onSkip: () => Promise<boolean>;
}

export function QuestionnaireCard({ request, onSubmit, onSkip }: QuestionnaireCardProps) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [custom, setCustom] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const question = request.questions[index];
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    setIndex(0);
    setAnswers({});
    setCustom(false);
  }, [request.requestId]);

  if (!question) return null;
  const answer = answers[question.id] ?? "";
  const selectedOption = question.options.some((option) => option.value === answer);
  // 上下箭头在选项间移动焦点（选中仍由点击/回车触发，保持与鼠标一致的自动跳题行为）。
  function onOptionsKeyDown(event: ReactKeyboardEvent<HTMLDivElement>, count: number) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    const focused = optionRefs.current.findIndex((node) => node === document.activeElement);
    if (focused < 0) return;
    const next = (focused + (event.key === "ArrowDown" ? 1 : -1) + count) % count;
    optionRefs.current[next]?.focus();
  }
  async function choose(value: string) {
    const nextAnswers = { ...answers, [question.id]: value };
    setAnswers(nextAnswers);
    setCustom(false);
    const unanswered = request.questions.findIndex((item, itemIndex) => itemIndex > index && !nextAnswers[item.id]?.trim());
    const remaining = unanswered >= 0 ? unanswered : request.questions.findIndex((item) => !nextAnswers[item.id]?.trim());
    if (remaining >= 0) {
      setIndex(remaining);
      return;
    }
    await submit(nextAnswers);
  }

  function move(next: number) {
    setIndex(Math.max(0, Math.min(request.questions.length - 1, next)));
    setCustom(false);
  }
  // Tab chips 与键盘共用同一个翻题入口。

  async function submit(nextAnswers: Record<string, string>) {
    if (submitting || !request.questions.every((item) => Boolean(nextAnswers[item.id]?.trim()))) return;
    setSubmitting(true);
    try {
      await onSubmit(request.questions.map((item) => ({ questionId: item.id, value: nextAnswers[item.id] })));
    } finally {
      setSubmitting(false);
    }
  }

  async function skip() {
    if (submitting) return;
    setSubmitting(true);
    try {
      await onSkip();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="questionnaire-card" aria-label={t("questionnaire.label")}>
      {request.questions.length > 1 ? (
        <div className="questionnaire-tabs" role="tablist" aria-label={t("questionnaire.tabsLabel")}>
          {request.questions.map((item, itemIndex) => {
            const answered = Boolean(answers[item.id]?.trim());
            return (
              <button
                type="button"
                key={item.id}
                role="tab"
                aria-selected={itemIndex === index}
                data-active={itemIndex === index || undefined}
                data-answered={answered || undefined}
                disabled={submitting}
                onClick={() => { move(itemIndex); }}
                className={itemIndex === index ? "questionnaire-tab-active" : undefined}
              >
                <span className="questionnaire-tab-mark">{answered ? <Check size={11} /> : itemIndex + 1}</span>
                <span className="questionnaire-tab-label">{item.prompt}</span>
              </button>
            );
          })}
        </div>
      ) : null}

      <strong className="questionnaire-prompt">{question.prompt}</strong>
      <div
        className="questionnaire-options"
        role="radiogroup"
        aria-label={question.prompt}
        onKeyDown={(event) => onOptionsKeyDown(event, question.options.length)}
      >
        {question.options.map((option, optionIndex) => (
          <button
            type="button"
            className={answer === option.value ? "questionnaire-option-selected" : undefined}
            role="radio"
            aria-checked={answer === option.value}
            disabled={submitting}
            key={option.value}
            ref={(node) => { optionRefs.current[optionIndex] = node; }}
            onClick={() => { void choose(option.value); }}
          >
            <span className="questionnaire-option-number">{answer === option.value ? <Check size={13} /> : optionIndex + 1}</span>
            <span className="questionnaire-option-copy">
              <strong>{option.label}{option.recommended ? <small>{t("providers.recommended")}</small> : null}</strong>
              {option.description ? <span>{option.description}</span> : null}
            </span>
          </button>
        ))}
      </div>

      <footer className="questionnaire-footer-row">
        {question.allowOther ? custom ? (
          <InlineAnswer
            editing
            value={selectedOption ? "" : answer}
            disabled={submitting}
            label={t("questionnaire.other")}
            onChange={(value) => setAnswers((current) => ({ ...current, [question.id]: value }))}
            onSubmit={() => void choose(answer.trim())}
            onCancel={() => setCustom(false)}
          />
        ) : (
          <InlineAnswer
            editing={false}
            disabled={submitting}
            label={t("questionnaire.other")}
            onEdit={() => { setAnswers((current) => ({ ...current, [question.id]: "" })); setCustom(true); }}
          />
        ) : <span />}
        <button className="questionnaire-skip" type="button" onClick={() => void skip()} disabled={submitting}>{t("common.skip")}</button>
      </footer>
    </section>
  );
}
