# Flow Review

검토일: 2026-06-13

## Audit Scope

허가온 V2 MVP의 전체 시연 흐름을 검토했다.

검토 범위:

- 첫 진입/자연어 입력
- 정보 수집 질문 루프
- 사전 진단
- 서류 체크리스트
- 문의 방법 선택/답변 입력
- 답변 반영
- 대시보드/진행 현황
- 제출 완료 엔딩

검토 방법:

- 브라우저에서 첫 화면, 입력 후 질문 루프, 진단, 서류 화면을 확인
- FastAPI API 계약으로 전체 상태 전환 추적
- 프론트 컴포넌트와 백엔드 상태 머신 코드 검토

저장된 화면 근거:

- `docs/flow-review-assets/01-landing.jpg`

## Implemented Improvements

2026-06-13 추가 반영:

- 상단 뒤로가기 오해를 줄이기 위해 `처음으로 돌아가기` 확인 시트를 추가했다.
- `GET /api/cases/{caseId}`와 프론트 `localStorage` 기반 case 복구를 연결했다.
- 선택형/서술형 모두 `아직 몰라요`를 누르면 바로 다음 질문으로 넘어가게 통일했다.
- 질문 화면에 `질문 N/M` 칩을 추가해 정보 수집 내부 진행도를 분리 표시했다.
- 온라인 문의 화면에 `복사` 버튼과 복사 완료 상태를 추가했다.
- 백엔드 turn validation을 강화해 잘못된 단계의 답변, 잘못된 서류 id, 문의 채널 미선택 답변 저장을 400으로 차단한다.
- 진단 결과에서 주소 관련 항목이 `더 확인할 것`과 `먼저 정할 것`에 중복 표시되지 않게 조정했다.
- 모든 서류가 이미 완료된 상태에서 문의 답변 분석이 `documents`를 반환하면 `DOCUMENTS`를 반복하지 않고 `DASHBOARD`로 이동한다.

## Step Health

| Step | Screen | Health | Notes |
| --- | --- | --- | --- |
| 1 | 앱 진입/입력 | Good | splash 후 자연어 입력으로 바로 진입한다. 첫 화면에는 로고가 없어 브랜드 인지가 약할 수 있다. |
| 2 | AI 분석 로딩 | Good | 입력 후 로딩 화면이 있고 전환이 자연스럽다. |
| 3 | 정보 수집 루프 | Good with risks | 질문은 한 번에 하나씩 나온다. 다만 free text의 `아직 몰라요`는 즉시 다음 질문으로 가고, 선택형은 선택 후 `다음`을 눌러야 해서 동작이 다르다. |
| 4 | 사전 진단 | Good with risks | 판단 결과 요약은 명확하다. `더 확인할 것`과 `먼저 정할 것`이 같은 주소 이슈를 중복해 보일 수 있다. |
| 5 | 서류 체크리스트 | Needs improvement | 진행률과 체크 조건은 명확하다. 체크박스 접근성/자동화 가능성이 낮고, 막힌 서류도 체크할 수 있다. |
| 6 | 문의 방법 | Good with risks | 전화/온라인/방문 구분은 명확하다. 온라인 문의 문안에 복사 버튼이 없어 요청 의도와 덜 맞는다. |
| 7 | 답변 반영 | Good | 답변 저장 후 `ANSWER_REVIEW`로 이동한다. 일부 답변은 다시 서류 화면을 거쳐 대시보드로 가서 중복 전환처럼 보일 수 있다. |
| 8 | 대시보드/진행 현황 | Good | 남은 일과 새 업데이트를 보여준다. 리스트가 2개까지만 노출되어 숨은 작업 수 표현이 필요하다. |
| 9 | 제출 완료 | Good with risks | 모든 서류와 문의가 끝난 뒤에만 100% 화면으로 간다. 실제 제출 행위 없이 체크 완료가 제출 완료로 이어지는 표현은 다듬을 여지가 있다. |

