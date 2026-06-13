from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


GRAPH_ROOT = Path(__file__).resolve().parents[1]
FINAL_GRAPH = GRAPH_ROOT / "output" / "final_graph"
EVIDENCE_PATH = GRAPH_ROOT / "input" / "evidence" / "evidence_chunks_augmented.jsonl"
NODES_PATH = FINAL_GRAPH / "graph_nodes_high_precision.csv"
EDGES_PATH = FINAL_GRAPH / "graph_edges_high_precision.csv"
REPORT_PATH = FINAL_GRAPH / "all_raw_rechunk_rebuild_report.md"


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


CONDITIONAL_MARKERS = [
    "경우",
    "해당",
    "한함",
    "한정",
    "제외",
    "다만",
    "변경신고",
    "법인",
    "임차",
    "위임",
    "미리 교육",
]

GENERIC_DOCUMENT_NAMES = {
    "필수적 첨부서류",
    "허가신청시 첨부서류",
    "첨부서류",
    "구비서류",
    "구비서류 있음",
    "민원인이 제출해야하는 서류",
    "민원인이 제출하지 않아도 되는 서류",
    "옥외광고물 등의 표시허가(신고) 서류",
    "도면(설계도면 및 주요지하매설물 관리자의 의견서/사후관리계획 등 서류)",
}


LOCAL_SUPPLEMENTAL_CHUNKS = [
    {
        "chunk_id": "evchunk_local_mapo_food_report_docs",
        "source_document_id": "mapo_food_report_page",
        "source_type": "local_official_page",
        "source_record_id": "mapo_food_report",
        "authority_level": "official",
        "title": "마포구 식품접객업 영업신고 안내",
        "section_path": "마포구 식품접객업 영업신고 안내 > 구비서류",
        "source_url": "https://www.mapo.go.kr/site/health/content/health05050201",
        "raw_path": "data/raw/local_official/mapo_food_report.html",
        "chunk_kind": "local_atomic_required_document_group",
        "text": "구비서류: 영업신고(허가) 신청서, 임대차계약서, 위생교육수료증, LPG 필증(해당 시), 소방방화시설완비증명서(지하 66㎡ 또는 지상 2층 이상 100㎡ 등 대상 시), 건강진단결과서, 전기안전검사필증(허가 대상 시), 신분증, 위임장 또는 법인서류(해당 시).",
    },
    {
        "chunk_id": "evchunk_local_gangnam_food_report_docs",
        "source_document_id": "gangnam_food_report_page",
        "source_type": "local_official_page",
        "source_record_id": "gangnam_food_report",
        "authority_level": "official",
        "title": "강남구 식품접객업 영업신고 안내",
        "section_path": "강남구 식품접객업 영업신고 안내 > 구비서류",
        "source_url": "https://health.gangnam.go.kr/web/hygiene/report/food/sub01.do",
        "raw_path": "data/raw/local_official/gangnam_food_report.html",
        "chunk_kind": "local_atomic_required_document_group",
        "text": "구비서류: 식품영업신고서, 상담일지, 위임장, 위생교육수료증, 건강진단결과서, 건물 임대차계약서, 신분증. 추가 서류: 소방완비증명서, LPG 검사필증, 건물주 동의서 또는 신탁동의서, 수질검사시험성적서, 어린이놀이시설 검사합격증 등은 해당하는 경우 확인합니다.",
    },
    {
        "chunk_id": "evchunk_local_gangnam_road_occupation_docs",
        "source_document_id": "gangnam_road_occupation_page",
        "source_type": "local_official_page",
        "source_record_id": "gangnam_road_occupation",
        "authority_level": "official",
        "title": "강남구 도로점용허가 안내",
        "section_path": "강남구 도로점용허가 안내 > 구비서류",
        "source_url": "https://www.gangnam.go.kr/contents/permit_road/1/view.do?mid=ID03_010906",
        "raw_path": "data/raw/local_official/gangnam_road_occupation.html",
        "chunk_kind": "local_atomic_required_document_group",
        "text": "구비서류: 도로점용허가 신청서, 사업자등록증 사본, 위치도. 첨부서류: 설계도면. 도로 굴착 시 지하매설물 관련 의견서, 사후관리계획, 안전대책 서류 등을 확인합니다.",
    },
    {
        "chunk_id": "evchunk_local_songpa_outdoor_ad_docs",
        "source_document_id": "songpa_outdoor_ad_page",
        "source_type": "local_official_page",
        "source_record_id": "songpa_outdoor_ad",
        "authority_level": "official",
        "title": "송파구 옥외광고물 표시 허가·신고 안내",
        "section_path": "송파구 옥외광고물 표시 허가·신고 안내 > 구비서류",
        "source_url": "https://www.songpa.go.kr/www/contents.do?key=6083",
        "raw_path": "data/raw/local_official/songpa_outdoor_ad.html",
        "chunk_kind": "local_atomic_required_document_group",
        "text": "고정 광고물 구비서류: 옥외광고물 표시 신고 신청서, 건물주 또는 관리자 승낙서, 원색사진 또는 원색도안, 설계도서 또는 설명서. 입간판(배너) 신고 구비서류: 옥외광고물 표시 신고 신청서, 건물주 또는 관리자 승낙서, 사업자등록증 사본, 입간판 도안(길이, 크기 표기된 사진으로 대체 가능). 신청은 구청 민원행정과 통합민원창구 또는 정부24 경로를 확인합니다.",
    },
    {
        "chunk_id": "evchunk_local_gangnam_food_succession_docs",
        "source_document_id": "gangnam_food_succession_page",
        "source_type": "local_official_page",
        "source_record_id": "gangnam_food_succession",
        "authority_level": "official",
        "title": "강남구 식품영업자 지위승계 안내",
        "section_path": "강남구 식품위생신고 > 지위승계 > 식품접객업",
        "source_url": "https://health.gangnam.go.kr/web/hygiene/report/food/sub02.do",
        "raw_path": "data/raw/local_official/gangnam_food_succession.html",
        "chunk_kind": "local_atomic_required_document_group",
        "text": "구비서류: 식품영업자 지위승계신고서, 양도양수계약서, 양도인 신분증, 기존 영업신고증, 양수인 신분증, 위생교육수료증, 건강진단결과서, 건물 임대차계약서. 위임 신청 시 위임장과 대리인 신분증, 법인인 경우 법인서류를 확인합니다.",
    },
    {
        "chunk_id": "evchunk_local_gangnam_mail_order_docs",
        "source_document_id": "gangnam_mail_order_page",
        "source_type": "local_official_page",
        "source_record_id": "gangnam_mail_order",
        "authority_level": "official",
        "title": "강남구 통신판매업 신고 안내",
        "section_path": "강남구 민원서식 > 통신판매업 신고서",
        "source_url": "https://www.gangnam.go.kr/board/B_000060/1071199/view.do?mid=ID03_010104",
        "raw_path": "data/raw/local_official/gangnam_mail_order.html",
        "chunk_kind": "local_atomic_required_document_group",
        "text": "방문접수 제출서류: 사업자등록증, 구매안전서비스이용확인증, 대표자 실물신분증. 대리인 방문 시 대표자 인감도장, 대표자 인감증명서, 대리인 실물신분증을 지참합니다. 담당부서는 지역경제과입니다.",
    },
]


