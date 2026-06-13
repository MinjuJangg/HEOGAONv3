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
OUT_JSON = ROOT / "ten_scenario_full_answers.json"
OUT_MD = ROOT / "ten_scenario_full_answers.md"


FOOD_PERMIT = "식품관련영업신고"
ROAD_PERMIT = "도로점용허가"
AD_PERMIT = "옥외광고물 등의 표시허가(신고)"
BUSINESS_REGISTRATION = "사업자등록 신청"
SUCCESSION_PERMIT = "영업자 지위승계 신고"
MAIL_ORDER_PERMIT = "통신판매업신고"


SCENARIOS = [
    {
        "scenario_id": "s01_mapo_cafe_basic",
        "input": "마포구 카페 창업(휴게음식점, LPG 없음, 지상 1층)",
        "district": "마포구",
        "business_type": "휴게음식점영업",
        "permits": [FOOD_PERMIT, BUSINESS_REGISTRATION],
        "condition_terms": [],
        "force_documents": ["영업신고증"],
        "order": [
            "점포 후보 주소 확정",
            "건물 소유자/관리인 권한 및 임대차 가능 여부 확인",
            "건축물대장 발급 후 용도와 위반건축물 여부 확인",
            "휴게음식점 가능 여부 및 주류 판매 없음 확인",
            "위생교육 수료증과 건강진단결과서 준비",
            "임대차계약서, 신분증, 영업신고 신청서 준비",
            "마포구보건소 식품위생 담당 창구에 식품관련영업신고",
            "영업신고증 발급 후 사업자등록 신청",
        ],
    },
    {
        "scenario_id": "s02_mapo_cafe_lpg",
        "input": "마포구 카페 창업 + LPG 사용",
        "district": "마포구",
        "business_type": "휴게음식점영업",
        "permits": [FOOD_PERMIT, BUSINESS_REGISTRATION],
        "condition_terms": ["LPG", "액화석유가스"],
        "force_documents": ["영업신고증", "LPG 검사필증/필증"],
        "order": [
            "주소 확정 및 건축물대장 용도/위반 여부 확인",
            "LPG 사용 여부와 가스 배관/화구 시공 범위 확정",
            "한국가스안전공사 완성검사 후 LPG 검사필증 준비",
            "위생교육 수료증, 건강진단결과서, 임대차계약서 준비",
            "식품관련영업신고 제출",
            "영업신고증 발급 후 사업자등록 신청",
        ],
    },
    {
        "scenario_id": "s03_mapo_cafe_basement_fire",
        "input": "마포구 지하 80㎡ 카페 창업(소방완비 대상)",
        "district": "마포구",
        "business_type": "휴게음식점영업",
        "permits": [FOOD_PERMIT, BUSINESS_REGISTRATION],
        "condition_terms": ["소방", "안전시설", "지하층", "66㎡", "100㎡"],
        "force_documents": ["영업신고증", "안전시설등 완비증명서/소방완비증명서"],
        "order": [
            "주소 확정 및 건축물대장 용도/위반 여부 확인",
            "지하층 면적 기준으로 안전시설등 완비증명서 대상 여부 확인",
            "소방시설 설치/보완 및 관할 소방서 현장 확인",
            "안전시설등 완비증명서 발급",
            "위생교육 수료증, 건강진단결과서, 임대차계약서 준비",
            "식품관련영업신고 제출",
            "영업신고증 발급 후 사업자등록 신청",
        ],
    },
    {
        "scenario_id": "s04_gangnam_restaurant_basic",
        "input": "강남구 일반음식점 신규 창업",
        "district": "강남구",
        "business_type": "일반음식점영업",
        "permits": [FOOD_PERMIT, BUSINESS_REGISTRATION],
        "condition_terms": [],
        "force_documents": ["영업신고증"],
        "order": [
            "점포 주소 확정",
            "건축물대장 용도와 위반건축물 여부 확인",
            "같은 장소 기존 업소 행정처분 이력 확인",
            "위생교육 수료증과 건강진단결과서 준비",
            "식품영업신고서, 상담일지, 임대차계약서, 신분증 준비",
            "강남구보건소 2층 위생민원실에 신규신고",
            "영업신고증 발급 후 사업자등록 신청",
        ],
    },
    {
        "scenario_id": "s05_gangnam_restaurant_road_terrace",
        "input": "강남구 일반음식점 + 도로점용 테라스",
        "district": "강남구",
        "business_type": "일반음식점영업",
        "permits": [FOOD_PERMIT, BUSINESS_REGISTRATION, ROAD_PERMIT],
        "condition_terms": [],
        "force_documents": ["영업신고증", "사업자등록증 사본"],
        "order": [
            "점포 주소 확정 및 건축물대장 확인",
            "영업신고 선행서류 준비 후 강남구보건소에 식품관련영업신고",
            "영업신고증 발급 후 사업자등록 신청",
            "테라스가 사유지인지 공공 도로/보도인지 확인",
            "도로점용 위치도, 평면도, 설계도면 준비",
            "강남구청 건설관리과 도로점용 담당에 도로점용허가 신청",
        ],
    },
    {
        "scenario_id": "s06_gangnam_restaurant_groundwater",
        "input": "강남구 일반음식점 + 지하수 사용",
        "district": "강남구",
        "business_type": "일반음식점영업",
        "permits": [FOOD_PERMIT, BUSINESS_REGISTRATION],
        "condition_terms": ["지하수", "수질검사", "수질"],
        "force_documents": ["영업신고증", "수질검사시험성적서"],
        "order": [
            "주소 확정 및 건축물대장 용도/위반 여부 확인",
            "조리·세척에 지하수를 쓰는지 확인",
            "먹는물 수질검사기관에 수질검사 의뢰 및 시험성적서 발급",
            "위생교육 수료증, 건강진단결과서, 임대차계약서 준비",
            "강남구보건소 위생민원실에 식품관련영업신고",
            "영업신고증 발급 후 사업자등록 신청",
        ],
    },
    {
        "scenario_id": "s07_songpa_fixed_sign",
        "input": "송파구 벽면/돌출/지주 간판 설치",
        "district": "송파구",
        "business_type": "간판 설치",
        "permits": [AD_PERMIT],
        "condition_terms": ["간판", "옥외광고물", "고정 광고물"],
        "force_documents": [],
        "exclude_condition_terms": ["입간판", "배너"],
        "order": [
            "간판 종류, 규격, 위치, 표시방법 확인",
            "건물주 또는 관리자 승낙 확보",
            "원색사진/원색도안, 설계도서 또는 설명서 준비",
            "송파구청 민원행정과 통합민원창구에 신청",
            "도시계획과 검토 후 수수료 납부",
            "허가·신고증 발부 후 설치",
        ],
    },
    {
        "scenario_id": "s08_songpa_standing_banner",
        "input": "송파구 입간판(배너) 설치",
        "district": "송파구",
        "business_type": "입간판 설치",
        "permits": [AD_PERMIT],
        "condition_terms": ["입간판", "배너"],
        "force_documents": ["사업자등록증 사본", "입간판 도안"],
        "exclude_documents": ["광고물 형상·규격·구조·의장 설명서", "설계도서", "설치장소 주변 원색사진", "원색사진 또는 원색도안"],
        "order": [
            "사업자등록증 준비",
            "입간판 규격 제한과 설치 위치 확인",
            "건물주 또는 관리자 승낙 확보",
            "입간판 도안 또는 길이·크기 표기 사진 준비",
            "송파구청 민원행정과 통합민원창구 또는 정부24로 신고",
            "도시계획과 검토 후 수수료 납부 및 신고 처리",
        ],
    },
    {
        "scenario_id": "s09_gangnam_food_succession",
        "input": "강남구 음식점 양수 후 영업자 지위승계",
        "district": "강남구",
        "business_type": "일반음식점 지위승계",
        "permits": [SUCCESSION_PERMIT],
        "condition_terms": ["양도", "양수", "지위승계"],
        "force_documents": [],
        "exclude_documents": ["보험가입 증빙 서류", "책임보험 가입 증빙 서류", "영업신고증", "신분증"],
        "order": [
            "기존 업소 행정처분 이력과 영업신고증 상태 확인",
            "양도인·양수인 간 양도양수계약 체결",
            "양수인 위생교육 수료증과 건강진단결과서 준비",
            "임대차계약서 또는 사용권원 정리",
            "식품영업자 지위승계신고서와 기존 영업신고증 준비",
            "강남구보건소 위생민원실에 지위승계 신고",
            "필요 시 사업자등록 정정 또는 신규 등록",
        ],
    },
    {
        "scenario_id": "s10_gangnam_online_sales",
        "input": "강남구 온라인 판매 병행(통신판매업신고)",
        "district": "강남구",
        "business_type": "통신판매업",
        "permits": [BUSINESS_REGISTRATION, MAIL_ORDER_PERMIT],
        "condition_terms": ["통신판매", "구매안전", "선지급", "온라인"],
        "force_documents": ["구매안전서비스 이용확인증", "사업자등록증"],
        "exclude_documents": ["위생교육수료증", "영업신고증", "신분증"],
        "order": [
            "사업자등록 신청 및 사업자등록증 준비",
            "온라인 판매 방식, 결제 방식, 사이트/플랫폼 정보 확정",
            "선지급식 결제 또는 PG/에스크로 이용 시 구매안전서비스 이용확인증 발급",
            "통신판매업 신고서와 신분증 준비",
            "강남구청 지역경제과 또는 정부24로 통신판매업 신고",
            "신고 수리 후 등록면허세 납부 및 신고증 확인",
        ],
    },
]


