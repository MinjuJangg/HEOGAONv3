import { Icon, iconForOption } from "@/components/common/Icon";
import type { QuestionOption, SlotQuestionView as SlotQuestionViewModel } from "@/types/flow";

export function SlotQuestionView({
  view,
  selectedIds,
  freeText,
  onSelectIds,
  onFreeText,
  onUnknown,
}: {
  view: SlotQuestionViewModel;
  selectedIds: string[];
  freeText: string;
  onSelectIds: (ids: string[]) => void;
  onFreeText: (value: string) => void;
  onUnknown: () => void;
}) {
  return (
    <section className="question-card">
      <h1 className="question-title">{view.title}</h1>
      {view.subtitle ? <p className="question-sub">{view.subtitle}</p> : null}
      {view.validationMessage ? <p className="collect-status error-text" role="alert">{view.validationMessage}</p> : null}
      {view.inputMode === "free_text" ? (
        <div className="detail-form slot-free-text">
          <div className="detail-box">
            <textarea
              className="detail-field"
              value={freeText}
              onChange={(event) => onFreeText(event.target.value)}
              placeholder="아는 만큼만 적어주세요"
            />
          </div>
          <button className="unknown-inline-button" type="button" onClick={onUnknown}>
            <span className="unknown-inline-icon" aria-hidden="true"><Icon name="help" size={16} /></span>
            <span>아직 몰라요</span>
          </button>
        </div>
      ) : (
        <QuestionOptions view={view} selectedIds={selectedIds} onSelectIds={onSelectIds} onUnknown={onUnknown} />
      )}
    </section>
  );
}

function QuestionOptions({
  view,
  selectedIds,
  onSelectIds,
  onUnknown,
}: {
  view: SlotQuestionViewModel;
  selectedIds: string[];
  onSelectIds: (ids: string[]) => void;
  onUnknown: () => void;
}) {
  const isMulti = view.inputMode === "multi_select";

  function toggle(option: QuestionOption) {
    if (option.id === "unknown") {
      onUnknown();
      return;
    }

    if (!isMulti || option.exclusive) {
      onSelectIds([option.id]);
      return;
    }

    if (selectedIds.includes(option.id)) {
      onSelectIds(selectedIds.filter((id) => id !== option.id));
      return;
    }

    onSelectIds([...selectedIds.filter((id) => id !== "unknown"), option.id]);
  }

  return (
    <div className="options" role={isMulti ? "group" : "radiogroup"} aria-label="답변 선택">
      {view.options.map((option) => {
        const isUnknown = option.id === "unknown";
        return (
          <button
            className={`option${selectedIds.includes(option.id) ? " selected" : ""}${isUnknown ? " option-unknown" : ""}`}
            type="button"
            role={isMulti ? "checkbox" : "radio"}
            aria-checked={selectedIds.includes(option.id)}
            key={option.id}
            onClick={() => toggle(option)}
          >
            <span className="option-icon" aria-hidden="true"><Icon name={iconForOption(option.id)} /></span>
            <span className="option-main">
              <span className="option-title">{option.title}</span>
            </span>
            <span className="check-dot" aria-hidden="true"><Icon name="check" size={13} /></span>
          </button>
        );
      })}
    </div>
  );
}