CORE_TITLES_WITH_MANUAL_ATOMICS = {
    "식품관련영업신고",
    "도로점용허가",
    "옥외광고물 등의 표시허가(신고)",
}


MANUAL_ATOMIC_DOCUMENTS = [
    # Mapo/Gangnam food service official pages.
    ("식품관련영업신고", "영업신고 신청서", "evchunk_local_mapo_food_report_docs", "", "explicit"),
    ("식품관련영업신고", "식품영업신고서", "evchunk_local_gangnam_food_report_docs", "", "explicit"),
    ("식품관련영업신고", "상담일지", "evchunk_local_gangnam_food_report_docs", "강남구 식품접객업 신고 안내의 지역 구비서류입니다.", "explicit"),
    ("식품관련영업신고", "임대차계약서", "evchunk_local_mapo_food_report_docs", "", "explicit"),
    ("식품관련영업신고", "건물 임대차계약서", "evchunk_local_gangnam_food_report_docs", "", "explicit"),
    ("식품관련영업신고", "위생교육수료증", "evchunk_local_mapo_food_report_docs", "", "explicit"),
    ("식품관련영업신고", "건강진단결과서", "evchunk_local_mapo_food_report_docs", "", "explicit"),
    ("식품관련영업신고", "신분증", "evchunk_local_mapo_food_report_docs", "", "explicit"),
    ("식품관련영업신고", "위생교육수료증", "evchunk_local_gangnam_food_report_docs", "", "explicit"),
    ("식품관련영업신고", "건강진단결과서", "evchunk_local_gangnam_food_report_docs", "", "explicit"),
    ("식품관련영업신고", "신분증", "evchunk_local_gangnam_food_report_docs", "", "explicit"),
    ("식품관련영업신고", "LPG 필증", "evchunk_local_mapo_food_report_docs", "LPG 사용 시설인 경우 해당합니다.", "conditional"),
    ("식품관련영업신고", "LPG 검사필증", "evchunk_local_gangnam_food_report_docs", "LPG 사용 시설인 경우 해당합니다.", "conditional"),
    ("식품관련영업신고", "소방방화시설완비증명서", "evchunk_local_mapo_food_report_docs", "지하 66㎡ 또는 지상 2층 이상 100㎡ 등 소방완비 대상인 경우 해당합니다.", "conditional"),
    ("식품관련영업신고", "소방완비증명서", "evchunk_local_gangnam_food_report_docs", "소방완비 대상인 경우 해당합니다.", "conditional"),
    ("식품관련영업신고", "전기안전검사필증", "evchunk_local_mapo_food_report_docs", "허가 대상 영업인 경우 해당합니다.", "conditional"),
    ("식품관련영업신고", "위임장", "evchunk_local_mapo_food_report_docs", "대리 신청인 경우 해당합니다.", "conditional"),
    ("식품관련영업신고", "법인서류", "evchunk_local_mapo_food_report_docs", "법인 신청인 경우 해당합니다.", "conditional"),
    ("식품관련영업신고", "건물주 동의서 또는 신탁동의서", "evchunk_local_gangnam_food_report_docs", "건물 소유·신탁·임대차 구조상 동의가 필요한 경우 확인합니다.", "conditional"),
    ("식품관련영업신고", "수질검사시험성적서", "evchunk_local_gangnam_food_report_docs", "수돗물이 아닌 지하수 등을 사용하는 경우 해당합니다.", "conditional"),
    ("식품관련영업신고", "어린이놀이시설 검사합격증", "evchunk_local_gangnam_food_report_docs", "어린이놀이시설을 설치한 경우 해당합니다.", "conditional"),
    # Outdoor advertisement permit/report.
    ("옥외광고물 등의 표시허가(신고)", "옥외광고물등표시(변경)허가신청(신고)서", "evchunk_fc00bc82d79f50", "", "explicit"),
    ("옥외광고물 등의 표시허가(신고)", "옥외광고물 표시 신고 신청서", "evchunk_local_songpa_outdoor_ad_docs", "", "explicit"),
    ("옥외광고물 등의 표시허가(신고)", "소유자 또는 관리자의 사용승락 증명서류", "evchunk_817c8d4b3c0cb4", "타인 소유 또는 관리 토지·물건 등에 표시하는 경우 필요합니다.", "conditional"),
    ("옥외광고물 등의 표시허가(신고)", "건물주 또는 관리자 승낙서", "evchunk_local_songpa_outdoor_ad_docs", "", "explicit"),
    ("옥외광고물 등의 표시허가(신고)", "사업자등록증 사본", "evchunk_local_songpa_outdoor_ad_docs", "입간판(배너) 신고인 경우 필요합니다.", "conditional"),
    ("옥외광고물 등의 표시허가(신고)", "입간판 도안", "evchunk_local_songpa_outdoor_ad_docs", "입간판(배너) 신고인 경우 필요합니다. 길이와 크기가 표기된 사진으로 대체 가능합니다.", "conditional"),
    ("옥외광고물 등의 표시허가(신고)", "광고물관리심의위원회 심의관련서류", "evchunk_817c8d4b3c0cb4", "시·도조례로 정한 심의대상 광고물인 경우 필요합니다.", "conditional"),
    ("옥외광고물 등의 표시허가(신고)", "건물 구조안전 확인 서류", "evchunk_817c8d4b3c0cb4", "구조안전 확인 대상인 경우 필요합니다.", "conditional"),
    ("옥외광고물 등의 표시허가(신고)", "설치장소의 주변 원색사진", "evchunk_817c8d4b3c0cb4", "", "explicit"),
    ("옥외광고물 등의 표시허가(신고)", "광고물 등의 형상·규격·구조·의장 등에 관한 설명서", "evchunk_817c8d4b3c0cb4", "", "explicit"),
    ("옥외광고물 등의 표시허가(신고)", "설계도서", "evchunk_817c8d4b3c0cb4", "", "explicit"),
    ("옥외광고물 등의 표시허가(신고)", "원색사진 또는 원색도안", "evchunk_local_songpa_outdoor_ad_docs", "", "explicit"),
    ("옥외광고물 등의 표시허가(신고)", "설계도서 또는 설명서", "evchunk_local_songpa_outdoor_ad_docs", "", "explicit"),
    # Road occupation.
    ("도로점용허가", "도로점용허가 신청서", "evchunk_bd7db50425da39", "", "explicit"),
    ("도로점용허가", "사업자등록증 사본", "evchunk_local_gangnam_road_occupation_docs", "강남구 도로점용허가 안내 기준 구비서류입니다.", "explicit"),
    ("도로점용허가", "위치도", "evchunk_local_gangnam_road_occupation_docs", "강남구 도로점용허가 안내 기준 구비서류입니다.", "explicit"),
    ("도로점용허가", "위치도 및 평면도", "evchunk_5d22f8f03bf0a4", "점용 위치와 면적을 확인하기 위해 준비합니다.", "explicit"),
    ("도로점용허가", "설계도면", "evchunk_1dab80f546b5a0", "전자도면으로 제출합니다. 일부 생략 예외 가능.", "explicit"),
    ("도로점용허가", "주요지하매설물 관리자의 의견서", "evchunk_1dab80f546b5a0", "도로의 굴착을 수반하는 신청인 경우 필요합니다.", "conditional"),
    ("도로점용허가", "주요지하매설물의 사후관리계획", "evchunk_1dab80f546b5a0", "도로의 굴착을 수반하고 신청인이 주요지하매설물 관리자인 경우 필요합니다.", "conditional"),
    ("도로점용허가", "도로관리심의회 심의·조정 결과를 반영한 안전대책 서류", "evchunk_1dab80f546b5a0", "도로의 굴착을 수반하는 경우 필요합니다.", "conditional"),
    # Food business succession.
    ("영업자 지위승계 신고", "식품영업자 지위승계신고서", "evchunk_local_gangnam_food_succession_docs", "", "explicit"),
    ("영업자 지위승계 신고", "양도양수계약서", "evchunk_local_gangnam_food_succession_docs", "", "explicit"),
    ("영업자 지위승계 신고", "기존 영업신고증", "evchunk_local_gangnam_food_succession_docs", "", "explicit"),
    ("영업자 지위승계 신고", "양도인 신분증", "evchunk_local_gangnam_food_succession_docs", "", "explicit"),
    ("영업자 지위승계 신고", "양수인 신분증", "evchunk_local_gangnam_food_succession_docs", "", "explicit"),
    ("영업자 지위승계 신고", "위생교육수료증", "evchunk_local_gangnam_food_succession_docs", "", "explicit"),
    ("영업자 지위승계 신고", "건강진단결과서", "evchunk_local_gangnam_food_succession_docs", "", "explicit"),
    ("영업자 지위승계 신고", "건물 임대차계약서", "evchunk_local_gangnam_food_succession_docs", "", "explicit"),
    ("영업자 지위승계 신고", "위임장 및 대리인 신분증", "evchunk_local_gangnam_food_succession_docs", "대리 신청인 경우 필요합니다.", "conditional"),
    ("영업자 지위승계 신고", "법인서류", "evchunk_local_gangnam_food_succession_docs", "법인 신청인 경우 필요합니다.", "conditional"),
    # Mail-order sales.
    ("통신판매업신고", "통신판매업 신고서", "evchunk_local_gangnam_mail_order_docs", "", "explicit"),
    ("통신판매업신고", "사업자등록증", "evchunk_local_gangnam_mail_order_docs", "", "explicit"),
    ("통신판매업신고", "대표자 실물신분증", "evchunk_local_gangnam_mail_order_docs", "", "explicit"),
    ("통신판매업신고", "구매안전서비스이용확인증", "evchunk_local_gangnam_mail_order_docs", "선지급식 통신판매 또는 결제대금예치 이용 대상인 경우 필요합니다.", "conditional"),
    ("통신판매업신고", "대표자 인감도장 및 인감증명서", "evchunk_local_gangnam_mail_order_docs", "대리인 방문 신청인 경우 필요합니다.", "conditional"),
    ("통신판매업신고", "대리인 실물신분증", "evchunk_local_gangnam_mail_order_docs", "대리인 방문 신청인 경우 필요합니다.", "conditional"),
]