LOCAL_DISTRICTS = ("마포구", "강남구", "송파구")
EXCLUDED_DOCS = {"사업자등록증", "자금출처명세서"}


CANONICAL_DOCS = [
    ("기존 영업신고증", ["기존 영업신고증"]),
    ("양도인 신분증", ["양도인 신분증"]),
    ("양수인 신분증", ["양수인 신분증"]),
    ("대표자 실물신분증", ["대표자 실물신분증"]),
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
    ("영업신고증", ["영업신고증", "식품접객업 영업신고증"]),
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
    ("설계도서", ["설계도서", "설계도서 또는 설명서"]),
    ("광고물관리심의위원회 심의관련서류", ["광고물관리심의위원회 심의관련서류"]),
    ("건물 구조안전 확인 서류", ["건물 구조안전 확인 서류"]),
    ("입간판 도안", ["입간판 도안"]),
    ("통신판매업 신고서", ["통신판매업 신고서", "통신판매업 신고서 ( 전자상거래 등에서의 소비자보호에 관한 법률 시행규칙 : 별지서식 1호 )", "신청서"]),
    ("사업자등록증", ["사업자등록증", "사업자등록증명"]),
    ("구매안전서비스 이용확인증", ["구매안전서비스 이용 확인증", "구매안전서비스이용확인증", "통신판매업 신고 구매안전서비스 이용 확인증"]),
    ("영업자 지위승계신고서", ["영업자 지위승계 신고서", "식품영업자 지위승계신고서"]),
    ("양도양수계약서", ["양도양수계약서", "양도양수 계약서 또는 권리관계 증빙"]),
    ("기존 영업신고증", ["영업허가증·영업신고증·영업등록증 및 관련 서류"]),
    ("위임장/대리인 신분증", ["위임장 및 대리인 신분증", "위임장 및 위임인의 신분증명서 사본"]),
    ("법인서류", ["법인서류"]),
    ("대표자 인감도장 및 인감증명서", ["대표자 인감도장 및 인감증명서"]),
    ("대리인 실물신분증", ["대리인 실물신분증"]),
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
    "신탁",
    "입간판",
    "배너",
    "선지급",
    "대리",
]


