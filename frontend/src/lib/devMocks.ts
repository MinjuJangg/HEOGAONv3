import type { ApiEnvelope, ApiView, DocumentItem, ViewType } from "@/types/flow";

const now = "2026-06-13T00:00:00.000Z";

const documents: DocumentItem[] = [
  {
    id: "business-registration",
    title: "사업자등록 신청서",
    priority: 1,
    reason: "카페 영업을 시작하기 전에 세무서에 사업자 정보를 등록해야 합니다.",
    status: "not_started",
    statutoryDeadline: "영업 시작 전",
    perceivedDuration: "약 1일",
    prerequisites: "대표자 신분증과 임대차계약서가 필요합니다.",
    unlocks: "사업자등록증 발급 뒤 위생 신고와 카드 가맹 신청을 이어갈 수 있습니다.",
    officialLinks: [{ label: "홈택스", url: "https://www.hometax.go.kr" }],
    prepareInfo: ["대표자 이름", "사업장 주소", "업종", "임대차계약서"],
    steps: ["신청 정보 확인", "온라인 또는 세무서 제출", "사업자등록증 수령"],
    canPrepareBeforeInquiry: true,
  },
  {
    id: "hygiene-education",
    title: "위생교육 수료증",
    priority: 2,
    reason: "휴게음식점 영업 신고 전에 위생교육 수료 여부를 확인합니다.",
    status: "needs_check",
    statutoryDeadline: "영업 신고 전",
    perceivedDuration: "약 3시간",
    prerequisites: "대표자 또는 영업자가 교육을 수강해야 합니다.",
    unlocks: "수료 뒤 영업 신고 서류에 첨부할 수 있습니다.",
    officialLinks: [{ label: "한국외식업중앙회", url: "https://www.foodservice.or.kr" }],
    prepareInfo: ["대표자 정보", "업종", "교육 수료 확인"],
    steps: ["교육 기관 선택", "온라인 교육 수강", "수료증 저장"],
    canPrepareBeforeInquiry: true,
  },
  {
    id: "facility-check",
    title: "시설 기준 확인 자료",
    priority: 3,
    reason: "영업장 면적, 조리 공간, 급수 설비가 기준에 맞는지 확인해야 합니다.",
    status: "not_started",
    statutoryDeadline: "영업 신고 전",
    perceivedDuration: "약 1~2일",
    prerequisites: "매장 도면과 설비 사진을 준비하면 좋습니다.",
    unlocks: "현장 확인과 접수 준비를 빠르게 진행할 수 있습니다.",
    officialLinks: [{ label: "정부24", url: "https://www.gov.kr" }],
    prepareInfo: ["매장 도면", "주방 사진", "급수/배수 설비", "환기 설비"],
    steps: ["매장 자료 모으기", "기준표와 대조", "부족한 설비 확인"],
    canPrepareBeforeInquiry: false,
  },
];