CURATED_CORE_EDGES = [
    ("maps_to", "business_alias", "카페", "admin_business_type", "휴게음식점영업", "evchunk_b05df99a45d63a", "일반적인 음료·디저트 판매 카페는 휴게음식점영업으로 우선 매핑하되, 주류 판매 또는 조리 형태에 따라 일반음식점 여부를 확인합니다.", "inferred"),
    ("maps_to", "business_alias", "일반음식점", "admin_business_type", "일반음식점영업", "evchunk_b05df99a45d63a", "일반음식점 창업 입력은 일반음식점영업으로 매핑합니다.", "inferred"),
    ("requires_permit", "admin_business_type", "휴게음식점영업", "permit_service", "식품관련영업신고", "evchunk_b05df99a45d63a", "신고대상 식품관련 영업은 영업의 종류별·영업소별로 시장·군수·구청장에게 신고합니다.", "explicit"),
    ("requires_permit", "admin_business_type", "일반음식점영업", "permit_service", "식품관련영업신고", "evchunk_b05df99a45d63a", "신고대상 식품관련 영업은 영업의 종류별·영업소별로 시장·군수·구청장에게 신고합니다.", "explicit"),
    ("triggers", "condition_module", "간판 설치", "permit_service", "옥외광고물 등의 표시허가(신고)", "evchunk_dead1f0754d4fd", "옥외광고물 등을 허가 또는 신고하는 민원사무입니다.", "conditional"),
    ("triggers", "condition_module", "도로 공간 사용", "permit_service", "도로점용허가", "evchunk_7203dce9f19534", "도로점용허가를 받기 위한 민원사무입니다.", "conditional"),
    ("precedes", "procedure_step", "주소 확정", "procedure_step", "건축물대장 확인", "evchunk_9dddfe6a5ea01c", "영업신고 전 건축물대장 또는 건축물 임시사용 승인서를 확인합니다.", "explicit"),
    ("precedes", "procedure_step", "건축물대장 확인", "procedure_step", "용도 및 위반건축물 확인", "evchunk_9dddfe6a5ea01c", "건축물대장에서 용도와 위반건축물 여부를 확인합니다.", "explicit"),
    ("precedes", "procedure_step", "용도 및 위반건축물 확인", "procedure_step", "위생교육 및 건강진단 준비", "evchunk_local_mapo_food_report_docs", "영업신고 전에 위생교육수료증과 건강진단결과서를 준비합니다.", "explicit"),
    ("precedes", "procedure_step", "위생교육 및 건강진단 준비", "procedure_step", "영업신고 신청", "evchunk_local_mapo_food_report_docs", "선행 서류를 준비한 뒤 영업신고를 신청합니다.", "explicit"),
    ("precedes", "procedure_step", "영업신고 신청", "procedure_step", "영업신고증 발급", "evchunk_64284a635e9064", "식품관련영업신고는 즉시 처리 민원이며 신고가 수리되면 신고증 발급 흐름으로 이어집니다.", "explicit"),
    ("precedes", "procedure_step", "영업신고증 발급", "procedure_step", "사업자등록 신청", "evchunk_local_mapo_food_report_docs", "인허가 신고 업종은 영업신고증을 준비한 뒤 사업자등록을 진행합니다.", "explicit"),
    ("precedes", "procedure_step", "간판 규격 위치 표시방법 확인", "procedure_step", "옥외광고물 표시허가 신고 신청", "evchunk_817c8d4b3c0cb4", "간판 규격·위치·표시방법과 첨부서류를 확인한 뒤 옥외광고물 표시허가 또는 신고를 신청합니다.", "explicit"),
    ("precedes", "procedure_step", "옥외광고물 표시허가 신고 신청", "procedure_step", "수수료 납부 및 허가·신고증 발부", "evchunk_local_songpa_outdoor_ad_docs", "송파구 안내 기준 신청사항 검토 후 수수료 납부와 허가·신고증 발부 흐름으로 이어집니다.", "explicit"),
]