ISSUE_GUIDE = {
    "식품 영업 신고서/영업신고 신청서": "정부24/관할 보건소 서식",
    "상담일지": "강남구보건소 위생민원실 서식",
    "임대차계약서": "임대인·임차인 계약 체결",
    "위생교육수료증": "업종별 위생교육기관(일반음식점: 한국외식업중앙회, 휴게음식점: 한국휴게음식업중앙회 등)",
    "건강진단결과서": "보건소 또는 지정 의료기관",
    "신분증": "본인 보유",
    "대표자 실물신분증": "대표자 보유",
    "안전시설등 완비증명서/소방완비증명서": "관할 소방서",
    "LPG 검사필증/필증": "한국가스안전공사",
    "전기안전검사필증": "한국전기안전공사",
    "수질검사시험성적서": "먹는물 수질검사기관",
    "사업자등록 신청서": "홈택스 또는 관할 세무서 서식",
    "영업신고증": "관할 보건소/식품위생 담당",
    "도로점용허가 신청서": "정부24 또는 관할 구청 도로점용 담당 서식",
    "사업자등록증 사본": "홈택스 또는 관할 세무서",
    "사업자등록증": "홈택스 또는 관할 세무서",
    "위치도": "신청인/설계자 작성",
    "위치도 및 평면도": "신청인/설계자 작성",
    "설계도면": "설계자/시공업체 작성",
    "옥외광고물 표시 신청서": "정부24 또는 관할 구청 광고물 담당 서식",
    "소유자/관리자 사용승낙서": "건물주 또는 관리자 작성",
    "설치장소 주변 원색사진": "신청인/광고업체 준비",
    "원색사진 또는 원색도안": "신청인/광고업체 준비",
    "광고물 형상·규격·구조·의장 설명서": "신청인/광고업체 또는 설계자 작성",
    "설계도서": "광고업체/설계자 작성",
    "입간판 도안": "신청인/광고업체 준비",
    "통신판매업 신고서": "정부24 또는 관할 구청 통신판매 담당 서식",
    "구매안전서비스 이용확인증": "은행, PG사, 오픈마켓/플랫폼 등 구매안전서비스 제공기관",
    "영업자 지위승계신고서": "정부24 또는 관할 보건소 서식",
    "양도양수계약서": "양도인·양수인 작성",
    "기존 영업신고증": "양도인/기존 영업자 보유",
    "양도인 신분증": "양도인 보유",
    "양수인 신분증": "양수인 보유",
    "위임장/대리인 신분증": "위임자 작성 및 대리인 보유",
    "법인서류": "인터넷등기소/법인 보유",
    "대표자 인감도장 및 인감증명서": "대표자 보유 및 주민센터/정부24 등",
    "대리인 실물신분증": "대리인 보유",
}


