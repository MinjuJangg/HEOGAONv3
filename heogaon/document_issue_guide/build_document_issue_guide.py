from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HEOGAON_ROOT = ROOT.parent
GRAPH_ROOT = HEOGAON_ROOT / "graph" / "output" / "final_graph"
DEPARTMENT_ROOT = HEOGAON_ROOT / "department_mapping"


FOOD_PERMIT_SERVICE_ROUTES = {
    "식품관련영업신고": {
        "permit_area": "식품영업신고",
        "submit_to_local_task_key": "food_business_report",
        "submit_to": "자치구 식품위생 담당부서",
    },
    "영업신고 및 사업자등록": {
        "permit_area": "식품영업신고",
        "submit_to_local_task_key": "food_business_report",
        "submit_to": "자치구 식품위생 담당부서 또는 관할 세무서",
    },
    "영업신고": {
        "permit_area": "식품영업신고",
        "submit_to_local_task_key": "food_business_report",
        "submit_to": "자치구 식품위생 담당부서",
    },
    "식품위생법 시행규칙 제42조 영업의 신고 등": {
        "permit_area": "식품영업신고",
        "submit_to_local_task_key": "food_business_report",
        "submit_to": "자치구 식품위생 담당부서",
    },
    "식품위생법 시행규칙 제43조 영업의 등록 등": {
        "permit_area": "식품영업등록",
        "submit_to_local_task_key": "food_business_report",
        "submit_to": "등록관청 또는 자치구 식품위생 담당부서",
    },
    "사업자등록 신청": {
        "permit_area": "사업자등록",
        "submit_to_local_task_key": "business_registration",
        "submit_to": "관할 세무서 또는 홈택스",
    },
    "사업자등록": {
        "permit_area": "사업자등록",
        "submit_to_local_task_key": "business_registration",
        "submit_to": "관할 세무서 또는 홈택스",
    },
    "옥외광고물 등의 표시허가(신고)": {
        "permit_area": "간판/옥외광고물",
        "submit_to_local_task_key": "outdoor_ad_report",
        "submit_to": "자치구 옥외광고물 담당부서",
    },
    "옥외광고물 등의 표시허가": {
        "permit_area": "간판/옥외광고물",
        "submit_to_local_task_key": "outdoor_ad_report",
        "submit_to": "자치구 옥외광고물 담당부서",
    },
    "도로점용허가": {
        "permit_area": "도로점용",
        "submit_to_local_task_key": "road_occupation_permit",
        "submit_to": "자치구 도로점용 담당부서",
    },
    "도로법 시행규칙 제26조 도로점용허가 신청 등": {
        "permit_area": "도로점용",
        "submit_to_local_task_key": "road_occupation_permit",
        "submit_to": "자치구 도로점용 담당부서",
    },
    "도로법 시행령 제56조 도로굴착을 수반하는 점용에 관한 사업계획서 등": {
        "permit_area": "도로점용/굴착",
        "submit_to_local_task_key": "road_occupation_permit",
        "submit_to": "자치구 도로점용 담당부서",
    },
    "통신판매업신고": {
        "permit_area": "통신판매",
        "submit_to_local_task_key": "ecommerce_report",
        "submit_to": "자치구 통신판매 담당부서",
    },
    "영업에 필요한 기반시설 설치": {
        "permit_area": "소방/LPG/기반시설",
        "submit_to_local_task_key": "fire_safety_completion",
        "submit_to": "관할 소방서 또는 관련 기반시설 담당기관",
    },
    "소방안전 등에 관한 관리": {
        "permit_area": "소방/LPG/기반시설",
        "submit_to_local_task_key": "fire_safety_completion",
        "submit_to": "관할 소방서",
    },
    "식품위생교육": {
        "permit_area": "영업신고 선행교육",
        "submit_to_local_task_key": "food_business_report",
        "submit_to": "자치구 식품위생 담당부서",
    },
    "건강진단": {
        "permit_area": "영업신고 선행검사",
        "submit_to_local_task_key": "food_business_report",
        "submit_to": "자치구 식품위생 담당부서",
    },
    "영업자 지위승계 신고": {
        "permit_area": "기존 업소 인수/승계",
        "submit_to_local_task_key": "food_admin_disposition_history",
        "submit_to": "자치구 식품위생 담당부서",
    },
    "영업승계 신고": {
        "permit_area": "기존 업소 인수/승계",
        "submit_to_local_task_key": "food_admin_disposition_history",
        "submit_to": "자치구 식품위생 담당부서",
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite(path: Path, tables: dict[str, tuple[list[dict[str, str]], list[str]]]) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        for table_name, (rows, fields) in tables.items():
            columns = ", ".join(f"{field} TEXT" for field in fields)
            conn.execute(f"CREATE TABLE {table_name} ({columns})")
            if rows:
                placeholders = ", ".join("?" for _ in fields)
                conn.executemany(
                    f"INSERT INTO {table_name} ({', '.join(fields)}) VALUES ({placeholders})",
                    [[row.get(field, "") for field in fields] for row in rows],
                )
        conn.execute("CREATE INDEX idx_issue_document_name ON document_issue_guide(document_name)")
        conn.execute("CREATE INDEX idx_issue_local_task ON document_issue_guide(submit_to_local_task_key)")
        conn.execute("CREATE INDEX idx_requirement_document ON permit_document_requirements(document_name)")
        conn.execute("CREATE INDEX idx_requirement_service ON permit_document_requirements(permit_service_name)")
        conn.execute("CREATE INDEX idx_all_issue_document_name ON all_document_issue_guide(document_name)")
        conn.execute("CREATE INDEX idx_all_submission_document ON all_permit_submission_documents(document_name)")
        conn.execute("CREATE INDEX idx_all_submission_service ON all_permit_submission_documents(permit_service_name)")
        conn.execute("CREATE INDEX idx_food_submission_document ON food_permit_submission_documents(document_name)")
        conn.execute("CREATE INDEX idx_food_submission_service ON food_permit_submission_documents(permit_service_name)")
        conn.commit()
    finally:
        conn.close()


def compact(text: str, limit: int = 260) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def load_graph() -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, dict[str, str]]]:
    nodes = read_csv(GRAPH_ROOT / "graph_nodes_high_precision.csv")
    edges = read_csv(GRAPH_ROOT / "graph_edges_high_precision.csv")
    nodes_by_id = {row["node_id"]: row for row in nodes}
    return nodes, edges, nodes_by_id


