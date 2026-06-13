from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
MINJU_ROOT = ROOT.parent
GRAPH_ROOT = MINJU_ROOT / "graph" / "output" / "final_graph"
EDGES_PATH = GRAPH_ROOT / "graph_edges_high_precision.csv"
OUT_JSON = ROOT / "scenario_results_after_rechunk.json"
OUT_MD = ROOT / "scenario_results_after_rechunk.md"


FOOD_PERMIT = "식품관련영업신고"
ROAD_PERMIT = "도로점용허가"
AD_PERMIT = "옥외광고물 등의 표시허가(신고)"
BUSINESS_REGISTRATION = "사업자등록 신청"


SCENARIOS = [
    {
        "scenario_id": "mapo_cafe_startup",
        "input": "마포구 카페 창업",
        "district": "마포구",
        "business_type": "휴게음식점영업",
        "permits": [FOOD_PERMIT, BUSINESS_REGISTRATION],
        "checks": [FOOD_PERMIT],
        "order_terms": ["주소", "건축물대장", "용도", "위생교육", "건강진단", "영업신고", "사업자등록"],
    },
    {
        "scenario_id": "gangnam_restaurant_road_occupation",
        "input": "강남구 일반음식점 + 도로점용",
        "district": "강남구",
        "business_type": "일반음식점영업",
        "permits": [FOOD_PERMIT, ROAD_PERMIT, BUSINESS_REGISTRATION],
        "checks": [FOOD_PERMIT, ROAD_PERMIT],
        "order_terms": ["주소", "건축물대장", "용도", "위생교육", "건강진단", "영업신고", "도로점용", "사업자등록"],
    },
    {
        "scenario_id": "songpa_outdoor_sign",
        "input": "송파구 간판 설치",
        "district": "송파구",
        "business_type": "간판 설치",
        "permits": [AD_PERMIT],
        "checks": [AD_PERMIT],
        "order_terms": ["간판", "옥외광고물", "표시허가", "허가·신고증"],
    },
]


LOCAL_DISTRICTS = ("마포구", "강남구", "송파구")
EXCLUDED_SCENARIO_DOCS = {
    "사업자등록증",
    "자금출처명세서",
}


CANONICAL_DOCS = [
    ("식품 영업 신고서/영업신고 신청서", ["식품 영업 신고서", "식품영업신고서", "영업신고 신청서"]),
    ("임대차계약서", ["임대차계약서", "건물 임대차계약서", "임대차계약서 또는 시설사용계약서"]),
    ("위생교육수료증", ["위생교육수료증", "위생교육 수료증", "교육이수증"]),
    ("건강진단결과서", ["건강진단결과서"]),
    ("신분증", ["신분증"]),
    ("상담일지", ["상담일지"]),
    ("안전시설등 완비증명서/소방완비증명서", ["안전시설등 완비증명서", "소방방화시설완비증명서", "소방완비증명서"]),
    ("LPG 검사필증/필증", ["LPG 필증", "LPG 검사필증", "액화석유가스 사용시설완성검사증명서"]),
    ("전기안전검사필증", ["전기안전검사필증"]),
    ("수질검사시험성적서", ["수질검사시험성적서", "먹는물 수질검사기관의 수질검사(시험)성적서"]),
    ("어린이놀이시설 검사합격증", ["어린이놀이시설 검사합격증", "어린이놀이시설 설치검사합격증"]),
    ("건물주 동의서 또는 신탁동의서", ["건물주 동의서 또는 신탁동의서"]),
    ("사업자등록 신청서", ["사업자등록신청서", "사업자등록 신청서"]),
    ("영업신고증", ["영업신고증"]),
    ("도로점용허가 신청서", ["도로점용허가 신청서"]),
    ("사업자등록증 사본", ["사업자등록증 사본"]),
    ("위치도", ["위치도"]),
    ("위치도 및 평면도", ["위치도 및 평면도"]),
    ("설계도면", ["설계도면"]),
    ("주요지하매설물 관리자의 의견서", ["주요지하매설물 관리자의 의견서"]),
    ("주요지하매설물의 사후관리계획", ["주요지하매설물의 사후관리계획"]),
    ("도로관리심의회 심의·조정 안전대책 서류", ["도로관리심의회 심의·조정 결과를 반영한 안전대책 서류"]),
    ("옥외광고물 표시 신청서", ["옥외광고물 표시 신청서", "옥외광고물 표시 신고 신청서", "옥외광고물등표시(변경)허가신청(신고)서"]),
    ("소유자/관리자 사용승낙서", ["소유자 또는 관리자의 사용승락 증명서류", "건물주 또는 관리자 승낙서"]),
    ("설치장소 주변 원색사진", ["설치장소의 주변 원색사진"]),
    ("원색사진 또는 원색도안", ["원색사진 또는 원색도안", "광고물 원색도안 또는 원색사진"]),
    ("광고물 형상·규격·구조·의장 설명서", ["광고물 등의 형상·규격·구조·의장 등에 관한 설명서"]),
    ("설계도서", ["설계도서"]),
    ("설계도서 또는 설명서", ["설계도서 또는 설명서"]),
    ("광고물관리심의위원회 심의관련서류", ["광고물관리심의위원회 심의관련서류"]),
    ("건물 구조안전 확인 서류", ["건물 구조안전 확인 서류"]),
]


