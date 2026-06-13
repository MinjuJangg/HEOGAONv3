import type { CSSProperties } from "react";
import { Icon } from "@/components/common/Icon";
import type { DocumentItem, DocumentsView as DocumentsViewModel } from "@/types/flow";

export function DocumentsView({
  view,
  completedDocumentIds,
  activeDocument,
  onToggleDocument,
  onOpenDocument,
  onCloseDocument,
}: {
  view: DocumentsViewModel;
  completedDocumentIds: string[];
  activeDocument: DocumentItem | null;
  onToggleDocument: (documentId: string, completed: boolean) => void;
  onOpenDocument: (document: DocumentItem) => void;
  onCloseDocument: () => void;
}) {
  const completedCount = completedDocumentIds.length;
  const totalCount = view.documents.length;
  const completionRate = totalCount ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <>
      <section className="question-card">
        <h1 className="question-title">{view.title}</h1>
      </section>
      <div className="summary-view">
        <section className="summary-review document-prep">
          <div className="document-prep-overview" aria-label="서류 준비 요약">
            <div className="document-prep-meter-head">
              <span className="document-prep-meter-title">준비한 서류</span>
              <span className="document-prep-meter-count">{completedCount}/{totalCount}</span>
            </div>
            <div className="document-prep-meter-track" aria-hidden="true">
              <span className="document-prep-meter-fill" style={{ "--document-progress": `${completionRate}%` } as CSSProperties} />
            </div>
            <span className="document-prep-meter-note">{totalCount - completedCount > 0 ? `${totalCount - completedCount}개 남았어요.` : "서류 준비 완료"}</span>
          </div>
          <section className="document-prep-group">
            <div className="document-prep-group-head">
              <h3 className="document-prep-group-title">준비 순서</h3>
              <span className="document-prep-group-count">{view.documents.length}개</span>
            </div>
            <ul className="document-prep-list">
              {view.documents.map((document) => {
                const checked = completedDocumentIds.includes(document.id);
                const metaLine = [
                  document.issuer ? `발급처 ${document.issuer}` : null,
                  document.submitTo ? `제출처 ${document.submitTo}` : null,
                ].filter(Boolean).join(" · ");
                const prerequisitePreview = document.blockingPrerequisites?.slice(0, 3).join(", ");
                return (
                  <li
                    className={`document-prep-item${checked ? " is-complete" : ""}`}
                    key={document.id}
                    onClick={(event) => {
                      if ((event.target as HTMLElement).closest("label,input")) return;
                      onOpenDocument(document);
                    }}
                  >
                    <label className={`document-prep-check${checked ? " is-checked" : ""}`}>
                      <input
                        className="document-prep-check-input"
                        type="checkbox"
                        checked={checked}
                        aria-label={`${document.title} 완료`}
                        onChange={(event) => onToggleDocument(document.id, event.target.checked)}
                      />
                    </label>
                    <button className="document-prep-main" type="button" onClick={() => onOpenDocument(document)}>
                      <span className="document-prep-title-row">
                        <span className="document-prep-title-main">
                          <span className="document-prep-rank">{document.priority}</span>
                          <span className="document-prep-title">{document.title}</span>
                        </span>
                        <span className="document-prep-link">자세히 <Icon name="arrowRight" size={14} /></span>
                      </span>
                      <span className="document-prep-text">예상 소요 {document.perceivedDuration}</span>
                      {metaLine ? <span className="document-prep-meta">{metaLine}</span> : null}
                      {prerequisitePreview ? <span className="document-prep-meta">먼저 필요: {prerequisitePreview}</span> : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        </section>
      </div>
      {activeDocument ? <DocumentDetail document={activeDocument} onClose={onCloseDocument} /> : null}
    </>
  );
}

function DocumentDetail({ document, onClose }: { document: DocumentItem; onClose: () => void }) {
  const blockers = document.blockingPrerequisites ?? [];

  return (
    <div className="document-detail-overlay" data-document-detail-overlay onClick={(event) => event.target === event.currentTarget && onClose()}>
      <section className="document-detail-sheet" role="dialog" aria-modal="true" aria-labelledby="documentDetailTitle">
        <div className="document-detail-head">
          <div>
            <span className="document-detail-kicker">서류</span>
            <h3 className="document-detail-title" id="documentDetailTitle">{document.title}</h3>
            <p className="document-detail-desc">{document.reason}</p>
          </div>
          <button className="document-detail-close" type="button" aria-label="닫기" onClick={onClose}>×</button>
        </div>
        <ul className="document-detail-steps" aria-label={`${document.title} 확인 순서`}>
          {document.steps.map((step, index) => (
            <li className="document-detail-step" key={step}>
              <span className="document-detail-step-mark">{index + 1}</span>
              <span>
                <span className="document-detail-step-title">{step}</span>
                <span className="document-detail-step-text">{index === 0 ? document.prerequisites : index === 1 ? `예상 소요 ${document.perceivedDuration}` : document.unlocks}</span>
              </span>
            </li>
          ))}
        </ul>
        <div className="document-detail-meta-grid">
          <div className="document-detail-meta-card">
            <span className="document-detail-label">발급처</span>
            <span className="document-detail-meta-text">{document.issuer || "해당 발급기관 확인 필요"}</span>
          </div>
          <div className="document-detail-meta-card">
            <span className="document-detail-label">제출처</span>
            <span className="document-detail-meta-text">{document.submitTo || "관할 담당부서 확인 필요"}</span>
          </div>
          <div className="document-detail-meta-card">
            <span className="document-detail-label">제출 시점</span>
            <span className="document-detail-meta-text">{document.submissionPhase || "제출 전 확인"}</span>
          </div>
        </div>
        {blockers.length ? (
          <div className="document-detail-section">
            <span className="document-detail-label">제출 전 먼저 필요한 것</span>
            <ul className="document-detail-fields document-detail-fields-list">
              {blockers.map((item) => <li className="document-detail-field" key={item}>{item}</li>)}
            </ul>
          </div>
        ) : null}
        {document.graphPrerequisites ? (
          <p className="document-detail-note">그래프 기준 선행관계: {document.graphPrerequisites}</p>
        ) : null}
        {document.dependencyNote ? <p className="document-detail-note">{document.dependencyNote}</p> : null}
        <div className="document-detail-section">
          <span className="document-detail-label">필요한 정보</span>
          <ul className="document-detail-fields">
            {document.prepareInfo.map((field) => <li className="document-detail-field" key={field}>{field}</li>)}
          </ul>
        </div>
        <div className="document-detail-actions">
          <a className="document-detail-site" href={document.officialLinks[0]?.url || "https://www.gov.kr"} target="_blank" rel="noreferrer">
            <span className="document-detail-site-icon" aria-hidden="true"><Icon name="building2" /></span>
            <span className="document-detail-site-main">
              <span className="document-detail-site-kicker">공식 사이트</span>
              <span className="document-detail-site-title">{document.officialLinks[0]?.label || "정부24"}</span>
              <span className="document-detail-site-meta">문의 전 준비: {document.canPrepareBeforeInquiry ? "가능" : "확인 필요"}</span>
              <span className="document-detail-link">열기 <Icon name="arrowRight" size={16} /></span>
            </span>
          </a>
        </div>
      </section>
    </div>
  );
}
