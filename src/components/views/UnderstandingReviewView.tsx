import { Icon } from "@/components/common/Icon";
import type { UnderstandingReviewView as UnderstandingReviewViewModel } from "@/types/flow";

export function UnderstandingReviewView({ view, onEdit }: {
  view: UnderstandingReviewViewModel;
  onEdit: () => void;
}) {
  const showDecision = Boolean(view.suitabilityTitle || view.suitabilitySummary);

  return (
    <>
      <section className="question-card">
        <h1 className="question-title">{view.title}</h1>
        {view.subtitle ? <p className="question-sub">{view.subtitle}</p> : null}
      </section>
      <div className="summary-view understanding-view">
        <section className="summary-review understanding-summary">
          <div className="summary-review-title-row">
            <span aria-hidden="true"><Icon name="check" /></span>
            <h2 className="summary-review-title">입력 내용 요약</h2>
          </div>
          {view.items.length ? (
            <ul className="confirmed-summary-list">
              {view.items.map((item) => (
                <li className="confirmed-summary-item" key={`${item.label}-${item.value}`}>
                  <span className="confirmed-summary-key">{item.label}</span>
                  <span className="confirmed-summary-value">{item.value}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="summary-review-subtitle">아직 확정된 입력이 많지 않아요.</p>
          )}
        </section>

        {showDecision ? (
          <section className="summary-review understanding-decision">
            <div className="summary-review-title-row">
              <span aria-hidden="true"><Icon name="search" /></span>
              <h2 className="summary-review-title">{view.suitabilityTitle || "적합성 판단"}</h2>
            </div>
            {view.suitabilitySummary ? <p className="summary-review-subtitle">{view.suitabilitySummary}</p> : null}
          </section>
        ) : null}

        {view.apiItems.length ? <ListBlock title="확인된 근거" icon="fileCheck" items={view.apiItems} /> : null}

        <div className="understanding-actions">
          <button className="understanding-edit-button" type="button" onClick={onEdit}>
            <Icon name="edit" size={18} />
            <span>{view.editButtonLabel || "아니에요, 수정할게요"}</span>
          </button>
        </div>
      </div>
    </>
  );
}

function ListBlock({
  title,
  icon,
  items,
}: {
  title: string;
  icon: Parameters<typeof Icon>[0]["name"];
  items: string[];
}) {
  return (
    <section className="summary-review">
      <div className="summary-review-title-row">
        <span aria-hidden="true"><Icon name={icon} /></span>
        <h2 className="summary-review-title">{title}</h2>
      </div>
      <ul className="missing-summary-list">
        {items.map((item) => (
          <li className="missing-summary-item" key={item}>
            <span className="missing-summary-icon" aria-hidden="true"><Icon name={icon} /></span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
