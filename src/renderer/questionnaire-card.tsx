import { Check, Pencil } from "./icons.js";
import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import type { QuestionnaireQuestion, ThreadItem } from "../shared/contracts.js";
import { InlineAnswer } from "./inline-answer.js";
import { t } from "./i18n.js";

type UserInputRequest = Extract<ThreadItem, { type: "userInputRequest" }>;

interface QuestionnaireCardProps {
  request: UserInputRequest;
  onSubmit: (answers: Array<{ questionId: string; value: string; notes?: string }>) => Promise<boolean>;
  onSkip: () => Promise<boolean>;
}

// 多选答案以换行拼接存进 answers[qid]；提交协议与单选一致（value 为字符串）。
function selectedValues(question: QuestionnaireQuestion, value: string): string[] {
  return question.multiSelect ? value.split("\n").map((line) => line.trim()).filter(Boolean) : value.trim() ? [value.trim()] : [];
}

function joinNotes(question: QuestionnaireQuestion, selected: string[], notes: Record<string, string>): string | undefined {
  const lines = selected.flatMap((value) => {
    const note = notes[value]?.trim();
    if (!note) return [];
    const option = question.options.find((candidate) => candidate.value === value);
    return [`${option?.label ?? value}: ${note}`];
  });
  return lines.length > 0 ? lines.join("\n") : undefined;
}

