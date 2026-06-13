from __future__ import annotations

from typing import Any


FLOW_SCHEMA_VERSION = "2026-06-13"
MAX_TOTAL_QUESTIONS = 10
MAX_ATTEMPTS_PER_FIELD = 2


def option(option_id: str, title: str, exclusive: bool = False) -> dict[str, Any]:
    item = {"id": option_id, "title": title}
    if exclusive:
        item["exclusive"] = True
    return item


def unknown_option() -> dict[str, Any]:
    return {"id": "unknown", "title": "아직 몰라요", "exclusive": True}


QUESTION_BANK = [
    {
        "field": "business_activity",
        "label": "업종/판매품목",
        "question": "어떤 가게를 준비하나요?",
        "why": "카페, 일반음식점, 제과점, 간판/도로점용처럼 필요한 인허가 흐름을 잡기 위해 필요해요.",
        "inputMode": "free_text",
        "required": True,
    },
    {
        "field": "exact_address",
        "label": "정확한 주소",
        "question": "가게 주소가 정해졌나요?",
        "why": "주소로 관할 부서와 건물 용도를 확인해요.",
        "inputMode": "free_text",
        "required": True,
    },
    {
        "field": "floor_unit",
        "label": "층/호수",
        "question": "층과 호수도 알려줄 수 있나요?",
        "why": "층별 용도, 소방 기준, 같은 장소 이력 확인 정확도를 높이는 데 필요해요.",
        "inputMode": "free_text",
        "required": False,
    },
    {
        "field": "area",
        "label": "영업장 면적",
        "question": "영업장 면적을 알고 있나요?",
        "why": "소방완비증명서와 일부 면적 기준 판단에 필요해요. 모르면 건축물대장/API 결과로 보조 확인할게요.",
        "inputMode": "free_text",
        "required": False,
    },
    {
        "field": "on_site_consumption",
        "label": "매장 취식 여부",
        "question": "매장에서 먹고 갈 수 있나요?",
        "why": "객석 유무에 따라 신고 유형이 달라져요.",
        "inputMode": "single_select",
        "required": True,
        "options": [
            option("yes", "네, 매장 이용 가능"),
            option("no", "아니요, 포장·배달만"),
            unknown_option(),
        ],
    },
    {
        "field": "manufacturing_or_simple_sale",
        "label": "조리·제조 방식",
        "question": "음식이나 디저트를 직접 만드나요?",
        "why": "직접 만드는지에 따라 필요한 신고가 달라져요.",
        "inputMode": "single_select",
        "required": True,
        "options": [
            option("cook", "매장에서 조리"),
            option("make_or_process", "직접 제조·가공"),
            option("finished_goods", "완제품 판매"),
            unknown_option(),
        ],
    },
    {
        "field": "liquor_sales",
        "label": "주류 판매 여부",
        "question": "술도 판매하나요?",
        "why": "주류 판매 여부에 따라 신고 유형이 달라져요.",
        "inputMode": "single_select",
        "required": True,
        "options": [
            option("yes", "네, 판매해요"),
            option("no", "아니요"),
            unknown_option(),
        ],
    },
    {
        "field": "signboard_planned",
        "label": "간판 설치 여부",
        "question": "외부 간판을 설치하거나 바꿀 예정인가요?",
        "why": "간판이 있으면 옥외광고물 신고/허가와 담당 부서 안내가 필요해요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("yes", "네, 설치/변경 예정"),
            option("no", "아니요"),
            unknown_option(),
        ],
    },
    {
        "field": "outdoor_space_planned",
        "label": "외부공간 사용 여부",
        "question": "가게 밖 테이블이나 테라스 공간을 사용할 예정인가요?",
        "why": "보도·도로 또는 사유지 사용 여부에 따라 도로점용/사용권한 확인이 필요할 수 있어요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("yes", "네, 사용할 예정"),
            option("no", "아니요"),
            unknown_option(),
        ],
    },
    {
        "field": "condition_screening",
        "label": "추가 조건",
        "question": "해당되는 항목이 있나요?",
        "why": "있으면 골라주세요. 없으면 해당 없음을 누르세요.",
        "inputMode": "multi_select",
        "required": False,
        "options": [
            option("signage_planned", "간판/옥외광고물"),
            option("outdoor_space_planned", "외부 테이블/보도 사용"),
            option("lpg_use", "LPG 등 가스 사용"),
            option("online_sales_planned", "온라인/택배 판매"),
            option("none", "해당 없음", exclusive=True),
            unknown_option(),
        ],
    },
    {
        "field": "building_use",
        "label": "건축물 용도",
        "question": "건물 용도를 알고 있나요?",
        "why": "모르면 넘어가도 돼요.",
        "inputMode": "free_text",
        "required": True,
    },
    {
        "field": "lease_contract",
        "label": "임대차계약",
        "question": "임대차계약서나 사용권한을 확인할 수 있나요?",
        "why": "영업신고 서류와 건물주/관리인 권한 확인에 필요해요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("prepared", "계약 완료"),
            option("before_contract", "계약 전"),
            option("not_prepared", "아직 준비 안 됨"),
            unknown_option(),
        ],
    },
    {
        "field": "owner_consent",
        "label": "소유자/관리인 승낙",
        "question": "건물주나 관리인에게 설치/사용 승낙을 받았나요?",
        "why": "간판, 외부공간, 도로점용 관련 서류에 사용승낙서가 필요할 수 있어요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("yes", "네, 받았어요"),
            option("no", "아직 안 받았어요"),
            option("owner", "본인 소유예요"),
            unknown_option(),
        ],
    },
    {
        "field": "signboard_type",
        "label": "간판 종류",
        "question": "어떤 간판을 설치하거나 변경하려고 하나요?",
        "why": "벽면간판, 돌출간판, 입간판 등 종류에 따라 허가/신고 기준이 달라질 수 있어요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("wall", "벽면간판"),
            option("projecting", "돌출간판"),
            option("standing", "입간판"),
            option("banner", "현수막"),
            unknown_option(),
        ],
    },
    {
        "field": "signboard_size",
        "label": "간판 크기",
        "question": "간판의 대략적인 크기나 면적을 알고 있나요?",
        "why": "크기와 설치 높이에 따라 허가/신고/심의 여부가 갈릴 수 있어요.",
        "inputMode": "free_text",
        "required": False,
    },
    {
        "field": "signboard_location",
        "label": "간판 설치 위치",
        "question": "간판을 어디에 설치하려고 하나요?",
        "why": "건물 외벽, 돌출, 지주 등 위치에 따라 확인 항목이 달라져요.",
        "inputMode": "free_text",
        "required": False,
    },
    {
        "field": "signboard_image",
        "label": "현장 사진",
        "question": "간판 설치 예정 위치 사진이 있나요?",
        "why": "신청서류 준비 때 현장 사진이 필요할 수 있어요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("prepared", "사진 있음"),
            option("not_prepared", "아직 없음"),
            unknown_option(),
        ],
    },
    {
        "field": "outdoor_location",
        "label": "외부공간 위치",
        "question": "테이블을 둘 곳이 보도/도로인가요, 건물 사유지인가요?",
        "why": "공공도로/보도 여부에 따라 도로점용 확인이 필요할 수 있어요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("road_or_sidewalk", "보도/도로 위"),
            option("private_land", "건물 앞 사유지"),
            option("terrace", "테라스/전용공간"),
            unknown_option(),
        ],
    },
    {
        "field": "outdoor_area",
        "label": "외부공간 면적",
        "question": "외부에 둘 테이블 수나 사용 면적을 알고 있나요?",
        "why": "사용 면적과 위치가 도로점용/외부공간 검토에 필요해요.",
        "inputMode": "free_text",
        "required": False,
    },
    {
        "field": "hygieneTraining",
        "label": "위생교육 수료증",
        "question": "위생교육 수료증은 준비되어 있나요?",
        "why": "영업신고 제출 전에 수료증 준비 상태를 확인해야 해요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("prepared", "준비 완료"),
            option("not_prepared", "아직 준비 안 됨"),
            unknown_option(),
        ],
    },
    {
        "field": "healthCertificate",
        "label": "건강진단결과서",
        "question": "건강진단결과서(구 보건증)는 준비되어 있나요?",
        "why": "식품접객업 영업신고 제출 전에 필요한 핵심 서류예요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("prepared", "준비 완료"),
            option("not_prepared", "아직 준비 안 됨"),
            unknown_option(),
        ],
    },
    {
        "field": "fireCertificate",
        "label": "소방완비증명서",
        "question": "소방완비증명서가 필요한지 또는 준비됐는지 확인했나요?",
        "why": "지하 66㎡, 지상 2층 100㎡ 이상 등 조건이면 필요할 수 있어요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("prepared", "준비 완료"),
            option("not_prepared", "아직 준비 안 됨"),
            option("not_applicable", "해당 없음으로 확인"),
            unknown_option(),
        ],
    },
    {
        "field": "takeover_type",
        "label": "기존 영업 승계 여부",
        "question": "기존 가게를 인수하나요?",
        "why": "새로 신고할지, 승계할지 확인해요.",
        "inputMode": "single_select",
        "required": False,
        "options": [
            option("transfer", "네, 인수해요"),
            option("new_report", "아니요, 새로 시작해요"),
            unknown_option(),
        ],
    },
]


