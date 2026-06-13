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
  const documentPhases = buildDocumentPhases(view.documents);

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
              <h3 className="document-prep-group-title">준비 트랙</h3>
              <span className="document-prep-group-count">{documentPhases.length}단계 · {view.documents.length}개</span>
            </div>
            <div className="document-phase-list">
              {documentPhases.map((phase) => (
                <section className="document-phase" key={phase.id}>
                  <div className="document-phase-head">
                    <span className="document-phase-title">{phase.title}</span>
                    <span className="document-phase-note">{phase.tracks.length > 1 ? "동시에 진행 가능" : "순서 진행"}</span>
                  </div>
                  <div className="document-track-list">
                    {phase.tracks.map((track) => (
                      <section className="document-track-card" key={track.id}>
                        <div className="document-track-head">
                          <h4 className="document-track-title">{track.title}</h4>
                          <span className="document-track-count">{track.documents.length}개</span>
                        </div>
                        {track.description ? <p className="document-track-desc">{track.description}</p> : null}
                        <ul className="document-prep-list document-prep-list--track">
                          {track.documents.map((document) => (
                            <DocumentPrepItem
                              document={document}
                              checked={completedDocumentIds.includes(document.id)}
                              key={document.id}
                              onOpenDocument={onOpenDocument}
                              onToggleDocument={onToggleDocument}
                            />
                          ))}
                        </ul>
                      </section>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </section>
        </section>
      </div>
      {activeDocument ? <DocumentDetail document={activeDocument} onClose={onCloseDocument} /> : null}
    </>
  );
}

interface DocumentPhaseGroup {
  id: string;
  phase: number;
  title: string;
  tracks: DocumentTrackGroup[];
}

interface DocumentTrackGroup {
  id: string;
  title: string;
  description: string;
  documents: DocumentItem[];
}

function DocumentPrepItem({
  document,
  checked,
  onToggleDocument,
  onOpenDocument,
}: {
  document: DocumentItem;
  checked: boolean;
  onToggleDocument: (documentId: string, completed: boolean) => void;
  onOpenDocument: (document: DocumentItem) => void;
}) {
  const metaLine = [
    document.issuer ? `발급처 ${document.issuer}` : null,
    document.submitTo ? `제출처 ${document.submitTo}` : null,
  ].filter(Boolean).join(" · ");
  const prerequisitePreview = document.blockingPrerequisites?.slice(0, 3).join(", ");

  return (
    <li
      className={`document-prep-item${checked ? " is-complete" : ""}`}
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
}

function buildDocumentPhases(documents: DocumentItem[]): DocumentPhaseGroup[] {
  const phaseMap = new Map<number, DocumentPhaseGroup>();
  const sorted = [...documents].sort((left, right) => left.priority - right.priority);

  for (const document of sorted) {
    const phase = document.phase || fallbackPhase(document);
    const phaseTitle = document.phaseTitle || fallbackPhaseTitle(phase);
    const trackId = document.trackId || fallbackTrackId(document);
    const trackTitle = document.trackTitle || fallbackTrackTitle(trackId);
    const trackDescription = document.trackDescription || fallbackTrackDescription(trackId);

    if (!phaseMap.has(phase)) {
      phaseMap.set(phase, {
        id: `phase-${phase}`,
        phase,
        title: `${phase}단계 · ${phaseTitle}`,
        tracks: [],
      });
    }

    const phaseGroup = phaseMap.get(phase)!;
    let track = phaseGroup.tracks.find((item) => item.id === trackId);
    if (!track) {
      track = {
        id: trackId,
        title: trackTitle,
        description: trackDescription,
        documents: [],
      };
      phaseGroup.tracks.push(track);
    }
    track.documents.push(document);
  }

  return [...phaseMap.values()].sort((left, right) => left.phase - right.phase);
}

function fallbackPhase(document: DocumentItem) {
  if (/사업자등록/.test(document.title)) return 3;
  if (/영업신고|간판|옥외광고|도로점용/.test(document.title)) return 2;
  return 1;
}

function fallbackPhaseTitle(phase: number) {
  if (phase === 3) return "이후 등록";
  if (phase === 2) return "영업신고";
  return "동시 준비";
}

function fallbackTrackId(document: DocumentItem) {
  if (/사업자등록/.test(document.title)) return "after-registration";
  if (/영업신고/.test(document.title)) return "food-report";
  if (/간판|옥외광고|도로점용/.test(document.title)) return "extra-permits";
  if (/소방|안전시설|가스|LPG/i.test(document.title)) return "facility-check";
  if (/위생교육|건강진단|보건증/.test(document.title)) return "health-hygiene";
  return "basic-proof";
}

function fallbackTrackTitle(trackId: string) {
  return {
    "after-registration": "후속 등록",
    "food-report": "영업신고 접수",
    "extra-permits": "간판·외부공간",
    "facility-check": "시설 조건",
    "health-hygiene": "보건·위생",
    "basic-proof": "기본 증빙",
  }[trackId] || "준비 서류";
}

function fallbackTrackDescription(trackId: string) {
  return {
    "after-registration": "영업신고증을 받은 뒤 진행해요.",
    "food-report": "선행 서류를 모아서 접수하고 신고증을 받아요.",
    "extra-permits": "설치나 외부 사용 전에 별도 신고 여부를 확인해요.",
    "facility-check": "면적, 층수, 설비 조건에 따라 필요 여부가 갈려요.",
    "health-hygiene": "영업신고 전에 미리 준비할 수 있어요.",
    "basic-proof": "영업장 사용 권한과 본인 확인 자료를 먼저 정리해요.",
  }[trackId] || "";
}

function DocumentDetail({ document, onClose }: { document: DocumentItem; onClose: () => void }) {
  const blockers = document.blockingPrerequisites ?? [];
  const prepareInfo = (document.prepareInfo ?? []).filter((field) => {
    if (!field || field === document.title || field === document.reason) return false;
    return !["영업신고 전에 준비해야 하는 서류", "조건에 해당하면 준비해야 하는 서류", "앞 단계가 끝난 뒤 진행하는 서류"].includes(field);
  });
  const officialLinks = document.officialLinks?.filter((link) => link.url) ?? [];

  return (
    <div className="document-detail-overlay" data-document-detail-overlay onClick={(event) => event.target === event.currentTarget && onClose()}>
      <section className="document-detail-sheet" role="dialog" aria-modal="true" aria-labelledby="documentDetailTitle">
        <div className="document-detail-head">
          <div>
            <span className="document-detail-kicker">서류</span>
            <h3 className="document-detail-title" id="documentDetailTitle">{document.title}</h3>
            {document.issueChannel ? <p className="document-detail-desc">{document.issueChannel}</p> : null}
          </div>
          <button className="document-detail-close" type="button" aria-label="닫기" onClick={onClose}>×</button>
        </div>
        <div className="document-detail-meta-grid">
          <DetailMetaCard
            label="발급처"
            value={document.issuer || "해당 발급기관 확인 필요"}
            url={document.issuerUrl}
            linkLabel={document.issuerLinkLabel || "발급처 보기"}
          />
          <DetailMetaCard
            label="제출처"
            value={document.submitTo || "관할 담당부서 확인 필요"}
            url={document.submitUrl}
            linkLabel={document.submitLinkLabel || "제출처 보기"}
          />
          <DetailMetaCard label="제출 시점" value={document.submissionPhase || "제출 전 확인"} />
        </div>
        {blockers.length ? (
          <div className="document-detail-section">
            <span className="document-detail-label">제출 전 먼저 필요한 것</span>
            <ul className="document-detail-fields document-detail-fields-list">
              {blockers.map((item) => <li className="document-detail-field" key={item}>{item}</li>)}
            </ul>
          </div>
        ) : null}
        {document.dependencyNote ? <p className="document-detail-note">{document.dependencyNote}</p> : null}
        {prepareInfo.length ? (
          <div className="document-detail-section">
            <span className="document-detail-label">준비 체크</span>
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
}: {
  label: string;
  value: string;
  url?: string;
  linkLabel?: string;
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
    </div>
  );
}
