import { DashboardView } from "@/components/views/DashboardView";
import { DiagnosisView } from "@/components/views/DiagnosisView";
import { DocumentsView } from "@/components/views/DocumentsView";
import { SlotQuestionView } from "@/components/views/SlotQuestionView";
import { SubmittedView } from "@/components/views/SubmittedView";
import { UnderstandingReviewView } from "@/components/views/UnderstandingReviewView";
import type { ApiView, DocumentItem, FlowActionId } from "@/types/flow";

export function FlowView({
  view,
  selectedIds,
  freeText,
  activeDocument,
  completedDocumentIds,
  onSelectIds,
  onFreeText,
  onUnknown,
  onToggleDocument,
  onOpenDocument,
  onCloseDocument,
  onDashboardAction,
  onAction,
}: {
  view: ApiView;
  selectedIds: string[];
  freeText: string;
  activeDocument: DocumentItem | null;
  completedDocumentIds: string[];
  onSelectIds: (ids: string[]) => void;
  onFreeText: (value: string) => void;
  onUnknown: () => void;
  onToggleDocument: (documentId: string, completed: boolean) => void;
  onOpenDocument: (document: DocumentItem) => void;
  onCloseDocument: () => void;
  onDashboardAction: (actionId: FlowActionId) => void;
  onAction: (actionId: FlowActionId) => void;
}) {
  if (view.type === "slot_question") {
    return (
      <SlotQuestionView
        view={view}
        selectedIds={selectedIds}
        freeText={freeText}
        onSelectIds={onSelectIds}
        onFreeText={onFreeText}
        onUnknown={onUnknown}
      />
    );
  }

  if (view.type === "diagnosis") return <DiagnosisView view={view} />;
  if (view.type === "understanding_review") return <UnderstandingReviewView view={view} />;

  if (view.type === "documents") {
    return (
      <DocumentsView
        view={view}
        completedDocumentIds={completedDocumentIds}
        activeDocument={activeDocument}
        onToggleDocument={onToggleDocument}
        onOpenDocument={onOpenDocument}
        onCloseDocument={onCloseDocument}
      />
    );
  }

  if (view.type === "dashboard") {
    return <DashboardView view={view} onAction={onDashboardAction} />;
  }
  if (view.type === "submitted") return <SubmittedView view={view} />;
  return null;
}
