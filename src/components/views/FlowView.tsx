import { AddressSearchView } from "@/components/views/AddressSearchView";
import { DashboardView } from "@/components/views/DashboardView";
import { DiagnosisView } from "@/components/views/DiagnosisView";
import { DocumentsView } from "@/components/views/DocumentsView";
import { SlotQuestionView } from "@/components/views/SlotQuestionView";
import { SubmittedView } from "@/components/views/SubmittedView";
import { UnderstandingReviewView } from "@/components/views/UnderstandingReviewView";
import type { BuildingLedgerRaw, ResolvedAddress } from "@/lib/address";
import type { ApiView, DocumentItem, FlowActionId } from "@/types/flow";

const ADDRESS_FIELD = "exact_address";

export function FlowView({
  view,
  selectedIds,
  freeText,
  activeDocument,
  completedDocumentIds,
  documents,
  onSelectIds,
  onFreeText,
  onUnknown,
  onToggleDocument,
  onOpenDocument,
  onCloseDocument,
  onDashboardContinue,
  onDashboardAction,
  onAction,
  onAddressResolved,
  onAddressClear,
  dashboardContinueDisabled,
}: {
  view: ApiView;
  selectedIds: string[];
  freeText: string;
  activeDocument: DocumentItem | null;
  completedDocumentIds: string[];
  documents: DocumentItem[];
  onSelectIds: (ids: string[]) => void;
  onFreeText: (value: string) => void;
  onUnknown: () => void;
  onToggleDocument: (documentId: string, completed: boolean) => void;
  onOpenDocument: (document: DocumentItem) => void;
  onCloseDocument: () => void;
  onDashboardContinue: () => void;
  onDashboardAction: (actionId: FlowActionId) => void;
  onAction: (actionId: FlowActionId) => void;
  onAddressResolved: (address: ResolvedAddress, building: BuildingLedgerRaw | null) => void;
  onAddressClear: () => void;
  dashboardContinueDisabled: boolean;
}) {
  if (view.type === "slot_question") {
    if (view.field === ADDRESS_FIELD) {
      return <AddressSearchView view={view} onResolved={onAddressResolved} onClear={onAddressClear} onUnknown={onUnknown} />;
    }
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
  if (view.type === "understanding_review") return <UnderstandingReviewView view={view} onEdit={() => onAction("edit_understanding")} />;

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
    return <DashboardView view={view} documents={documents} completedDocumentIds={completedDocumentIds} onContinue={onDashboardContinue} onAction={onDashboardAction} continueDisabled={dashboardContinueDisabled} />;
  }
  if (view.type === "submitted") return <SubmittedView view={view} />;
  return null;
}