const views: Record<ViewType, ApiView> = {
  slot_question: {
    type: "slot_question",
    field: "business_type",
    title: "가게에서 어떤 걸 판매하나요?",
    subtitle: "가장 가까운 항목을 골라주세요.",
    inputMode: "single_select",
    options: [
      { id: "dessert_cafe", title: "디저트와 커피" },
      { id: "takeout", title: "포장 전문" },
      { id: "alcohol", title: "주류도 판매" },
      { id: "unknown", title: "아직 몰라요", exclusive: true },
    ],
    nextButtonLabel: "다음",
    loop: {
      totalAsked: 1,
      maxTotalQuestions: 5,
      plannedTotalQuestions: 4,
      attemptsForField: 1,
      maxAttemptsPerField: 2,
    },
  },
  diagnosis: {
    type: "diagnosis",
    title: "카페 영업 신고가 필요해 보여요",
    headline: "입력한 내용을 기준으로 먼저 준비할 허가와 확인 항목을 정리했어요.",
    candidatePermits: [
      {
        name: "휴게음식점 영업 신고",
        status: "candidate",
        reason: "커피와 디저트를 매장에서 판매하는 경우에 주로 필요합니다.",
      },
    ],
    decisionBlocks: [
      {
        type: "ready_for_documents",
        title: "바로 준비할 수 있어요",
        items: ["사업자등록 신청서", "위생교육 수료증"],
      },
      {
        type: "needs_department_check",
        title: "구청 확인이 필요해요",
        items: ["매장 시설 기준", "간판 설치 가능 여부"],
      },
    ],
    nextButtonLabel: "서류 보러가기",
  },
  understanding_review: {
    type: "understanding_review",
    title: "이렇게 이해했어요",
    subtitle: "맞으면 서류 준비 순서로 넘어가고, 다르면 지금 수정할 수 있어요.",
    items: [
      { label: "업종/판매품목", value: "디저트 카페" },
      { label: "정확한 주소", value: "서울특별시 마포구 포은로 63, 1층 101호" },
      { label: "주류 판매 여부", value: "아니요" },
      { label: "간판·외부공간·가스 등 추가 조건", value: "간판/옥외광고물 + 외부 테이블/보도 사용" },
    ],
    apiItems: ["건축물대장: 확인됨", "용도/업종 판정: 확인됨", "동일 장소 이력: 보류"],
    buildingItems: ["주용도: 제2종근린생활시설", "대장상 면적: 49.5㎡"],
    suitabilityTitle: "진행 가능성이 높아요",
    suitabilitySummary: "건축물대장과 업종 판정 결과를 기준으로 진행 가능성이 높게 나왔어요.",
    nextButtonLabel: "맞아요, 계속",
    editButtonLabel: "수정할래요",
  },
  documents: {
    type: "documents",
    title: "먼저 준비할 서류예요",
    documents,
    completedDocumentIds: ["business-registration"],
    nextButtonLabel: "진행 상황 보기",
  },
  dashboard: {
    type: "dashboard",
    title: "남은 일을 한눈에 볼게요",
    summary: {
      documents: "1/3",
      answeredQuestions: 3,
      unknownFields: 1,
    },
    sections: [
      {
        id: "updated",
        title: "업데이트된 일",
        subtitle: "새로 확인한 정보를 반영했어요.",
        icon: "refresh",
        badge: "새로고침",
        items: [
          {
            id: "facility",
            title: "시설 기준 확인",
            description: "면적 기준은 가능하지만 간판 조건은 추가 입력이 필요해요.",
            statusLabel: "업데이트",
            tone: "updated",
            meta: "방금 반영",
            actionId: "documents",
          },
        ],
      },
      {
        id: "remaining",
        title: "남은 일",
        icon: "list",
        items: [
          {
            id: "docs",
            title: "서류 2개 더 체크",
            description: "위생교육 수료증과 시설 기준 확인 자료가 남았어요.",
            statusLabel: "대기",
            tone: "pending",
            actionId: "documents",
          },
        ],
      },
    ],
    nextActions: ["남은 서류를 마저 체크하세요."],
    nextButtonLabel: "서류 보러가기",
  },
  submitted: {
    type: "submitted",
    title: "서류 제출이 끝났어요",
    subtitle: "준비한 서류를 제출 완료 상태로 정리했어요.",
    completionRate: 100,
    statusCards: [
      { label: "서류", value: "완료" },
      { label: "진행률", value: "100%" },
    ],
    submittedDocuments: documents.map((document) => ({
      id: document.id,
      title: document.title,
      statusLabel: "완료",
      meta: `우선순위 ${document.priority}`,
    })),
    nextNotes: ["접수번호와 제출 기록을 따로 보관하세요.", "보완 요청이 오면 필요한 서류만 다시 확인하세요."],
    nextButtonLabel: "처음으로",
  },
};

const progressStageByView: Record<ViewType, string> = {
  slot_question: "intake",
  diagnosis: "diagnosis",
  understanding_review: "diagnosis",
  documents: "documents",
  dashboard: "dashboard",
  submitted: "submitted",
};

export const devViewLabels: Array<{ type: ViewType; label: string }> = [
  { type: "slot_question", label: "질문" },
  { type: "diagnosis", label: "진단" },
  { type: "understanding_review", label: "확인" },
  { type: "documents", label: "서류" },
  { type: "dashboard", label: "대시보드" },
  { type: "submitted", label: "완료" },
];

export function createDevEnvelope(type: ViewType): ApiEnvelope {
  return {
    ok: true,
    caseId: "dev-local-case",
    turnId: `dev-${type}`,
    view: views[type],
    caseState: {
      status: type === "submitted" ? "SUBMITTED" : "DEV_PREVIEW",
      currentStep: type,
      progressStage: progressStageByView[type],
    },
    statePatch: {
      slots: {
        business_type: {
          field: "business_type",
          value: "dessert_cafe",
          userText: "디저트와 커피",
          adminTerm: "휴게음식점",
          status: "known",
          updatedAt: now,
        },
      },
      answers: [
        {
          id: "answer-1",
          field: "business_type",
          question: "가게에서 어떤 걸 판매하나요?",
          answer: "디저트와 커피",
          createdAt: now,
        },
      ],
      documents,
      inquiryTasks: [],
      completedDocumentIds: type === "documents" ? ["business-registration"] : documents.map((document) => document.id),
      questionLoop: {
        status: "active",
        maxTotalQuestions: 5,
        maxAttemptsPerField: 2,
        askedFields: ["business_type"],
        answeredFields: ["business_type"],
        unknownFields: [],
        skippedFields: [],
        answers: { business_type: "dessert_cafe" },
        totalAsked: 1,
      },
      flowState: {},
    },
    meta: {
      schemaVersion: "dev",
      source: "local-dev-panel",
      fallback: true,
      warnings: [],
    },
  };
}
