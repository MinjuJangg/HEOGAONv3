import { useEffect, useMemo, useRef, type CSSProperties } from "react";
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
  const sortedDocuments = [...view.documents].sort((a, b) => a.priority - b.priority);
  const trackGroups = groupDocumentsByTrack(sortedDocuments);
  const titleById = new Map(view.documents.map((document) => [document.id, document.title]));
  const completedCount = completedDocumentIds.length;
  const totalCount = view.documents.length;
  const completionRate = totalCount ? Math.round((completedCount / totalCount) * 100) : 0;
  const firstCurrentId = sortedDocuments.find((document) => {
    const completed = completedDocumentIds.includes(document.id);
    const locked = !completed && blockingTitlesFor(document, completedDocumentIds, titleById).length > 0;
    return !completed && !locked;
  })?.id;
  const activeBlockingTitles = activeDocument ? blockingTitlesFor(activeDocument, completedDocumentIds, titleById) : [];
  const completedKey = useMemo(() => [...completedDocumentIds].sort().join("|"), [completedDocumentIds]);
  const didMountRef = useRef(false);
  const previousCompletedKeyRef = useRef(completedKey);

  useEffect(() => {
    if (!didMountRef.current) {
      didMountRef.current = true;
      previousCompletedKeyRef.current = completedKey;
      return;
    }

    if (previousCompletedKeyRef.current === completedKey) return;
    previousCompletedKeyRef.current = completedKey;
    if (!firstCurrentId) return;

    const target = document.querySelector<HTMLElement>(`[data-document-id="${CSS.escape(firstCurrentId)}"]`);
    window.setTimeout(() => {
      target?.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    }, 80);
  }, [completedKey, firstCurrentId]);

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
            <div className="document-track-list">
              {trackGroups.map((group) => (
                <section className="document-track-group" key={group.id}>
                  <div className="document-track-head">
                    <h4 className="document-track-title">{group.title}</h4>
                    {group.description ? <p className="document-track-desc">{group.description}</p> : null}
                  </div>
                  <ol className="document-timeline">
                    {group.documents.map((document) => {
                      const completed = completedDocumentIds.includes(document.id);
                      const blockingTitles = blockingTitlesFor(document, completedDocumentIds, titleById);
                      const locked = !completed && blockingTitles.length > 0;
                      const current = document.id === firstCurrentId;
                      const stateClass = completed ? " is-done" : current ? " is-current" : locked ? " is-locked" : "";
                      return (
                        <li className={`document-timeline-item${stateClass}`} data-document-id={document.id} key={document.id}>
                          <span className="document-timeline-rail" aria-hidden="true">
                            <span className="document-timeline-marker">
                              {completed ? <Icon name="check" size={14} /> : locked ? <Icon name="lock" size={14} /> : document.priority}
                            </span>
                          </span>
                          <button className="document-timeline-body" type="button" onClick={() => onOpenDocument(document)}>
                            <span className="document-timeline-head">
                              <span className="document-timeline-title">{document.title}</span>
                              {current ? <span className="document-timeline-badge">지금 작성</span> : null}
                            </span>
                            <span className="document-timeline-meta">예상 소요 {document.perceivedDuration}</span>
                            {locked ? (
                              <span className="document-timeline-lock">{blockingTitles.join(" · ")} 완료 후 작성할 수 있어요</span>
                            ) : (
                              <span className="document-timeline-link">자세히 <Icon name="arrowRight" size={14} /></span>
                            )}
                          </button>
                          {!locked ? (
                            <label className={`document-prep-check${completed ? " is-checked" : ""}`}>
                              <input
                                className="document-prep-check-input"
                                type="checkbox"
                                checked={completed}
                                aria-label={`${document.title} 완료 표시`}
                                onChange={(event) => onToggleDocument(document.id, event.target.checked)}
                              />
                            </label>
                          ) : null}
                        </li>
                      );
                    })}
                  </ol>
                </section>
              ))}
            </div>
          </section>
        </section>
      </div>
      {activeDocument ? (
        <DocumentDetail
          document={activeDocument}
          blockingTitles={activeBlockingTitles}
          onClose={onCloseDocument}
        />
      ) : null}
    </>
  );
}

function blockingTitlesFor(
  document: DocumentItem,
  completedDocumentIds: string[],
  titleById: Map<string, string>,
) {
  return (document.dependsOn ?? [])
    .filter((id) => !completedDocumentIds.includes(id))
    .map((id) => titleById.get(id) || id);
}

