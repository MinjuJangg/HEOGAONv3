# Final Service Graph Manifest

## Build Inputs

- base_nodes: C:\Users\SSAFY\Desktop\New project 2\minju\graph\input\base_graph\graph_nodes_high_precision.csv
- base_edges: C:\Users\SSAFY\Desktop\New project 2\minju\graph\input\base_graph\graph_edges_high_precision.csv
- evidence: C:\Users\SSAFY\Desktop\New project 2\minju\graph\input\evidence\evidence_chunks_augmented.jsonl
- attach_evidence: True
- evidence_min_score: 6
- require_evidence_for_seeds: True
- seed_files:
  - C:\Users\SSAFY\Desktop\New project 2\minju\graph\seeds\core_route_seed.yaml
  - C:\Users\SSAFY\Desktop\New project 2\minju\graph\seeds\core_document_check_seed.yaml
  - C:\Users\SSAFY\Desktop\New project 2\minju\graph\seeds\core_department_seed.yaml
  - C:\Users\SSAFY\Desktop\New project 2\minju\graph\seeds\core_procedure_seed.yaml
  - C:\Users\SSAFY\Desktop\New project 2\minju\graph\seeds\core_before_prerequisite_seed.yaml

## Build Method

1. Load the existing high precision graph CSV files.
2. Parse service seed claims as candidate relations for route, document, check, department function, and procedure order.
3. Attach the best matching official/raw evidence chunk to each seed claim when the evidence score is strong enough.
4. When require_evidence_for_seeds is true, discard seed claims that do not receive an evidence match.
5. Validate every remaining seed claim against the ontology predicate/type rules.
6. Build seed nodes and edges with the same stable node id logic as the original graph builder.
7. Merge seed graph into the existing graph and de-duplicate by edge id plus relation tuple.

## Counts

- base_nodes: 2008
- base_edges: 3348
- valid_seed_claims: 91
- invalid_seed_claims: 0
- seed_nodes: 85
- seed_edges: 91
- final_nodes: 2069
- final_edges: 3429
- added_nodes: 61
- added_edges: 81

## Final Node Types

- evidence_chunk: 461
- document: 449
- legal_basis: 278
- permit_service: 249
- check_item: 213
- condition_module: 174
- risk_flag: 112
- source_document: 82
- procedure_step: 26
- admin_business_type: 9
- business_alias: 9
- department_function: 7

## Final Edge Predicates

- has_source: 1467
- requires_document: 661
- supported_by: 461
- based_on: 310
- needs_check: 215
- triggers: 135
- raises_risk: 111
- requires_prerequisite: 24
- precedes: 16
- handled_by: 12
- maps_to: 9
- requires_permit: 8

## Final Edge Sources

- derived_grounding: 1928
- llm_claim: 1384
- source_backed_seed: 81
- gov24_parser: 20
- rule_seed: 16

## Notes

- Regional real department names are intentionally not hard-coded in this graph. The graph stores reusable department functions such as 식품위생 업무 and 옥외광고물 관리 업무.
- Local department name mapping should be applied as a separate lookup layer when a district is selected.
