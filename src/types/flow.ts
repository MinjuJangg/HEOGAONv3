export type ViewType =
  | "slot_question"
  | "diagnosis"
  | "understanding_review"
  | "documents"
  | "dashboard"
  | "submitted";

export interface ApiEnvelope {
  ok: boolean;
  caseId: string;
  turnId: string;
  view: ApiView;
  caseState: {
    status: string;
    currentStep: string;
    progressStage: string;
  };
  statePatch: {
    slots: Record<string, SlotRecord>;
    answers: AnswerLog[];
    documents: DocumentItem[];
    inquiryTasks: unknown[];
    completedDocumentIds: string[];
    questionLoop: QuestionLoop;
    flowState: Record<string, unknown>;
  };
  meta: {
    schemaVersion: string;
    source: string;
    fallback: boolean;
    warnings: string[];
  };
}

export type ApiView =
  | SlotQuestionView
  | DiagnosisView
  | UnderstandingReviewView
  | DocumentsView
  | DashboardView
  | SimpleView;

export interface SimpleView {
  type: "submitted";
  title: string;
  subtitle?: string;
  completionRate?: number;
  statusCards?: Array<{ label: string; value: string }>;
  submittedDocuments?: Array<{
    id: string;
    title: string;
    statusLabel: string;
    meta: string;
  }>;
  nextNotes?: string[];
  nextButtonLabel: string;
}

export interface SlotQuestionView {
  type: "slot_question";
  field: string;
  title: string;
  subtitle?: string;
  inputMode: "single_select" | "multi_select" | "free_text";
  options: QuestionOption[];
  validationMessage?: string;
  nextButtonLabel: string;
  loop: {
    totalAsked: number;
    maxTotalQuestions: number;
    plannedTotalQuestions?: number;
    attemptsForField: number;
    maxAttemptsPerField: number;
  };
}

export interface QuestionOption {
  id: string;
  title: string;
  exclusive?: boolean;
}

export interface DiagnosisView {
  type: "diagnosis";
  title: string;
  headline: string;
  guidance?: DiagnosisGuidance;
  candidatePermits: Array<{
    name: string;
    status: "candidate";
    reason: string;
  }>;
  decisionBlocks: DecisionBlock[];
  nextButtonLabel: string;
}

export interface DiagnosisGuidance {
  title?: string;
  headline?: string;
  provider: "rule" | "gms" | "openai" | string;
  decisionStatus?: string;
  suitability?: "available" | "needs_info" | "needs_check" | "blocked" | "pending" | string;
  suitabilityTitle?: string;
  suitabilitySummary?: string;
  summary?: string;
  finalResponseDraft?: string;
  apiStatusItems: string[];
  buildingItems: string[];
  canSayNow: string[];
  cannotConfirmYet: string[];
  questionsToAsk: string[];
  procedureSteps: string[];
  documentOrderItems: string[];
  departmentItems?: string[];
}

export interface DecisionBlock {
  type: "ready_for_documents" | "needs_user_info" | "needs_department_check" | "needs_user_decision";
  title: string;
  items: string[];
}

export interface UnderstandingReviewView {
  type: "understanding_review";
  title: string;
  subtitle?: string;
  items: Array<{ label: string; value: string }>;
  apiItems: string[];
  buildingItems: string[];
  suitabilityTitle?: string;
  suitabilitySummary?: string;
  nextButtonLabel: string;
  editButtonLabel: string;
}

export interface DocumentsView {
  type: "documents";
  title: string;
  documents: DocumentItem[];
  completedDocumentIds: string[];
  nextButtonLabel: string;
}

export interface DocumentItem {
  id: string;
  title: string;
  priority: number;
  reason: string;
  status: "not_started" | "needs_check" | "blocked" | "completed" | string;
  statutoryDeadline: string;
  perceivedDuration: string;
  prerequisites: string;
  unlocks: string;
  officialLinks: Array<{ label: string; url: string }>;
  prepareInfo: string[];
  steps: string[];
  canPrepareBeforeInquiry: boolean;
  issuer?: string;
  issuerUrl?: string;
  issuerLinkLabel?: string;
  issuerNote?: string;
  submitTo?: string;
  submitUrl?: string;
  submitLinkLabel?: string;
  submissionPhase?: string;
  issueChannel?: string;
  blockingPrerequisites?: string[];
  dependencyNote?: string;
  graphPrerequisites?: string;
  dependsOn?: string[];
  trackId?: string;
  trackTitle?: string;
  trackDescription?: string;
  phase?: number;
  phaseTitle?: string;
}

export interface DashboardView {
  type: "dashboard";
  title: string;
  summary: {
    documents: string;
    answeredQuestions: number;
    unknownFields: number;
  };
  sections: DashboardSection[];
  nextActions: string[];
  nextButtonLabel: string;
}

export interface DashboardSection {
  id: string;
  title: string;
  subtitle?: string;
  icon: "check" | "fileCheck" | "list" | "message" | "refresh" | "search";
  badge?: string;
  empty?: string;
  items: DashboardSectionItem[];
}

export interface DashboardSectionItem {
  id: string;
  title: string;
  description: string;
  statusLabel: string;
  tone: "ready" | "new" | "updated" | "pending" | "done";
  meta?: string;
  actionId?: FlowActionId;
}

export interface SlotRecord {
  field: string;
  value: unknown;
  userText: string;
  adminTerm: string;
  status: "known" | "unknown";
  updatedAt: string;
}

export interface AnswerLog {
  id: string;
  field: string;
  question: string;
  answer: string;
  createdAt: string;
}

export interface QuestionLoop {
  status: "idle" | "active" | "complete";
  maxTotalQuestions: number;
  maxAttemptsPerField: number;
  askedFields: string[];
  answeredFields: string[];
  unknownFields: string[];
  skippedFields: string[];
  answers: Record<string, unknown>;
  totalAsked: number;
  stopReason?: string;
}

export type TurnInput =
  | { type: "natural_language"; text: string }
  | {
      type: "slot_answer";
      fieldKey: string;
      optionIds: string[];
      text?: string;
      value?: string;
      unknown?: boolean;
      // 주소 단계에서 프론트가 카카오로 확정한 주소 + 직접 호출한 건축물대장 raw 데이터.
      // 백엔드는 이 raw 데이터를 "해석"만 한다(JUSO 우회).
      address?: import("@/lib/address").ResolvedAddress;
      building?: import("@/lib/address").BuildingLedgerRaw;
    }
  | { type: "action"; actionId: FlowActionId }
  | { type: "document_toggle"; documentId: string; completed: boolean };

export type FlowActionId =
  | "primary"
  | "restart"
  | "documents"
  | "dashboard"
  | "submitted"
  | "edit_understanding";
