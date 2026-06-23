# HEOGAON Intake Pipeline

사용자 자연어를 바로 판단엔진에 넣지 않고, 먼저 슬롯으로 구조화한 뒤 부족한 정보를 묶어서 반환하는 MVP 파이프라인입니다.

## Flow

```text
사용자 자연어
-> slot extraction
-> scenario registry에서 의도별 흐름 선택
-> missingInfo.requiredNow / recommendedNext / later
-> requirement graph에서 서류/부서/조건부 요구사항 계산
-> API/decision/graph가 필요한 근거 생성
-> aiGuidance가 최종 안내 AI에 넘길 context 생성
```

지원하는 대표 시나리오:

- `food_business_precheck`: 카페/음식점/제과점 창업 또는 영업신고 사전진단
- `signboard_permit_check`: 간판만 설치/변경
- `outdoor_space_permit_check`: 가게 앞 테이블, 테라스, 도로점용 확인
- `takeover_history_check`: 기존 업소 인수, 동일 장소 행정처분 이력 확인
- `building_use_check`: 건축물대장 용도, 위반건축물 여부 확인
- `document_readiness_check`: 제출 서류 준비상태와 영업신고/사업자등록 순서 확인

최종 사용자 답변은 AI가 만들되, AI는 `aiGuidance.context` 안의 intent, scenario, slots,
preliminaryDiagnosis, missingInfo, requirementGraph, apiPlan, currentState, decisionEngine 결과만 근거로 삼도록 한다.
즉 AI는 말하기/질문/안내를 담당하고, API/그래프/룰은 사실 확인과 근거 생성을 담당한다.

## Example

```powershell
python heogaon\intake\intake_pipeline.py --text "마포구 포은로 63 1층에서 카페 열고 와인도 팔고 싶어. 12평 정도야."
```

판단엔진/API 호출 없이 슬롯만 확인:

```powershell
python heogaon\intake\intake_pipeline.py --text "카페 열고 싶은데 주소는 아직 몰라" --no-decision
```

10개 대표 시나리오 라우팅/서류 그래프 검증:

```powershell
python heogaon\intake\validate_scenarios.py --api-mode auto
```

`--api-mode auto`는 `JUSO_API_KEY`, `DATA_GO_KR_SERVICE_KEY`가 환경변수에 있을 때만 실제 API를 호출합니다.
키 없이도 intent, slot filling, requirement graph, 최종 서류/부서 산출 검증은 수행합니다.

AI judgement를 먼저 시도하고 실패 시 rule fallback으로 검증:

```powershell
python heogaon\intake\validate_scenarios.py --api-mode auto --judgement-provider gms
python heogaon\intake\validate_scenarios.py --api-mode auto --judgement-provider openai
```

`gms`는 OpenAI-compatible SSAFY GMS 프록시를 호출합니다. 키는 코드에 저장하지 말고 환경변수로만 설정합니다.
`openai`는 `OPENAI_API_KEY`와 선택적으로 `HEOGAON_AI_MODEL` 환경변수를 사용하며, 실패하면 기본적으로 rule judgement로 fallback합니다.

```powershell
$env:GMS_API_KEY="..."
$env:GMS_MODEL="gpt-4.1"
$env:GMS_BASE_URL="https://gms.ssafy.io/gmsapi/api.openai.com/v1"
```

문의처/문의 스크립트도 같은 방식으로 provider를 선택할 수 있습니다.

```powershell
python heogaon\intake\validate_scenarios.py --api-mode auto --judgement-provider gms --inquiry-provider gms
```

문의 스크립트도 `GMS_API_KEY`, `GMS_MODEL`, `GMS_BASE_URL` 환경변수를 사용합니다.

slot filler provider를 명시:

```powershell
python heogaon\intake\intake_pipeline.py --text "마포구 망원동에서 15평 카페를 열고 싶어요" --slot-provider rule
python heogaon\intake\intake_pipeline.py --text "마포구 망원동에서 15평 카페를 열고 싶어요" --judgement-provider gms
```

slot filler도 `--slot-provider gms`로 실제 GMS structured-output 호출을 사용합니다. GMS 출력 후에도 후보 업종과 부족정보는 백엔드 정책 룰이 다시 계산합니다.

## Missing Info Policy

- `requiredNow`: API/판단 정확도를 막는 핵심 정보입니다. 사업장 전체 주소(도로명/지번 + 층/호), 주류 여부, 면적, 업종이 여기에 들어갑니다.
- `recommendedNext`: 간판, 외부 공간, 임대차계약처럼 부서/서류 안내를 정교하게 만드는 정보입니다.
- `later`: 위생교육, 보건증, 소방완비증명서처럼 체크리스트 상태 관리 단계에서 확인해도 되는 정보입니다.

면적은 API에서 추정할 수 있지만 실제 신고 기준은 영업장/임대 면적이 우선입니다. 따라서 파이프라인은 사용자 입력 면적을 1순위로 쓰고, 없을 때만 건축물대장 전유부/층별 면적 또는 기존 인허가 데이터를 참고하도록 판단엔진에 넘깁니다.

PDF 흐름 대비 남은 작업은 `heogaon/intake/FLOW_GAP_ANALYSIS.md`에 정리했습니다.
