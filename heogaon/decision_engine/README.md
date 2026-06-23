# HEOGAON Decision Engine

`permit_judgement.py`는 전처리 결과와 공공 API를 사용해 상세주소/업종 기준 사전 가능성을 판단한다.

## Required Environment

```powershell
$env:JUSO_API_KEY="행정안전부_실시간 주소정보 조회(검색API) 승인키"
$env:DATA_GO_KR_SERVICE_KEY="국토교통부_건축HUB_건축물대장정보 서비스 인증키"
```

## Examples

일반음식점:

```powershell
python heogaon\decision_engine\permit_judgement.py --address "서울특별시 마포구 포은로 63, 1층 101호" --business-type 일반음식점영업
```

휴게음식점/카페:

```powershell
python heogaon\decision_engine\permit_judgement.py --address "서울특별시 마포구 포은로 63, 1층 101호" --business-type 휴게음식점영업 --area-m2 36.75
```

주류 판매 계획이 있는 경우:

```powershell
python heogaon\decision_engine\permit_judgement.py --address "서울특별시 마포구 포은로 63, 1층 101호" --business-type 휴게음식점영업 --liquor-sales
```

카페/음식점 전체 조합:

```powershell
python heogaon\decision_engine\permit_judgement.py --address "서울특별시 마포구 포은로 63, 1층 101호" --area-m2 36.75 --all-combinations
```

## Output Shape

- `fetched.normalizedAddress`: 주소 API 정규화 결과
- `fetched.buildingSummary`: 건축물대장 표제부/층별/지역지구 요약
- `fetched.selectedFloorRecords`: 상세주소의 층과 매칭되는 층별개요
- `fetched.samePlacePastBusinesses`: 서울 LOCALDATA 기준 동일 장소 전체 업소 이력
- `fetched.sameBusinessTypePastBusinesses`: 서울 LOCALDATA 기준 동일 장소/동일 업종 업소 이력
- `decision.result`: `possible`, `blocked`, `needs_more_info`, `needs_department_check`, `needs_use_change_or_department_check`
- `decision.criteriaChecks`: 건축물 용도, 300㎡ 면적 기준, 주류 판매, 위반건축물, 동일 장소 기존 업소, 소방완비증명서 기준별 판정
- `decision.requiredDocuments`: 영업신고 전 준비서류
- `decision.recommendedStepOrder`: 추천 진행 순서

`--all-combinations` 모드에서는 다음 필드가 추가된다.

- `recommendedRoutes`: 바로 가능성이 높은 조합
- `attentionRoutes`: 용도변경/담당부서/면적 확인이 필요한 조합
- `blockedRoutes`: 선택 조합 자체가 불가한 조합
- `combinations`: 일반음식점/휴게음식점/제과점 × 주류판매 여부 전체 판정
- `legalBasis`: 판정에 사용한 법령/기준 출처
