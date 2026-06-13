import type { ApiView } from "@/types/flow";

export function primaryActionState(
  view: ApiView,
  selectedIds: string[],
  freeText: string,
  pending: boolean,
  _completedDocumentIds: string[] = [],
) {
  let label = "다음";
  let disabled = pending;

  if (view.type === "slot_question") {
    label = view.nextButtonLabel;
    disabled = pending || (view.inputMode === "free_text" ? freeText.trim().length < 1 : selectedIds.length === 0);
  } else if (view.type === "documents") {
    label = view.nextButtonLabel;
    disabled = pending;
  } else {
    label = view.nextButtonLabel;
  }

  return { label: pending ? "처리 중" : label, disabled };
}

// Single source of truth for the flow's progress stages, shared by the question
// header progress bar and the history panel stepper so naming never drifts.
// Mirrors HEOGAONV3_FLOW.md: 정보 수집 → 판단 → 확인 → 서류 → 현황 → 완료.
// 판단(가능 여부 판단)과 확인(사용자 이해 확인)은 FLOW상 별개 단계이므로 분리한다.
export const FLOW_STAGES = [
  { key: "intake", label: "정보 수집" },
  { key: "diagnosis", label: "판단" },
  { key: "review", label: "확인" },
  { key: "documents", label: "서류" },
  { key: "dashboard", label: "현황" },
  { key: "submitted", label: "완료" },
] as const;

const STAGE_BY_VIEW: Record<string, string> = {
  slot_question: "intake",
  diagnosis: "diagnosis",
  understanding_review: "review",
  documents: "documents",
  dashboard: "dashboard",
  submitted: "submitted",
};

// Derive the canonical stage from the current view type (authoritative), falling
// back to the server-provided progressStage when the view type is unknown.
export function stageForView(viewType: string | undefined, fallbackStage = "intake") {
  if (viewType && STAGE_BY_VIEW[viewType]) return STAGE_BY_VIEW[viewType];
  return fallbackStage || "intake";
}

export function progressFor(stage: string) {
  const stages = FLOW_STAGES.map((item) => ({ key: item.key as string, label: item.label }));
  const order = stages.map((item) => item.key);
  const index = Math.max(0, order.indexOf(stage));

  return {
    width: `${Math.min(100, ((index + 1) / order.length) * 100)}%`,
    label: stages[index]?.label || stages[0].label,
    current: index + 1,
    total: stages.length,
    stages,
  };
}