SUBMISSION_GUIDE = {
    FOOD_PERMIT: {
        "마포구": "마포구보건소 식품위생 담당 창구",
        "강남구": "강남구보건소 2층 위생민원실",
        "default": "관할 시·군·구 식품위생 담당 부서",
    },
    BUSINESS_REGISTRATION: {"default": "관할 세무서 또는 홈택스"},
    ROAD_PERMIT: {
        "강남구": "강남구청 건설관리과 도로점용 담당",
        "default": "관할 구청 도로점용 담당 부서",
    },
    AD_PERMIT: {
        "송파구": "송파구청 민원행정과 통합민원창구(2층), 검토: 도시계획과",
        "default": "관할 구청 옥외광고물 담당 부서",
    },
    SUCCESSION_PERMIT: {
        "강남구": "강남구보건소 2층 위생민원실",
        "default": "관할 보건소/식품위생 담당 부서",
    },
    MAIL_ORDER_PERMIT: {
        "강남구": "강남구청 지역경제과 또는 정부24",
        "default": "관할 구청 통신판매/지역경제 담당 부서 또는 정부24",
    },
}


PERMIT_PREREQUISITE_SUBJECTS = {
    FOOD_PERMIT: ["식품접객업 영업신고증"],
    BUSINESS_REGISTRATION: ["사업자등록증"],
    ROAD_PERMIT: ["도로점용허가"],
    AD_PERMIT: ["옥외광고물(간판) 허가 및 신고증"],
}


