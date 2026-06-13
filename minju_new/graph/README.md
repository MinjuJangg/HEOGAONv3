# Minju Final Graph Package

이 폴더는 발표용 최종 그래프를 다시 만들기 위한 최소 패키지입니다.
프론트, 라우터, 사례 DB, raw 원문 복사본은 넣지 않았고, 기존 그래프 생성 코드와 이번에 추가한 seed 보강 방식만 남겼습니다.

## 폴더 구조

- `src/`: 기존 그래프 생성 파이프라인 코드와 seed 보강 코드
- `ontology/`: 그래프 노드 타입, 관계 타입, 기본 seed가 들어 있는 ontology
- `seeds/`: 서비스에 필요한 route, 절차, 부서 기능, 선행요건 후보 seed
- `input/base_graph/`: 기존 high precision graph 생성 방식으로 만든 seed 보강 전 base graph
- `input/evidence/`: source-backed seed 매칭에 쓰는 evidence chunks
- `output/final_graph/`: 최종 graph CSV와 검증 리포트

## 지금 최종 그래프

- nodes: 2069
- edges: 3429
- status: PASS
- requires_document: 661
- requires_prerequisite: 24
- precedes: 16
- handled_by: 12
- needs_check: 215
- source_backed_seed: 81
- rule_seed: 16

## 빠른 재빌드

발표 직전에는 아래 두 명령만 실행하면 됩니다.

```powershell
cd "C:\Users\SSAFY\Desktop\New project 2\minju\graph"
python .\src\augment_graph_with_seed_claims.py
python .\src\validate_final_graph_for_demo.py
```

산출물은 `output/final_graph/graph_nodes_high_precision.csv`와 `output/final_graph/graph_edges_high_precision.csv`입니다.

## 전체 생성 흐름

원래 그래프 생성 방식은 아래 흐름입니다.

1. `prepare_evidence_chunks.py`: `data/processed`의 법령, EasyLaw, Gov24 데이터를 evidence chunk로 정리
2. `prepare_claim_extraction_queue.py`: 음식점 창업과 관련된 chunk만 claim 추출 queue로 필터링
3. `run_llm_claim_extraction.py`: LLM으로 `requires_document`, `needs_check`, `based_on`, `triggers` 등 claim 추출
4. `repair_invalid_claims.py`: 타입 오류, 낮은 품질 claim 보정
5. `canonicalize_gov24_food_business.py`: Gov24 식품관련영업신고 서류명을 canonical하게 보정
6. `build_graph_from_claims.py`: claim과 ontology seed를 stable node/edge CSV로 변환
7. `augment_graph_with_seed_claims.py`: 서비스 후보 seed를 evidence와 매칭하고, evidence가 붙은 seed만 최종 graph로 병합
8. `validate_final_graph_for_demo.py`: 근거 없는 상세 seed가 섞이지 않았는지 검증

## 이번에 추가한 방식

이번 보강은 `seeds/*.yaml`를 사실 출처로 쓰지 않습니다. seed는 후보 관계 목록이고, `input/evidence/evidence_chunks_augmented.jsonl`에서 충분히 강한 evidence match가 붙은 후보만 최종 graph에 들어갑니다.

사용자 대화에서 나온 상세 서류 목록을 기준으로 만든 `detail_prerequisite_document_seed.yaml`는 제거했습니다. 현재 최종 그래프에는 해당 사용자 발화 기반 상세 seed가 들어가지 않습니다.

최종 그래프에서 seed 보강분은 `source_backed_seed` 81개만 추가 반영됐고, 모두 `chunk_id`와 `source_document_id`를 갖습니다. 남아 있는 `rule_seed` 16개는 base graph 단계의 ontology routing seed입니다.

## 발표 때 말할 핵심

`ontology/cafe_restaurant_mvp.yaml` 하나가 최종 그래프가 아닙니다. 최종 그래프는 기존 raw/evidence 기반 claim graph에, evidence chunk로 다시 확인된 seed 후보만 병합해서 만든 CSV 산출물입니다.

지역별 실제 과명은 core graph에 박지 않았습니다. 그래프에는 `식품위생 업무`, `건축물 용도 업무`, `옥외광고물 관리 업무`, `도로점용 업무`, `소방 안전 업무` 같은 기능부서를 넣고, 실제 구청 과명은 지역 선택 이후 별도 매핑 레이어에서 붙이는 구조가 맞습니다.
