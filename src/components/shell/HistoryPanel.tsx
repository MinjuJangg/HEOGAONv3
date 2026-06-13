"use client";

import { useEffect } from "react";
import { Icon } from "@/components/common/Icon";
import type { ApiEnvelope, FlowActionId } from "@/types/flow";
import { FLOW_STAGES, stageForView } from "@/lib/viewState";

// Shared single source of truth so the stepper labels match the header progress bar.
const stageItems = FLOW_STAGES;

export function HistoryPanel({
  open,
  envelope,
  onClose,
  onAction,
}: {
  open: boolean;
  envelope: ApiEnvelope | null;
  onClose: () => void;
  onAction: (actionId: FlowActionId) => void;
}) {
  const answers = envelope?.statePatch.answers || [];
  const documents = envelope?.statePatch.documents || [];
  const completedDocumentIds = envelope?.statePatch.completedDocumentIds || [];
  const questionLoop = envelope?.statePatch.questionLoop;
  const pendingDocuments = documents.filter((document) => !completedDocumentIds.includes(document.id));
  const currentStage = stageForView(envelope?.view?.type, envelope?.caseState.progressStage || "intake");
  const currentStageIndex = Math.max(0, stageItems.findIndex((item) => item.key === currentStage));
  const currentStageLabel = stageItems[currentStageIndex]?.label || "정보 수집";
  const currentViewTitle = envelope?.view.title || "진행 중인 케이스";
  const totalAsked = questionLoop?.totalAsked || answers.length;
  const maxQuestions = questionLoop?.maxTotalQuestions || 10;
  const nextFocus = focusText(envelope);
  const recentAnswers = answers.slice(-4).reverse();

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  return (
    <div
      className={`history-panel${open ? " open" : ""}`}
      aria-hidden={!open}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="history-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="history-title"
      >
        <span className="history-grabber" aria-hidden="true" />
        <div className="history-head">
          <div>
            <p className="history-eyebrow">진행 상황</p>
            <h2 className="history-title" id="history-title">히스토리</h2>
          </div>
          <button className="icon-button" type="button" aria-label="닫기" onClick={onClose}>
            <Icon name="close" />
          </button>
        </div>

        <div className="history-body">
          <section className="history-dashboard">
            <div className="history-overview">
              <div className="history-current-row">
                <span className="history-current-icon" aria-hidden="true"><Icon name={iconForStage(currentStage)} /></span>
                <div className="history-current-main">
                  <p className="history-current-label">현재 단계</p>
                  <h3 className="history-current-title">{currentStageLabel} · {currentViewTitle}</h3>
                  <p className="history-summary">{nextFocus}</p>
                </div>
              </div>

              <ol className="history-stage-list" aria-label="진행 단계">
                {stageItems.map((stage, index) => (
                  <li
                    className={`history-stage${index < currentStageIndex ? " is-done" : ""}${index === currentStageIndex ? " is-current" : ""}`}
                    key={stage.key}
                  >
                    <span className="history-stage-dot" aria-hidden="true" />
                    <span className="history-stage-label">{stage.label}</span>
                  </li>
                ))}
              </ol>

              <div className="history-metrics" aria-label="진행 요약">
                <Metric value={`${totalAsked}/${maxQuestions}`} label="질문" />
                <Metric value={`${completedDocumentIds.length}/${documents.length || 0}`} label="서류" />
              </div>
            </div>

            <section className="history-section">
              <div className="history-section-head">
                <h3 className="history-section-title">지금 할 일</h3>
                <span className="history-section-count">{nextActionCount(envelope, pendingDocuments.length)}개</span>
              </div>
              <ul className="history-task-list">
                <TaskRow
                  icon={iconForStage(currentStage)}
                  title={currentViewTitle}
                  meta={nextFocus}
                  status="현재"
                  accent
                  onClick={onClose}
                />
                {pendingDocuments.slice(0, 2).map((document) => (
                  <TaskRow
                    icon="fileCheck"
                    title={document.title}
                    meta={`예상 소요 ${document.perceivedDuration} · ${document.reason}`}
                    status="서류"
                    key={document.id}
                    onClick={() => onAction("documents")}
                  />
                ))}
              </ul>
            </section>

            <section className="history-section">
              <div className="history-section-head">
                <h3 className="history-section-title">최근 답변</h3>
                <span className="history-section-count">{answers.length}개</span>
              </div>
              <ul className="history-list">
                {recentAnswers.length ? recentAnswers.map((answer) => (
                  <li className="history-item" key={answer.id}>
                    <span>
                      <span className="history-question">{answer.question}</span>
                      <span className="history-answer">{answer.answer}</span>
                    </span>
                    <span className="history-item-chevron" aria-hidden="true"><Icon name="check" /></span>
                  </li>
                )) : (
                  <li className="history-empty">
                    <span>아직 답변이 없어요.</span>
                    <span className="history-item-chevron" aria-hidden="true"><Icon name="edit" /></span>
                  </li>
                )}
              </ul>
            </section>
          </section>
        </div>
        <div className="history-return-bar">
          <button className="history-return-button" type="button" onClick={onClose}>
            <span className="history-return-icon" aria-hidden="true"><Icon name={iconForStage(currentStage)} /></span>
            <span>{resumeLabel(envelope)}</span>
          </button>
        </div>
      </section>
    </div>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <span className="history-metric">
      <span className="history-metric-value">{value}</span>
      <span className="history-metric-label">{label}</span>
    </span>
  );
}