DOCUMENT_PREREQUISITE_SUBJECTS = {
    "LPG 검사필증/필증": ["액화석유가스 완성검사필증"],
    "안전시설등 완비증명서/소방완비증명서": ["안전시설등 완비증명서"],
    "영업신고증": ["식품접객업 영업신고증"],
    "사업자등록증": ["사업자등록증"],
}


def read_edges() -> list[dict[str, str]]:
    with EDGES_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def compact(text: str, limit: int = 180) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def canonical_doc(name: str, subject: str = "") -> str:
    if subject == MAIL_ORDER_PERMIT and name == "신청서":
        return "통신판매업 신고서"
    for canonical, aliases in CANONICAL_DOCS:
        if any(alias in name for alias in aliases):
            return canonical
    return name


def source_matches_district(edge: dict[str, str], district: str) -> bool:
    source_blob = " ".join([edge.get("title", ""), edge.get("source_url", ""), edge.get("chunk_id", "")])
    for local in LOCAL_DISTRICTS:
        if local in source_blob and local != district:
            return False
    return True


def district_rank(edge: dict[str, str], district: str) -> int:
    source_blob = " ".join([edge.get("title", ""), edge.get("source_url", ""), edge.get("chunk_id", "")])
    return 0 if district in source_blob else 1


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


def is_conditional(edge: dict[str, str], canonical: str) -> bool:
    if edge.get("assertion_level") == "conditional":
        return True
    if edge.get("assertion_level") == "explicit" and not edge.get("condition_text"):
        return False
    blob = " ".join([canonical, edge.get("condition_text", ""), edge.get("object_name", "")])
    return any(keyword in blob for keyword in OPTIONAL_KEYWORDS)


def condition_matches(edge: dict[str, str], canonical: str, scenario: dict[str, Any]) -> bool:
    if canonical in set(scenario.get("force_documents", [])):
        return True
    blob = " ".join([canonical, edge.get("object_name", ""), edge.get("condition_text", ""), edge.get("evidence_text", "")])
    if any(term and term in blob for term in scenario.get("exclude_condition_terms", [])):
        return False
    return any(term and term in blob for term in scenario.get("condition_terms", []))


def excluded_by_scenario(edge: dict[str, str], canonical: str, scenario: dict[str, Any]) -> bool:
    blob = " ".join([canonical, edge.get("object_name", ""), edge.get("condition_text", ""), edge.get("evidence_text", "")])
    return any(term and term in blob for term in scenario.get("exclude_condition_terms", []))


def submission_for(permit: str, district: str) -> str:
    guide = SUBMISSION_GUIDE.get(permit, {})
    return guide.get(district) or guide.get("default") or "관할 담당 부서 확인 필요"


def edge_payload(edge: dict[str, str], scenario: dict[str, Any]) -> dict[str, str]:
    canonical = canonical_doc(edge["object_name"], edge["subject_name"])
    return {
        "subject": edge["subject_name"],
        "object": edge["object_name"],
        "canonical_object": canonical,
        "predicate": edge["predicate"],
        "assertion_level": edge["assertion_level"],
        "condition_text": edge["condition_text"],
        "issue_or_prepare_at": ISSUE_GUIDE.get(canonical, "발급/준비처 확인 필요"),
        "submit_to": submission_for(edge["subject_name"], scenario["district"]),
        "source_title": edge["title"],
        "source_url": edge["source_url"],
        "chunk_id": edge["chunk_id"],
        "evidence_text": compact(edge["evidence_text"]),
        "edge_source": edge["edge_source"],
    }


