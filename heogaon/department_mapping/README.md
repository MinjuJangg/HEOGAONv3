# Seoul Department Mapping DB

서울 25개 자치구의 실제 담당 부서명을 그래프 결과에 붙이기 위한 별도 매핑 DB입니다.
최종 그래프는 절차, 서류, 선행조건, 인허가 관계를 설명하고, 이 DB는 사용자가 선택한 지역에 맞는 실제 구청 부서명을 찾아줍니다.

## 범위

- 서울 25개 자치구
- 창업/인허가 처리에 필요한 로컬 업무 10개
- 총 250개 매핑 행
- 모든 행은 공식 구청 또는 공식 기관 출처 URL을 포함합니다.
- 서울 25개 자치구 구청 대표 주소와 위도/경도 좌표를 포함합니다.
- 사업자등록·소방필증처럼 사업장 주소로 관할기관이 갈리는 업무는 `office_location_scope`에 주소 기반 관할임을 별도 표시합니다.

## 산출물

- `seoul_districts.csv`: 서울 25개 자치구 코드, 이름, 공식 홈페이지
- `seoul_office_locations.csv`: 서울 25개 자치구 구청 대표 주소, 우편번호, 위도/경도
- `department_functions.csv`: 최종 그래프의 담당 기능 분류
- `local_department_tasks.csv`: 실제 민원 업무 단위 task
- `seoul_department_mapping.csv`: 자치구별 실제 담당 부서 매핑 및 구청 대표 위치
- `source_index.csv`: 사용한 공식 출처 목록
- `seoul_department_mapping.sqlite`: 서비스에서 바로 조회할 SQLite DB
- `mapping_build_summary.json`: 생성 결과 요약
- `lookup_department.py`: 매핑 조회용 CLI

## department_mapping 필드

- `district_code`: 자치구 코드
- `district_name`: 자치구명
- `graph_function_key`: 그래프의 담당 기능 키
- `local_task_key`: 실제 민원 업무 키
- `local_task_label`: 실제 민원 업무명
- `actual_department_name`: 실제 담당 부서명
- `actual_team_name`: 실제 담당 팀명
- `phone`: 대표 또는 업무 연락처
- `jurisdiction_level`: 관할 수준
- `source_url`: 공식 출처 URL
- `source_title`: 공식 출처명
- `evidence_text`: 출처에서 확인한 근거 문구
- `last_verified_date`: 생성/확인일
- `office_name`: 위치 기준 기관명
- `office_address`: 위치 기준 주소
- `office_postal_code`: 우편번호
- `office_latitude`: 위도
- `office_longitude`: 경도
- `office_location_scope`: 위치 기준 범위
- `office_location_source_url`: 위치 출처 URL
- `office_location_source_title`: 위치 출처명
- `office_geocode_source`: 좌표 생성 방식
- `office_geocode_status`: 좌표 생성 상태
- `office_location_last_verified_date`: 위치 확인일

내부 판정용 보조 컬럼은 최종 산출물과 SQLite DB에 저장하지 않습니다.

## 재생성

```powershell
python heogaon\department_mapping\build_department_mapping_db.py
```

Kakao Local API 키가 있으면 아래처럼 환경변수로 넣은 뒤 재생성하면 주소 기준 좌표가 API 결과로 갱신됩니다.

```powershell
$env:KAKAO_REST_API_KEY="..."
python heogaon\department_mapping\build_department_mapping_db.py
```

API 키가 없으면 스크립트에 포함된 구청 좌표 스냅샷을 사용합니다. 구청 주소 출처는 서울특별시 자치구 공식 안내 페이지입니다.
사업장 주소 기준 업무는 실제 점포 주소를 받은 뒤 관할 세무서/소방서 API 또는 별도 관할 DB로 풀어야 하므로 좌표를 임의로 저장하지 않습니다.

## 조회 예시

```powershell
python heogaon\department_mapping\lookup_department.py --district-code 11440 --task food_business_report
python heogaon\department_mapping\lookup_department.py --district-code 11710 --task outdoor_ad_report
python heogaon\department_mapping\lookup_department.py --district-code 11680 --task road_occupation_permit
```

## 서비스 연결 방식

서비스에서는 최종 그래프가 반환한 `graph_function_key` 또는 절차 단계의 `local_task_key`와 사용자의 자치구를 조인해서 `seoul_department_mapping`을 조회하면 됩니다.
그래프는 “무슨 절차와 서류가 필요한지”를 설명하고, 이 DB는 “해당 지역에서 어느 부서로 연결할지”를 담당합니다.
