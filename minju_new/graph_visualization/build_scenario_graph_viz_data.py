from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
MINJU_ROOT = ROOT.parent
GRAPH_ROOT = MINJU_ROOT / "graph" / "output" / "final_graph"
SCENARIO_ROOT = MINJU_ROOT / "graph_only_scenarios"

NODES_PATH = GRAPH_ROOT / "graph_nodes_high_precision.csv"
EDGES_PATH = GRAPH_ROOT / "graph_edges_high_precision.csv"
SCENARIOS_PATH = SCENARIO_ROOT / "ten_scenario_full_answers.json"
OUT_PATH = ROOT / "scenario_graph_viz_data.js"


NODE_TYPE_META = {
    "business_alias": {"label": "입력 표현", "color": "#6b7280"},
    "admin_business_type": {"label": "행정 업종", "color": "#2563eb"},
    "permit_service": {"label": "인허가", "color": "#dc2626"},
    "document": {"label": "서류", "color": "#16a34a"},
    "check_item": {"label": "사전 확인", "color": "#d97706"},
    "procedure_step": {"label": "절차", "color": "#7c3aed"},
    "department_function": {"label": "담당 기능", "color": "#0891b2"},
    "condition_module": {"label": "조건", "color": "#be185d"},
    "legal_basis": {"label": "법령/근거", "color": "#475569"},
    "source_document": {"label": "source", "color": "#94a3b8"},
}

CATEGORY_META = {
    "flow": {"label": "절차 흐름(PRECEDES)", "color": "#111827"},
    "permit": {"label": "인허가 판단", "color": "#4f46e5"},
    "required": {"label": "필수 제출서류", "color": "#2563eb"},
    "triggered": {"label": "조건으로 추가된 서류", "color": "#f97316"},
    "conditional": {"label": "조건부 확인서류", "color": "#a855f7"},
    "check": {"label": "사전 확인/리스크", "color": "#16a34a"},
    "prerequisite": {"label": "선행요건", "color": "#e11d48"},
    "route": {"label": "제출/문의 담당", "color": "#0891b2"},
}

FOOD_PERMIT = "식품관련영업신고"
ROAD_PERMIT = "도로점용허가"
AD_PERMIT = "옥외광고물 등의 표시허가(신고)"
BUSINESS_REGISTRATION = "사업자등록 신청"
SUCCESSION_PERMIT = "영업자 지위승계 신고"
MAIL_ORDER_PERMIT = "통신판매업신고"

CORE_FOOD_FLOW = [
    ("주소 확정", "건축물대장 확인"),
    ("건축물대장 확인", "용도 및 위반건축물 확인"),
    ("용도 및 위반건축물 확인", "위생교육 및 건강진단 준비"),
    ("위생교육 및 건강진단 준비", "영업신고 신청"),
    ("영업신고 신청", "영업신고증 발급"),
    ("영업신고증 발급", "사업자등록 신청"),
    ("사업자등록 신청", "사업자등록증 발급"),
]

LIQUOR_FLOW = [
    ("주류 판매 여부 확인", "일반음식점 전환 여부 확인"),
    ("일반음식점 전환 여부 확인", "영업신고 신청"),
]

FIRE_FLOW = [
    ("안전시설등 완비증명서 필요 여부 확인", "영업신고 신청"),
]

ROAD_FLOW = [
    ("도로점용허가 대상 확인", "도로점용허가 신청"),
]

AD_FLOW = [
    ("간판 규격 위치 표시방법 확인", "옥외광고물 표시허가 신고 신청"),
    ("옥외광고물 표시허가 신고 신청", "수수료 납부 및 허가·신고증 발부"),
]

BUSINESS_ONLY_FLOW = [
    ("사업자등록 신청", "사업자등록증 발급"),
]

SUCCESSION_FLOW = [
    ("기존 업소 행정처분 이력 확인", "건물 소유자와 관리인 권한 확인"),
]

FLOW_EDGE_SOURCE_RANK = {
    "source_backed_core_flow": 0,
    "source_backed_seed": 1,
    "rule_seed": 2,
    "manual_atomic_rechunk": 3,
    "raw_atomic_rechunk": 4,
}


