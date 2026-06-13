import { Icon, iconForDecision } from "@/components/common/Icon";
import type { DecisionBlock, DiagnosisGuidance, DiagnosisView as DiagnosisViewModel } from "@/types/flow";

export function DiagnosisView({ view }: { view: DiagnosisViewModel }) {
  const guidance = view.guidance;
  const apiStatusItems = guidance?.apiStatusItems ?? [];
  const buildingItems = guidance?.buildingItems ?? [];
  const questionsToAsk = guidance?.questionsToAsk ?? [];
  const procedureSteps = guidance?.procedureSteps ?? [];
  const documentOrderItems = guidance?.documentOrderItems ?? [];
  const hasGuidance = Boolean(
    guidance
    && (
      guidance.summary
      || guidance.finalResponseDraft
      || apiStatusItems.length
      || questionsToAsk.length
    ),
  );

  return (
    <>
      <section className="question-card">
        <h1 className="question-title">{view.title}</h1>
        <p className="question-sub">{view.headline}</p>
      </section>
      <div className="summary-view">
        {hasGuidance && guidance ? <SuitabilityCard guidance={guidance} /> : null}
        {apiStatusItems.length ? (
          <ListCard title="확인 근거" icon="search" items={apiStatusItems} />
        ) : null}
        {buildingItems.length ? (
          <ListCard title="건축물대장 확인" icon="building2" items={buildingItems} />
        ) : null}
        {questionsToAsk.length ? (
          <ListCard title="추가로 물어볼 것" icon="help" items={questionsToAsk} />
        ) : null}
        {procedureSteps.length ? (
          <ListCard title="준비 순서" icon="list" items={procedureSteps} />
        ) : null}
        {documentOrderItems.length ? (
          <ListCard title="서류 준비 순서" icon="fileCheck" items={documentOrderItems} />
        ) : null}
        {view.decisionBlocks.map((block) => (
          <DecisionBlockView block={block} key={`${block.type}-${block.title}`} />
        ))}
      </div>
    </>
  );
}

function SuitabilityCard({ guidance }: { guidance: DiagnosisGuidance }) {
  return (
    <section className="summary-review">
      <div className="summary-review-title-row">
        <span aria-hidden="true"><Icon name={guidance.suitability === "blocked" ? "close" : "check"} /></span>
        <h2 className="summary-review-title">{guidance.suitabilityTitle || "적합성 판단"}</h2>
      </div>
      <p className="summary-review-subtitle">{guidance.suitabilitySummary || guidance.summary}</p>
    </section>
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

function DecisionBlockView({ block }: { block: DecisionBlock }) {
  return (
    <section className="summary-review">
      <div className="summary-review-title-row">
        <span aria-hidden="true"><Icon name={iconForDecision(block.type)} /></span>
        <h2 className="summary-review-title">{block.title}</h2>
      </div>
      <ul className="missing-summary-list">
        {block.items.map((item) => (
          <li className="missing-summary-item" key={item}>
            <span className="missing-summary-icon" aria-hidden="true"><Icon name={iconForDecision(block.type)} /></span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
