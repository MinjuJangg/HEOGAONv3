import { Icon } from "@/components/common/Icon";
import type { DashboardView as DashboardViewModel, DocumentItem, FlowActionId } from "@/types/flow";

export function DashboardView({
  view,
  documents,
  completedDocumentIds,
  onContinue,
  continueDisabled,
}: {
  view: DashboardViewModel;
  documents: DocumentItem[];
  completedDocumentIds: string[];
  onContinue: () => void;
  // Accepted from FlowView for API parity; the command-center layout routes
  // every row through the primary action (onContinue), so it is unused here.
  onAction: (actionId: FlowActionId) => void;
  continueDisabled: boolean;
}) {
  const sorted = [...documents].sort((a, b) => a.priority - b.priority);
  const titleById = new Map(documents.map((document) => [document.id, document.title]));
  const total = documents.length;
  const completed = completedDocumentIds.length;
  const pct = total ? Math.round((completed / total) * 100) : 0;

  const blockingTitlesFor = (document: DocumentItem) =>
    (document.dependsOn ?? [])
      .filter((id) => !completedDocumentIds.includes(id))
      .map((id) => titleById.get(id) || id);

  const remaining = sorted.filter((document) => !completedDocumentIds.includes(document.id));
  const next = remaining.find((document) => blockingTitlesFor(document).length === 0);
  const rest = remaining.filter((document) => document.id !== next?.id);
  const unknown = view.summary.unknownFields;
  const updatedNote = view.sections
    ?.flatMap((section) => section.items)
    .find((item) => item.tone === "updated");
  const remainCount = rest.length + (unknown > 0 ? 1 : 0);

  return (
    <>
      <section className="question-card dashboard-hero">
        <h1 className="question-title">{view.title}</h1>
        <div className="dash-progress" aria-label="전체 진행 현황">
          <div className="dash-progress-head">
            <span className="dash-progress-label">진행 현황</span>
            <span className="dash-progress-count">서류 {completed}/{total}</span>
          </div>
          <p className="dash-progress-pct">{pct}<small>%</small> <em>전체 진행</em></p>
          <div className="dash-progress-track" aria-hidden="true">
            <span style={{ width: `${pct}%` }} />
          </div>
        </div>
      </section>

      <div className="summary-view dashboard-view">
        <button
          className="dash-focal"
          type="button"
          onClick={onContinue}
          disabled={continueDisabled}
        >
          <span className="dash-focal-kicker">지금 할 일</span>
          {next ? (
            <>
              <span className="dash-focal-title">{next.title}</span>
              <span className="dash-focal-meta">예상 소요 {next.perceivedDuration} · 지금 작성할 수 있어요</span>
            </>
          ) : remaining.length ? (
            <>
              <span className="dash-focal-title">선행 서류를 먼저 끝내요</span>
              <span className="dash-focal-meta">앞 단계 서류를 완료하면 다음이 열려요</span>
            </>
          ) : (
            <>
              <span className="dash-focal-title">서류 준비 완료</span>
              <span className="dash-focal-meta">제출 현황을 확인해 보세요</span>
            </>
          )}
          <span className="dash-focal-cta">
            <span>{next ? "작성하러 가기" : view.nextButtonLabel}</span>
            <Icon name="arrowRight" size={18} />
          </span>
        </button>

        {remainCount > 0 ? (
          <section className="dash-remain">
            <h2 className="dash-remain-head">
              다음 할 일 <span className="dash-remain-count">{remainCount}</span>
            </h2>
            <ul className="dash-remain-list">
              {rest.map((document) => {
                const blockers = blockingTitlesFor(document);
                const locked = blockers.length > 0;
                return (
                  <li key={document.id}>
                    <button className={`dash-row${locked ? " is-locked" : ""}`} type="button" onClick={onContinue}>
                      <span className="dash-row-icon" aria-hidden="true">
                        <Icon name={locked ? "lock" : "fileCheck"} size={15} />
                      </span>
                      <span className="dash-row-main">
                        <span className="dash-row-title">{document.title}</span>
                        <span className="dash-row-meta">
                          {locked ? `선행: ${blockers.join(", ")}` : `예상 소요 ${document.perceivedDuration}`}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
              {unknown > 0 ? (
                <li>
                  <button className="dash-row dash-row--check" type="button" onClick={onContinue}>
                    <span className="dash-row-icon" aria-hidden="true"><Icon name="help" size={15} /></span>
                    <span className="dash-row-main">
                      <span className="dash-row-title">확인이 필요한 항목</span>
                      <span className="dash-row-meta">{unknown}개 더 확인하면 정확해져요</span>
                    </span>
                    <span className="dash-row-arrow">확인 <Icon name="arrowRight" size={15} /></span>
                  </button>
                </li>
              ) : null}
            </ul>
          </section>
        ) : null}

        {updatedNote ? (
          <p className="dash-update-note">· {updatedNote.description || updatedNote.title}</p>
        ) : null}
      </div>
    </>
  );
}
