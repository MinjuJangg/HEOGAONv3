from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


GRAPH_ROOT = Path(__file__).resolve().parents[1]
FINAL_GRAPH = GRAPH_ROOT / "output" / "final_graph"
EVIDENCE_PATH = GRAPH_ROOT / "input" / "evidence" / "evidence_chunks_augmented.jsonl"
NODES_PATH = FINAL_GRAPH / "graph_nodes_high_precision.csv"
EDGES_PATH = FINAL_GRAPH / "graph_edges_high_precision.csv"
REPORT_PATH = FINAL_GRAPH / "raw_rechunk_reinforcement_report.md"


NODE_COLUMNS = [
    "node_id",
    "node_type",
    "name",
    "normalized_name",
    "source_document_id",
    "chunk_id",
    "source_type",
    "source_url",
    "title",
    "section_path",
    "claim_count",
]

EDGE_COLUMNS = [
    "edge_id",
    "source_node_id",
    "target_node_id",
    "predicate",
    "subject_type",
    "subject_name",
    "object_type",
    "object_name",
    "claim_id",
    "edge_source",
    "assertion_level",
    "authority_level",
    "review_status",
    "confidence",
    "source_document_id",
    "chunk_id",
    "evidence_text",
    "condition_text",
    "source_type",
    "source_url",
    "title",
    "section_path",
    "extraction_method",
    "model",
]


FOOD_REQUIRED_CONDITIONS = {
    "evchunk_gov24_food_business_required_01": "식품위생법 제41조제2항에 따라 미리 교육을 받은 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_02": "식품위생법 시행령 제21조제1호부터 제3호까지의 영업만 해당합니다.",
    "evchunk_gov24_food_business_required_03": "식품운반업을 하려는 경우로서 차고 또는 세차장을 임대할 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_04": "수돗물이 아닌 지하수 등을 먹는물, 식품 제조과정, 조리 또는 세척에 사용하는 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_05": "수상구조물로 된 유선장 또는 도선장에서 휴게음식점, 일반음식점, 제과점영업을 하려는 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_06": "다중이용업소 안전시설등 완비증명서 발급대상 영업의 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_07": "식품자동판매기 2대 이상을 일괄 신고하는 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_08": "수상구조물로 된 수상레저사업장에서 휴게음식점 또는 제과점영업을 하려는 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_09": "국유철도 정거장시설 또는 군사시설에서 해당 식품영업을 하려는 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_10": "도시철도 정거장시설에서 해당 식품영업을 하려는 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_11": "군사시설에서 일반음식점영업을 하려는 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_12": "음식판매자동차 등 별표 15의2에 따른 영업장 사용 증명이 필요한 경우만 해당합니다.",
    "evchunk_gov24_food_business_required_13": "어린이놀이시설을 설치하는 경우만 해당합니다.",
}


BAD_GENERIC_EDGES = {
    ("requires_document", "옥외광고물 등의 표시허가", "필수적 첨부서류"),
    ("requires_document", "옥외광고물 등의 표시허가(신고)", "옥외광고물 등의 표시허가(신고) 서류"),
    ("requires_document", "도로점용허가", "도면(설계도면 및 주요지하매설물 관리자의 의견서/사후관리계획 등 서류)"),
}


