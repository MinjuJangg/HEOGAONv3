"use client";

import { useEffect, useState } from "react";
import { DevPanel } from "@/components/dev/DevPanel";
import { BottomBar } from "@/components/shell/BottomBar";
import { BrandLogo } from "@/components/shell/BrandLogo";
import { HistoryPanel } from "@/components/shell/HistoryPanel";
import { ProcessingOverlay } from "@/components/shell/ProcessingOverlay";
import { QuestionHeader } from "@/components/shell/QuestionHeader";
import { AnalysisLoadingScreen } from "@/components/views/AnalysisLoadingScreen";
import { FlowView } from "@/components/views/FlowView";
import { LandingScreen } from "@/components/views/LandingScreen";
import { getCase, sendTurn, startCase } from "@/lib/api";
import type { BuildingLedgerRaw, ResolvedAddress } from "@/lib/address";
import { createDevEnvelope } from "@/lib/devMocks";
import { primaryActionState, progressFor } from "@/lib/viewState";
import type { ApiEnvelope, DocumentItem, FlowActionId, TurnInput, ViewType } from "@/types/flow";

const MIN_ANALYSIS_LOADING_MS = 950;
const CASE_STORAGE_KEY = "heogaon:v2:caseId";

export function HeogaonFlowApp({ initialDevView }: { initialDevView?: ViewType | "landing" }) {
  const [splashPhase, setSplashPhase] = useState<"visible" | "hiding" | "done">(initialDevView ? "done" : "visible");
  const [envelope, setEnvelope] = useState<ApiEnvelope | null>(() => {
    if (!initialDevView || initialDevView === "landing") return null;
    return createDevEnvelope(initialDevView);
  });
  const [caseId, setCaseId] = useState<string | null>(null);
  const [inputText, setInputText] = useState("");
  const [freeText, setFreeText] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [addressResolved, setAddressResolved] = useState<ResolvedAddress | null>(null);
  const [addressBuilding, setAddressBuilding] = useState<BuildingLedgerRaw | null>(null);
  const [activeDocument, setActiveDocument] = useState<DocumentItem | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const view = envelope?.view;
  const showLanding = !view;
  const questionType = view?.type || "landing";
  const primary = view
    ? primaryActionState(view, selectedIds, freeText, pending, envelope?.statePatch.completedDocumentIds || [])
    : null;
  const progress = progressFor(envelope?.caseState.progressStage || "intake");
  const ready = splashPhase === "done";
  const showDevPanel = process.env.NODE_ENV === "development";

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const hideDelay = prefersReducedMotion ? 180 : 880;
    const doneDelay = prefersReducedMotion ? 260 : 1180;
    const hideTimer = window.setTimeout(() => setSplashPhase("hiding"), hideDelay);
    const doneTimer = window.setTimeout(() => setSplashPhase("done"), doneDelay);

    return () => {
      window.clearTimeout(hideTimer);
      window.clearTimeout(doneTimer);
    };
  }, []);

  useEffect(() => {
    const savedCaseId = window.localStorage.getItem(CASE_STORAGE_KEY);
    if (!savedCaseId) return;

    let mounted = true;
    setRestoring(true);
    getCase(savedCaseId)
      .then((response) => {
        if (!mounted) return;
        setEnvelope(response);
        setCaseId(response.caseId);
        resetTransientInputs();
      })
      .catch(() => {
        window.localStorage.removeItem(CASE_STORAGE_KEY);
      })
      .finally(() => {
        if (mounted) setRestoring(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (caseId) {
      window.localStorage.setItem(CASE_STORAGE_KEY, caseId);
      return;
    }
    window.localStorage.removeItem(CASE_STORAGE_KEY);
  }, [caseId]);

  async function run(task: () => Promise<void>) {
    setPending(true);
    setError("");
    try {
      await task();
    } catch (err) {
      setError(err instanceof Error ? err.message : "요청 처리에 실패했습니다.");
    } finally {
      setPending(false);
    }
  }

  async function handleStart() {
    const text = inputText.trim();
    if (!text || pending) return;

    await run(async () => {
      const [response] = await Promise.all([startCase(text), wait(MIN_ANALYSIS_LOADING_MS)]);
      setEnvelope(response);
      setCaseId(response.caseId);
      resetTransientInputs();
    });
  }

  async function handleTurn(input: TurnInput) {
    if (!caseId || pending) return;

    await run(async () => {
      const response = await sendTurn(caseId, input);
      setEnvelope(response);
      resetTransientInputs();
    });
  }

  function resetTransientInputs() {
    setSelectedIds([]);
    setFreeText("");
    setAddressResolved(null);
    setAddressBuilding(null);
  }

  function handleAddressResolved(address: ResolvedAddress, building: BuildingLedgerRaw | null) {
    setAddressResolved(address);
    setAddressBuilding(building);
    setFreeText(address.roadAddress || address.jibunAddress);
  }

  function handleAddressClear() {
    setAddressResolved(null);
    setAddressBuilding(null);
    setFreeText("");
  }

  function resetCase() {
    window.localStorage.removeItem(CASE_STORAGE_KEY);
    setEnvelope(null);
    setCaseId(null);
    setInputText("");
    setSelectedIds([]);
    setFreeText("");
    setAddressResolved(null);
    setAddressBuilding(null);
    setActiveDocument(null);
    setHistoryOpen(false);
    setResetConfirmOpen(false);
    setError("");
  }

  function showDevLanding() {
    resetCase();
    setSplashPhase("done");
  }

  function showDevPreview(type: ViewType) {
    window.localStorage.removeItem(CASE_STORAGE_KEY);
    setEnvelope(createDevEnvelope(type));
    setCaseId(null);
    setInputText("");
    setSelectedIds([]);
    setFreeText("");
    setActiveDocument(null);
    setHistoryOpen(false);
    setResetConfirmOpen(false);
    setError("");
    setSplashPhase("done");
  }

  function submitPrimary() {
    if (!view || !primary || primary.disabled) return;

    if (view.type === "slot_question") {
      handleTurn({
        type: "slot_answer",
        fieldKey: view.field,
        optionIds: selectedIds,
        text: freeText,
        value: freeText,
        unknown: selectedIds.includes("unknown"),
        ...(addressResolved
          ? { address: addressResolved, ...(addressBuilding ? { building: addressBuilding } : {}) }
          : {}),
      });
      return;
    }

    handleTurn({ type: "action", actionId: "primary" });
  }

  function submitAction(actionId: FlowActionId) {
    if (!caseId || pending) return;
    setHistoryOpen(false);
    handleTurn({ type: "action", actionId });
  }

  function submitUnknown() {
    if (!view || view.type !== "slot_question") return;

    handleTurn({
      type: "slot_answer",
      fieldKey: view.field,
      optionIds: ["unknown"],
      unknown: true,
    });
  }

  return (
    <>
      <main className={`app${ready ? " is-ready" : ""}`} id="app" aria-label="허가온" data-question-type={questionType}>
        {showLanding && (pending || restoring) ? (
          <AnalysisLoadingScreen />
        ) : showLanding ? (
          <LandingScreen inputText={inputText} error={error} pending={pending} onChange={setInputText} onStart={handleStart} />
        ) : (
          <section className="screen active" data-screen="question">
            <QuestionHeader progress={progress} onBack={() => setResetConfirmOpen(true)} onHistory={() => setHistoryOpen(true)} />
            <div className="question-main">
              {error ? <p className="collect-status error-text" role="alert">{error}</p> : null}
              <FlowView
                view={view}
                selectedIds={selectedIds}
                freeText={freeText}
                activeDocument={activeDocument}
                completedDocumentIds={envelope?.statePatch.completedDocumentIds || []}
                onSelectIds={setSelectedIds}
                onFreeText={setFreeText}
                onUnknown={submitUnknown}
                onToggleDocument={(documentId, completed) => handleTurn({ type: "document_toggle", documentId, completed })}
                onOpenDocument={setActiveDocument}
                onCloseDocument={() => setActiveDocument(null)}
                onDashboardContinue={submitPrimary}
                onDashboardAction={submitAction}
                onAction={submitAction}
                onAddressResolved={handleAddressResolved}
                onAddressClear={handleAddressClear}
                dashboardContinueDisabled={!primary || primary.disabled}
              />
            </div>
            {primary ? (
              <BottomBar
                primary={primary}
                onPrimary={submitPrimary}
              />
            ) : null}
            <ProcessingOverlay active={pending} />
            <HistoryPanel open={historyOpen} envelope={envelope} onClose={() => setHistoryOpen(false)} onAction={submitAction} />
            <ResetConfirmSheet open={resetConfirmOpen} onClose={() => setResetConfirmOpen(false)} onConfirm={resetCase} />
          </section>
        )}
      </main>
      {splashPhase !== "done" ? (
        <div className={`splash${splashPhase === "hiding" ? " is-hiding" : ""}`} role="status" aria-label="허가온 시작 화면">
          <BrandLogo />
        </div>
      ) : null}
      {showDevPanel ? (
        <DevPanel currentView={view?.type || "landing"} onLanding={showDevLanding} onPreview={showDevPreview} />
      ) : null}
    </>
  );
}

function wait(duration: number) {
  return new Promise((resolve) => window.setTimeout(resolve, duration));
}

function ResetConfirmSheet({
  open,
  onClose,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <div
      className={`reset-confirm-panel${open ? " open" : ""}`}
      aria-hidden={!open}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section className="reset-confirm-sheet" aria-label="처음으로 돌아가기">
        <span className="history-grabber" aria-hidden="true" />
        <h2 className="reset-confirm-title">처음으로 돌아갈까요?</h2>
        <p className="reset-confirm-text">지금까지 입력한 진행 내용이 이 화면에서 닫힙니다.</p>
        <div className="reset-confirm-actions">
          <button className="reset-confirm-secondary" type="button" onClick={onClose}>
            계속 진행
          </button>
          <button className="reset-confirm-danger" type="button" onClick={onConfirm}>
            처음으로
          </button>
        </div>
      </section>
    </div>
  );
}