export function QuestionnaireCard({ request, onSubmit, onSkip }: QuestionnaireCardProps) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  // 备注按选项 value 记录，提交时按题目拼接。
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [noteFor, setNoteFor] = useState<string | null>(null);
  const [custom, setCustom] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const question = request.questions[index];
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    setIndex(0);
    setAnswers({});
    setNotes({});
    setNoteFor(null);
    setCustom(false);
  }, [request.requestId]);

  if (!question) return null;
  const multi = Boolean(question.multiSelect);
  const answer = answers[question.id] ?? "";
  const selected = selectedValues(question, answer);
  const selectedOption = question.options.some((option) => selected.includes(option.value));
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

  // 多选：切换一个选项的选中态，不自动跳题（由 Submit 提交）。
  function toggle(value: string) {
    const current = selectedValues(question, answer);
    const next = current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
    setAnswers((previous) => ({ ...previous, [question.id]: next.join("\n") }));
    if (!next.includes(value) && noteFor === value) setNoteFor(null);
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
    setNoteFor(null);
  }
  // Tab chips 与键盘共用同一个翻题入口。

  async function submit(nextAnswers: Record<string, string>) {
    if (submitting || !request.questions.every((item) => Boolean(nextAnswers[item.id]?.trim()))) return;
    setSubmitting(true);
    try {
      await onSubmit(request.questions.map((item) => {
        const selectedValuesForQuestion = selectedValues(item, nextAnswers[item.id] ?? "");
        return {
          questionId: item.id,
          value: nextAnswers[item.id],
          ...(joinNotes(item, selectedValuesForQuestion, notes) ? { notes: joinNotes(item, selectedValuesForQuestion, notes) } : {}),
        };
      }));
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

  // 存在多选题时不自动提交（toggle 不触发 choose），全部答完后显示显式提交按钮。
  const hasMulti = request.questions.some((item) => item.multiSelect);
  const allAnswered = request.questions.every((item) => Boolean(answers[item.id]?.trim()));

  // 多选的自定义答案作为额外一行追加，不覆盖已勾选项；单选直接作为答案。
  const customLine = selected.find((value) => !question.options.some((option) => option.value === value)) ?? "";
  function onCustomChange(text: string) {
    setAnswers((current) => {
      if (!multi) return { ...current, [question.id]: text };
      const kept = selectedValues(question, current[question.id] ?? "").filter((value) => question.options.some((option) => option.value === value));
      const trimmed = text.trim();
      return { ...current, [question.id]: [...kept, ...(trimmed ? [trimmed] : [])].join("\n") };
    });
  }

  // 预览面板：优先显示选中项的预览，否则回退到首个带预览的选项。
  const anyPreview = question.options.some((option) => option.preview);
  const previewOption = question.options.find((option) => selected.includes(option.value) && option.preview)
    ?? question.options.find((option) => option.preview);

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
                <span className="questionnaire-tab-label">{item.header ?? item.prompt}</span>
              </button>
            );
          })}
        </div>
      ) : null}

      <strong className="questionnaire-prompt">{question.prompt}</strong>
      <div className={anyPreview ? "questionnaire-body questionnaire-body-preview" : "questionnaire-body"}>
        <div
          className="questionnaire-options"
          role={multi ? "group" : "radiogroup"}
          aria-label={question.prompt}
          onKeyDown={(event) => onOptionsKeyDown(event, question.options.length)}
        >
          {question.options.map((option, optionIndex) => {
            const isSelected = selected.includes(option.value);
            return (
              <div key={option.value} className="questionnaire-option-wrapper">
                <button
                  type="button"
                  className={isSelected ? "questionnaire-option-selected" : undefined}
                  role={multi ? "checkbox" : "radio"}
                  aria-checked={isSelected}
                  disabled={submitting}
                  ref={(node) => { optionRefs.current[optionIndex] = node; }}
                  onClick={() => { multi ? toggle(option.value) : void choose(option.value); }}
                >
                  <span className="questionnaire-option-number">{isSelected ? <Check size={13} /> : optionIndex + 1}</span>
                  <span className="questionnaire-option-copy">
                    <strong>{option.label}{option.recommended ? <small>{t("providers.recommended")}</small> : null}</strong>
                    {option.description ? <span>{option.description}</span> : null}
                    {option.recommendedReason ? <span className="questionnaire-why">{t("questionnaire.why")} {option.recommendedReason}</span> : null}
                  </span>
                </button>
                {isSelected && !custom ? (
                  noteFor === option.value ? (
                    <textarea
                      className="questionnaire-option-note"
                      data-testid={`questionnaire-note-${option.value}`}
                      aria-label={t("questionnaire.noteLabel", { option: option.label })}
                      rows={2}
                      value={notes[option.value] ?? ""}
                      placeholder={t("questionnaire.notePlaceholder")}
                      disabled={submitting}
                      onChange={(event) => setNotes((current) => ({ ...current, [option.value]: event.target.value }))}
                      onKeyDown={(event) => {
                        // Enter 收起备注返回选项；Shift+Enter 换行；Esc 关闭但保留已输入文本。
                        if (event.key === "Escape" || (event.key === "Enter" && !event.shiftKey)) {
                          event.preventDefault();
                          setNoteFor(null);
                          optionRefs.current[optionIndex]?.focus();
                        }
                      }}
                    />
                  ) : (
                    <button
                      type="button"
                      className="questionnaire-option-note-toggle"
                      data-testid={`questionnaire-note-toggle-${option.value}`}
                      disabled={submitting}
                      onClick={() => setNoteFor(option.value)}
                    >
                      <Pencil size={11} aria-hidden="true" />
                      {notes[option.value]?.trim() ? t("questionnaire.editNote") : t("questionnaire.addNote")}
                    </button>
                  )
                ) : null}
              </div>
            );
          })}
        </div>
        {anyPreview && previewOption?.preview ? (
          <div className="questionnaire-preview" data-testid="questionnaire-preview">
            <div className="questionnaire-preview-title">{t("questionnaire.preview", { label: previewOption.label })}</div>
            <pre className="questionnaire-preview-text">{previewOption.preview}</pre>
          </div>
        ) : null}
      </div>

      <footer className="questionnaire-footer-row">
        {question.allowOther ? custom ? (
          <InlineAnswer
            editing
            value={multi ? customLine : selectedOption ? "" : answer}
            disabled={submitting}
            label={t("questionnaire.other")}
            onChange={onCustomChange}
            onSubmit={() => { multi ? setCustom(false) : void choose(answer.trim()); }}
            onCancel={() => setCustom(false)}
          />
        ) : (
          <InlineAnswer
            editing={false}
            disabled={submitting}
            label={t("questionnaire.other")}
            onEdit={() => setCustom(true)}
          />
        ) : <span />}
        <div className="questionnaire-footer-actions">
          {hasMulti && allAnswered ? (
            <button className="questionnaire-submit" type="button" onClick={() => { void submit(answers); }} disabled={submitting}>{t("questionnaire.submit")}</button>
          ) : null}
          <button className="questionnaire-skip" type="button" onClick={() => void skip()} disabled={submitting}>{t("common.skip")}</button>
        </div>
      </footer>
    </section>
  );
}