SUPPLEMENTAL_CHUNKS = [
    {
        "chunk_id": "evchunk_rechunk_outdoor_ad_owner_consent",
        "source_document_id": "gov24_outdoor_ad_display_permit",
        "source_type": "gov24",
        "source_record_id": "13100000152",
        "authority_level": "official",
        "title": "옥외광고물 등의 표시허가(신고)",
        "section_path": "옥외광고물 등의 표시허가(신고) > 민원인이 제출해야하는 서류 > 소유자 또는 관리자 사용승낙",
        "source_url": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=13100000152&HighCtgCD=A09006",
        "raw_path": "data/raw/gov24/outdoor_ad_display_permit.html",
        "chunk_kind": "atomic_required_document",
        "text": "타인소유 또는 관리하는 토지·물건 등에 표시시 소유자 또는 관리자의 사용승락 증명서류",
    },
    {
        "chunk_id": "evchunk_rechunk_outdoor_ad_review_and_safety",
        "source_document_id": "gov24_outdoor_ad_display_permit",
        "source_type": "gov24",
        "source_record_id": "13100000152",
        "authority_level": "official",
        "title": "옥외광고물 등의 표시허가(신고)",
        "section_path": "옥외광고물 등의 표시허가(신고) > 민원인이 제출해야하는 서류 > 심의 및 구조안전",
        "source_url": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=13100000152&HighCtgCD=A09006",
        "raw_path": "data/raw/gov24/outdoor_ad_display_permit.html",
        "chunk_kind": "atomic_conditional_document_group",
        "text": "시·도조례로 정한 광고물관리심의위원회 심의대상 광고물의 심의관련서류와 건물의 구조안전 확인 서류(각 1부)",
    },
    {
        "chunk_id": "evchunk_rechunk_outdoor_ad_design_docs",
        "source_document_id": "gov24_outdoor_ad_display_permit",
        "source_type": "gov24",
        "source_record_id": "13100000152",
        "authority_level": "official",
        "title": "옥외광고물 등의 표시허가(신고)",
        "section_path": "옥외광고물 등의 표시허가(신고) > 민원인이 제출해야하는 서류 > 허가신청 첨부서류",
        "source_url": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=13100000152&HighCtgCD=A09006",
        "raw_path": "data/raw/gov24/outdoor_ad_display_permit.html",
        "chunk_kind": "atomic_document_group",
        "text": "허가신청시 첨부서류: 설치장소의 주변 원색사진, 광고물등의 형상·규격·구조·의장등에 관한 설명서, 설계도서",
    },
    {
        "chunk_id": "evchunk_rechunk_road_design_drawings",
        "source_document_id": "gov24_road_occupation_permit",
        "source_type": "gov24",
        "source_record_id": "15000000209",
        "authority_level": "official",
        "title": "도로점용허가",
        "section_path": "도로점용허가 > 민원인이 제출해야하는 서류 > 설계도면",
        "source_url": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=15000000209&HighCtgCD=A09006",
        "raw_path": "data/raw/gov24/road_occupation_permit.html",
        "chunk_kind": "atomic_required_document",
        "text": "설계도면(전자도면으로 한정합니다). 다만, 도로의 굴착을 수반하는 도로점용허가의 신청인 경우로서 도로법 시행령 제56조제1항에 따라 제출한 사업계획서대로 도로점용에 관한 사업을 할 수 있다는 통보를 받은 경우는 제외합니다.",
    },
    {
        "chunk_id": "evchunk_rechunk_road_excavation_docs",
        "source_document_id": "gov24_road_occupation_permit",
        "source_type": "gov24",
        "source_record_id": "15000000209",
        "authority_level": "official",
        "title": "도로점용허가",
        "section_path": "도로점용허가 > 민원인이 제출해야하는 서류 > 도로굴착 추가서류",
        "source_url": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=15000000209&HighCtgCD=A09006",
        "raw_path": "data/raw/gov24/road_occupation_permit.html",
        "chunk_kind": "atomic_conditional_document_group",
        "text": "도로의 굴착을 수반하는 도로점용허가 신청인 경우 주요지하매설물 관리자의 의견서, 주요지하매설물의 사후관리계획, 도로관리심의회의 심의·조정 결과를 반영한 안전대책 등에 관한 서류를 제출합니다.",
    },
    {
        "chunk_id": "evchunk_local_gangnam_road_docs",
        "source_document_id": "gangnam_road_occupation_permit_page",
        "source_type": "local_official_page",
        "source_record_id": "gangnam_permit_road",
        "authority_level": "official",
        "title": "강남구 도로점용허가 안내",
        "section_path": "강남구 도로점용허가 안내 > 구비서류",
        "source_url": "https://www.gangnam.go.kr/contents/permit_road/1/view.do?mid=ID03_010906",
        "raw_path": "data/raw/local_official/gangnam_road_occupation.html",
        "chunk_kind": "local_atomic_required_document_group",
        "text": "도로점용허가 구비서류: 신청서, 사업자등록증 사본, 위치도. 첨부서류: 설계도면, 지하매설물 관련 의견서·사후관리계획·안전대책 등은 굴착 여부에 따라 확인합니다.",
    },
    {
        "chunk_id": "evchunk_local_gangnam_food_docs",
        "source_document_id": "gangnam_food_service_report_page",
        "source_type": "local_official_page",
        "source_record_id": "gangnam_food_report",
        "authority_level": "official",
        "title": "강남구 식품접객업 영업신고 안내",
        "section_path": "강남구 식품접객업 영업신고 안내 > 구비서류",
        "source_url": "https://health.gangnam.go.kr/web/hygiene/report/food/sub01.do",
        "raw_path": "data/raw/local_official/gangnam_food_report.html",
        "chunk_kind": "local_atomic_required_document_group",
        "text": "식품접객업 영업신고 구비서류: 식품영업신고서, 상담일지, 위임장. 공통 제출서류: 위생교육수료증, 건강진단결과서, 건물 임대차계약서, 신분증. 추가 서류: 소방완비증명서, LPG 검사필증, 건물주 동의서 또는 신탁동의서, 수질검사시험성적서, 어린이놀이시설 검사합격증 등은 해당하는 경우 확인합니다.",
    },
    {
        "chunk_id": "evchunk_local_songpa_outdoor_sign_docs",
        "source_document_id": "songpa_outdoor_ad_page",
        "source_type": "local_official_page",
        "source_record_id": "songpa_outdoor_ad",
        "authority_level": "official",
        "title": "송파구 옥외광고물 표시 허가·신고 안내",
        "section_path": "송파구 옥외광고물 표시 허가·신고 안내 > 구비서류",
        "source_url": "https://www.songpa.go.kr/www/contents.do?key=6083",
        "raw_path": "data/raw/local_official/songpa_outdoor_ad.html",
        "chunk_kind": "local_atomic_required_document_group",
        "text": "옥외광고물 표시 허가·신고 구비서류: 신청서, 건물주 또는 관리자 승낙서. 개별 서류: 원색사진 또는 원색도안, 설계도서 또는 설명서. 신청은 구청 민원행정과 통합민원창구 또는 정부24 경로를 확인합니다.",
    },
]