FIELD_VALUE_MAP = {
    "on_site_consumption": {"yes": True, "no": False},
    "manufacturing_or_simple_sale": {
        "cook": "cook",
        "make_or_process": "manufacturing_or_processing",
        "finished_goods": "resale_or_simple_sale",
    },
    "liquor_sales": {"yes": True, "no": False},
    "signboard_planned": {"yes": True, "no": False},
    "outdoor_space_planned": {"yes": True, "no": False},
    "condition_screening": {
        "signage_planned": "signage_planned",
        "outdoor_space_planned": "outdoor_space_planned",
        "lpg_use": "lpg_use",
        "online_sales_planned": "online_sales_planned",
        "none": "none",
    },
    "takeover_type": {
        "transfer": "transfer",
        "new_report": "new_report",
    },
    "lease_contract": {
        "prepared": "prepared",
        "before_contract": "before_contract",
        "not_prepared": "not_prepared",
    },
    "owner_consent": {
        "yes": "yes",
        "no": "no",
        "owner": "owner",
    },
    "signboard_type": {
        "wall": "벽면간판",
        "projecting": "돌출간판",
        "standing": "입간판",
        "banner": "현수막",
    },
    "signboard_image": {
        "prepared": "prepared",
        "not_prepared": "not_prepared",
    },
    "outdoor_location": {
        "road_or_sidewalk": "road_or_sidewalk",
        "private_land": "private_land",
        "terrace": "terrace",
    },
    "hygieneTraining": {
        "prepared": "prepared",
        "not_prepared": "not_prepared",
    },
    "healthCertificate": {
        "prepared": "prepared",
        "not_prepared": "not_prepared",
    },
    "fireCertificate": {
        "prepared": "prepared",
        "not_prepared": "not_prepared",
        "not_applicable": "not_applicable",
    },
}