def stable_int(*parts: Any) -> int:
    payload = "\u241f".join(str(part or "") for part in parts)
    return int(hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12], 16)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def compact(text: str, limit: int = 360) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def scenario_blob(scenario: dict[str, Any]) -> str:
    return " ".join(
        [
            scenario.get("input", ""),
            scenario.get("business_type", ""),
            *scenario.get("permits", []),
            *scenario.get("condition_terms", []),
            *scenario.get("force_documents", []),
        ]
    )


def pick_precedes_edge(edges: list[dict[str, str]], subject: str, obj: str) -> dict[str, str] | None:
    candidates = [
        edge
        for edge in edges
        if edge["predicate"] == "precedes"
        and edge["subject_name"] == subject
        and edge["object_name"] == obj
        and edge.get("edge_source") in FLOW_EDGE_SOURCE_RANK
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda edge: FLOW_EDGE_SOURCE_RANK.get(edge.get("edge_source", ""), 9))[0]


def scenario_flow_pairs(scenario: dict[str, Any]) -> list[tuple[str, str]]:
    permits = set(scenario.get("permits", []))
    blob = scenario_blob(scenario)
    pairs: list[tuple[str, str]] = []

    if FOOD_PERMIT in permits:
        pairs.extend(CORE_FOOD_FLOW)
        if any(term in blob for term in ["주류", "와인", "wine", "호프", "펍"]):
            pairs.extend(LIQUOR_FLOW)
        if any(term in blob for term in ["소방", "안전시설", "지하층", "지하 66", "지하66", "66㎡", "100㎡"]):
            pairs.extend(FIRE_FLOW)

    if ROAD_PERMIT in permits:
        pairs.extend(ROAD_FLOW)

    if AD_PERMIT in permits:
        pairs.extend(AD_FLOW)

    if BUSINESS_REGISTRATION in permits and FOOD_PERMIT not in permits:
        pairs.extend(BUSINESS_ONLY_FLOW)

    if SUCCESSION_PERMIT in permits:
        pairs.extend(SUCCESSION_FLOW)

    seen = set()
    unique = []
    for pair in pairs:
        if pair not in seen:
            seen.add(pair)
            unique.append(pair)
    return unique


def collect_flow_edges(scenario: dict[str, Any], edges: list[dict[str, str]]) -> list[dict[str, str]]:
    result = []
    for subject, obj in scenario_flow_pairs(scenario):
        edge = pick_precedes_edge(edges, subject, obj)
        if edge:
            result.append(edge)
    return result


def flow_timeline(flow_edges: list[dict[str, str]]) -> list[str]:
    result = []
    seen = set()
    for edge in flow_edges:
        subject = edge["subject_name"]
        obj = edge["object_name"]
        if subject not in seen and obj in seen:
            result.insert(result.index(obj), subject)
            seen.add(subject)
            continue
        for name in [subject, obj]:
            if name in seen:
                continue
            seen.add(name)
            result.append(name)
    return result