NEW_EDGES = [
    # Food business report: explicit core documents and before requirements.
    ("requires_prerequisite", "permit_service", "식품관련영업신고", "document", "위생교육 수료증", "evchunk_local_gangnam_food_docs", "영업신고 전에 관련 업종 위생교육을 수료해야 합니다.", "explicit"),
    ("requires_prerequisite", "permit_service", "식품관련영업신고", "document", "건강진단결과서", "evchunk_local_gangnam_food_docs", "식품접객업 영업신고 전에 건강진단결과서를 준비해야 합니다.", "explicit"),
    ("requires_prerequisite", "permit_service", "식품관련영업신고", "document", "임대차계약서", "evchunk_local_gangnam_food_docs", "영업장 사용 권원을 확인하기 위해 임대차계약서를 준비해야 합니다.", "explicit"),
    ("requires_prerequisite", "permit_service", "식품관련영업신고", "document", "신분증", "evchunk_local_gangnam_food_docs", "신고인 본인 확인 또는 대리 신청 확인을 위해 신분증을 준비해야 합니다.", "explicit"),
    ("requires_document", "permit_service", "식품관련영업신고", "document", "상담일지", "evchunk_local_gangnam_food_docs", "강남구 식품접객업 신고 안내에서 요구하는 지역 서류입니다.", "conditional"),
    ("requires_document", "permit_service", "식품관련영업신고", "document", "건물주 동의서 또는 신탁동의서", "evchunk_local_gangnam_food_docs", "건물 소유·신탁·임대차 구조상 동의가 필요한 경우 확인합니다.", "conditional"),
    # Outdoor ad permit: atomized documents.
    ("requires_document", "permit_service", "옥외광고물 등의 표시허가(신고)", "document", "소유자 또는 관리자의 사용승낙 증명서류", "evchunk_rechunk_outdoor_ad_owner_consent", "타인 소유 또는 관리 토지·물건 등에 광고물을 표시하는 경우 필요합니다.", "conditional"),
    ("requires_document", "permit_service", "옥외광고물 등의 표시허가(신고)", "document", "광고물관리심의위원회 심의 관련 서류", "evchunk_rechunk_outdoor_ad_review_and_safety", "시·도조례로 정한 광고물관리심의위원회 심의대상 광고물인 경우 필요합니다.", "conditional"),
    ("requires_document", "permit_service", "옥외광고물 등의 표시허가(신고)", "document", "건물 구조안전 확인 서류", "evchunk_rechunk_outdoor_ad_review_and_safety", "시·도조례로 정한 심의대상 광고물 또는 구조안전 확인 대상인 경우 필요합니다.", "conditional"),
    ("requires_document", "permit_service", "옥외광고물 등의 표시허가(신고)", "document", "설치장소 주변 원색사진", "evchunk_rechunk_outdoor_ad_design_docs", "허가신청 시 설치장소 주변 확인을 위해 준비합니다.", "explicit"),
    ("requires_document", "permit_service", "옥외광고물 등의 표시허가(신고)", "document", "광고물 등의 형상·규격·구조·의장 등에 관한 설명서", "evchunk_rechunk_outdoor_ad_design_docs", "허가신청 시 광고물의 형상·규격·구조·의장을 설명해야 합니다.", "explicit"),
    ("requires_document", "permit_service", "옥외광고물 등의 표시허가(신고)", "document", "설계도서", "evchunk_rechunk_outdoor_ad_design_docs", "허가신청 시 설계도서를 준비합니다.", "explicit"),
    ("requires_document", "permit_service", "옥외광고물 등의 표시허가(신고)", "document", "건물주 또는 관리자 승낙서", "evchunk_local_songpa_outdoor_sign_docs", "송파구 안내 기준 공통 구비서류입니다.", "conditional"),
    ("requires_document", "permit_service", "옥외광고물 등의 표시허가(신고)", "document", "원색사진 또는 원색도안", "evchunk_local_songpa_outdoor_sign_docs", "송파구 안내 기준 개별 구비서류입니다.", "explicit"),
    ("requires_document", "permit_service", "옥외광고물 등의 표시허가(신고)", "document", "설계도서 또는 설명서", "evchunk_local_songpa_outdoor_sign_docs", "송파구 안내 기준 개별 구비서류입니다.", "explicit"),
    ("precedes", "procedure_step", "간판 규격 위치 표시방법 확인", "procedure_step", "옥외광고물 표시허가 신고 신청", "evchunk_rechunk_outdoor_ad_design_docs", "간판 규격·위치·표시방법을 확인한 뒤 표시허가 또는 신고를 신청합니다.", "explicit"),
    # Road occupation: atomized documents and excavation branches.
    ("requires_document", "permit_service", "도로점용허가", "document", "설계도면", "evchunk_rechunk_road_design_drawings", "도로점용허가 신청 시 설계도면을 제출합니다. 도로굴착 사업계획 통보를 받은 경우 일부 생략될 수 있습니다.", "explicit"),
    ("requires_document", "permit_service", "도로점용허가", "document", "주요지하매설물 관리자의 의견서", "evchunk_rechunk_road_excavation_docs", "도로 굴착을 수반하는 도로점용허가 신청인 경우 필요합니다.", "conditional"),
    ("requires_document", "permit_service", "도로점용허가", "document", "주요지하매설물의 사후관리계획", "evchunk_rechunk_road_excavation_docs", "도로 굴착을 수반하고 신청인이 주요지하매설물 관리자인 경우 필요합니다.", "conditional"),
    ("requires_document", "permit_service", "도로점용허가", "document", "도로관리심의회 심의·조정 결과를 반영한 안전대책 서류", "evchunk_rechunk_road_excavation_docs", "도로 굴착을 수반하는 경우 도로관리심의회 심의·조정 결과를 반영해야 합니다.", "conditional"),
    ("requires_document", "permit_service", "도로점용허가", "document", "사업자등록증 사본", "evchunk_local_gangnam_road_docs", "강남구 도로점용허가 안내 기준 구비서류입니다.", "explicit"),
    ("requires_document", "permit_service", "도로점용허가", "document", "위치도", "evchunk_local_gangnam_road_docs", "강남구 도로점용허가 안내 기준 구비서류입니다.", "explicit"),
    ("requires_prerequisite", "permit_service", "도로점용허가", "document", "사업자등록증", "evchunk_local_gangnam_road_docs", "사업자등록증 사본 제출을 위해 사업자등록증이 선행되어야 합니다.", "explicit"),
    ("requires_prerequisite", "permit_service", "도로점용허가", "document", "위치도", "evchunk_local_gangnam_road_docs", "도로 점용 위치 확인 자료를 신청 전에 준비해야 합니다.", "explicit"),
]