## Confirmed Strengths

- 백엔드가 흐름을 통제하고 프론트는 `view.type`을 렌더링하는 구조가 유지된다.
- 정보 수집 루프는 field별/전체 질문 제한을 갖고 있어 무한 루프 위험이 낮다.
- API 상태 전환은 기본 시연 경로에서 끝까지 정상 동작한다.
- 모든 서류 완료와 열린 문의 없음 조건을 만족해야 `SUBMITTED`로 진입한다.
- 대시보드와 진행 현황 패널의 할 일 카드가 백엔드 action으로 실제 흐름에 복귀한다.
- 문서와 코드 구조가 Claude Code/Codex가 이어받기 쉽게 분리되어 있다.

## UX Risks

### P1. 뒤로가기 아이콘이 전체 케이스 초기화로 동작한다

현재 질문 이후 상단 왼쪽 버튼은 `이전`처럼 보이지만 실제로는 `resetCase()`를 호출해 전체 케이스를 처음으로 되돌린다. 사용자는 한 단계 뒤로 가는 것으로 예상할 수 있다.

권장:

- 진짜 이전 단계가 아니라면 아이콘/label을 `처음으로` 성격으로 바꾸고 확인 dialog를 둔다.
- 가능하면 `lastViewStack` 또는 백엔드 action으로 이전 단계 복귀를 제공한다.

### P1. 서류 체크박스 접근성/테스트성이 약하다

브라우저 DOM에는 checkbox가 보이지만 실제 input은 숨겨져 있어 자동화 `check()`나 role click이 실패했다. 실제 터치 사용자는 label 영역을 누를 수 있지만, 키보드/보조기기/자동화 관점에서는 취약하다.

권장:

- 체크 영역 자체를 `<button aria-pressed>` 또는 visible checkbox label로 재구성한다.
- focus ring과 checked 상태가 시각적으로 명확해야 한다.
- label 안에 시각적 텍스트 또는 `aria-labelledby`를 연결한다.

### P1. 온라인 문의에 복사 중심 액션이 없다

기획상 온라인 문의는 AI 문안 생성/복사 중심이어야 한다. 현재는 read-only textarea만 있고 복사 버튼이 없다.

권장:

- `문의 글 복사` 버튼 추가
- 복사 성공 상태 표시
- 가능하면 `온라인 문의 열기` 링크도 같이 제공

### P1. 백엔드 turn validation이 느슨하다

`consultation_answer`가 현재 state와 관계없이 들어오면 첫 pending inquiry를 resolved 처리할 수 있다. `document_toggle`도 존재하지 않는 document id를 completed ids에 넣을 수 있다.

권장:

- state별 허용 input type을 명시적으로 검증한다.
- document id가 현재 case documents에 없으면 400을 반환한다.
- inquiry channel 선택 후 답변 저장 가능 상태인지 검증한다.

### P1. 새로고침/서버 재시작에 약하다

프론트 case 상태는 React memory에 있고, 백엔드는 in-memory repository다. 브라우저 새로고침이나 서버 재시작 시 진행 상태가 사라진다.

권장:

- 최소 MVP: `caseId`를 sessionStorage/localStorage에 저장하고 `/api/cases/{caseId}`로 복구
- 다음 단계: SQLite/Postgres repository 구현

## UX Opportunities

### P2. 질문 루프의 `아직 몰라요` 동작을 통일한다

free text 질문에서는 `아직 몰라요`가 즉시 제출되고, 선택형 질문에서는 선택 후 `다음`을 눌러야 한다.

권장:

- 모든 질문에서 `아직 몰라요`를 누르면 즉시 다음으로 이동
- 또는 모든 질문에서 선택 후 하단 `다음`으로 통일

시연에서는 즉시 이동 방식이 더 빠르다.

### P2. 진행바가 정보 수집 내부 진행도를 보여주지 않는다

