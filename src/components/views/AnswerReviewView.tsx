import { ListSection } from "@/components/common/ListSection";
import type { AnswerReviewView as AnswerReviewViewModel } from "@/types/flow";

export function AnswerReviewView({ view }: { view: AnswerReviewViewModel }) {
  const analysis = view.analysis;

  return (
    <>
      <section className="question-card">
        <h1 className="question-title">{view.title}</h1>
        <p className="question-sub">{analysis.answerSummary || "받은 답변을 저장했어요."}</p>
      </section>
      <div className="summary-view">
        <ListSection title="해결됨" icon="check" items={analysis.resolvedItems || []} empty="아직 해결된 항목이 없어요." />
        <ListSection title="새로 확인할 것" icon="search" items={analysis.newMissingFields || []} empty="새 질문은 없어요." />
        <ListSection title="새 문의" icon="message" items={(analysis.newInquiryTasks || []).map((task) => task.title)} empty="새 문의는 없어요." />
      </div>
    </>
  );
}