OPTIONAL_KEYWORDS = [
    "해당",
    "경우",
    "대상",
    "LPG",
    "소방",
    "안전시설",
    "전기안전",
    "수질",
    "어린이",
    "위임",
    "법인",
    "국유",
    "도시철도",
    "수상",
    "유선",
    "도선",
    "굴착",
    "심의",
    "구조안전",
    "타인 소유",
    "건물주",
    "신탁",
]


def read_edges() -> list[dict[str, str]]:
    with EDGES_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def compact(text: str, limit: int = 220) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def source_matches_district(edge: dict[str, str], district: str) -> bool:
    source_blob = " ".join(
        [
            edge.get("title", ""),
            edge.get("source_title", ""),
            edge.get("source_url", ""),
            edge.get("chunk_id", ""),
        ]
    )
    for local in LOCAL_DISTRICTS:
        if local in source_blob and local != district:
            return False
    return True


def district_rank(edge: dict[str, str], district: str) -> int:
    source_blob = " ".join(
        [
            edge.get("title", ""),
            edge.get("source_title", ""),
            edge.get("source_url", ""),
            edge.get("chunk_id", ""),
        ]
    )
    return 0 if district in source_blob else 1


def canonical_doc(name: str) -> str:
    for canonical, aliases in CANONICAL_DOCS:
        if any(alias in name for alias in aliases):
            return canonical
    return name


def priority(edge: dict[str, str], district: str) -> tuple[int, int, int]:
    source_rank = {
        "manual_atomic_rechunk": 0,
        "gov24_parser": 1,
        "source_backed_seed": 2,
        "raw_atomic_rechunk": 3,
        "source_backed_core_flow": 4,
        "llm_claim": 5,
    }.get(edge.get("edge_source", ""), 9)
    condition_rank = 1 if edge.get("assertion_level") == "conditional" else 0
    return district_rank(edge, district), source_rank, condition_rank


def edge_payload(edge: dict[str, str]) -> dict[str, str]:
    return {
        "subject": edge["subject_name"],
        "object": edge["object_name"],
        "canonical_object": canonical_doc(edge["object_name"]),
        "predicate": edge["predicate"],
        "assertion_level": edge["assertion_level"],
        "condition_text": edge["condition_text"],
        "source_title": edge["title"],
        "source_url": edge["source_url"],
        "chunk_id": edge["chunk_id"],
        "evidence_text": compact(edge["evidence_text"]),
        "edge_source": edge["edge_source"],
    }


def is_conditional(edge: dict[str, str], canonical: str) -> bool:
    if edge.get("assertion_level") == "conditional":
        return True
    if edge.get("assertion_level") == "explicit" and not edge.get("condition_text"):
        return False
    blob = " ".join([canonical, edge.get("condition_text", ""), edge.get("object_name", "")])
    return any(keyword in blob for keyword in OPTIONAL_KEYWORDS)


