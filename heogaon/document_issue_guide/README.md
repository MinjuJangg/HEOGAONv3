# Document Issue Guide

최종 그래프의 `requires_document`, `requires_prerequisite`, `handled_by` 관계를 서비스에서 바로 조회할 수 있게 정리한 문서/제출처 레이어입니다.

그래프 원본은 "무엇이 무엇을 요구하는가"를 설명하고, 이 디렉터리의 산출물은 사용자가 "이 서류를 어디서 준비하고 어디에 제출하는가"를 볼 수 있게 만듭니다.

## 입력

- `heogaon/graph/output/final_graph/graph_edges_high_precision.csv`
- `heogaon/graph/output/final_graph/graph_nodes_high_precision.csv`
- `heogaon/department_mapping/local_department_tasks.csv`

## 산출물

- `all_document_issue_guide.csv`
  - 최종 그래프의 전체 문서 노드 기준 문서 카탈로그
  - 문서별 발급/준비처, 신청 채널, 제출처, 제출처 local task key, 사용되는 인허가/절차, 선행요건 요약 포함
- `all_permit_submission_documents.csv`
  - 최종 그래프의 `requires_document` 661개 관계 전체
  - 인허가/절차별 제출서류를 한 줄씩 펼친 전체 제출서류 테이블
- `food_permit_submission_documents.csv`
  - 요식업 창업 데모에서 바로 쓰기 좋은 제출서류 관계 테이블
  - 식품영업신고, 사업자등록, 소방, 간판, 도로점용, 통신판매 등 핵심 로컬 태스크 중심
- `document_issue_guide.csv`
  - 발표/시연용 핵심 서류 18개 요약판
  - UI에서 가장 먼저 보여줄 사람 친화적인 압축 테이블
- `permit_document_requirements.csv`
  - 최종 그래프의 `requires_document` 원본 관계 전체
- `document_prerequisites.csv`
  - 최종 그래프의 `requires_prerequisite` 원본 관계 전체
- `submission_routes.csv`
  - 최종 그래프의 `handled_by` 원본 관계 전체
- `document_issue_guide.sqlite`
  - 위 CSV들을 그대로 담은 SQLite DB
- `document_issue_guide_summary.json`
  - 생성 결과 요약
- `lookup_document_issue.py`
  - 문서명 기준 조회 CLI

## 서비스 사용 방식

1. 사용자가 업종/상황을 입력하면 그래프에서 필요한 인허가와 절차를 찾습니다.
2. `all_permit_submission_documents` 또는 `food_permit_submission_documents`에서 해당 인허가의 제출서류를 가져옵니다.
3. 문서별 발급/준비처는 `all_document_issue_guide`에서 붙입니다.
4. `submit_to_local_task_key`가 있으면 `heogaon/department_mapping/seoul_department_mapping.sqlite`와 조인해 서울 자치구별 실제 부서명을 붙입니다.
5. UI에서 너무 많은 문서가 한 번에 나오면 `document_issue_guide.csv`의 18개 핵심 요약판을 먼저 보여주고, 상세 버튼에서 전체판을 열면 됩니다.

## 재생성

```powershell
python heogaon\document_issue_guide\build_document_issue_guide.py
```

## 조회 예시

```powershell
python heogaon\document_issue_guide\lookup_document_issue.py --document 위생교육 --district-code 11440
python heogaon\document_issue_guide\lookup_document_issue.py --document 도로점용 --district-code 11680
python heogaon\document_issue_guide\lookup_document_issue.py --document 임대차계약서
```

`lookup_document_issue.py`는 기본적으로 전체 문서 카탈로그인 `all_document_issue_guide`를 조회합니다. 핵심 18개 요약판만 보고 싶으면 `--core`를 붙입니다.

## 주의

이 레이어는 최종 그래프와 evidence chunk를 기반으로 만든 서비스용 정규화 산출물입니다. 자치구별 실제 부서명과 연락처는 `department_mapping` DB에서 조인합니다.
