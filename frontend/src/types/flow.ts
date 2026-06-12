export type ViewType =
  | "slot_question"
  | "diagnosis"
  | "documents"
  | "inquiry"
  | "answer_review"
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
    inquiryTasks: InquiryTask[];
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
  | DocumentsView
  | InquiryView
  | AnswerReviewView
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
  candidatePermits: Array<{
    name: string;
    status: "candidate";
    reason: string;
  }>;
  decisionBlocks: DecisionBlock[];
  nextButtonLabel: string;
}

export interface DecisionBlock {
  type: "ready_for_documents" | "needs_user_info" | "needs_department_check" | "needs_user_decision";
  title: string;
  items: string[];
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
}

export interface InquiryView {
  type: "inquiry";
  title: string;
  mode: "channels" | "phone" | "online" | "visit";
  task?: InquiryTask;
  channels: Array<{ id: "phone" | "online" | "visit"; title: string; description: string }>;
  onlineDraft: { subject: string; body: string };
  nextButtonLabel: string;
}

export interface InquiryTask {
  id: string;
  title: string;
  department: string;
  phone: string;
  onlineUrl: string;
  visitHint: string;
  reason: string;
  status: "pending" | "resolved" | string;
  questions: string[];
}

export interface AnswerReviewView {
  type: "answer_review";
  title: string;
  analysis: {
    answerSummary?: string;
    resolvedItems?: string[];
    newMissingFields?: string[];
    newInquiryTasks?: InquiryTask[];
    nextAction?: string;
  };
  nextButtonLabel: string;
}

export interface DashboardView {
  type: "dashboard";
  title: string;
  summary: {
    documents: string;
    openInquiryTasks: number;
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
  | { type: "slot_answer"; fieldKey: string; optionIds: string[]; text?: string; value?: string; unknown?: boolean }
  | { type: "action"; actionId: FlowActionId }
  | { type: "document_toggle"; documentId: string; completed: boolean }
  | { type: "inquiry_channel"; channel: "phone" | "online" | "visit" }
  | { type: "consultation_answer"; text: string };

export type FlowActionId = "primary" | "restart" | "documents" | "inquiry" | "dashboard" | "submitted";