def flow_anchor(flow_edges: list[dict[str, str]], text: str) -> str | None:
    names = flow_timeline(flow_edges)
    if not names:
        return None
    if any(term in text for term in ["도로", "점용", "테라스"]):
        for name in names:
            if "도로점용허가" in name:
                return name
    if any(term in text for term in ["옥외광고물", "간판", "광고물", "입간판", "배너"]):
        for name in names:
            if "옥외광고물" in name or "간판" in name:
                return name
    if any(term in text for term in ["사업자등록", "세무", "홈택스"]):
        for name in names:
            if "사업자등록 신청" in name:
                return name
    if any(term in text for term in ["영업신고", "식품관련", "위생", "건강진단", "임대차", "신분증", "LPG", "소방", "안전시설"]):
        for name in names:
            if "영업신고 신청" in name:
                return name
    if any(term in text for term in ["건축물", "용도", "위반건축물", "주소"]):
        for name in names:
            if "건축물" in name or "용도" in name:
                return name
    return names[len(names) // 2]


def node_positions(nodes: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    type_counts = Counter(node["node_type"] for node in nodes)
    ordered_types = [name for name, _ in type_counts.most_common()]
    center_radius = 900
    centers: dict[str, tuple[float, float]] = {}
    fixed = {
        "permit_service": (-170, -40),
        "admin_business_type": (-720, -80),
        "business_alias": (-1050, -240),
        "document": (540, 20),
        "check_item": (-40, 610),
        "procedure_step": (-120, -650),
        "department_function": (860, -460),
        "condition_module": (-760, 500),
        "legal_basis": (720, 590),
        "source_document": (1120, 250),
    }
    for index, node_type in enumerate(ordered_types):
        if node_type in fixed:
            centers[node_type] = fixed[node_type]
        else:
            angle = 2 * math.pi * index / max(1, len(ordered_types))
            centers[node_type] = (math.cos(angle) * center_radius, math.sin(angle) * center_radius)

    per_type_seen: defaultdict[str, int] = defaultdict(int)
    result: dict[str, dict[str, float]] = {}
    for node in nodes:
        node_type = node["node_type"]
        i = per_type_seen[node_type]
        per_type_seen[node_type] += 1
        cx, cy = centers[node_type]
        angle = (stable_int(node["node_id"], node["name"]) % 6283) / 1000
        ring = 18 + 9.5 * math.sqrt(i + 1)
        jitter = (stable_int("jitter", node["node_id"]) % 100) / 100
        x = cx + math.cos(angle + i * 0.23) * ring * (0.85 + jitter * 0.35)
        y = cy + math.sin(angle + i * 0.19) * ring * (0.85 + jitter * 0.35)
        result[node["node_id"]] = {"x": round(x, 2), "y": round(y, 2)}
    return result


def edge_indexes(edges: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str, str], list[dict[str, str]]], dict[tuple[str, str, str], list[dict[str, str]]]]:
    by_chunk: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    by_plain: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for edge in edges:
        by_chunk[(edge["predicate"], edge["subject_name"], edge["object_name"], edge.get("chunk_id", ""))].append(edge)
        by_plain[(edge["predicate"], edge["subject_name"], edge["object_name"])].append(edge)
    return by_chunk, by_plain


def pick_edge(
    by_chunk: dict[tuple[str, str, str, str], list[dict[str, str]]],
    by_plain: dict[tuple[str, str, str], list[dict[str, str]]],
    predicate: str,
    subject: str,
    obj: str,
    chunk_id: str = "",
) -> dict[str, str] | None:
    if chunk_id:
        exact = by_chunk.get((predicate, subject, obj, chunk_id))
        if exact:
            return exact[0]
    plain = by_plain.get((predicate, subject, obj))
    if plain:
        return plain[0]
    return None


def edge_payload(edge: dict[str, str]) -> dict[str, str]:
    return {
        "id": edge["edge_id"],
        "source": edge["source_node_id"],
        "target": edge["target_node_id"],
        "predicate": edge["predicate"],
        "subject": edge["subject_name"],
        "object": edge["object_name"],
        "subjectType": edge["subject_type"],
        "objectType": edge["object_type"],
        "assertionLevel": edge["assertion_level"],
        "edgeSource": edge["edge_source"],
        "reviewStatus": edge["review_status"],
        "conditionText": compact(edge["condition_text"], 500),
        "evidenceText": compact(edge["evidence_text"], 700),
        "sourceTitle": edge["title"],
        "sourceUrl": edge["source_url"],
        "sectionPath": edge["section_path"],
        "chunkId": edge["chunk_id"],
    }


def match_doc_edges(
    scenario: dict[str, Any],
    by_chunk: dict[tuple[str, str, str, str], list[dict[str, str]]],
    by_plain: dict[tuple[str, str, str], list[dict[str, str]]],
) -> tuple[dict[str, list[str]], dict[str, str]]:
    used: dict[str, list[str]] = {key: [] for key in CATEGORY_META}
    edge_labels: dict[str, str] = {}

    for category, key in [("required", "required_documents"), ("triggered", "triggered_documents"), ("conditional", "conditional_documents")]:
        for doc in scenario.get(key, []):
            edge = pick_edge(by_chunk, by_plain, "requires_document", doc["subject"], doc["object"], doc.get("chunk_id", ""))
            if edge:
                used[category].append(edge["edge_id"])
                edge_labels[edge["edge_id"]] = doc["canonical_object"]

    for item in scenario.get("checks_and_risks", []):
        edge = pick_edge(by_chunk, by_plain, item["predicate"], item["subject"], item["object"], item.get("chunk_id", ""))
        if edge:
            used["check"].append(edge["edge_id"])
            edge_labels[edge["edge_id"]] = item["canonical_object"]

    for item in scenario.get("prerequisites", []):
        edge = pick_edge(by_chunk, by_plain, "requires_prerequisite", item["subject"], item["prerequisite"])
        if edge:
            used["prerequisite"].append(edge["edge_id"])
            edge_labels[edge["edge_id"]] = f"{item['subject']} 전에 {item['prerequisite']}"

    for item in scenario.get("submission_routes", []):
        edge = pick_edge(by_chunk, by_plain, "handled_by", item["subject"], item["object"], item.get("chunk_id", ""))
        if edge:
            used["route"].append(edge["edge_id"])
            edge_labels[edge["edge_id"]] = item["object"]

    return used, edge_labels