상단 진행바는 `정보 수집 1/6`으로 유지되고, 질문 7개 중 몇 번째인지 직접 보여주지 않는다.

권장:

- 질문 화면 subtitle 또는 progress caption에 `질문 3/7` 표시
- stage progress와 question progress를 분리

### P2. 진단 결과에서 같은 의미의 블록이 중복된다

주소가 unknown이면 `더 확인할 것`과 `먼저 정할 것`이 모두 주소 관련으로 보일 수 있다.

권장:

- `먼저 정할 것`이 있으면 해당 field는 `더 확인할 것`에서 제외
- 또는 `추가 확인` 안에 우선순위 badge로 합친다.

### P2. 서류의 선후관계가 체크 가능 상태에 반영되지 않는다

`사업자등록증`은 영업신고 후 진행해야 하지만 현재는 모든 서류가 동일하게 체크 가능하다.

권장:

- blocked 문서는 잠금 상태로 표시
- 선행 서류 완료 시 unlock
- 시연 편의를 위해 `건너뛰기/시연 완료 처리`는 dev mode에만 제공

### P2. 문의 답변 후 중복 전환처럼 느껴질 수 있다

답변 분석 결과 `nextAction=documents`면 `ANSWER_REVIEW -> DOCUMENTS -> DASHBOARD -> SUBMITTED`로 한 번 더 서류 화면을 거친다. 이미 모든 서류가 완료된 상황에서는 사용자가 불필요한 반복으로 느낄 수 있다.

권장:

- 모든 서류 완료 상태에서 `nextAction=documents`가 오면 바로 `DASHBOARD` 또는 `SUBMITTED` 후보로 라우팅
- `ANSWER_REVIEW`에 다음 이동 이유를 한 줄 표시

### P2. 대시보드와 진행 현황이 숨은 작업 수를 충분히 말하지 않는다

진행 현황 패널은 pending documents/tasks를 2개까지만 보여준다.

권장:

- `외 N개` 표시
- 전체 보기 CTA 제공

### P2. 엔딩 화면의 의미를 더 정확히 만든다

현재 체크리스트 완료가 곧 `서류 제출 완료`로 이어진다. 실제 제품에서는 준비 완료와 제출 완료가 다르다.

권장:

- MVP 시연용이면 `서류 제출 완료 처리` 버튼을 한 번 둔다.
- 장기적으로 `prepared`, `submitted`, `accepted` 상태를 분리한다.

## Technical Recommendations

1. Add backend input validation per machine state.
2. Add persistent case recovery using `GET /api/cases/{caseId}` and frontend sessionStorage.
3. Refactor document check control for accessibility.
4. Add copy action to online inquiry mode.
5. Add question-loop progress indicator.
6. Collapse duplicate diagnosis blocks.
7. Add document dependency/locked states.
8. Add a clean dev restart script to avoid stale `.next` runtime errors after build cleanup.

## Verification Notes

API happy path confirmed:

```text
slot_question / NEEDS_INFO
diagnosis / DIAGNOSIS
documents / DOCUMENTS
inquiry / INQUIRY
answer_review / ANSWER_REVIEW
dashboard / DASHBOARD
submitted / SUBMITTED / completion=100
```

API guard checks confirmed:

```text
consultation_answer before inquiry channel -> 400
invalid document id -> 400
all documents completed + nextAction documents -> DASHBOARD
```

Browser checks confirmed:

- Galaxy S24+ ratio viewport rendered landing, first question, reset confirmation sheet, and history panel without visible overlap
- first input to first question worked
- `질문 N/M` chip rendered on information collection questions
- free text and select `아직 몰라요` both advanced immediately
- history panel returned to the active flow
- online inquiry copy button rendered and showed `복사 완료`
- no runtime error overlay appeared during the checked browser path

Observed operational issue:

- The browser initially showed a Next runtime error, `Cannot find module './833.js'`, because the dev server was stale after build artifact cleanup. Restarting the frontend dev server fixed it.
