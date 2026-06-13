import { Icon } from "@/components/common/Icon";
import type { DiagnosisGuidance, DiagnosisView as DiagnosisViewModel } from "@/types/flow";

export function DiagnosisView({ view }: { view: DiagnosisViewModel }) {
  const guidance = view.guidance;
  const buildingItems = visibleItems(guidance?.buildingItems ?? []);
  const questionsToAsk = visibleItems(guidance?.questionsToAsk ?? []);
  const hasGuidance = Boolean(guidance && (guidance.suitabilitySummary || guidance.summary || buildingItems.length || questionsToAsk.length));

  return (
    <>
      <section className="question-card">
        <h1 className="question-title">{view.title}</h1>
        <p className="question-sub">{view.headline}</p>
      </section>
      <div className="summary-view">
        {hasGuidance && guidance ? <SuitabilityCard guidance={guidance} buildingItems={buildingItems} /> : null}
        {questionsToAsk.length ? (
          <ListCard title="추가로 확인할 것" icon="help" items={questionsToAsk} />
        ) : null}
      </div>
    </>
  );
}

function SuitabilityCard({ guidance, buildingItems }: { guidance: DiagnosisGuidance; buildingItems: string[] }) {
  return (
    <section className="summary-review">
      <div className="summary-review-title-row">
        <span aria-hidden="true"><Icon name={guidance.suitability === "blocked" ? "close" : "check"} /></span>
        <h2 className="summary-review-title">{guidance.suitabilityTitle || "가능성 판단"}</h2>
      </div>
      <p className="summary-review-subtitle">{guidance.suitabilitySummary || guidance.summary}</p>
      {buildingItems.length ? <BuildingLedgerSummary items={buildingItems} /> : null}
    </section>
  );
}

function BuildingLedgerSummary({ items }: { items: string[] }) {
  return (
    <div className="building-ledger-summary" aria-label="건축물대장 확인 결과">
      <div className="building-ledger-summary-head">
        <span aria-hidden="true"><Icon name="building2" size={18} /></span>
        <h3>건축물대장 확인 결과</h3>
      </div>
      <dl className="building-ledger-summary-list">
        {items.map((item) => {
          const { label, value } = splitLedgerItem(item);
          return (
            <div className="building-ledger-summary-row" key={item}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

function ListCard({ title, icon, items }: { title: string; icon: Parameters<typeof Icon>[0]["name"]; items: string[] }) {
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

function visibleItems(items: string[]) {
  return items
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => !looksLikeInternalStatus(item));
}

function splitLedgerItem(item: string) {
  const dividerIndex = item.indexOf(":");
  if (dividerIndex < 0) {
    return { label: "확인 항목", value: item };
  }
  const label = item.slice(0, dividerIndex).trim();
  const value = item.slice(dividerIndex + 1).trim();
  return { label: label || "확인 항목", value: value || "-" };
}

function looksLikeInternalStatus(item: string) {
  return /\b(active|conditional_if_planned|needs_address_normalization|not_run|skipped|missing_index)\b/.test(item)
    || /:\s*[a-z]+(?:_[a-z]+)+\b/.test(item);
}