function TaskRow({
  icon,
  title,
  meta,
  status,
  accent,
  onClick,
}: {
  icon: "edit" | "fileCheck" | "list" | "message" | "search" | "check";
  title: string;
  meta: string;
  status: string;
  accent?: boolean;
  onClick?: () => void;
}) {
  const content = (
    <>
      <span className="history-task-icon" aria-hidden="true"><Icon name={icon} /></span>
      <span className="history-task-main">
        <span className="history-task-title">{title}</span>
        <span className="history-task-meta">{meta}</span>
      </span>
      <span className="history-task-status">{status}</span>
    </>
  );

  if (onClick) {
    return (
      <li>
        <button className={`history-task-item history-task-button${accent ? " history-task-item--new" : ""}`} type="button" onClick={onClick}>
          {content}
        </button>
      </li>
    );
  }

  return (
    <li className={`history-task-item${accent ? " history-task-item--new" : ""}`}>
      {content}
    </li>
  );
}

function iconForStage(stage: string): "edit" | "fileCheck" | "list" | "message" | "search" | "check" {
  if (stage === "diagnosis") return "search";
  if (stage === "review") return "check";
  if (stage === "documents") return "fileCheck";
  if (stage === "dashboard") return "list";
  if (stage === "submitted") return "check";
  return "edit";
}

function focusText(envelope: ApiEnvelope | null) {
  const view = envelope?.view;
  if (!view) return "가게 준비 내용을 입력해 주세요.";
  if (view.type === "slot_question") return "답하면 다음 질문으로 이어갈게요.";
  if (view.type === "diagnosis") return "결과를 확인하고 서류로 넘어가세요.";
  if (view.type === "understanding_review") return "이해한 내용이 맞는지 확인하세요.";
  if (view.type === "documents") return "완료한 서류를 체크하세요.";
  if (view.type === "dashboard") return "남은 일을 한눈에 볼 수 있어요.";
  return "제출 완료 상태예요.";
}

function resumeLabel(envelope: ApiEnvelope | null) {
  const view = envelope?.view;
  if (!view) return "입력으로 돌아가기";
  if (view.type === "slot_question") return "질문으로 돌아가기";
  if (view.type === "diagnosis") return "결과로 돌아가기";
  if (view.type === "understanding_review") return "확인 화면으로 돌아가기";
  if (view.type === "documents") return "서류로 돌아가기";
  if (view.type === "dashboard") return "진행 상황으로 돌아가기";
  return "제출 현황으로 돌아가기";
}

function nextActionCount(envelope: ApiEnvelope | null, pendingDocumentCount: number) {
  const hasCurrentView = envelope?.view ? 1 : 0;
  return hasCurrentView + Math.min(2, pendingDocumentCount);
}