def load_local_tasks() -> dict[str, dict[str, str]]:
    return {
        row["local_task_key"]: row
        for row in read_csv(DEPARTMENT_ROOT / "local_department_tasks.csv")
    }


def build_requirement_rows(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for edge in edges:
        if edge["predicate"] != "requires_document":
            continue
        rows.append(
            {
                "permit_service_name": edge["subject_name"],
                "permit_service_type": edge["subject_type"],
                "document_name": edge["object_name"],
                "document_type": edge["object_type"],
                "source_url": edge["source_url"],
                "source_title": edge["title"],
                "section_path": edge["section_path"],
                "source_document_id": edge["source_document_id"],
                "chunk_id": edge["chunk_id"],
                "evidence_text": compact(edge["evidence_text"], 360),
                "condition_text": compact(edge["condition_text"], 220),
            }
        )
    return sorted(rows, key=lambda row: (row["permit_service_name"], row["document_name"]))


def build_prerequisite_rows(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for edge in edges:
        if edge["predicate"] != "requires_prerequisite":
            continue
        rows.append(
            {
                "target_document_or_step": edge["subject_name"],
                "prerequisite_name": edge["object_name"],
                "source_url": edge["source_url"],
                "source_title": edge["title"],
                "section_path": edge["section_path"],
                "source_document_id": edge["source_document_id"],
                "chunk_id": edge["chunk_id"],
                "evidence_text": compact(edge["evidence_text"], 360),
                "condition_text": compact(edge["condition_text"], 220),
            }
        )
    return sorted(rows, key=lambda row: (row["target_document_or_step"], row["prerequisite_name"]))


def build_submission_route_rows(edges: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for edge in edges:
        if edge["predicate"] != "handled_by":
            continue
        rows.append(
            {
                "service_or_check_name": edge["subject_name"],
                "service_or_check_type": edge["subject_type"],
                "department_function_name": edge["object_name"],
                "source_url": edge["source_url"],
                "source_title": edge["title"],
                "section_path": edge["section_path"],
                "source_document_id": edge["source_document_id"],
                "chunk_id": edge["chunk_id"],
                "evidence_text": compact(edge["evidence_text"], 360),
            }
        )
    return sorted(rows, key=lambda row: (row["department_function_name"], row["service_or_check_name"]))


def find_edge(
    edges: list[dict[str, str]],
    *,
    predicate: str | None = None,
    subject_contains: str | None = None,
    object_contains: str | None = None,
    text_contains: str | None = None,
) -> dict[str, str]:
    candidates: list[dict[str, str]] = []
    for edge in edges:
        if predicate and edge["predicate"] != predicate:
            continue
        if subject_contains and subject_contains not in edge["subject_name"]:
            continue
        if object_contains and object_contains not in edge["object_name"]:
            continue
        haystack = " ".join(
            [
                edge.get("subject_name", ""),
                edge.get("object_name", ""),
                edge.get("evidence_text", ""),
                edge.get("condition_text", ""),
                edge.get("title", ""),
                edge.get("section_path", ""),
            ]
        )
        if text_contains and text_contains not in haystack:
            continue
        candidates.append(edge)
    if not candidates:
        return {}

    source_priority = {
        "gov24": 0,
        "law.go.kr": 1,
        "easylaw": 2,
        "ontology": 9,
    }
    edge_priority = {
        "source_backed_seed": 0,
        "gov24_parser": 1,
        "derived_grounding": 2,
        "llm_claim": 3,
        "rule_seed": 9,
    }

    return sorted(
        candidates,
        key=lambda edge: (
            edge_priority.get(edge.get("edge_source", ""), 5),
            source_priority.get(edge.get("source_type", ""), 5),
            -len(edge.get("evidence_text", "")),
        ),
    )[0]


def source_from_edge(edge: dict[str, str]) -> dict[str, str]:
    return {
        "source_url": edge.get("source_url", ""),
        "source_title": edge.get("title", ""),
        "section_path": edge.get("section_path", ""),
        "source_document_id": edge.get("source_document_id", ""),
        "chunk_id": edge.get("chunk_id", ""),
        "evidence_text": compact(edge.get("evidence_text", ""), 420),
    }


def join_unique(values: list[str], limit: int | None = None) -> str:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = " ".join((value or "").split())
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if limit is not None and len(result) >= limit:
            break
    return "; ".join(result)


def route_for_service(service_name: str) -> dict[str, str]:
    explicit = FOOD_PERMIT_SERVICE_ROUTES.get(service_name)
    if explicit:
        return explicit

    rules = [
        (
            ("통신판매", "구매안전서비스"),
            "통신판매",
            "ecommerce_report",
            "자치구 통신판매 담당부서",
        ),
        (
            ("옥외광고", "광고물", "간판", "상호 및 광고물"),
            "간판/옥외광고물",
            "outdoor_ad_report",
            "자치구 옥외광고물 담당부서",
        ),
        (
            ("도로점용", "도로굴착", "도로법"),
            "도로점용",
            "road_occupation_permit",
            "자치구 도로점용 담당부서",
        ),
        (
            ("소방", "안전시설", "다중이용업소"),
            "소방/다중이용업소",
            "fire_safety_completion",
            "관할 소방서",
        ),
        (
            ("가스", "LPG", "액화석유"),
            "가스/LPG",
            "fire_safety_completion",
            "한국가스안전공사 또는 관할 가스/소방 담당기관",
        ),
        (
            ("사업자등록", "세금", "부가가치세", "종합소득세", "주류 면허", "면허세"),
            "세무/사업자등록",
            "business_registration",
            "관할 세무서 또는 홈택스",
        ),
        (
            ("사업자 유형", "간이과세", "간편장부", "현금영수증"),
            "세무/사업자유형",
            "business_registration",
            "관할 세무서 또는 홈택스",
        ),
        (
            ("건축물", "위반건축물", "용도", "상가건물", "임대차"),
            "건축물/임대차 확인",
            "building_register_issue",
            "정부24 또는 자치구 건축물대장/건축 담당부서",
        ),
        (
            ("임차인의 보호", "확정일자"),
            "상가임대차/확정일자",
            "business_registration",
            "관할 세무서 또는 임대차 확정일자 담당기관",
        ),
        (
            ("폐업",),
            "폐업/말소",
            "food_business_report",
            "자치구 식품위생 담당부서 또는 관할 세무서",
        ),
        (
            ("4대보험", "4대 보험", "근로", "채용", "고용", "산재", "국민연금", "건강보험"),
            "노무/4대보험",
            "",
            "4대사회보험 정보연계센터 또는 국민연금/건강보험/근로복지공단/고용센터",
        ),
        (
            (
                "매장운영",
                "금연구역",
                "커피 및 부자재",
                "쓰레기",
                "음식물 쓰레기",
                "영업설비",
                "청소년유해",
                "고객과의 분쟁",
                "모범업소",
                "업종별 영업시설",
                "허가 및 신고사항",
                "휴업신고",
                "영업자 지위",
            ),
            "식품영업 운영/변경",
            "food_business_report",
            "자치구 식품위생 담당부서 또는 관련 운영 기준 담당기관",
        ),
        (
            ("자금지원", "자금 지원", "소상공인"),
            "자금지원",
            "",
            "소상공인시장진흥공단 또는 정책자금 담당기관",
        ),
        (
            (
                "독립창업",
                "가맹사업",
                "창업형태",
                "상권",
                "입지분석",
                "커피전문점 창업",
                "인테리어",
                "상호 선정",
                "성공적인 운영",
            ),
            "창업준비/계약",
            "",
            "신청인, 계약 당사자, 가맹본부 또는 창업지원기관",
        ),
        (
            ("식품", "영업신고", "영업허가", "위생", "건강진단", "음식점", "원산지"),
            "식품영업",
            "food_business_report",
            "자치구 식품위생 담당부서",
        ),
    ]
    for keywords, permit_area, local_task_key, submit_to in rules:
        if any(keyword in service_name for keyword in keywords):
            return {
                "permit_area": permit_area,
                "submit_to_local_task_key": local_task_key,
                "submit_to": submit_to,
            }

    return {
        "permit_area": "기타 인허가/운영",
        "submit_to_local_task_key": "",
        "submit_to": "해당 인허가 또는 민원 담당기관",
    }


def profile_for_document(document_name: str, related_services: list[str]) -> dict[str, str]:
    haystack = f"{document_name} {' '.join(related_services)}"
    rules = [
        (
            ("건축물대장",),
            "건축물/용도 확인",
            "정부24 또는 자치구 건축물대장 발급 창구",
            "온라인 열람·발급 또는 방문 발급",
            "계약 전 또는 영업신고 전",
            "점포 주소 확정 후 용도와 위반건축물 여부 확인",
        ),
        (
            ("건강진단결과서", "보건증"),
            "식품영업 선행검사",
            "보건소 또는 지정 의료기관",
            "방문 검사 후 발급",
            "영업신고 전",
            "신분증 지참, 식품취급자 검사 대상 확인",
        ),
        (
            ("위생교육", "교육이수증", "수료증"),
            "식품영업 선행교육",
            "업종별 식품위생교육기관",
            "기관 선택 후 신청·결제·수강·수료증 출력",
            "영업신고 전",
            "일반음식점/휴게음식점 등 업종에 맞는 교육기관 선택",
        ),
        (
            ("식품접객업 영업신고증", "영업신고증"),
            "식품영업 결과물",
            "자치구 식품위생 담당부서",
            "구비서류 제출 후 신고 수리 시 발급",
            "사업자등록 신청 전",
            "위생교육, 건강진단결과서, 임대차계약서 등 영업신고 구비서류 선행",
        ),
        (
            ("식품 영업 신고서", "영업신고서"),
            "식품영업신고",
            "정부24 또는 자치구 식품위생 담당부서 민원서식",
            "온라인 신청 또는 방문 제출",
            "영업신고 신청 시",
            "점포 용도·위생교육·건강진단·임대차계약 준비 후 작성",
        ),
        (
            ("사업자등록 신청서",),
            "사업자등록",
            "홈택스 또는 관할 세무서 민원서식",
            "홈택스 온라인 신청 또는 세무서 방문",
            "영업신고증 발급 후, 사업개시일부터 20일 이내",
            "영업신고증, 임대차계약서 등 준비",
        ),
        (
            ("사업자등록증",),
            "사업자등록 결과물",
            "관할 세무서 또는 홈택스",
            "사업자등록 신청 수리 후 발급",
            "영업 개시 및 후속 인허가 전",
            "영업신고증과 임대차계약서 등 사업자등록 구비서류 선행",
        ),
        (
            ("임대차", "사용계약", "계약서", "승낙"),
            "계약/사용권 증빙",
            "임대인·임차인·소유자·관리자 등 계약 당사자",
            "계약 또는 승낙서 작성 후 원본/사본 준비",
            "각 인허가 신청 전",
            "소유자·관리인 권한 확인 후 계약 또는 승낙 확보",
        ),
        (
            ("신분증",),
            "본인확인",
            "신청인 본인 준비",
            "방문 신청 시 지참 또는 온라인 본인인증",
            "방문 접수 또는 본인확인 시",
            "신청자 본인 확인",
        ),
        (
            ("안전시설등 완비증명",),
            "소방/다중이용업소",
            "관할 소방서",
            "소방시설 설치·완공 신고 및 현장 확인 후 발급",
            "영업신고 전, 대상 조건 해당 시",
            "소방시설 설치신고서, 완공신고서, 도면, 현장 실사 준비",
        ),
        (
            ("소방시설", "완공신고", "설치신고", "소방"),
            "소방/다중이용업소",
            "관할 소방서 또는 소방시설 설계·시공업체",
            "신고서·도면 작성 후 소방서 제출",
            "안전시설등 완비증명서 발급 전",
            "임대차계약서, 건축물 용도 확인, 소방 도면·시공 상태 준비",
        ),
        (
            ("LPG", "액화석유가스", "가스"),
            "가스/LPG",
            "한국가스안전공사 또는 가스 시공·검사기관",
            "시공 완료 후 완성검사 및 증명서 발급",
            "영업신고 전, LPG 사용 시",
            "가스 배관·화구 시공 완료 및 검사 신청",
        ),
        (
            ("옥외광고물", "광고물", "간판"),
            "간판/옥외광고물",
            "정부24 또는 자치구 옥외광고물 담당부서",
            "온라인 신청 또는 방문 제출",
            "간판 설치 전",
            "표시 위치·규격·도안·소유자 승낙 여부 확인",
        ),
        (
            ("원색도안", "원색사진", "시방서", "구조안전"),
            "간판/옥외광고물 첨부서류",
            "신청인, 간판 제작업체 또는 구조안전 확인 전문기관",
            "도안·사진·시방서·구조안전 서류 작성 후 첨부",
            "옥외광고물 표시허가/신고 시",
            "건물 또는 물건 소유자 승낙, 설치 위치·규격 확인",
        ),
        (
            ("도로점용", "도로굴착"),
            "도로점용",
            "정부24 또는 자치구 도로점용 담당부서",
            "온라인 신청 또는 방문 제출",
            "도로·보도 공간 사용 전",
            "점용 위치·면적·기간, 굴착 여부 확인",
        ),
        (
            ("위치도", "평면도", "설계도", "도면", "복구계획", "지하매설물"),
            "도면/공사 첨부서류",
            "신청인, 설계·시공업체 또는 주요지하매설물 관리자",
            "도면·의견서·복구계획 작성 후 첨부",
            "해당 인허가 신청 시",
            "설치 위치·면적·공사 범위와 굴착 여부 확인",
        ),
        (
            ("구매안전서비스",),
            "통신판매",
            "은행, 전자결제사 또는 오픈마켓 등 구매안전서비스 제공기관",
            "서비스 가입 후 이용확인증 발급",
            "통신판매업신고 전",
            "온라인 판매 여부와 결제/정산 수단 확인",
        ),
        (
            ("통신판매",),
            "통신판매",
            "정부24 또는 자치구 통신판매 담당부서",
            "온라인 신청 또는 방문 제출",
            "온라인 판매 전",
            "사업자등록증, 구매안전서비스 이용확인증 등 준비",
        ),
        (
            ("법인등기", "등기부", "인감"),
            "법인/등기",
            "인터넷등기소 또는 등기소",
            "온라인 발급 또는 방문 발급",
            "법인 명의 신청 시",
            "법인 대표자와 신청 권한 확인",
        ),
        (
            ("주민등록", "가족관계"),
            "신원/관계 증빙",
            "정부24, 전자가족관계등록시스템 또는 주민센터",
            "온라인 발급 또는 방문 발급",
            "해당 증빙 제출 시",
            "신청인 정보 확인",
        ),
        (
            ("4대", "보험", "고용", "산재", "국민연금", "건강보험"),
            "노무/4대보험",
            "4대사회보험 정보연계센터 또는 각 보험기관",
            "온라인 신고 또는 기관별 제출",
            "근로자 채용 시",
            "근로계약 및 사업장 정보 준비",
        ),
        (
            ("근로계약",),
            "노무",
            "사업주와 근로자",
            "계약서 작성 및 교부",
            "근로자 채용 시",
            "임금, 근로시간, 업무내용 등 근로조건 확정",
        ),
        (
            ("세금계산서", "부가가치세", "소득세", "납세", "세무"),
            "세무",
            "국세청 홈택스 또는 관할 세무서",
            "온라인 신고·발급 또는 세무서 방문",
            "세무 신고·납부 시",
            "사업자등록과 거래 증빙 자료 준비",
        ),
        (
            ("수질검사", "먹는물"),
            "식품/수질검사",
            "공인 수질검사기관 또는 관할 기관",
            "검사 의뢰 후 성적서 발급",
            "해당 시설·영업 조건 해당 시",
            "수돗물 외 물 사용 여부 등 검사 대상 확인",
        ),
        (
            ("어린이놀이시설",),
            "시설 안전검사",
            "어린이놀이시설 안전검사기관",
            "검사 신청 후 합격증 발급",
            "놀이시설 설치·운영 조건 해당 시",
            "놀이시설 설치 여부 확인",
        ),
        (
            ("국유재산",),
            "재산 사용허가",
            "해당 국유재산 관리청",
            "사용허가 신청 후 허가서 발급",
            "국유재산 사용 조건 해당 시",
            "사용 대상 재산과 권한 확인",
        ),
        (
            ("도시철도시설",),
            "시설 사용계약",
            "도시철도 운영기관",
            "시설 사용계약 체결",
            "도시철도시설 내 영업 조건 해당 시",
            "시설 사용 권한과 계약 조건 확인",
        ),
    ]
    for keywords, document_group, place, channel, when_needed, prerequisite in rules:
        if any(keyword in haystack for keyword in keywords):
            return {
                "document_group": document_group,
                "issue_or_prepare_place": place,
                "issue_channel": channel,
                "when_needed": when_needed,
                "prerequisite_summary": prerequisite,
            }

    route = route_for_service(related_services[0]) if related_services else route_for_service(document_name)
    return {
        "document_group": route["permit_area"],
        "issue_or_prepare_place": "신청인 또는 해당 발급기관 준비",
        "issue_channel": "해당 민원 안내에 따라 온라인·방문·첨부 제출",
        "when_needed": "관련 인허가 신청 전 또는 신청 시",
        "prerequisite_summary": "해당 인허가의 조건과 신청인 자격 확인",
    }


def prerequisite_map(prerequisite_rows: list[dict[str, str]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for row in prerequisite_rows:
        target = row["target_document_or_step"]
        mapping.setdefault(target, []).append(row["prerequisite_name"])
    return mapping


def best_source_row(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        return {}
    source_priority = {"gov24": 0, "law.go.kr": 1, "easylaw": 2, "ontology": 9}
    return sorted(
        rows,
        key=lambda row: (
            source_priority.get(row.get("source_type", ""), 5),
            -len(row.get("evidence_text", "")),
        ),
    )[0]


def graph_key_for_task(local_tasks: dict[str, dict[str, str]], task_key: str) -> str:
    if not task_key:
        return ""
    return local_tasks.get(task_key, {}).get("graph_function_key", "")


def build_all_submission_rows(
    requirement_rows: list[dict[str, str]],
    prerequisite_rows: list[dict[str, str]],
    local_tasks: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    prereqs = prerequisite_map(prerequisite_rows)
    rows: list[dict[str, str]] = []
    for requirement in requirement_rows:
        service_name = requirement["permit_service_name"]
        document_name = requirement["document_name"]
        route = route_for_service(service_name)
        profile = profile_for_document(document_name, [service_name])
        task_key = route["submit_to_local_task_key"]
        prerequisite_summary = join_unique(prereqs.get(document_name, []), 20) or profile["prerequisite_summary"]
        rows.append(
            {
                "permit_area": route["permit_area"],
                "permit_service_name": service_name,
                "permit_service_type": requirement["permit_service_type"],
                "document_name": document_name,
                "document_type": requirement["document_type"],
                "document_group": profile["document_group"],
                "issue_or_prepare_place": profile["issue_or_prepare_place"],
                "issue_channel": profile["issue_channel"],
                "submit_to": route["submit_to"],
                "submit_to_local_task_key": task_key,
                "submit_to_graph_function_key": graph_key_for_task(local_tasks, task_key),
                "when_needed": profile["when_needed"],
                "prerequisite_summary": prerequisite_summary,
                "source_url": requirement["source_url"],
                "source_title": requirement["source_title"],
                "section_path": requirement["section_path"],
                "source_document_id": requirement["source_document_id"],
                "chunk_id": requirement["chunk_id"],
                "evidence_text": requirement["evidence_text"],
                "condition_text": requirement["condition_text"],
            }
        )
    return sorted(rows, key=lambda row: (row["permit_area"], row["permit_service_name"], row["document_name"]))


def build_food_permit_submission_rows(
    all_submission_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    food_services = set(FOOD_PERMIT_SERVICE_ROUTES)
    return [
        row
        for row in all_submission_rows
        if row["permit_service_name"] in food_services
        or row["submit_to_local_task_key"]
        in {
            "food_business_report",
            "fire_safety_completion",
            "outdoor_ad_report",
            "road_occupation_permit",
            "business_registration",
            "ecommerce_report",
        }
    ]


def build_all_issue_rows(
    nodes: list[dict[str, str]],
    requirement_rows: list[dict[str, str]],
    prerequisite_rows: list[dict[str, str]],
    local_tasks: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    prereqs = prerequisite_map(prerequisite_rows)
    requirements_by_doc: dict[str, list[dict[str, str]]] = {}
    document_node_counts: dict[str, int] = {}
    document_node_source: dict[str, dict[str, str]] = {}

    for requirement in requirement_rows:
        requirements_by_doc.setdefault(requirement["document_name"], []).append(requirement)

    for node in nodes:
        if node.get("node_type") != "document":
            continue
        name = node["name"]
        document_node_counts[name] = document_node_counts.get(name, 0) + 1
        document_node_source.setdefault(
            name,
            {
                "source_url": node.get("source_url", ""),
                "source_title": node.get("title", ""),
                "section_path": node.get("section_path", ""),
                "source_document_id": node.get("source_document_id", ""),
                "chunk_id": node.get("chunk_id", ""),
                "evidence_text": "",
            },
        )
        requirements_by_doc.setdefault(name, [])

    rows: list[dict[str, str]] = []
    for document_name in sorted(requirements_by_doc):
        requirements = requirements_by_doc[document_name]
        services = [row["permit_service_name"] for row in requirements]
        routes = [route_for_service(service) for service in services] or [route_for_service(document_name)]
        task_keys = [route["submit_to_local_task_key"] for route in routes]
        graph_keys = [graph_key_for_task(local_tasks, task_key) for task_key in task_keys]
        profile = profile_for_document(document_name, services)
        best = best_source_row(requirements) or document_node_source.get(document_name, {})
        prerequisite_summary = join_unique(prereqs.get(document_name, []), 30) or profile["prerequisite_summary"]
        rows.append(
            {
                "document_name": document_name,
                "document_group": profile["document_group"],
                "issue_or_prepare_place": profile["issue_or_prepare_place"],
                "issue_channel": profile["issue_channel"],
                "submit_to": join_unique([route["submit_to"] for route in routes], 12),
                "submit_to_local_task_key": join_unique(task_keys, 12),
                "submit_to_graph_function_key": join_unique(graph_keys, 12),
                "required_for": join_unique(services, 40),
                "when_needed": profile["when_needed"],
                "prerequisite_summary": prerequisite_summary,
                "graph_requirement_count": str(len(requirements)),
                "graph_document_node_count": str(document_node_counts.get(document_name, 0)),
                "source_url": best.get("source_url", ""),
                "source_title": best.get("source_title", ""),
                "section_path": best.get("section_path", ""),
                "source_document_id": best.get("source_document_id", ""),
                "chunk_id": best.get("chunk_id", ""),
                "evidence_text": best.get("evidence_text", ""),
            }
        )
    return rows


def build_core_issue_rows(
    edges: list[dict[str, str]],
    local_tasks: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    specs = [
        {
            "document_key": "building_register",
            "document_name": "건축물대장",
            "document_group": "계약 전 건물 확인",
            "issue_or_prepare_place": "정부24 또는 자치구 민원/부동산정보 담당 창구",
            "issue_channel": "온라인 발급 또는 방문 발급",
            "submit_to": "영업신고 전 용도·위반건축물 확인에 사용, 신고 단계에서는 담당공무원 확인 대상",
            "submit_to_local_task_key": "building_register_issue",
            "required_for": "건축물 용도 확인, 위반건축물 여부 확인, 식품관련영업신고 담당공무원 확인",
            "when_needed": "계약 직전 또는 영업신고 전",
            "prerequisite_summary": "주소 후보 확정 후 확인",
            "hint": {"predicate": "handled_by", "subject_contains": "건물 소유자와 관리인 권한 확인"},
        },
        {
            "document_key": "food_business_report_form",
            "document_name": "식품 영업 신고서",
            "document_group": "영업신고",
            "issue_or_prepare_place": "정부24 또는 자치구 식품위생 담당부서 민원서식",
            "issue_channel": "온라인 신청 또는 방문 제출",
            "submit_to": "자치구 식품위생 담당부서",
            "submit_to_local_task_key": "food_business_report",
            "required_for": "식품관련영업신고",
            "when_needed": "영업신고 신청 시",
            "prerequisite_summary": "위생교육, 건강진단결과서, 임대차계약서 등 준비 후 제출",
            "hint": {"predicate": "requires_document", "subject_contains": "식품관련영업신고", "object_contains": "식품 영업 신고서"},
        },
        {
            "document_key": "hygiene_training_certificate",
            "document_name": "위생교육 수료증",
            "document_group": "영업신고 선행서류",
            "issue_or_prepare_place": "업종별 식품위생교육기관",
            "issue_channel": "기관 선택 후 신청·결제·수강·수료증 출력",
            "submit_to": "자치구 식품위생 담당부서",
            "submit_to_local_task_key": "food_business_report",
            "required_for": "식품관련영업신고, 식품접객업 영업신고증",
            "when_needed": "영업신고 전",
            "prerequisite_summary": "일반음식점은 한국외식업중앙회·한국외식산업협회 등, 휴게음식점은 한국휴게음식업중앙회 등 업종별 기관 선택",
            "hint": {"predicate": "needs_check", "subject_contains": "식품위생교육", "text_contains": "한국외식업중앙회"},
        },
        {
            "document_key": "health_exam_result",
            "document_name": "건강진단결과서",
            "document_group": "영업신고 선행서류",
            "issue_or_prepare_place": "보건소 또는 지정 의료기관",
            "issue_channel": "방문 검사 후 발급",
            "submit_to": "자치구 식품위생 담당부서",
            "submit_to_local_task_key": "food_business_report",
            "required_for": "식품관련영업신고, 식품접객업 영업신고증",
            "when_needed": "영업신고 전",
            "prerequisite_summary": "창업자 및 종업원 인적사항 확인 후 검사",
            "hint": {"predicate": "requires_prerequisite", "subject_contains": "건강진단결과서", "object_contains": "보건소 또는 지정 의료기관 방문"},
        },
        {
            "document_key": "lease_contract",
            "document_name": "임대차계약서 또는 시설사용계약서",
            "document_group": "계약/사용권 증빙",
            "issue_or_prepare_place": "임대인·임차인 또는 시설사용 계약 당사자",
            "issue_channel": "계약 체결 후 원본/사본 준비",
            "submit_to": "자치구 식품위생 담당부서, 관할 세무서, 조건별 소방·도로·광고물 담당부서",
            "submit_to_local_task_key": "food_business_report",
            "required_for": "식품관련영업신고, 사업자등록, 안전시설등 완비증명서 등",
            "when_needed": "계약 후 각 인허가 신청 전",
            "prerequisite_summary": "건물 소유자·관리인 권한 확인 권장",
            "hint": {"predicate": "requires_document", "subject_contains": "식품관련영업신고", "object_contains": "임대차계약서"},
        },
        {
            "document_key": "id_card",
            "document_name": "신분증",
            "document_group": "본인확인",
            "issue_or_prepare_place": "신청인 본인 준비",
            "issue_channel": "방문 신청 시 지참",
            "submit_to": "자치구 식품위생 담당부서 등 방문 접수처",
            "submit_to_local_task_key": "food_business_report",
            "required_for": "식품관련영업신고",
            "when_needed": "영업신고 신청 시",
            "prerequisite_summary": "신청자 본인 확인",
            "hint": {"predicate": "requires_document", "subject_contains": "식품관련영업신고", "object_contains": "신분증"},
        },
        {
            "document_key": "fire_safety_completion_certificate",
            "document_name": "안전시설등 완비증명서",
            "document_group": "소방/다중이용업소",
            "issue_or_prepare_place": "소방본부장 또는 소방서장",
            "issue_channel": "관할 소방서 신고·현장 확인 후 발급",
            "submit_to": "자치구 식품위생 담당부서",
            "submit_to_local_task_key": "fire_safety_completion",
            "required_for": "식품관련영업신고 조건 해당 시",
            "when_needed": "영업신고 전, 소방 대상 조건 해당 시",
            "prerequisite_summary": "임대차계약서, 건축물대장 용도 확인, 소방시설 현장 실사 준비",
            "hint": {"predicate": "requires_document", "subject_contains": "식품관련영업신고", "object_contains": "안전시설등 완비증명서"},
        },
        {
            "document_key": "lpg_completion_certificate",
            "document_name": "액화석유가스 사용시설완성검사증명서",
            "document_group": "가스/LPG",
            "issue_or_prepare_place": "LPG 사용시설 완성검사 기관",
            "issue_channel": "가스 배관·화구 시공 후 완성검사",
            "submit_to": "식품관련영업신고 담당공무원 확인 대상",
            "submit_to_local_task_key": "food_business_report",
            "required_for": "LPG 사용 음식점의 식품관련영업신고 조건 해당 시",
            "when_needed": "영업신고 전, LPG 사용 시",
            "prerequisite_summary": "LPG 사용 여부 확인, 가스 배관 및 화구 시공 완료",
            "hint": {"text_contains": "액화석유가스 사용시설완성검사증명서"},
        },
        {
            "document_key": "food_business_report_certificate",
            "document_name": "식품접객업 영업신고증",
            "document_group": "영업신고 결과물",
            "issue_or_prepare_place": "자치구 식품위생 담당부서",
            "issue_channel": "구비서류 제출 후 신고 수리 시 발급",
            "submit_to": "관할 세무서 또는 홈택스",
            "submit_to_local_task_key": "food_business_report",
            "required_for": "사업자등록증 발급 전 선행 결과물",
            "when_needed": "사업자등록 신청 전",
            "prerequisite_summary": "위생교육 수료증, 건강진단결과서, 임대차계약서 또는 시설사용계약서, 신분증, 조건별 안전시설등 완비증명서",
            "hint": {"predicate": "requires_prerequisite", "subject_contains": "사업자등록증", "object_contains": "식품접객업 영업신고증"},
        },
        {
            "document_key": "business_registration_application",
            "document_name": "사업자등록 신청서",
            "document_group": "세무",
            "issue_or_prepare_place": "홈택스 또는 관할 세무서 민원서식",
            "issue_channel": "홈택스 온라인 신청 또는 세무서 방문",
            "submit_to": "관할 세무서 또는 홈택스",
            "submit_to_local_task_key": "business_registration",
            "required_for": "사업자등록증 발급",
            "when_needed": "영업신고증 발급 후, 사업개시일부터 20일 이내",
            "prerequisite_summary": "영업신고증, 임대차계약서 등 준비",
            "hint": {"predicate": "requires_document", "subject_contains": "사업자등록 신청", "object_contains": "사업자등록 신청서"},
        },
        {
            "document_key": "business_registration_certificate",
            "document_name": "사업자등록증",
            "document_group": "세무 결과물",
            "issue_or_prepare_place": "관할 세무서 또는 홈택스",
            "issue_channel": "사업자등록 신청 수리 후 발급",
            "submit_to": "옥외광고물·도로점용 등 후속 인허가에서 필요할 수 있음",
            "submit_to_local_task_key": "business_registration",
            "required_for": "영업 개시 및 후속 신고",
            "when_needed": "영업신고증 발급 후",
            "prerequisite_summary": "식품접객업 영업신고증, 임대차계약서, 20일 이내 신청기한 확인",
            "hint": {"predicate": "requires_prerequisite", "subject_contains": "사업자등록증", "object_contains": "식품접객업 영업신고증"},
        },
        {
            "document_key": "outdoor_ad_application",
            "document_name": "옥외광고물 표시 신청서",
            "document_group": "간판/옥외광고물",
            "issue_or_prepare_place": "정부24 또는 자치구 옥외광고물 담당부서 민원서식",
            "issue_channel": "온라인 신청 또는 방문 제출",
            "submit_to": "자치구 옥외광고물 담당부서",
            "submit_to_local_task_key": "outdoor_ad_report",
            "required_for": "옥외광고물 등의 표시허가(신고)",
            "when_needed": "간판 설치 전",
            "prerequisite_summary": "간판 디자인, 원색사진/도안, 설치 위치·규격 확인",
            "hint": {"predicate": "requires_document", "subject_contains": "옥외광고물", "object_contains": "옥외광고물 표시 신청서"},
        },
        {
            "document_key": "outdoor_ad_design_photo",
            "document_name": "광고물 원색도안 또는 원색사진",
            "document_group": "간판/옥외광고물",
            "issue_or_prepare_place": "신청인 또는 간판 제작업체",
            "issue_channel": "도안·사진 제작 후 첨부",
            "submit_to": "자치구 옥외광고물 담당부서",
            "submit_to_local_task_key": "outdoor_ad_report",
            "required_for": "옥외광고물 등의 표시허가(신고)",
            "when_needed": "간판 신청 시",
            "prerequisite_summary": "소유자 또는 관리자의 사용승낙 증명서류, 구조안전 확인 서류 등 분기 가능",
            "hint": {"predicate": "requires_document", "subject_contains": "옥외광고물", "object_contains": "광고물 원색도안"},
        },
        {
            "document_key": "outdoor_ad_owner_consent",
            "document_name": "소유자 또는 관리자의 사용승낙 증명서류",
            "document_group": "간판/옥외광고물",
            "issue_or_prepare_place": "토지·건물·물건 소유자 또는 관리자",
            "issue_channel": "승낙서 작성 후 첨부",
            "submit_to": "자치구 옥외광고물 담당부서",
            "submit_to_local_task_key": "outdoor_ad_report",
            "required_for": "타인 소유 또는 관리 물건에 광고물을 표시하는 경우",
            "when_needed": "간판 신청 시 조건 해당",
            "prerequisite_summary": "타인 소유 또는 관리 물건 여부 확인",
            "hint": {"predicate": "needs_check", "subject_contains": "옥외광고물", "text_contains": "소유자 또는 관리자의 사용승락"},
        },
        {
            "document_key": "road_occupation_application",
            "document_name": "도로점용허가 신청서",
            "document_group": "도로/외부공간",
            "issue_or_prepare_place": "정부24 또는 자치구 도로점용 담당부서 민원서식",
            "issue_channel": "온라인 신청 또는 방문 제출",
            "submit_to": "자치구 도로점용 담당부서",
            "submit_to_local_task_key": "road_occupation_permit",
            "required_for": "도로점용허가",
            "when_needed": "보도·도로 공간 점용 전",
            "prerequisite_summary": "도로점용 대상 확인, 위치도 및 평면도 준비",
            "hint": {"predicate": "requires_document", "subject_contains": "도로점용허가", "object_contains": "도로점용허가 신청서"},
        },
        {
            "document_key": "road_location_plan",
            "document_name": "위치도 및 평면도",
            "document_group": "도로/외부공간",
            "issue_or_prepare_place": "신청인 또는 설계/시공업체",
            "issue_channel": "점용 위치·면적 도면 작성 후 첨부",
            "submit_to": "자치구 도로점용 담당부서",
            "submit_to_local_task_key": "road_occupation_permit",
            "required_for": "도로점용허가",
            "when_needed": "도로점용허가 신청 시",
            "prerequisite_summary": "도로굴착을 수반하는 경우 주요지하매설물 관리자 의견서·사후관리계획 등 추가 가능",
            "hint": {"predicate": "requires_document", "subject_contains": "도로점용허가", "object_contains": "위치도 및 평면도"},
        },
        {
            "document_key": "road_excavation_drawings",
            "document_name": "도면(설계도면 및 주요지하매설물 관리자의 의견서/사후관리계획 등 서류)",
            "document_group": "도로/굴착 분기",
            "issue_or_prepare_place": "신청인, 설계/시공업체, 주요지하매설물 관리자",
            "issue_channel": "굴착 여부에 따라 도면·의견서·사후관리계획 준비",
            "submit_to": "자치구 도로점용 담당부서",
            "submit_to_local_task_key": "road_occupation_permit",
            "required_for": "도로굴착을 수반하는 도로점용허가",
            "when_needed": "굴착 포함 도로점용 신청 시",
            "prerequisite_summary": "점용 위치·구간·면적, 굴착공사 시행범위 표시",
            "hint": {"predicate": "requires_document", "subject_contains": "도로점용허가", "object_contains": "도면"},
        },
        {
            "document_key": "ecommerce_purchase_safety",
            "document_name": "구매안전서비스 이용확인증",
            "document_group": "온라인 판매/통신판매",
            "issue_or_prepare_place": "은행 또는 전자결제/오픈마켓 등 구매안전서비스 제공기관",
            "issue_channel": "서비스 가입 후 확인증 발급",
            "submit_to": "자치구 통신판매·지역경제 담당부서",
            "submit_to_local_task_key": "ecommerce_report",
            "required_for": "통신판매업신고",
            "when_needed": "온라인 판매를 할 경우 신고 전",
            "prerequisite_summary": "온라인 판매 여부 확인",
            "hint": {"predicate": "requires_document", "subject_contains": "통신판매업신고", "object_contains": "구매안전서비스 이용확인증"},
        },
    ]

    rows: list[dict[str, str]] = []
    for spec in specs:
        edge = find_edge(edges, **spec.pop("hint"))
        local_task = local_tasks.get(spec["submit_to_local_task_key"], {})
        row = {
            **spec,
            "submit_to_graph_function_key": local_task.get("graph_function_key", ""),
        }
        row.update(source_from_edge(edge))
        rows.append(row)
    return rows


def main() -> None:
    nodes, edges, _nodes_by_id = load_graph()
    local_tasks = load_local_tasks()

    issue_rows = build_core_issue_rows(edges, local_tasks)
    requirement_rows = build_requirement_rows(edges)
    prerequisite_rows = build_prerequisite_rows(edges)
    submission_route_rows = build_submission_route_rows(edges)
    all_issue_rows = build_all_issue_rows(nodes, requirement_rows, prerequisite_rows, local_tasks)
    all_submission_rows = build_all_submission_rows(requirement_rows, prerequisite_rows, local_tasks)
    food_submission_rows = build_food_permit_submission_rows(all_submission_rows)

    issue_fields = [
        "document_key",
        "document_name",
        "document_group",
        "issue_or_prepare_place",
        "issue_channel",
        "submit_to",
        "submit_to_local_task_key",
        "submit_to_graph_function_key",
        "required_for",
        "when_needed",
        "prerequisite_summary",
        "source_url",
        "source_title",
        "section_path",
        "source_document_id",
        "chunk_id",
        "evidence_text",
    ]
    requirement_fields = [
        "permit_service_name",
        "permit_service_type",
        "document_name",
        "document_type",
        "source_url",
        "source_title",
        "section_path",
        "source_document_id",
        "chunk_id",
        "evidence_text",
        "condition_text",
    ]
    prerequisite_fields = [
        "target_document_or_step",
        "prerequisite_name",
        "source_url",
        "source_title",
        "section_path",
        "source_document_id",
        "chunk_id",
        "evidence_text",
        "condition_text",
    ]
    route_fields = [
        "service_or_check_name",
        "service_or_check_type",
        "department_function_name",
        "source_url",
        "source_title",
        "section_path",
        "source_document_id",
        "chunk_id",
        "evidence_text",
    ]
    all_issue_fields = [
        "document_name",
        "document_group",
        "issue_or_prepare_place",
        "issue_channel",
        "submit_to",
        "submit_to_local_task_key",
        "submit_to_graph_function_key",
        "required_for",
        "when_needed",
        "prerequisite_summary",
        "graph_requirement_count",
        "graph_document_node_count",
        "source_url",
        "source_title",
        "section_path",
        "source_document_id",
        "chunk_id",
        "evidence_text",
    ]
    all_submission_fields = [
        "permit_area",
        "permit_service_name",
        "permit_service_type",
        "document_name",
        "document_type",
        "document_group",
        "issue_or_prepare_place",
        "issue_channel",
        "submit_to",
        "submit_to_local_task_key",
        "submit_to_graph_function_key",
        "when_needed",
        "prerequisite_summary",
        "source_url",
        "source_title",
        "section_path",
        "source_document_id",
        "chunk_id",
        "evidence_text",
        "condition_text",
    ]

    write_csv(ROOT / "document_issue_guide.csv", issue_rows, issue_fields)
    write_csv(ROOT / "permit_document_requirements.csv", requirement_rows, requirement_fields)
    write_csv(ROOT / "document_prerequisites.csv", prerequisite_rows, prerequisite_fields)
    write_csv(ROOT / "submission_routes.csv", submission_route_rows, route_fields)
    write_csv(ROOT / "all_document_issue_guide.csv", all_issue_rows, all_issue_fields)
    write_csv(ROOT / "all_permit_submission_documents.csv", all_submission_rows, all_submission_fields)
    write_csv(ROOT / "food_permit_submission_documents.csv", food_submission_rows, all_submission_fields)
    write_sqlite(
        ROOT / "document_issue_guide.sqlite",
        {
            "document_issue_guide": (issue_rows, issue_fields),
            "permit_document_requirements": (requirement_rows, requirement_fields),
            "document_prerequisites": (prerequisite_rows, prerequisite_fields),
            "submission_routes": (submission_route_rows, route_fields),
            "all_document_issue_guide": (all_issue_rows, all_issue_fields),
            "all_permit_submission_documents": (all_submission_rows, all_submission_fields),
            "food_permit_submission_documents": (food_submission_rows, all_submission_fields),
        },
    )

    summary = {
        "core_issue_guide_rows": len(issue_rows),
        "all_document_issue_guide_rows": len(all_issue_rows),
        "all_permit_submission_document_rows": len(all_submission_rows),
        "food_permit_submission_document_rows": len(food_submission_rows),
        "permit_document_requirement_rows": len(requirement_rows),
        "document_prerequisite_rows": len(prerequisite_rows),
        "submission_route_rows": len(submission_route_rows),
        "source_graph_edges": str(GRAPH_ROOT / "graph_edges_high_precision.csv"),
        "source_graph_nodes": str(GRAPH_ROOT / "graph_nodes_high_precision.csv"),
        "source_local_tasks": str(DEPARTMENT_ROOT / "local_department_tasks.csv"),
        "outputs": [
            "document_issue_guide.csv",
            "all_document_issue_guide.csv",
            "all_permit_submission_documents.csv",
            "food_permit_submission_documents.csv",
            "permit_document_requirements.csv",
            "document_prerequisites.csv",
            "submission_routes.csv",
            "document_issue_guide.sqlite",
        ],
    }
    (ROOT / "document_issue_guide_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
