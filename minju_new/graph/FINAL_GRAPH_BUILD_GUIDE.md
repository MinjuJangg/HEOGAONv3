# Final Graph Build Guide

## 최종 사용 파일

- `minju/graph/output/final_graph/graph_nodes_high_precision.csv`
- `minju/graph/output/final_graph/graph_edges_high_precision.csv`
- `minju/graph/input/evidence/evidence_chunks_augmented.jsonl`
- `minju/graph/output/final_graph/all_raw_rechunk_rebuild_report.md`
- `minju/graph_only_scenarios/scenario_results_after_rechunk.md`
- `minju/graph_only_scenarios/scenario_results_after_rechunk.json`
- `minju/graph_only_scenarios/ten_scenario_full_answers.md`
- `minju/graph_only_scenarios/ten_scenario_full_answers.json`
- `minju/graph_only_scenarios/official_verification_after_rechunk.md`

## 최종 재생성 명령

```powershell
Copy-Item -LiteralPath "minju\graph\output\final_graph\graph_nodes_high_precision.before_all_raw_rechunk.csv" -Destination "minju\graph\output\final_graph\graph_nodes_high_precision.csv" -Force
Copy-Item -LiteralPath "minju\graph\output\final_graph\graph_edges_high_precision.before_all_raw_rechunk.csv" -Destination "minju\graph\output\final_graph\graph_edges_high_precision.csv" -Force
Copy-Item -LiteralPath "minju\graph\input\evidence\evidence_chunks_augmented.before_all_raw_rechunk.jsonl" -Destination "minju\graph\input\evidence\evidence_chunks_augmented.jsonl" -Force
python -X utf8 minju\graph\src\rechunk_all_evidence_and_rebuild_final_graph.py
python -X utf8 minju\graph_only_scenarios\extract_scenarios_after_rechunk.py
python -X utf8 minju\graph_only_scenarios\extract_ten_full_scenarios.py
```

## 생성 방식

1. 기존 최종 graph CSV와 evidence backup을 기준점으로 복구한다.
2. `evidence_chunks_augmented.jsonl`의 전체 민원 chunk를 읽는다.
3. gov24 민원 chunk의 제출서류/담당공무원 확인서류/신청서 섹션을 문서 단위로 원자화한다.
4. 기존 edge 중 긴 문장 전체가 `requires_document`로 들어간 noisy edge를 제거하고, 조건 문구가 있는 문서는 `conditional`로 보정한다.
5. 마포/강남/송파 공식 페이지에서 발표 시나리오 검증에 필요한 지역 source-backed chunk를 보강한다.
6. 음식점 창업, 도로점용, 옥외광고물 신고의 핵심 절차와 사전확인 edge를 추가한다.
7. 최종 결과는 전체 그래프에 저장하고, 시나리오 응답은 그래프 CSV만 읽어서 추출한다.

## 주요 관계

- `precedes`: 절차 순서
- `requires_permit`: 업종/조건이 요구하는 인허가
- `triggers`: 특정 조건이 추가 인허가를 유발
- `requires_document`: 인허가별 제출서류
- `requires_prerequisite`: 특정 서류/단계 전에 필요한 선행요건
- `needs_check`: 신청 전 확인해야 하는 사실 또는 담당공무원 확인사항
- `handled_by`: 제출/문의 담당 기능
- `maps_to`: 사용자 표현과 행정 업종의 매핑

## 현재 최종 그래프 크기

- nodes: 2,158
- edges: 3,546
- `requires_document`: 736
- `needs_check`: 243
- `precedes`: 24

## 주의

그래프에는 전체 민원 근거를 보존하기 때문에 조건부/특수 업종 서류도 포함된다. 사용자 응답 단계에서는 `condition_text`, `assertion_level`, 지역 source, 업종 조건을 보고 기본 제출서류와 조건부 제출서류를 분리해야 한다.