def match_permit_edges(
    scenario: dict[str, Any],
    edges: list[dict[str, str]],
    used: dict[str, list[str]],
    edge_labels: dict[str, str],
) -> None:
    scenario_blob = " ".join([scenario["input"], scenario["business_type"], *scenario.get("condition_terms", [])])
    for edge in edges:
        if edge["predicate"] == "requires_permit" and edge["object_name"] in scenario["permits"]:
            if edge["subject_name"] == scenario["business_type"] or edge["subject_name"] in scenario_blob:
                used["permit"].append(edge["edge_id"])
                edge_labels[edge["edge_id"]] = edge["object_name"]
        elif edge["predicate"] == "triggers" and edge["object_name"] in scenario["permits"]:
            if edge["subject_name"] in scenario_blob or any(term in edge["subject_name"] for term in scenario.get("condition_terms", [])):
                used["permit"].append(edge["edge_id"])
                edge_labels[edge["edge_id"]] = edge["object_name"]


def scenario_node_positions(
    used: dict[str, list[str]],
    flow_edges: list[dict[str, str]],
    edge_by_id: dict[str, dict[str, str]],
) -> dict[str, dict[str, float]]:
    flow_names = flow_timeline(flow_edges)
    if not flow_names:
        return {}

    step_gap = 250
    start_x = -((len(flow_names) - 1) * step_gap) / 2
    name_x = {name: start_x + index * step_gap for index, name in enumerate(flow_names)}
    positions: dict[str, dict[str, float]] = {}

    for edge in flow_edges:
        positions[edge["source_node_id"]] = {"x": round(name_x[edge["subject_name"]], 2), "y": 0}
        positions[edge["target_node_id"]] = {"x": round(name_x[edge["object_name"]], 2), "y": 0}

    category_y = {
        "permit": -240,
        "route": -380,
        "required": 230,
        "triggered": 315,
        "conditional": 410,
        "check": 520,
        "prerequisite": 610,
    }
    bucket_counts: defaultdict[tuple[str, int], int] = defaultdict(int)

    for category, edge_ids in used.items():
        if category == "flow":
            continue
        base_y = category_y.get(category, 320)
        for edge_id in edge_ids:
            edge = edge_by_id.get(edge_id)
            if not edge:
                continue
            text = " ".join([edge["subject_name"], edge["object_name"], edge.get("condition_text", "")])
            anchor_name = flow_anchor(flow_edges, text)
            anchor_x = name_x.get(anchor_name or "", 0)
            slot = bucket_counts[(anchor_name or "center", base_y)]
            bucket_counts[(anchor_name or "center", base_y)] += 1
            x_offset = ((slot % 5) - 2) * 74
            y_offset = (slot // 5) * 58

            source_already = edge["source_node_id"] in positions
            target_already = edge["target_node_id"] in positions
            if not source_already:
                positions[edge["source_node_id"]] = {
                    "x": round(anchor_x + x_offset - 36, 2),
                    "y": round(base_y + y_offset, 2),
                }
            if not target_already:
                positions[edge["target_node_id"]] = {
                    "x": round(anchor_x + x_offset + 36, 2),
                    "y": round(base_y + y_offset, 2),
                }

    return positions


def build_scenarios(edges: list[dict[str, str]], scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_chunk, by_plain = edge_indexes(edges)
    edge_by_id = {edge["edge_id"]: edge for edge in edges}
    result = []
    for scenario in scenarios:
        used, edge_labels = match_doc_edges(scenario, by_chunk, by_plain)
        flow_edges = collect_flow_edges(scenario, edges)
        for edge in flow_edges:
            used["flow"].append(edge["edge_id"])
            edge_labels[edge["edge_id"]] = f"{edge['subject_name']} → {edge['object_name']}"
        match_permit_edges(scenario, edges, used, edge_labels)

        used_edge_ids = []
        seen = set()
        for category in CATEGORY_META:
            deduped = []
            for edge_id in used[category]:
                if edge_id in deduped:
                    continue
                deduped.append(edge_id)
                if edge_id not in seen:
                    seen.add(edge_id)
                    used_edge_ids.append(edge_id)
            used[category] = deduped

        required_count = len(scenario.get("required_documents", []))
        triggered_count = len(scenario.get("triggered_documents", []))
        conditional_count = len(scenario.get("conditional_documents", []))
        node_positions = scenario_node_positions(used, flow_edges, edge_by_id)
        result.append(
            {
                "id": scenario["scenario_id"],
                "title": scenario["input"],
                "district": scenario["district"],
                "businessType": scenario["business_type"],
                "permits": scenario["permits"],
                "summary": {
                    "neededDocuments": required_count + triggered_count,
                    "requiredDocuments": required_count,
                    "triggeredDocuments": triggered_count,
                    "conditionalDocuments": conditional_count,
                    "checks": len(scenario.get("checks_and_risks", [])),
                    "prerequisites": len(scenario.get("prerequisites", [])),
                    "flowEdges": len(flow_edges),
                },
                "usedEdgesByCategory": used,
                "usedEdgeIds": used_edge_ids,
                "edgeLabels": edge_labels,
                "flowTimeline": flow_timeline(flow_edges),
                "nodePositions": node_positions,
                "requiredDocuments": scenario.get("required_documents", []),
                "triggeredDocuments": scenario.get("triggered_documents", []),
                "conditionalDocuments": scenario.get("conditional_documents", []),
                "checksAndRisks": scenario.get("checks_and_risks", []),
                "prerequisites": scenario.get("prerequisites", []),
                "submissionRoutes": scenario.get("submission_routes", []),
                "order": scenario.get("order", []),
            }
        )
    return result


def main() -> None:
    nodes_raw = read_csv(NODES_PATH)
    edges_raw = read_csv(EDGES_PATH)
    scenarios_raw = json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))
    positions = node_positions(nodes_raw)

    nodes = []
    for node in nodes_raw:
        pos = positions[node["node_id"]]
        nodes.append(
            {
                "id": node["node_id"],
                "name": node["name"],
                "type": node["node_type"],
                "claimCount": int(node.get("claim_count") or 0),
                "sourceTitle": node.get("title", ""),
                "sourceUrl": node.get("source_url", ""),
                "x": pos["x"],
                "y": pos["y"],
            }
        )

    edges = [edge_payload(edge) for edge in edges_raw]
    scenarios = build_scenarios(edges_raw, scenarios_raw)

    predicate_counts = Counter(edge["predicate"] for edge in edges_raw)
    node_type_counts = Counter(node["node_type"] for node in nodes_raw)
    payload = {
        "meta": {
            "title": "Heogaon Scenario Graph Demo",
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "scenarioCount": len(scenarios),
            "predicateCounts": dict(predicate_counts),
            "nodeTypeCounts": dict(node_type_counts),
            "generatedFrom": {
                "nodes": str(NODES_PATH.relative_to(MINJU_ROOT.parent)),
                "edges": str(EDGES_PATH.relative_to(MINJU_ROOT.parent)),
                "scenarios": str(SCENARIOS_PATH.relative_to(MINJU_ROOT.parent)),
            },
        },
        "nodeTypeMeta": NODE_TYPE_META,
        "categoryMeta": CATEGORY_META,
        "nodes": nodes,
        "edges": edges,
        "scenarios": scenarios,
    }
    OUT_PATH.write_text("window.GRAPH_VIZ_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    for scenario in scenarios:
        print(scenario["id"], "used_edges", len(scenario["usedEdgeIds"]), "needed_docs", scenario["summary"]["neededDocuments"])
    print(f"wrote={OUT_PATH}")


if __name__ == "__main__":
    main()
