import { Icon } from "@/components/common/Icon";
import { BrandLogo } from "@/components/shell/BrandLogo";
import type { SimpleView } from "@/types/flow";

export function SubmittedView({ view }: { view: SimpleView }) {
  const completionRate = view.completionRate ?? 100;
  const statusCards = view.statusCards?.length ? view.statusCards : [
    { label: "서류", value: "완료" },
    { label: "진행률", value: `${completionRate}%` },
  ];
  const submittedDocuments = view.submittedDocuments?.length ? view.submittedDocuments : [
    { id: "building-ledger", title: "건축물대장 확인", statusLabel: "완료", meta: "우선순위 1" },
    { id: "health-check", title: "건강진단결과서", statusLabel: "완료", meta: "우선순위 3" },
    { id: "hygiene-education", title: "위생교육 수료증", statusLabel: "완료", meta: "우선순위 5" },
  ];
  const nextNotes = view.nextNotes?.length ? view.nextNotes : [
    "접수번호나 방문 기록은 따로 보관하세요.",
    "추가 연락이 오면 진행 상황에 기록하세요.",
  ];

  return (
    <div className="submitted-ending" aria-labelledby="submitted-title">
      <section className="submitted-ending-hero">
        <div className="submitted-ending-brand">
          <BrandLogo />
        </div>
        <div className="submitted-ending-meter" aria-label={`제출 준비 ${completionRate}% 완료`}>
          <span>{completionRate}</span>
          <small>%</small>
        </div>
        <h1 className="submitted-ending-title" id="submitted-title">{view.title}</h1>
        <p className="submitted-ending-copy">{view.subtitle || "준비한 서류가 제출 완료 상태로 정리되었어요."}</p>
        <div className="submitted-ending-status-grid" aria-label="최종 진행 요약">
          {statusCards.map((item) => (
            <span className="submitted-ending-status-card" key={item.label}>
              <strong>{item.value}</strong>
              <small>{item.label}</small>
            </span>
          ))}
        </div>
      </section>

      <section className="submitted-ending-receipt" aria-label="제출한 서류">
        <div className="submitted-ending-receipt-head">
          <h2>제출한 서류</h2>
          <span>100% 완료</span>
        </div>
        <ul className="submitted-ending-list">
          {submittedDocuments.map((item) => (
            <li className="submitted-ending-item" key={item.id}>
              <span className="submitted-ending-item-icon" aria-hidden="true"><Icon name="fileCheck" /></span>
              <span className="submitted-ending-item-main">
                <strong>{item.title}</strong>
                <small>{item.meta}</small>
              </span>
              <span className="submitted-ending-item-status">{item.statusLabel}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="submitted-ending-note">
        <div className="submitted-ending-note-head">
          <span aria-hidden="true"><Icon name="list" /></span>
          <h2>마지막 확인</h2>
        </div>
        <ul>
          {nextNotes.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