def collect_documents(edges: list[dict[str, str]], permits: list[str], district: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    candidates = [
        edge
        for edge in edges
        if edge["predicate"] == "requires_document" and edge["subject_name"] in permits
        and source_matches_district(edge, district)
    ]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for edge in candidates:
        canonical = canonical_doc(edge["object_name"])
        if canonical in EXCLUDED_SCENARIO_DOCS:
            continue
        grouped[canonical].append(edge)

    required: list[dict[str, str]] = []
    conditional: list[dict[str, str]] = []
    for canonical, group in grouped.items():
        best = sorted(group, key=lambda edge: priority(edge, district))[0]
        payload = edge_payload(best)
        payload["canonical_object"] = canonical
        if is_conditional(best, canonical):
            conditional.append(payload)
        else:
            required.append(payload)

    required.sort(key=lambda row: row["canonical_object"])
    conditional.sort(key=lambda row: row["canonical_object"])
    return required, conditional


def collect_checks(edges: list[dict[str, str]], names: list[str], district: str) -> list[dict[str, str]]:
    result = []
    for edge in edges:
        if not source_matches_district(edge, district):
            continue
        if edge["predicate"] in {"needs_check", "raises_risk"} and edge["subject_name"] in names:
            result.append(edge_payload(edge))
    seen = set()
    unique = []
    for item in sorted(result, key=lambda row: row["canonical_object"]):
        key = (item["predicate"], item["canonical_object"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def collect_order(edges: list[dict[str, str]], terms: list[str]) -> list[dict[str, str]]:
    result = []
    for edge in edges:
        if edge["predicate"] != "precedes":
            continue
        blob = f"{edge['subject_name']} {edge['object_name']}"
        if any(term in blob for term in terms):
            result.append(edge_payload(edge))
    return result


def collect_routes(edges: list[dict[str, str]], names: list[str], district: str) -> list[dict[str, str]]:
    result = []
    names_set = set(names)
    for edge in edges:
        if not source_matches_district(edge, district):
            continue
        if edge["predicate"] == "handled_by" and (edge["subject_name"] in names_set or edge["object_name"] in names_set):
            result.append(edge_payload(edge))
    return result


def build_results() -> list[dict[str, Any]]:
    edges = read_edges()
    results = []
    for scenario in SCENARIOS:
        required, conditional = collect_documents(edges, scenario["permits"], scenario["district"])
        checks = collect_checks(edges, scenario["checks"], scenario["district"])
        order = collect_order(edges, scenario["order_terms"])
        routes = collect_routes(edges, scenario["permits"] + scenario["checks"], scenario["district"])
        results.append(
            {
                **scenario,
                "required_documents": required,
                "conditional_documents": conditional,
                "checks_and_risks": checks,
                "procedure_order": order,
                "submission_routes": routes,
            }
        )
    return results


def write_markdown(results: list[dict[str, Any]]) -> None:
    lines = [
        "# Scenario Results After Raw Rechunk",
        "",
        "최종 graph_edges_high_precision.csv만 읽어서 추출한 결과입니다. 기본 제출서류와 조건부 제출서류를 분리했습니다.",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"## {result['input']}",
                "",
                f"- district: {result['district']}",
                f"- resolved_type: {result['business_type']}",
                f"- permits: {', '.join(result['permits'])}",
                "",
                "### 기본 제출서류",
            ]
        )
        for doc in result["required_documents"]:
            lines.append(f"- {doc['canonical_object']} <- {doc['subject']} [{doc['source_title']} / {doc['edge_source']}]")
        lines.extend(["", "### 조건부/분기 제출서류"])
        for doc in result["conditional_documents"]:
            cond = f" / 조건: {compact(doc['condition_text'], 120)}" if doc["condition_text"] else ""
            lines.append(f"- {doc['canonical_object']} <- {doc['subject']} [{doc['source_title']} / {doc['edge_source']}]{cond}")
        lines.extend(["", "### 사전 확인/리스크"])
        for check in result["checks_and_risks"]:
            cond = f" / {compact(check['condition_text'], 120)}" if check["condition_text"] else ""
            lines.append(f"- {check['predicate']} {check['subject']} -> {check['canonical_object']}{cond}")
        lines.extend(["", "### 절차 순서"])
        for step in result["procedure_order"]:
            lines.append(f"- {step['subject']} -> {step['object']}")
        lines.extend(["", "### 담당 기능"])
        if not result["submission_routes"]:
            lines.append("- 그래프에 담당 기능 edge 없음")
        for route in result["submission_routes"]:
            lines.append(f"- {route['subject']} -> {route['object']}")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    results = build_results()
    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(results)
    for result in results:
        print(
            result["scenario_id"],
            "required",
            len(result["required_documents"]),
            "conditional",
            len(result["conditional_documents"]),
            "checks",
            len(result["checks_and_risks"]),
            "order",
            len(result["procedure_order"]),
        )
    print(f"json={OUT_JSON}")
    print(f"markdown={OUT_MD}")


if __name__ == "__main__":
    main()