function groupDocumentsByTrack(documents: DocumentItem[]) {
  const groups: Array<{
    id: string;
    title: string;
    description: string;
    phase: number;
    phaseTitle: string;
    documents: DocumentItem[];
  }> = [];
  const groupById = new Map<string, (typeof groups)[number]>();

  documents.forEach((document) => {
    const phase = document.phase ?? 1;
    const title = document.trackTitle || document.phaseTitle || "서류 준비";
    const id = `${phase}-${document.trackId || title}`;
    const existing = groupById.get(id);
    if (existing) {
      existing.documents.push(document);
      return;
    }

    const group = {
      id,
      title,
      description: document.trackDescription || "",
      phase,
      phaseTitle: document.phaseTitle || `${phase}단계`,
      documents: [document],
    };
    groups.push(group);
    groupById.set(id, group);
  });

  return groups.sort((a, b) => a.phase - b.phase || documents.indexOf(a.documents[0]) - documents.indexOf(b.documents[0]));
}

function DocumentDetail({
  document,
  blockingTitles,
  onClose,
}: {
  document: DocumentItem;
  blockingTitles: string[];
  onClose: () => void;
}) {
  const blockers = document.blockingPrerequisites ?? [];
  const officialLinks = document.officialLinks ?? [];
  const prepareInfo = document.prepareInfo ?? [];

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
        {blockingTitles.length ? (
          <div className="document-detail-lock">
            <Icon name="lock" size={16} />
            <span>{blockingTitles.join(", ")} 완료 후 작성할 수 있어요</span>
          </div>
        ) : null}
        {document.trackTitle || document.phaseTitle ? (
          <p className="document-detail-note">
            {document.phaseTitle ? `${document.phaseTitle} · ` : ""}{document.trackTitle || "서류 준비"}
            {document.trackDescription ? `: ${document.trackDescription}` : ""}
          </p>
        ) : null}
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
          <DetailMetaCard
            label="발급처"
            value={document.issuer || "해당 발급기관 확인 필요"}
            url={document.issuerUrl}
            linkLabel={document.issuerLinkLabel}
            note={document.issuerNote}
          />
          <DetailMetaCard
            label="제출처"
            value={document.submitTo || "관할 담당부서 확인 필요"}
            url={document.submitUrl}
            linkLabel={document.submitLinkLabel}
          />
          <DetailMetaCard label="제출 시점" value={document.submissionPhase || "제출 전 확인"} />
          {document.issueChannel ? <DetailMetaCard label="준비 방식" value={document.issueChannel} /> : null}
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
        {prepareInfo.length ? (
          <div className="document-detail-section">
            <span className="document-detail-label">필요한 정보</span>
            <ul className="document-detail-fields">
              {prepareInfo.map((field) => <li className="document-detail-field" key={field}>{field}</li>)}
            </ul>
          </div>
        ) : null}
        {officialLinks.length ? (
          <div className="document-detail-actions">
            {officialLinks.map((link) => (
              <a className="document-detail-site" href={link.url} target="_blank" rel="noreferrer" key={`${link.label}-${link.url}`}>
                <span className="document-detail-site-icon" aria-hidden="true"><Icon name="building2" /></span>
                <span className="document-detail-site-main">
                  <span className="document-detail-site-kicker">관련 링크</span>
                  <span className="document-detail-site-title">{link.label}</span>
                  <span className="document-detail-site-meta">서류 준비 {document.canPrepareBeforeInquiry ? "가능" : "확인 필요"}</span>
                  <span className="document-detail-link">열기 <Icon name="arrowRight" size={16} /></span>
                </span>
              </a>
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function DetailMetaCard({
  label,
  value,
  url,
  linkLabel,
  note,
}: {
  label: string;
  value: string;
  url?: string;
  linkLabel?: string;
  note?: string;
}) {
  return (
    <div className="document-detail-meta-card">
      <span className="document-detail-label">{label}</span>
      {url ? (
        <a className="document-detail-meta-link" href={url} target="_blank" rel="noreferrer">
          <span>{value}</span>
          <span className="document-detail-meta-link-action">{linkLabel || "열기"} <Icon name="arrowRight" size={14} /></span>
        </a>
      ) : (
        <span className="document-detail-meta-text">{value}</span>
      )}
      {note ? <span className="document-detail-meta-note">{note}</span> : null}
    </div>
  );
}
