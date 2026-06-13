# AI Integration

허가온 V2는 AI API 키가 없어도 규칙 기반 fallback으로 시연됩니다. AI API를 넣으면 같은 경계에서 자연어 이해와 답변 분석 품질만 높아지도록 설계되어 있습니다.

## 환경 변수

`backend/.env.example`을 참고합니다.

```bash
cd backend
cp .env.example .env

LLM_API_KEY=
LLM_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1
LLM_MODEL=gpt-5.5
LLM_REASONING_EFFORT=low
LLM_MAX_OUTPUT_TOKENS=1024
LLM_TIMEOUT_SECONDS=12
ENABLE_LLM=true
ENABLE_DEMO_FALLBACK=true
ENABLE_GRAPH_RAG=false
GRAPH_RAG_BASE_URL=
```

`GMS_API_KEY`도 `LLM_API_KEY`의 fallback으로 인식합니다.
`backend/.env`는 서버 시작 시 자동으로 읽습니다.

## 연결 지점

```text
backend/app/integrations/llm_client.py
backend/app/services/intake_agent.py
backend/app/services/consultation_analyzer.py
backend/app/schemas/ai.py
backend/app/services/output_guard.py
```

## AI가 해야 할 일

- 사용자의 자연어 입력에서 명시된 사실 추출
- 모르는 값은 `unknown`
- 후보 업종/인허가는 확정하지 않고 candidate로 유지
- 부족 정보 도출
- 쉬운 질문 문장 생성
- 문의 답변 요약
- 해결된 항목, 새 missing field, 새 문의 task 도출

## AI가 하면 안 되는 일

- 다음 화면 직접 결정
- 질문 반복 횟수 결정
- 제출 가능 여부 단독 판단
- 법률 확정 표현 생성
- 사용자에게 보이는 schema를 임의 변경

## 예시 출력

문의 답변 분석은 다음 형태를 기대합니다.

```json
{
  "answerSummary": "건축물 용도를 먼저 확인하라는 답변을 받음",
  "resolvedItems": ["food_business_type"],
  "newMissingFields": ["building_use"],
  "newInquiryTasks": [
    {
      "title": "간판 신고 확인",
      "department": "옥외광고물 담당"
    }
  ],
  "nextAction": "ask_followup"
}
```

백엔드는 이 결과를 검증한 뒤 `NEEDS_INFO`, `INQUIRY`, `DOCUMENTS`, `DASHBOARD` 중 하나로 라우팅합니다.

## GraphRAG 확장 위치

GraphRAG는 `backend/app/services/graph_rag_service.py` 뒤에 연결합니다. `ENABLE_GRAPH_RAG=true`와 `GRAPH_RAG_BASE_URL`을 설정하면 질문 후보, 서류, 문의 task를 GraphRAG에서 먼저 받아오고, 실패하면 `backend/app/data/catalog.py` fallback을 사용합니다.

연결 지점:

- 서류 후보: `DocumentService`
- 부서/연락처: `InquiryService`
- 근거 문장: `GraphRagService.retrieve_evidence`
- 질문 후보: `QuestionPlanner`

상세 schema는 [GraphRAG Integration](./graph-rag-integration.md)을 기준으로 맞춥니다.