def stable_hash(*parts: Any, length: int = 16) -> str:
    payload = "\u241f".join(str(part or "") for part in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:length]


def normalize(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def node_id(node_type: str, name: str) -> str:
    return f"n_{stable_hash(node_type, normalize(name))}"


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
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                item = json.loads(line)
                rows[item["chunk_id"]] = item
    return rows


def write_evidence(path: Path, rows: dict[str, dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for key in sorted(rows):
            file.write(json.dumps(rows[key], ensure_ascii=False) + "\n")


def backup_once(path: Path) -> None:
    backup = path.with_name(f"{path.stem}.before_all_raw_rechunk{path.suffix}")
    if not backup.exists():
        shutil.copy2(path, backup)


def strip_prefixes(text: str) -> str:
    text = normalize(text)
    for prefix in [
        "민원인이 제출해야하는 서류",
        "민원인이 제출하지 않아도 되는 서류",
        "(담당공무원이 확인)",
        "※민원처리에 관한 법률 제 10조(불필요한 서류 요구의 금지)에 의하여 민원인이 본인정보제공 동의 후, 담당공무원이 [행정정보공동이용서비스]를 통하여 확인 가능한 서류",
        "서비스 개요",
        "신청서",
        "구비서류",
    ]:
        if text.startswith(prefix):
            text = normalize(text[len(prefix) :])
    text = re.sub(r"참고 담당공무원 확인.*$", "", text)
    text = re.sub(r"신청작성예시.*$", "", text)
    return normalize(text)


def split_parenthetical_items(text: str) -> list[str]:
    text = strip_prefixes(text)
    if not text:
        return []

    protected = (
        text.replace("시.군.구", "시·군·구")
        .replace("시.도", "시·도")
        .replace("1의2.", "1의2 ")
    )
    # Split after a closing parenthesis when a new Korean item begins.
    parts = re.split(r"(?<=[\]\)])\s+(?=[가-힣A-Z0-9「｢])", protected)
    expanded: list[str] = []
    for part in parts:
        part = normalize(part)
        if not part:
            continue
        # Split numbered subitems that Gov24 flattened into one sentence.
        subparts = re.split(r"\s+(?=(?:[가-하]\.|[0-9]+\.|[0-9]+의[0-9]+\.))", part)
        expanded.extend(normalize(item) for item in subparts if normalize(item))
    return expanded


def split_local_group_items(text: str) -> list[str]:
    text = strip_prefixes(text)
    text = re.sub(r"^(구비서류|공통 제출서류|추가 서류|첨부서류)\s*:\s*", "", text)
    if ":" in text:
        # Keep only the content side for source supplements like "구비서류: A, B".
        text = text.split(":", 1)[1]
    items = [normalize(item) for item in re.split(r",|ㆍ|·", text) if normalize(item)]
    result: list[str] = []
    buffer = ""
    for item in items:
        if buffer:
            item = normalize(f"{buffer} {item}")
            buffer = ""
        if item.count("(") > item.count(")"):
            buffer = item
            continue
        result.append(item)
    if buffer:
        result.append(buffer)
    return result


def extract_application_form(text: str) -> str:
    text = normalize(text)
    match = re.search(r"신청서\s+(.+?)(?:\s+신청작성예시|\s+구비서류|\s+수수료|$)", text)
    if match:
        return normalize(match.group(1))
    return ""


def document_name_and_condition(item: str) -> tuple[str, str]:
    item = normalize(item)
    condition = ""
    parens = re.findall(r"[\(\[]([^\)\]]+)[\)\]]", item)
    if parens:
        conditional_parts = [part for part in parens if any(marker in part for marker in CONDITIONAL_MARKERS)]
        if conditional_parts:
            condition = " / ".join(normalize(part) for part in conditional_parts)
    name = re.sub(r"[\(\[][^\)\]]+[\)\]]", "", item)
    name = re.sub(r"^(?:[가-하]\.|[0-9]+\.|[0-9]+의[0-9]+\.|\d+의\d+)\s*", "", name)
    name = re.sub(r"\s*(?:1부|각 1부|사본|원본)$", "", name)
    name = re.sub(r"^(?:필수적 첨부서류|허가신청시 첨부서류)\s*", "", name)
    name = normalize(name.strip(" :-"))
    if not condition and any(marker in item for marker in CONDITIONAL_MARKERS):
        condition = item
    return name, condition


def assertion_for(condition_text: str, text: str) -> str:
    if condition_text or any(marker in text for marker in CONDITIONAL_MARKERS):
        return "conditional"
    return "explicit"


def make_atomic_chunk(parent: dict[str, Any], suffix: str, kind: str, name: str, text: str) -> dict[str, Any]:
    chunk_id_value = f"evchunk_atomic_{stable_hash(parent.get('chunk_id'), suffix, name)}"
    return {
        "chunk_id": chunk_id_value,
        "source_document_id": parent.get("source_document_id", ""),
        "source_type": parent.get("source_type", ""),
        "source_record_id": parent.get("source_record_id", ""),
        "authority_level": parent.get("authority_level", "official"),
        "title": parent.get("title", ""),
        "section_path": f"{parent.get('section_path', '')} > {name}",
        "source_url": parent.get("source_url", ""),
        "raw_path": parent.get("raw_path", ""),
        "chunk_kind": kind,
        "sequence": "",
        "char_len": len(text),
        "estimated_tokens": max(1, len(text) // 2),
        "relevance_score": parent.get("relevance_score", 5),
        "scope_tags": parent.get("scope_tags", []),
        "text": text,
    }


def supplement_chunk(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "sequence": "",
        "char_len": len(row["text"]),
        "estimated_tokens": max(1, len(row["text"]) // 2),
        "relevance_score": 5,
        "scope_tags": ["startup", "permit", "local_official"],
    }


def add_node(nodes_by_key: dict[tuple[str, str], dict[str, str]], node_type: str, name: str, evidence: dict[str, Any]) -> str:
    clean = normalize(name)
    key = (node_type, clean)
    if key in nodes_by_key:
        return nodes_by_key[key]["node_id"]
    n_id = node_id(node_type, clean)
    nodes_by_key[key] = {
        "node_id": n_id,
        "node_type": node_type,
        "name": clean,
        "normalized_name": clean.casefold(),
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
    edge_source: str = "raw_atomic_rechunk",
) -> dict[str, str]:
    evidence = evidence_by_chunk[chunk_id_value]
    source_id = add_node(nodes_by_key, subject_type, subject_name, evidence)
    target_id = add_node(nodes_by_key, object_type, object_name, evidence)
    c_id = claim_id(edge_source, predicate, subject_type, subject_name, object_type, object_name, chunk_id_value)
    return {
        "edge_id": edge_id(edge_source, c_id),
        "source_node_id": source_id,
        "target_node_id": target_id,
        "predicate": predicate,
        "subject_type": subject_type,
        "subject_name": normalize(subject_name),
        "object_type": object_type,
        "object_name": normalize(object_name),
        "claim_id": c_id,
        "edge_source": edge_source,
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
        "extraction_method": edge_source,
        "model": "",
    }


def build_atomic_edges(
    evidence_by_chunk: dict[str, dict[str, Any]],
    nodes_by_key: dict[tuple[str, str], dict[str, str]],
) -> tuple[list[dict[str, str]], Counter[str]]:
    edges: list[dict[str, str]] = []
    stats: Counter[str] = Counter()

    for parent in list(evidence_by_chunk.values()):
        title = normalize(parent.get("title", ""))
        section = normalize(parent.get("section_path", ""))
        text = normalize(parent.get("text", ""))
        if not title or not text:
            continue
        if parent.get("chunk_id", "").startswith("evchunk_atomic_"):
            continue
        if str(parent.get("chunk_kind", "")).startswith("atomic_"):
            continue

        if (
            parent.get("source_type") == "gov24"
            and "서비스 개요" in section
            and title not in CORE_TITLES_WITH_MANUAL_ATOMICS
        ):
            form = extract_application_form(text)
            if form:
                chunk = make_atomic_chunk(parent, "application_form", "atomic_application_form", form, form)
                evidence_by_chunk[chunk["chunk_id"]] = chunk
                edges.append(
                    make_edge(
                        nodes_by_key,
                        evidence_by_chunk,
                        "requires_document",
                        "permit_service",
                        title,
                        "document",
                        form,
                        chunk["chunk_id"],
                        "신청서",
                        "explicit",
                    )
                )
                stats["application_form_edges"] += 1

        if (
            parent.get("source_type") == "gov24"
            and "민원인이 제출해야하는 서류" in section
            and title not in CORE_TITLES_WITH_MANUAL_ATOMICS
        ):
            for index, item in enumerate(split_parenthetical_items(text), start=1):
                name, condition = document_name_and_condition(item)
                if not name or name in GENERIC_DOCUMENT_NAMES or len(name) < 2:
                    continue
                if (
                    len(name) > 90
                    or "다음 각 목" in name
                    or "추가 서류:" in name
                    or name.endswith("확인합니다.")
                    or "허가신청시 첨부서류" in name
                    or "," in name
                ):
                    stats["skipped_noisy_required_item"] += 1
                    continue
                chunk = make_atomic_chunk(parent, f"required_{index}", "atomic_required_document", name, item)
                evidence_by_chunk[chunk["chunk_id"]] = chunk
                edges.append(
                    make_edge(
                        nodes_by_key,
                        evidence_by_chunk,
                        "requires_document",
                        "permit_service",
                        title,
                        "document",
                        name,
                        chunk["chunk_id"],
                        condition,
                        assertion_for(condition, item),
                    )
                )
                stats["required_document_edges"] += 1

        if parent.get("source_type") == "gov24" and "민원인이 제출하지 않아도 되는 서류" in section:
            for index, item in enumerate(split_parenthetical_items(text), start=1):
                name, condition = document_name_and_condition(item)
                if not name or name in GENERIC_DOCUMENT_NAMES or len(name) < 2:
                    continue
                chunk = make_atomic_chunk(parent, f"official_check_{index}", "atomic_official_check", name, item)
                evidence_by_chunk[chunk["chunk_id"]] = chunk
                check_condition = "담당공무원이 확인합니다."
                if condition:
                    check_condition = f"{check_condition} {condition}"
                edges.append(
                    make_edge(
                        nodes_by_key,
                        evidence_by_chunk,
                        "needs_check",
                        "permit_service",
                        title,
                        "check_item",
                        name,
                        chunk["chunk_id"],
                        check_condition,
                        assertion_for(condition, item),
                    )
                )
                stats["official_check_edges"] += 1

        if (
            parent.get("source_type") == "local_official_page"
            and "구비서류" in section
            and title not in {
                "마포구 식품접객업 영업신고 안내",
                "강남구 식품접객업 영업신고 안내",
                "강남구 도로점용허가 안내",
                "송파구 옥외광고물 표시 허가·신고 안내",
            }
        ):
            for index, item in enumerate(split_local_group_items(text), start=1):
                name, condition = document_name_and_condition(item)
                if not name or name in GENERIC_DOCUMENT_NAMES or len(name) < 2:
                    continue
                chunk = make_atomic_chunk(parent, f"local_required_{index}", "local_atomic_required_document", name, item)
                evidence_by_chunk[chunk["chunk_id"]] = chunk
                target_permit = title
                if "식품접객업" in title or "식품" in title:
                    target_permit = "식품관련영업신고"
                elif "도로점용" in title:
                    target_permit = "도로점용허가"
                elif "옥외광고물" in title:
                    target_permit = "옥외광고물 등의 표시허가(신고)"
                edges.append(
                    make_edge(
                        nodes_by_key,
                        evidence_by_chunk,
                        "requires_document",
                        "permit_service",
                        target_permit,
                        "document",
                        name,
                        chunk["chunk_id"],
                        condition,
                        assertion_for(condition, item),
                    )
                )
                stats["local_required_document_edges"] += 1

    return edges, stats


def add_manual_atomic_documents(
    evidence_by_chunk: dict[str, dict[str, Any]],
    nodes_by_key: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    for subject, document, parent_chunk_id, condition, assertion in MANUAL_ATOMIC_DOCUMENTS:
        parent = evidence_by_chunk[parent_chunk_id]
        chunk_id_value = f"evchunk_manual_atomic_{stable_hash(subject, document, parent_chunk_id)}"
        text = document if not condition else f"{document} ({condition})"
        evidence_by_chunk[chunk_id_value] = {
            **parent,
            "chunk_id": chunk_id_value,
            "section_path": f"{parent.get('section_path', '')} > {document}",
            "chunk_kind": "manual_atomic_required_document",
            "text": text,
            "char_len": len(text),
            "estimated_tokens": max(1, len(text) // 2),
        }
        edges.append(
            make_edge(
                nodes_by_key,
                evidence_by_chunk,
                "requires_document",
                "permit_service",
                subject,
                "document",
                document,
                chunk_id_value,
                condition,
                assertion,
                edge_source="manual_atomic_rechunk",
            )
        )
    return edges


def cleanup_existing_edges(edges: list[dict[str, str]]) -> tuple[list[dict[str, str]], Counter[str]]:
    stats: Counter[str] = Counter()
    cleaned: list[dict[str, str]] = []
    for edge in edges:
        if edge.get("edge_source") == "raw_atomic_rechunk" and edge.get("subject_name") in CORE_TITLES_WITH_MANUAL_ATOMICS:
            stats["removed_core_raw_atomic"] += 1
            continue
        if edge["predicate"] == "requires_document" and normalize(edge["object_name"]) in GENERIC_DOCUMENT_NAMES:
            stats["removed_generic_requires_document"] += 1
            continue
        if edge["predicate"] == "requires_document" and (
            len(normalize(edge["object_name"])) > 90
            or "다음 각 목" in edge["object_name"]
            or "추가 서류:" in edge["object_name"]
            or edge["object_name"].endswith("확인합니다.")
            or "허가신청시 첨부서류" in edge["object_name"]
        ):
            stats["removed_noisy_long_document"] += 1
            continue
        if edge["predicate"] == "requires_document":
            evidence_text = normalize(edge.get("evidence_text", ""))
            if not edge.get("condition_text") and any(marker in evidence_text for marker in CONDITIONAL_MARKERS):
                _, condition = document_name_and_condition(evidence_text)
                edge["condition_text"] = condition or evidence_text
                edge["assertion_level"] = "conditional"
                edge["review_status"] = "official_document"
                edge["extraction_method"] = "condition_backfill_from_evidence"
                stats["condition_backfilled"] += 1
        cleaned.append(edge)
    return cleaned, stats


def main() -> None:
    for path in [NODES_PATH, EDGES_PATH, EVIDENCE_PATH]:
        backup_once(path)

    nodes = read_csv(NODES_PATH)
    edges = read_csv(EDGES_PATH)
    evidence_by_chunk = read_evidence(EVIDENCE_PATH)

    for chunk in LOCAL_SUPPLEMENTAL_CHUNKS:
        evidence_by_chunk[chunk["chunk_id"]] = supplement_chunk(chunk)

    nodes_by_key = {(node["node_type"], normalize(node["name"])): node for node in nodes}
    cleaned_edges, cleanup_stats = cleanup_existing_edges(edges)
    atomic_edges, atomic_stats = build_atomic_edges(evidence_by_chunk, nodes_by_key)

    all_new_edges = []
    for spec in CURATED_CORE_EDGES:
        all_new_edges.append(make_edge(nodes_by_key, evidence_by_chunk, *spec, edge_source="source_backed_core_flow"))
    all_new_edges.extend(add_manual_atomic_documents(evidence_by_chunk, nodes_by_key))
    all_new_edges.extend(atomic_edges)

    seen = {
        (
            edge["predicate"],
            edge["subject_type"],
            normalize(edge["subject_name"]),
            edge["object_type"],
            normalize(edge["object_name"]),
            edge.get("chunk_id", ""),
        )
        for edge in cleaned_edges
    }
    added = 0
    for edge in all_new_edges:
        key = (
            edge["predicate"],
            edge["subject_type"],
            normalize(edge["subject_name"]),
            edge["object_type"],
            normalize(edge["object_name"]),
            edge.get("chunk_id", ""),
        )
        if key in seen:
            continue
        cleaned_edges.append(edge)
        seen.add(key)
        added += 1

    claim_counts: Counter[str] = Counter()
    for edge in cleaned_edges:
        if edge.get("claim_id"):
            claim_counts[edge["source_node_id"]] += 1
            claim_counts[edge["target_node_id"]] += 1

    final_nodes = list(nodes_by_key.values())
    for node in final_nodes:
        node["claim_count"] = str(claim_counts.get(node["node_id"], int(node.get("claim_count") or 0)))

    final_nodes.sort(key=lambda row: (row["node_type"], row["name"], row["node_id"]))
    cleaned_edges.sort(key=lambda row: (row["predicate"], row["source_node_id"], row["target_node_id"], row["edge_id"]))

    write_evidence(EVIDENCE_PATH, evidence_by_chunk)
    write_csv(NODES_PATH, final_nodes, NODE_COLUMNS)
    write_csv(EDGES_PATH, cleaned_edges, EDGE_COLUMNS)

    predicate_counts = Counter(edge["predicate"] for edge in cleaned_edges)
    source_counts = Counter(edge["edge_source"] for edge in cleaned_edges)
    report = [
        "# All Raw Rechunk Rebuild Report",
        "",
        "현재 minju evidence 전체를 대상으로 gov24 민원 서류 섹션, 담당공무원 확인 서류, 서비스 개요 신청서, 지역 공식 보강 source를 atomic chunk/edge로 다시 반영했습니다.",
        "",
        "## Counts",
        f"- final_nodes: {len(final_nodes)}",
        f"- final_edges: {len(cleaned_edges)}",
        f"- added_edges: {added}",
        f"- evidence_chunks_total: {len(evidence_by_chunk)}",
        "",
        "## Atomic Rechunk Stats",
    ]
    for key, value in sorted(atomic_stats.items()):
        report.append(f"- {key}: {value}")
    report.extend(["", "## Cleanup Stats"])
    for key, value in sorted(cleanup_stats.items()):
        report.append(f"- {key}: {value}")
    report.extend(["", "## Predicate Counts"])
    for key, value in sorted(predicate_counts.items()):
        report.append(f"- {key}: {value}")
    report.extend(["", "## Edge Source Counts"])
    for key, value in sorted(source_counts.items()):
        report.append(f"- {key}: {value}")
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"final_nodes={len(final_nodes)} final_edges={len(cleaned_edges)} added_edges={added}")
    print(f"atomic_stats={dict(atomic_stats)}")
    print(f"cleanup_stats={dict(cleanup_stats)}")
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
