# GraphRAG Integration

허가온 V2에서 GraphRAG는 서류, 부서, 근거, 질문 후보를 확장하는 메인 도메인 레이어입니다. 백엔드는 상태 머신과 질문 루프를 계속 통제하고, GraphRAG는 판단에 필요한 후보 데이터를 반환합니다.

## 켜는 방법

```bash
cd backend
cp .env.example .env

ENABLE_GRAPH_RAG=true
GRAPH_RAG_BASE_URL=http://127.0.0.1:8200
GRAPH_RAG_API_KEY=
GRAPH_RAG_TIMEOUT_SECONDS=8
```

`GRAPH_RAG_BASE_URL`이 비어 있거나 요청이 실패하면 먼저 저장소에 포함된 `minju_new/graph/output/final_graph` CSV/JSONL을 로컬 GraphRAG 후보 소스로 사용합니다. 로컬 그래프에서도 유효한 응답을 만들 수 없을 때만 기존 `catalog.py` fallback으로 시연이 유지됩니다.

## 백엔드 연결 지점

```text
backend/app/services/graph_rag_service.py
backend/app/services/question_planner.py
backend/app/services/document_service.py
backend/app/services/inquiry_service.py
```

GraphRAG 우선순위:

1. `QuestionPlanner`가 질문 후보를 요청합니다.
2. `DocumentService`가 필요한 서류 목록을 요청합니다.
3. `InquiryService`가 문의 task와 담당 부서를 요청합니다.
4. 응답이 없거나 schema가 맞지 않으면 catalog fallback을 사용합니다.

응답 소스 우선순위:

1. 원격 `POST /retrieve`
2. 로컬 `minju_new/graph/output/final_graph`
3. `backend/app/data/catalog.py`

## 요청 계약

백엔드는 모든 GraphRAG 확장을 같은 endpoint로 요청합니다.

```http
POST /retrieve
Content-Type: application/json
Authorization: Bearer <GRAPH_RAG_API_KEY>
```

```json
{
  "kind": "documents",
  "schemaVersion": "2026-06-13",
  "case": {
    "caseId": "case_xxx",
    "rawInput": "연남동에서 디저트 카페를 열고 싶어요.",
    "slots": {
      "location": {
        "field": "location",
        "value": "연남동",
        "userText": "연남동",
        "adminTerm": "사용자 입력 지역",
        "status": "known"
      }
    },
    "candidatePermits": [],
    "answers": [],
    "documents": [],
    "inquiryTasks": []
  }
}
```

`kind` 값은 다음 중 하나입니다.

- `questions`: 부족 정보 질문 후보
- `documents`: 필요한 서류
- `inquiries`: 문의 task, 부서, 연락처
- `evidence`: 근거 문장이나 출처

## 질문 응답

```json
{
  "questions": [
    {
      "field": "on_site_consumption",
      "label": "매장 취식 여부",
      "question": "손님이 매장에서 먹고 갈 수 있나요?",
      "why": "객석 유무에 따라 신고 유형이 달라져요.",
      "inputMode": "single_select",
      "required": true,
      "options": [
        { "id": "yes", "title": "네" },
        { "id": "no", "title": "아니요" },
        { "id": "unknown", "title": "아직 몰라요", "exclusive": true }
      ]
    }
  ]
}
```

백엔드는 같은 field 반복, 최대 질문 수, unknown 처리, 다음 화면 전환을 직접 제어합니다. GraphRAG는 질문 후보만 줍니다.

## 서류 응답

```json
{
  "documents": [
    {
      "id": "building-ledger",
      "title": "건축물대장 확인",
      "priority": 1,
      "reason": "계약 전 건물 용도와 위반 여부를 확인해야 해요.",
      "status": "needs_check",
      "perceivedDuration": "즉시",
      "prerequisites": "정확한 주소",
      "unlocks": "임대차계약, 영업신고 검토",
      "officialLinks": [
        { "label": "정부24 건축물대장", "url": "https://www.gov.kr" }
      ],
      "prepareInfo": ["정확한 주소", "층수", "위반건축물 여부"],
      "steps": ["주소 확정", "건축물대장 조회", "용도와 위반 여부 확인"],
      "canPrepareBeforeInquiry": true,
      "evidence": ["건축물 용도 확인 후 식품접객업 신고 가능 여부를 검토합니다."]
    }
  ]
}
```

프론트는 `perceivedDuration`을 예상 소요시간으로 보여줍니다. `D-28` 같은 날짜 역산 값은 사용하지 않습니다.

## 문의 응답

```json
{
  "inquiryTasks": [
    {
      "id": "food-business-type",
      "title": "영업신고 유형 확인",
      "department": "마포구 보건소 위생과",
      "phone": "tel:0231539180",
      "onlineUrl": "https://www.epeople.go.kr/index.jsp",
      "visitHint": "마포구 보건소 또는 구청 위생 민원 창구",
      "reason": "우리 가게에 맞는 신고 유형을 확인해야 해요.",
      "status": "pending",
      "questions": [
        "제 가게는 어떤 영업신고 유형을 보면 될까요?",
        "건물 용도나 객석 기준으로 더 필요한 서류가 있나요?"
      ]
    }
  ]
}
```

## 책임 분리

- 프론트: 백엔드가 내려준 `view.type`과 schema 렌더링
- 백엔드: case 저장, 상태 전환, 질문 루프, 무한루프 방지, GraphRAG 응답 검증
- LLM: 자연어 추출, 문의 문안, 답변 분석
- GraphRAG: 법령, 서류, 부서, 근거, 질문 후보 확장

GraphRAG가 같은 field를 다시 물어도 백엔드가 차단합니다. GraphRAG가 빈 배열이나 잘못된 schema를 반환하면 해당 영역은 catalog fallback으로 대체됩니다.
