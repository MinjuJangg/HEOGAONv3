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

export function progressFor(stage: string) {
  const stages = [
    { key: "intake", label: "정보 수집" },
    { key: "diagnosis", label: "확인 결과" },
    { key: "documents", label: "서류" },
    { key: "dashboard", label: "진행 현황" },
    { key: "submitted", label: "제출 완료" },
  ];
  const order = stages.map((item) => item.key);
  const labels: Record<string, string> = Object.fromEntries(stages.map((item) => [item.key, item.label]));
  const index = Math.max(0, order.indexOf(stage));

  return {
    width: `${Math.min(100, ((index + 1) / order.length) * 100)}%`,
    label: labels[stage] || "정보 수집",
    current: index + 1,
    total: stages.length,
    stages,
  };
}
