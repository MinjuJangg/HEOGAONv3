# All Raw Rechunk Rebuild Report

현재 minju evidence 전체를 대상으로 gov24 민원 서류 섹션, 담당공무원 확인 서류, 서비스 개요 신청서, 지역 공식 보강 source를 atomic chunk/edge로 다시 반영했습니다.

## Counts
- final_nodes: 2158
- final_edges: 3546
- added_edges: 122
- evidence_chunks_total: 4227

## Atomic Rechunk Stats
- application_form_edges: 6
- official_check_edges: 28
- required_document_edges: 16
- skipped_noisy_required_item: 2

## Cleanup Stats
- condition_backfilled: 181
- removed_generic_requires_document: 4
- removed_noisy_long_document: 1

## Predicate Counts
- based_on: 310
- handled_by: 12
- has_source: 1467
- maps_to: 11
- needs_check: 243
- precedes: 24
- raises_risk: 111
- requires_document: 736
- requires_permit: 10
- requires_prerequisite: 24
- supported_by: 461
- triggers: 137

## Edge Source Counts
- derived_grounding: 1928
- gov24_parser: 20
- llm_claim: 1379
- manual_atomic_rechunk: 58
- raw_atomic_rechunk: 50
- rule_seed: 16
- source_backed_core_flow: 14
- source_backed_seed: 81
