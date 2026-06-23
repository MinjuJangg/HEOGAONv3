# HEOGAON Flow Gap Analysis

PDF 기준 서비스 흐름:

```text
1. 업종 선택 / 자연어 상황 입력
2. 기본 정보 입력
3. AI 사전 진단
4. 체크리스트 작성
5. 담당부서 문의 가이드
6. 진행 상태 관리
```

## 현재 구현된 것

- 자연어 입력에서 intent, scope, action, slot 추출
- full opening / partial change / specific check / document readiness / takeover 분기
- 주소, 층/호, 면적, 주류, 간판, 외부공간, 승낙 여부 부족정보 계산
- requirement graph 기반 서류, 조건부 서류, 담당 부서 산출
- AI judgement 우선 실행 구조와 rule fallback
- 건축물대장/동일 장소 이력 API 호출 연결 지점
- 구별 담당 부서, 전화번호, 링크 연결
- 문의 스크립트/온라인 문의 초안 생성, LLM provider와 rule fallback
- 10개 대표 시나리오 자동 검증

## 아직 부족한 것

1. Frontend 연결
   - `intake_pipeline.py` 결과를 FastAPI endpoint로 감싸야 한다.
   - 프론트는 `aiJudgement`, `requirementGraph`, `inquiryPackage`를 주요 렌더링 데이터로 사용한다.

2. 상태 관리
   - PDF의 "진행 상태 관리"는 아직 영속 DB가 없다.
   - 준비항목별 상태값: `not_started`, `needs_input`, `ready_to_prepare`, `in_progress`, `prepared`, `submitted`, `confirmed`.
   - Supabase/PostgreSQL에 사용자 세션, 답변, 체크리스트 상태를 저장해야 한다.

3. 실제 API 운영 검증
   - `JUSO_API_KEY`, `DATA_GO_KR_SERVICE_KEY`가 세팅된 환경에서 10개 시나리오를 `--api-mode on`으로 재검증해야 한다.
   - API 실패/빈 응답/캐시 정책을 프론트에 표시할 에러 메시지로 정리해야 한다.

4. 문서 발급 링크 고도화
   - 현재는 문서별 발급처/제출처/출처 링크를 연결한다.
   - 정부24 신청 URL, 협회 위생교육 URL, 보건소/소방서 페이지까지 버튼화하면 PDF의 "발급처 바로 연결"에 가까워진다.

5. 문의 답변 반영 루프
   - 사용자가 부서에 전화 후 받은 답변을 입력하면 체크리스트 상태와 판단 결과에 반영하는 단계가 필요하다.
   - 예: "건축과에서 용도변경 필요하다고 했어요" -> blocker 추가, 다음 행동 재계산.

## Backend API Contract 초안

```http
POST /api/intake/analyze
{
  "text": "마포구 망원동에서 15평 카페 창업하고 싶어요...",
  "runDecision": true,
  "slotProvider": "gms",
  "judgementProvider": "gms",
  "inquiryProvider": "gms"
}
```

프론트 핵심 사용 필드:

- `slots`: 사용자가 말한 조건
- `missingInfo`: 기본 질문 UI
- `requirementGraph.documentPlan`: 서류/조건부 서류
- `requirementGraph.departmentPlan`: 부서 후보
- `aiJudgement.judgement`: 최종 판단 상태, 질문, 답변 초안
- `inquiryPackage.contacts`: 부서명, 전화번호, 링크
- `inquiryPackage.scripts`: 전화/온라인 문의 스크립트
- `externalChecks`: 건축물대장/API 조회 상태

## 다음 구현 우선순위

1. FastAPI endpoint 생성
2. 프론트에서 `analyze` 호출 후 4개 화면에 매핑
   - 사전진단
   - 추가정보 질문
   - 서류 체크리스트
   - 문의 패키지
3. 진행 상태 저장 테이블 설계
4. 실제 API 키 환경에서 end-to-end 검증
5. 문의 답변을 다시 입력받아 상태를 갱신하는 `POST /api/intake/update-status` 추가