def dedupe_payload(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    result = []
    for item in items:
        key = (item["canonical_object"], item["subject"], item["submit_to"])
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return sorted(result, key=lambda row: (row["subject"], row["canonical_object"]))


def collect_documents(edges: list[dict[str, str]], scenario: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    candidates = [
        edge
        for edge in edges
        if edge["predicate"] == "requires_document"
        and edge["subject_name"] in scenario["permits"]
        and source_matches_district(edge, scenario["district"])
    ]
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for edge in candidates:
        canonical = canonical_doc(edge["object_name"], edge["subject_name"])
        if edge["subject_name"] == BUSINESS_REGISTRATION and canonical == "사업자등록증":
            continue
        if canonical in EXCLUDED_DOCS and canonical not in set(scenario.get("force_documents", [])):
            continue
        if canonical in set(scenario.get("exclude_documents", [])):
            continue
        grouped[(edge["subject_name"], canonical)].append(edge)

    required: list[dict[str, str]] = []
    triggered: list[dict[str, str]] = []
    conditional: list[dict[str, str]] = []
    for (_, canonical), group in grouped.items():
        best = sorted(group, key=lambda edge: priority(edge, scenario["district"]))[0]
        payload = edge_payload(best, scenario)
        if is_conditional(best, canonical):
            if excluded_by_scenario(best, canonical, scenario):
                continue
            if condition_matches(best, canonical, scenario):
                triggered.append(payload)
            else:
                conditional.append(payload)
        else:
            required.append(payload)

    return dedupe_payload(required), dedupe_payload(triggered), dedupe_payload(conditional)


def collect_checks(edges: list[dict[str, str]], scenario: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    for edge in edges:
        if edge["predicate"] not in {"needs_check", "raises_risk"}:
            continue
        if edge["subject_name"] not in scenario["permits"]:
            continue
        if not source_matches_district(edge, scenario["district"]):
            continue
        item = edge_payload(edge, scenario)
        item["canonical_object"] = canonical_doc(edge["object_name"], edge["subject_name"])
        result.append(item)
    seen = set()
    unique = []
    for item in sorted(result, key=lambda row: (row["subject"], row["canonical_object"])):
        key = (item["predicate"], item["subject"], item["canonical_object"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def collect_prerequisites(edges: list[dict[str, str]], scenario: dict[str, Any], needed_docs: list[dict[str, str]]) -> list[dict[str, str]]:
    needed_names = {doc["canonical_object"] for doc in needed_docs}
    needed_names.update(doc["object"] for doc in needed_docs)
    needed_names.update(scenario["permits"])
    for permit in scenario["permits"]:
        needed_names.update(PERMIT_PREREQUISITE_SUBJECTS.get(permit, []))
    for document in scenario.get("force_documents", []):
        needed_names.update(DOCUMENT_PREREQUISITE_SUBJECTS.get(document, []))

    result = []
    for edge in edges:
        if edge["predicate"] != "requires_prerequisite":
            continue
        subject_canonical = canonical_doc(edge["subject_name"], edge["subject_name"])
        if edge["subject_name"] not in needed_names and subject_canonical not in needed_names:
            continue
        if (
            edge["subject_name"] == "사업자등록증"
            and edge["object_name"] == "식품접객업 영업신고증"
            and FOOD_PERMIT not in scenario["permits"]
        ):
            continue
        result.append(
            {
                "subject": edge["subject_name"],
                "prerequisite": edge["object_name"],
                "condition_text": edge["condition_text"],
                "source_title": edge["title"],
                "edge_source": edge["edge_source"],
            }
        )
    seen = set()
    unique = []
    for item in sorted(result, key=lambda row: (row["subject"], row["prerequisite"])):
        key = (item["subject"], item["prerequisite"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def collect_routes(edges: list[dict[str, str]], scenario: dict[str, Any]) -> list[dict[str, str]]:
    result = []
    for edge in edges:
        if edge["predicate"] == "handled_by" and edge["subject_name"] in scenario["permits"]:
            result.append(edge_payload(edge, scenario))
    return dedupe_payload(result)


def build_results() -> list[dict[str, Any]]:
    edges = read_edges()
    results = []
    for scenario in SCENARIOS:
        required, triggered, conditional = collect_documents(edges, scenario)
        needed = required + triggered
        results.append(
            {
                **scenario,
                "required_documents": required,
                "triggered_documents": triggered,
                "conditional_documents": conditional,
                "checks_and_risks": collect_checks(edges, scenario),
                "prerequisites": collect_prerequisites(edges, scenario, needed),
                "submission_routes": collect_routes(edges, scenario),
            }
        )
    return results


def docs_table(lines: list[str], docs: list[dict[str, str]]) -> None:
    if not docs:
        lines.append("- 없음")
        return
    lines.append("| 서류 | 발급/준비처 | 제출처 | 그래프 근거 |")
    lines.append("|---|---|---|---|")
    for doc in docs:
        condition = f"<br>조건: {compact(doc['condition_text'], 90)}" if doc["condition_text"] else ""
        lines.append(
            f"| {doc['canonical_object']} | {doc['issue_or_prepare_at']} | {doc['submit_to']} | {doc['source_title']} / {doc['edge_source']}{condition} |"
        )


def write_markdown(results: list[dict[str, Any]]) -> None:
    lines = [
        "# Ten Scenario Full Graph Check",
        "",
        "최종 그래프 CSV만 읽어 필수 제출서류, 이번 조건에서 추가로 필요한 서류, 조건부 확인서류, 발급/준비처, 제출처, 선행요건, 추천 순서를 정리했습니다.",
        "문서별 발급/준비처는 그래프의 담당 기능 edge와 공식 페이지 근거를 바탕으로 한 최종 판단값입니다.",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"## {result['input']}",
                "",
                f"- 지역: {result['district']}",
                f"- 행정 업종/상황: {result['business_type']}",
                f"- 필요한 인허가: {', '.join(result['permits'])}",
                "",
                "### 필수 제출서류",
            ]
        )
        docs_table(lines, result["required_documents"])
        lines.extend(["", "### 이번 조건 때문에 추가로 필요한 서류"])
        docs_table(lines, result["triggered_documents"])
        lines.extend(["", "### 조건부 확인서류"])
        docs_table(lines, result["conditional_documents"])
        lines.extend(["", "### 선행으로 먼저 갖춰야 할 것"])
        if result["prerequisites"]:
            for item in result["prerequisites"]:
                cond = f" / {compact(item['condition_text'], 100)}" if item["condition_text"] else ""
                lines.append(f"- {item['subject']} 전에 `{item['prerequisite']}`{cond}")
        else:
            lines.append("- 그래프에 별도 선행요건 edge 없음. 아래 추천 순서 기준으로 진행.")
        lines.extend(["", "### 사전 확인/리스크"])
        for check in result["checks_and_risks"][:12]:
            cond = f" / {compact(check['condition_text'], 100)}" if check["condition_text"] else ""
            lines.append(f"- {check['subject']} -> {check['canonical_object']}{cond}")
        if not result["checks_and_risks"]:
            lines.append("- 그래프에 별도 확인 edge 없음")
        lines.extend(["", "### 제출/문의 담당"])
        route_seen = set()
        for permit in result["permits"]:
            route = submission_for(permit, result["district"])
            if (permit, route) not in route_seen:
                lines.append(f"- {permit}: {route}")
                route_seen.add((permit, route))
        if result["submission_routes"]:
            lines.append("- 그래프 담당 기능: " + ", ".join(f"{route['subject']} -> {route['object']}" for route in result["submission_routes"]))
        lines.extend(["", "### 추천 진행 순서"])
        for idx, step in enumerate(result["order"], 1):
            lines.append(f"{idx}. {step}")
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
            "triggered",
            len(result["triggered_documents"]),
            "conditional",
            len(result["conditional_documents"]),
            "prereq",
            len(result["prerequisites"]),
        )
    print(f"json={OUT_JSON}")
    print(f"markdown={OUT_MD}")


if __name__ == "__main__":
    main()