DOCUMENT_PRIORITY_RULES = [
    {
        "id": "building-ledger",
        "priority": 1,
        "title": "건축물대장 확인",
        "statutoryDeadline": "즉시",
        "perceivedDuration": "즉시",
        "prerequisites": "점포 매물 탐색 완료",
        "unlocks": "임대차계약, 소방필증, 영업신고 검토",
        "reason": "계약 전 건물 용도와 위반 여부를 확인해야 해요.",
    },
    {
        "id": "fire-safety",
        "priority": 2,
        "title": "소방시설완비증명서",
        "statutoryDeadline": "3~7일",
        "perceivedDuration": "5~7일",
        "prerequisites": "임대차계약서, 건축물대장",
        "unlocks": "식품접객업 영업신고증",
        "reason": "대상 여부와 현장 확인 일정이 필요할 수 있어요.",
    },
    {
        "id": "health-check",
        "priority": 3,
        "title": "건강진단결과서",
        "statutoryDeadline": "즉시",
        "perceivedDuration": "4~5일",
        "prerequisites": "창업자 및 종업원 인적사항",
        "unlocks": "식품접객업 영업신고증",
        "reason": "검사 후 결과가 나오기까지 며칠 걸려요.",
    },
    {
        "id": "lpg-certificate",
        "priority": 4,
        "title": "LPG 완성검사필증",
        "statutoryDeadline": "즉시",
        "perceivedDuration": "3~5일",
        "prerequisites": "임대차계약서, 가스 배관 및 화구 시공 완료",
        "unlocks": "식품접객업 영업신고증",
        "reason": "공사 후 검사 일정이 필요해요.",
    },
    {
        "id": "hygiene-education",
        "priority": 5,
        "title": "위생교육 수료증",
        "statutoryDeadline": "즉시",
        "perceivedDuration": "1일",
        "prerequisites": "창업자 인적사항",
        "unlocks": "식품접객업 영업신고증",
        "reason": "신고 전에 수료증이 필요해요.",
    },
    {
        "id": "food-business-report",
        "priority": 6,
        "title": "식품접객업 영업신고증",
        "statutoryDeadline": "즉시",
        "perceivedDuration": "방문 시 즉시",
        "prerequisites": "건축물대장, 보건증, 위생교육 등 선행 서류",
        "unlocks": "사업자등록증, 간판 허가 신청",
        "reason": "앞 서류가 준비돼야 접수할 수 있어요.",
    },
    {
        "id": "business-registration",
        "priority": 7,
        "title": "사업자등록증",
        "statutoryDeadline": "2일 이내",
        "perceivedDuration": "즉시~1일",
        "prerequisites": "영업신고증, 임대차계약서",
        "unlocks": "카드단말기, POS, 세금계산서 등 매출 활동",
        "reason": "영업신고 후 사업자등록을 진행해요.",
    },
    {
        "id": "signage-report",
        "priority": 8,
        "title": "옥외광고물 허가 및 신고증",
        "statutoryDeadline": "7일 이내",
        "perceivedDuration": "3~5일",
        "prerequisites": "사업자등록증, 간판 디자인 도면, 건물 정면도",
        "unlocks": "합법적인 외부 간판 설치",
        "reason": "간판 위치와 크기 기준 확인이 필요해요.",
    },
]