def stable_hash(*parts: Any, length: int = 16) -> str:
    payload = "\u241f".join(str(part or "") for part in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:length]


def normalize_name(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def node_id(node_type: str, name: str) -> str:
    return f"n_{stable_hash(node_type, normalize_name(name))}"


def edge_id(*parts: Any) -> str:
    return f"edge_{stable_hash(*parts)}"


def claim_id(*parts: Any) -> str:
    return f"claim_{stable_hash(*parts)}"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def read_evidence(path: Path) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            item = json.loads(line)
            evidence[item["chunk_id"]] = item
    return evidence


def write_evidence(path: Path, evidence: dict[str, dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for chunk_id in sorted(evidence):
            item = evidence[chunk_id]
            file.write(json.dumps(item, ensure_ascii=False) + "\n")


def backup_once(path: Path) -> None:
    backup = path.with_name(f"{path.stem}.before_raw_rechunk{path.suffix}")
    if not backup.exists():
        shutil.copy2(path, backup)


def add_or_update_node(
    nodes_by_key: dict[tuple[str, str], dict[str, str]],
    node_type: str,
    name: str,
    evidence: dict[str, Any],
) -> str:
    clean_name = normalize_name(name)
    key = (node_type, clean_name)
    existing = nodes_by_key.get(key)
    if existing:
        return existing["node_id"]

    n_id = node_id(node_type, clean_name)
    nodes_by_key[key] = {
        "node_id": n_id,
        "node_type": node_type,
        "name": clean_name,
        "normalized_name": clean_name.casefold(),
        "source_document_id": evidence.get("source_document_id", ""),
        "chunk_id": evidence.get("chunk_id", ""),
        "source_type": evidence.get("source_type", ""),
        "source_url": evidence.get("source_url", ""),
        "title": evidence.get("title", ""),
        "section_path": evidence.get("section_path", ""),
        "claim_count": "0",
    }
    return n_id


def make_edge(
    nodes_by_key: dict[tuple[str, str], dict[str, str]],
    evidence_by_chunk: dict[str, dict[str, Any]],
    predicate: str,
    subject_type: str,
    subject_name: str,
    object_type: str,
    object_name: str,
    chunk_id_value: str,
    condition_text: str,
    assertion_level: str,
) -> dict[str, str]:
    evidence = evidence_by_chunk[chunk_id_value]
    source_id = add_or_update_node(nodes_by_key, subject_type, subject_name, evidence)
    target_id = add_or_update_node(nodes_by_key, object_type, object_name, evidence)
    c_id = claim_id("raw_rechunk", predicate, subject_type, subject_name, object_type, object_name, chunk_id_value)
    return {
        "edge_id": edge_id("raw_rechunk", c_id),
        "source_node_id": source_id,
        "target_node_id": target_id,
        "predicate": predicate,
        "subject_type": subject_type,
        "subject_name": normalize_name(subject_name),
        "object_type": object_type,
        "object_name": normalize_name(object_name),
        "claim_id": c_id,
        "edge_source": "raw_rechunk",
        "assertion_level": assertion_level,
        "authority_level": evidence.get("authority_level", "official"),
        "review_status": "official_document",
        "confidence": "0.95",
        "source_document_id": evidence.get("source_document_id", ""),
        "chunk_id": chunk_id_value,
        "evidence_text": evidence.get("text", ""),
        "condition_text": condition_text,
        "source_type": evidence.get("source_type", ""),
        "source_url": evidence.get("source_url", ""),
        "title": evidence.get("title", ""),
        "section_path": evidence.get("section_path", ""),
        "extraction_method": "raw_atomic_rechunk",
        "model": "",
    }


def main() -> None:
    backup_once(NODES_PATH)
    backup_once(EDGES_PATH)
    backup_once(EVIDENCE_PATH)

    nodes = read_csv(NODES_PATH)
    edges = read_csv(EDGES_PATH)
    evidence_by_chunk = read_evidence(EVIDENCE_PATH)

    for chunk in SUPPLEMENTAL_CHUNKS:
        row = {
            **chunk,
            "sequence": "",
            "char_len": len(chunk["text"]),
            "estimated_tokens": max(1, len(chunk["text"]) // 2),
            "relevance_score": 5,
            "scope_tags": ["food", "startup", "permit"],
        }
        evidence_by_chunk[chunk["chunk_id"]] = row

    filtered_edges: list[dict[str, str]] = []
    removed_generic = 0
    condition_updates = 0
    for edge in edges:
        edge_key = (edge["predicate"], edge["subject_name"], edge["object_name"])
        if edge_key in BAD_GENERIC_EDGES:
            removed_generic += 1
            continue

        food_condition = FOOD_REQUIRED_CONDITIONS.get(edge.get("chunk_id", ""))
        if edge["predicate"] == "requires_document" and food_condition:
            edge["condition_text"] = food_condition
            edge["assertion_level"] = "conditional"
            edge["authority_level"] = "official"
            edge["review_status"] = "official_document"
            edge["confidence"] = "0.95"
            edge["extraction_method"] = "gov24_atomic_rechunk_condition_update"
            condition_updates += 1
        filtered_edges.append(edge)

    nodes_by_key = {
        (node["node_type"], normalize_name(node["name"])): node
        for node in nodes
    }
    existing_edge_keys = {
        (
            edge["predicate"],
            edge["subject_type"],
            normalize_name(edge["subject_name"]),
            edge["object_type"],
            normalize_name(edge["object_name"]),
            edge.get("chunk_id", ""),
        )
        for edge in filtered_edges
    }

    added_edges: list[dict[str, str]] = []
    for predicate, subject_type, subject_name, object_type, object_name, chunk_id_value, condition_text, assertion_level in NEW_EDGES:
        key = (
            predicate,
            subject_type,
            normalize_name(subject_name),
            object_type,
            normalize_name(object_name),
            chunk_id_value,
        )
        if key in existing_edge_keys:
            continue
        edge = make_edge(
            nodes_by_key,
            evidence_by_chunk,
            predicate,
            subject_type,
            subject_name,
            object_type,
            object_name,
            chunk_id_value,
            condition_text,
            assertion_level,
        )
        added_edges.append(edge)
        filtered_edges.append(edge)
        existing_edge_keys.add(key)

    claim_counts: Counter[str] = Counter()
    for edge in filtered_edges:
        if edge.get("claim_id"):
            claim_counts[edge["source_node_id"]] += 1
            claim_counts[edge["target_node_id"]] += 1

    final_nodes = list(nodes_by_key.values())
    for node in final_nodes:
        node["claim_count"] = str(claim_counts.get(node["node_id"], int(node.get("claim_count") or 0)))

    final_nodes.sort(key=lambda row: (row["node_type"], row["name"], row["node_id"]))
    filtered_edges.sort(key=lambda row: (row["predicate"], row["source_node_id"], row["target_node_id"], row["edge_id"]))

    write_evidence(EVIDENCE_PATH, evidence_by_chunk)
    write_csv(NODES_PATH, final_nodes, NODE_COLUMNS)
    write_csv(EDGES_PATH, filtered_edges, EDGE_COLUMNS)

    predicate_counts = Counter(edge["predicate"] for edge in filtered_edges)
    report = [
        "# Raw Rechunk Reinforcement Report",
        "",
        "핵심 민원 3개(식품관련영업신고, 옥외광고물 표시허가/신고, 도로점용허가)를 RAW evidence 기준으로 보강했습니다.",
        "",
        "## Changes",
        f"- updated_food_condition_edges: {condition_updates}",
        f"- removed_generic_edges: {removed_generic}",
        f"- added_atomic_edges: {len(added_edges)}",
        f"- supplemental_chunks_total: {len(SUPPLEMENTAL_CHUNKS)}",
        "",
        "## Added Edge Predicates",
    ]
    added_counts = Counter(edge["predicate"] for edge in added_edges)
    for predicate, count in sorted(added_counts.items()):
        report.append(f"- {predicate}: {count}")
    report.extend(["", "## Final Predicate Counts"])
    for predicate, count in sorted(predicate_counts.items()):
        report.append(f"- {predicate}: {count}")
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"updated_food_condition_edges={condition_updates}")
    print(f"removed_generic_edges={removed_generic}")
    print(f"added_atomic_edges={len(added_edges)}")
    print(f"nodes={len(final_nodes)} edges={len(filtered_edges)}")
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
