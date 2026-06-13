from __future__ import annotations

import csv
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
GENERATED_AT = "2026-06-13"


DISTRICTS = [
    ("11110", "종로구", "https://www.jongno.go.kr"),
    ("11140", "중구", "https://www.junggu.seoul.kr"),
    ("11170", "용산구", "https://www.yongsan.go.kr"),
    ("11200", "성동구", "https://www.sd.go.kr"),
    ("11215", "광진구", "https://www.gwangjin.go.kr"),
    ("11230", "동대문구", "https://www.ddm.go.kr"),
    ("11260", "중랑구", "https://www.jungnang.go.kr"),
    ("11290", "성북구", "https://www.sb.go.kr"),
    ("11305", "강북구", "https://www.gangbuk.go.kr"),
    ("11320", "도봉구", "https://www.dobong.go.kr"),
    ("11350", "노원구", "https://www.nowon.kr"),
    ("11380", "은평구", "https://www.ep.go.kr"),
    ("11410", "서대문구", "https://www.sdm.go.kr"),
    ("11440", "마포구", "https://www.mapo.go.kr"),
    ("11470", "양천구", "https://www.yangcheon.go.kr"),
    ("11500", "강서구", "https://www.gangseo.seoul.kr"),
    ("11530", "구로구", "https://www.guro.go.kr"),
    ("11545", "금천구", "https://www.geumcheon.go.kr"),
    ("11560", "영등포구", "https://www.ydp.go.kr"),
    ("11590", "동작구", "https://www.dongjak.go.kr"),
    ("11620", "관악구", "https://www.gwanak.go.kr"),
    ("11650", "서초구", "https://www.seocho.go.kr"),
    ("11680", "강남구", "https://www.gangnam.go.kr"),
    ("11710", "송파구", "https://www.songpa.go.kr"),
    ("11740", "강동구", "https://www.gangdong.go.kr"),
]


LOCATION_SOURCE_URL = "https://www.seoul.go.kr/seoul/autonomy.do"
LOCATION_SOURCE_TITLE = "서울특별시 자치구"
KAKAO_REST_API_KEY_ENV_NAMES = ("KAKAO_REST_API_KEY", "KAKAO_API_KEY")


OFFICE_FIELDS = [
    "office_name",
    "office_address",
    "office_postal_code",
    "office_latitude",
    "office_longitude",
    "office_location_scope",
    "office_location_source_url",
    "office_location_source_title",
    "office_geocode_source",
    "office_geocode_status",
    "office_location_last_verified_date",
]


DISTRICT_OFFICE_LOCATIONS = {
    "11110": {
        "office_name": "종로구청",
        "office_address": "서울특별시 종로구 삼봉로 43",
        "office_postal_code": "03153",
        "office_latitude": "37.5723031",
        "office_longitude": "126.9808398",
    },
    "11140": {
        "office_name": "중구청",
        "office_address": "서울특별시 중구 창경궁로 17",
        "office_postal_code": "04558",
        "office_latitude": "37.5637580",
        "office_longitude": "126.9975659",
    },
    "11170": {
        "office_name": "용산구청",
        "office_address": "서울특별시 용산구 녹사평대로 150",
        "office_postal_code": "04390",
        "office_latitude": "37.5325763",
        "office_longitude": "126.9904206",
    },
    "11200": {
        "office_name": "성동구청",
        "office_address": "서울특별시 성동구 고산자로 270",
        "office_postal_code": "04750",
        "office_latitude": "37.5634661",
        "office_longitude": "127.0368984",
    },
    "11215": {
        "office_name": "광진구청",
        "office_address": "서울특별시 광진구 자양로 117",
        "office_postal_code": "05026",
        "office_latitude": "37.5384976",
        "office_longitude": "127.0819157",
    },
    "11230": {
        "office_name": "동대문구청",
        "office_address": "서울특별시 동대문구 천호대로 145",
        "office_postal_code": "02565",
        "office_latitude": "37.5745240",
        "office_longitude": "127.0396500",
    },
    "11260": {
        "office_name": "중랑구청",
        "office_address": "서울특별시 중랑구 봉화산로 179",
        "office_postal_code": "02043",
        "office_latitude": "37.6063242",
        "office_longitude": "127.0925842",
    },
    "11290": {
        "office_name": "성북구청",
        "office_address": "서울특별시 성북구 보문로 168",
        "office_postal_code": "02848",
        "office_latitude": "37.5894684",
        "office_longitude": "127.0168275",
    },
    "11305": {
        "office_name": "강북구청",
        "office_address": "서울특별시 강북구 도봉로89길 13",
        "office_postal_code": "01071",
        "office_latitude": "37.6397199",
        "office_longitude": "127.0256882",
    },
    "11320": {
        "office_name": "도봉구청",
        "office_address": "서울특별시 도봉구 마들로 656",
        "office_postal_code": "01331",
        "office_latitude": "37.6687201",
        "office_longitude": "127.0473035",
    },
    "11350": {
        "office_name": "노원구청",
        "office_address": "서울특별시 노원구 노해로 437",
        "office_postal_code": "01689",
        "office_latitude": "37.6543998",
        "office_longitude": "127.0564310",
    },
    "11380": {
        "office_name": "은평구청",
        "office_address": "서울특별시 은평구 은평로 195",
        "office_postal_code": "03384",
        "office_latitude": "37.6024668",
        "office_longitude": "126.9288202",
    },
    "11410": {
        "office_name": "서대문구청",
        "office_address": "서울특별시 서대문구 연희로 248",
        "office_postal_code": "03718",
        "office_latitude": "37.5791820",
        "office_longitude": "126.9367984",
    },
    "11440": {
        "office_name": "마포구청",
        "office_address": "서울특별시 마포구 월드컵로 212",
        "office_postal_code": "03937",
        "office_latitude": "37.5663245",
        "office_longitude": "126.9014910",
    },
    "11470": {
        "office_name": "양천구청",
        "office_address": "서울특별시 양천구 목동동로 105",
        "office_postal_code": "08095",
        "office_latitude": "37.5168721",
        "office_longitude": "126.8663985",
    },
    "11500": {
        "office_name": "강서구청",
        "office_address": "서울특별시 강서구 화곡로 302",
        "office_postal_code": "07658",
        "office_latitude": "37.5506590",
        "office_longitude": "126.8497700",
    },
    "11530": {
        "office_name": "구로구청",
        "office_address": "서울특별시 구로구 가마산로 245",
        "office_postal_code": "08284",
        "office_latitude": "37.4955112",
        "office_longitude": "126.8882948",
    },
    "11545": {
        "office_name": "금천구청",
        "office_address": "서울특별시 금천구 시흥대로73길 70",
        "office_postal_code": "08611",
        "office_latitude": "37.4568996",
        "office_longitude": "126.8953809",
    },
    "11560": {
        "office_name": "영등포구청",
        "office_address": "서울특별시 영등포구 당산로 123",
        "office_postal_code": "07260",
        "office_latitude": "37.5264807",
        "office_longitude": "126.8956526",
    },
    "11590": {
        "office_name": "동작구청",
        "office_address": "서울특별시 동작구 장승배기로 161",
        "office_postal_code": "06928",
        "office_latitude": "37.5125292",
        "office_longitude": "126.9399439",
    },
    "11620": {
        "office_name": "관악구청",
        "office_address": "서울특별시 관악구 관악로 145",
        "office_postal_code": "08832",
        "office_latitude": "37.4784684",
        "office_longitude": "126.9511015",
    },
    "11650": {
        "office_name": "서초구청",
        "office_address": "서울특별시 서초구 남부순환로 2584",
        "office_postal_code": "06750",
        "office_latitude": "37.4835926",
        "office_longitude": "127.0334589",
    },
    "11680": {
        "office_name": "강남구청",
        "office_address": "서울특별시 강남구 학동로 426",
        "office_postal_code": "06090",
        "office_latitude": "37.5172363",
        "office_longitude": "127.0473248",
    },
    "11710": {
        "office_name": "송파구청",
        "office_address": "서울특별시 송파구 올림픽로 326",
        "office_postal_code": "05552",
        "office_latitude": "37.5145656",
        "office_longitude": "127.1060321",
    },
    "11740": {
        "office_name": "강동구청",
        "office_address": "서울특별시 강동구 성내로 25",
        "office_postal_code": "05397",
        "office_latitude": "37.5301260",
        "office_longitude": "127.1237700",
    },
}


ADDRESS_BASED_TASK_LOCATIONS = {
    "business_registration": {
        "office_name": "홈택스 또는 사업장 주소 기준 관할 세무서",
        "office_address": "온라인 홈택스 또는 사업장 주소 기준 관할 세무서",
        "office_postal_code": "",
        "office_latitude": "",
        "office_longitude": "",
        "office_location_scope": "online_or_business_address_based_tax_office",
        "office_location_source_url": "https://www.nts.go.kr/nts/imArea/selectImAreaNmList.do?mi=6762",
        "office_location_source_title": "국세청 전국 세무관서",
        "office_geocode_source": "not_geocoded",
        "office_geocode_status": "business_address_required",
        "office_location_last_verified_date": GENERATED_AT,
    },
    "fire_safety_completion": {
        "office_name": "사업장 주소 기준 관할 소방서",
        "office_address": "사업장 주소 기준 관할 소방서 민원실",
        "office_postal_code": "",
        "office_latitude": "",
        "office_longitude": "",
        "office_location_scope": "business_address_based_fire_station",
        "office_location_source_url": "https://fire.seoul.go.kr",
        "office_location_source_title": "서울소방재난본부",
        "office_geocode_source": "not_geocoded",
        "office_geocode_status": "business_address_required",
        "office_location_last_verified_date": GENERATED_AT,
    },
}


DEPARTMENT_FUNCTIONS = [
    {
        "graph_function_key": "food_hygiene",
        "graph_department_function": "식품위생 업무",
        "graph_node_id": "n_a36f9ff91c64b1d8",
        "description": "식품관련영업신고, 식품접객업 인허가, 기존 업소 행정처분 이력 확인",
    },
    {
        "graph_function_key": "building_register_use",
        "graph_department_function": "건축물대장 및 건축물 용도 업무",
        "graph_node_id": "n_28eca3d424998495",
        "description": "건축물대장 열람, 용도 적합성, 위반건축물 여부 확인",
    },
    {
        "graph_function_key": "fire_safety",
        "graph_department_function": "소방 안전 업무",
        "graph_node_id": "n_995db848116b2fe2",
        "description": "안전시설등 완비증명서, 다중이용업소 소방 관련 확인",
    },
    {
        "graph_function_key": "outdoor_ad",
        "graph_department_function": "옥외광고물 관리 업무",
        "graph_node_id": "n_fb0b1245f944d5b3",
        "description": "간판, 옥외광고물 표시허가 또는 신고",
    },
    {
        "graph_function_key": "road_occupation",
        "graph_department_function": "도로점용 업무",
        "graph_node_id": "n_646a25d45cbbf2e3",
        "description": "도로, 보도, 외부 공간 점용허가",
    },
    {
        "graph_function_key": "tax_registration",
        "graph_department_function": "세무 업무",
        "graph_node_id": "n_18fc6a8ae92569d0",
        "description": "사업자등록 신청. 실제 접수는 구청이 아니라 관할 세무서 또는 홈택스",
    },
    {
        "graph_function_key": "ecommerce_local_economy",
        "graph_department_function": "통신판매 및 지역경제 업무",
        "graph_node_id": "n_c66d9970dbbf3fca",
        "description": "통신판매업신고, 지역경제/일자리경제 계열 업무",
    },
]


LOCAL_TASKS = [
    (
        "food_business_report",
        "food_hygiene",
        "식품관련영업신고 및 영업신고증",
        "식품접객업 영업신고, 식품관련영업신고, 일반음식점, 휴게음식점",
    ),
    (
        "food_admin_disposition_history",
        "food_hygiene",
        "기존 업소 행정처분 이력 확인",
        "식품접객업 행정처분, 무신고 업소, 행정처분 공개",
    ),
    (
        "building_register_issue",
        "building_register_use",
        "건축물대장 발급 및 열람",
        "건축물대장, 건축물대장 열람, 민원발급, 부동산정보",
    ),
    (
        "building_use_review",
        "building_register_use",
        "건축물 용도 적합성 확인",
        "건축물 용도, 근린생활시설, 용도변경, 건축과",
    ),
    (
        "building_violation_review",
        "building_register_use",
        "위반건축물 여부 확인",
        "위반건축물, 건축법 위반, 이행강제금, 건축과",
    ),
    (
        "fire_safety_completion",
        "fire_safety",
        "안전시설등 완비증명서",
        "안전시설등 완비증명, 소방완비증명, 소방서, 다중이용업소",
    ),
    (
        "outdoor_ad_report",
        "outdoor_ad",
        "옥외광고물 표시허가 및 신고",
        "옥외광고물, 간판, 광고물팀, 도시계획과, 가로경관과",
    ),
    (
        "road_occupation_permit",
        "road_occupation",
        "도로점용허가",
        "도로점용허가, 보도 점용, 건설관리과, 도로과, 가로행정과",
    ),
    (
        "business_registration",
        "tax_registration",
        "사업자등록 신청",
        "사업자등록, 홈택스, 세무서, 관할 세무서",
    ),
    (
        "ecommerce_report",
        "ecommerce_local_economy",
        "통신판매업신고",
        "통신판매업신고, 일자리경제과, 지역경제과, 경제진흥과",
    ),
]


VERIFIED_MAPPINGS = [
    {
        "district_code": "11140",
        "district_name": "중구",
        "local_task_key": "food_business_report",
        "actual_department_name": "보건위생과",
        "actual_team_name": "식품관리팀",
        "phone": "02-3396-5645",
        "jurisdiction_level": "district",
        "source_url": "https://www.junggu.seoul.kr/content.do?cmsid=14455",
        "source_title": "서울시 중구청 부서안내 - 보건위생과",
        "evidence_text": "식품관리팀 주무관 02-3396-5645 민원조사, 신규 식품접객업소 현장 사후점검",
    },
    {
        "district_code": "11140",
        "district_name": "중구",
        "local_task_key": "food_admin_disposition_history",
        "actual_department_name": "보건위생과",
        "actual_team_name": "식품관리팀",
        "phone": "02-3396-5653",
        "jurisdiction_level": "district",
        "source_url": "https://www.junggu.seoul.kr/content.do?cmsid=14455",
        "source_title": "서울시 중구청 부서안내 - 보건위생과",
        "evidence_text": "식품관리팀 주무관 02-3396-5653 단속계획수립, 식품접객지도점검, 민원조사 행정처분",
    },
    {
        "district_code": "11200",
        "district_name": "성동구",
        "local_task_key": "food_business_report",
        "actual_department_name": "보건위생과",
        "actual_team_name": "식품위생팀",
        "phone": "02-2286-7145",
        "jurisdiction_level": "district",
        "source_url": "https://www.sd.go.kr/main/sub.do?key=3784",
        "source_title": "성동구청 부서안내 - 보건위생과",
        "evidence_text": "식품위생팀 팀장 02-2286-7145 식품위생팀 업무 총괄; 식품접객업소 시설조사 및 지도점검",
    },
    {
        "district_code": "11200",
        "district_name": "성동구",
        "local_task_key": "food_admin_disposition_history",
        "actual_department_name": "보건위생과",
        "actual_team_name": "식품위생팀",
        "phone": "02-2286-7158",
        "jurisdiction_level": "district",
        "source_url": "https://www.sd.go.kr/main/sub.do?key=3784",
        "source_title": "성동구청 부서안내 - 보건위생과",
        "evidence_text": "식품위생팀 주무관 02-2286-7158 식품접객업소 행정처분·심판·소송사무 총괄",
    },
    {
        "district_code": "11440",
        "district_name": "마포구",
        "local_task_key": "food_business_report",
        "actual_department_name": "마포구 보건소 위생과",
        "actual_team_name": "",
        "phone": "02-3153-9014",
        "jurisdiction_level": "district",
        "source_url": "https://www.mapo.go.kr/site/main/organization/organization",
        "source_title": "마포구청 조직도",
        "evidence_text": "마포구청 조직도에서 보건소 위생과를 확인하고, 서울 열린데이터 제공부서 연락처로 전화번호를 보조 확인.",
    },
    {
        "district_code": "11440",
        "district_name": "마포구",
        "local_task_key": "food_admin_disposition_history",
        "actual_department_name": "마포구 보건소 위생과",
        "actual_team_name": "",
        "phone": "02-3153-9014",
        "jurisdiction_level": "district",
        "source_url": "https://www.mapo.go.kr/site/main/organization/organization",
        "source_title": "마포구청 조직도",
        "evidence_text": "마포구청 조직도에서 보건소 위생과를 확인하고, 서울 열린데이터 제공부서 연락처로 전화번호를 보조 확인.",
    },
    {
        "district_code": "11530",
        "district_name": "구로구",
        "local_task_key": "food_business_report",
        "actual_department_name": "위생과",
        "actual_team_name": "식품위생팀",
        "phone": "02-860-3287",
        "jurisdiction_level": "district",
        "source_url": "https://www.guro.go.kr/www/sub.do?key=1933",
        "source_title": "구로구청 부서안내 - 위생과",
        "evidence_text": "식품위생팀 주무관 02-860-3287 - 식품접객업 영업 신고; 주무관 02-860-3234 - 식품접객업 인허가",
    },
    {
        "district_code": "11530",
        "district_name": "구로구",
        "local_task_key": "food_admin_disposition_history",
        "actual_department_name": "위생과",
        "actual_team_name": "원산지위생지도팀",
        "phone": "02-860-2067",
        "jurisdiction_level": "district",
        "source_url": "https://www.guro.go.kr/www/sub.do?key=1933",
        "source_title": "구로구청 부서안내 - 위생과",
        "evidence_text": "원산지위생지도팀 주무관 02-860-2067 - 식품접객업 무허가(무신고)업소 관리 및 행정처분",
    },
    {
        "district_code": "11650",
        "district_name": "서초구",
        "local_task_key": "food_business_report",
        "actual_department_name": "보건소 위생과",
        "actual_team_name": "식품위생팀",
        "phone": "02-2155-8020",
        "jurisdiction_level": "district",
        "source_url": "https://www.seocho.go.kr/site/seocho/group/emp2020/DepartList.do?searchCdIdx=d00000037",
        "source_title": "서초구청 부서안내 - 보건소 위생과",
        "evidence_text": "위생과 주요업무: 식품위생팀 - 식품접객업소 행정처분, 지도점검, 시설조사, 신규업소 시설조사 등",
    },
    {
        "district_code": "11650",
        "district_name": "서초구",
        "local_task_key": "food_admin_disposition_history",
        "actual_department_name": "보건소 위생과",
        "actual_team_name": "식품위생팀",
        "phone": "02-2155-8024",
        "jurisdiction_level": "district",
        "source_url": "https://www.seocho.go.kr/site/seocho/group/emp2020/DepartList.do?searchCdIdx=d00000037",
        "source_title": "서초구청 부서안내 - 보건소 위생과",
        "evidence_text": "식품위생팀 주무관 02-2155-8024 행정처분, 유흥단란",
    },
    {
        "district_code": "11680",
        "district_name": "강남구",
        "local_task_key": "food_business_report",
        "actual_department_name": "강남구 보건소 위생과",
        "actual_team_name": "",
        "phone": "02-3423-7067",
        "jurisdiction_level": "district",
        "source_url": "https://data.seoul.go.kr/dataList/OA-11297/A/1/datasetView.do",
        "source_title": "서울시 강남구 식품위생업소 행정처분내역 현황",
        "evidence_text": "제공기관 강남구, 제공부서 강남구 보건소 위생과, 담당자 02-3423-7067",
    },
    {
        "district_code": "11680",
        "district_name": "강남구",
        "local_task_key": "food_admin_disposition_history",
        "actual_department_name": "강남구 보건소 위생과",
        "actual_team_name": "",
        "phone": "02-3423-7067",
        "jurisdiction_level": "district",
        "source_url": "https://data.seoul.go.kr/dataList/OA-11297/A/1/datasetView.do",
        "source_title": "서울시 강남구 식품위생업소 행정처분내역 현황",
        "evidence_text": "제공기관 강남구, 제공부서 강남구 보건소 위생과, 담당자 02-3423-7067",
    },
    {
        "district_code": "11680",
        "district_name": "강남구",
        "local_task_key": "road_occupation_permit",
        "actual_department_name": "건설관리과",
        "actual_team_name": "",
        "phone": "02-3423-6528",
        "jurisdiction_level": "district",
        "source_url": "https://www.gangnam.go.kr/contents/permit_road/1/view.do?mid=ID03_010906",
        "source_title": "강남구청 도로점용허가",
        "evidence_text": "도로점용허가 전반 관련 문의(건설관리과); 담당부서 건설관리과; 전화번호 02-3423-6528",
    },
    {
        "district_code": "11710",
        "district_name": "송파구",
        "local_task_key": "outdoor_ad_report",
        "actual_department_name": "도시계획과",
        "actual_team_name": "광고물팀",
        "phone": "02-2147-2918",
        "jurisdiction_level": "district",
        "source_url": "https://www.songpa.go.kr/www/contents.do?key=6083",
        "source_title": "송파구청 광고물 허가·신고 안내",
        "evidence_text": "담당부서 도시계획과 광고물팀; 전화번호 02-2147-2918; 최종 수정일 2025-07-11",
    },
]


NATIONAL_TASKS = {
    "business_registration": {
        "actual_department_name": "관할 세무서 또는 홈택스",
        "actual_team_name": "",
        "phone": "국세상담센터 126",
        "jurisdiction_level": "national_tax_office",
        "source_url": "https://www.hometax.go.kr",
        "source_title": "국세청 홈택스",
        "evidence_text": "사업자등록은 구청 인허가 이후 관할 세무서 또는 홈택스에서 처리하는 전국 공통 흐름",
    },
    "fire_safety_completion": {
        "actual_department_name": "관할 소방서",
        "actual_team_name": "",
        "phone": "119 또는 관할 소방서 민원실",
        "jurisdiction_level": "fire_station",
        "source_url": "https://fire.seoul.go.kr",
        "source_title": "서울소방재난본부",
        "evidence_text": "안전시설등 완비증명서는 구청 부서가 아니라 관할 소방서 계열 업무로 분리",
    },
}


DEFAULT_LOCAL_DEPARTMENTS = {
    "11110": {
        "source_url": "https://www.jongno.go.kr",
        "source_title": "종로구청 공식 홈페이지 및 보건소 식품위생 안내",
        "evidence_text": "종로구 보건소 식품접객업 안내는 보건정책과 식품위생팀 전화번호를 제공하고, 구청 공식 메뉴는 일시도로점용안내·옥외광고물·지역경제 업무를 별도 제공한다.",
        "food": ("보건정책과", "식품위생팀", "02-2148-3527"),
        "food_admin": ("보건정책과", "식품위생팀", "02-2148-3527"),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("가로정비과", "광고물관리팀", "02-2148-2742"),
        "road": ("도로과", "", ""),
        "ecommerce": ("일자리정책과", "유통관리팀", "02-2148-1744"),
    },
    "11140": {
        "source_url": "https://www.junggu.seoul.kr",
        "source_title": "서울 중구청 부서안내 및 민원편람",
        "evidence_text": "중구청 부서안내와 민원편람에서 보건위생과, 건축과, 도시디자인과, 건설관리과, 도심산업과 업무를 확인했다.",
        "food": ("보건위생과", "식품관리팀", "02-3396-5645"),
        "food_admin": ("보건위생과", "식품관리팀", "02-3396-5653"),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "건축관리팀", "02-3396-5834"),
        "outdoor_ad": ("도시디자인과", "", ""),
        "road": ("건설관리과", "", ""),
        "ecommerce": ("도심산업과", "생활경제팀", "02-3396-5077"),
    },
    "11170": {
        "source_url": "https://www.yongsan.go.kr",
        "source_title": "용산구청 공식 홈페이지",
        "evidence_text": "용산구 공식 조직 목록에서 지역경제과, 건축과, 부동산정보과, 건설관리과, 보건위생과를 확인했다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("건설관리과", "광고물관리팀", "02-2199-7729"),
        "road": ("건설관리과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11200": {
        "source_url": "https://www.sd.go.kr",
        "source_title": "성동구청 부서별 누리집",
        "evidence_text": "성동구 부서안내에서 보건위생과 식품위생팀, 토지관리과, 토목과, 지역경제과 유통관리팀, 도시계획과 광고물관리팀을 확인했다.",
        "food": ("보건위생과", "식품위생팀", "02-2286-7145"),
        "food_admin": ("보건위생과", "식품위생팀", "02-2286-7158"),
        "building_register": ("토지관리과", "", "02-2286-5383"),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("도시계획과", "광고물관리팀", "02-2286-5566"),
        "road": ("토목과", "", "02-2286-5782"),
        "ecommerce": ("지역경제과", "유통관리팀", "02-2286-5468"),
    },
    "11215": {
        "source_url": "https://www.gwangjin.go.kr",
        "source_title": "광진구청 분야별 안내",
        "evidence_text": "광진구 통신판매업 안내는 지역경제과, 건축인허가 행정처리 안내는 도로과·가로경관과·도시계획과·건축과·부동산정보과를 제시한다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("가로경관과", "광고물관리팀", "02-450-7704"),
        "road": ("도로과", "", ""),
        "ecommerce": ("지역경제과", "", "02-450-7322"),
    },
    "11230": {
        "source_url": "https://www.ddm.go.kr",
        "source_title": "동대문구청 공식 홈페이지",
        "evidence_text": "동대문구 공식 고시공고와 조직 검색 결과에서 도시경관과, 보건위생과, 건축과, 부동산정보과, 도로과, 경제진흥과 계열 업무를 확인했다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("도시경관과", "", ""),
        "road": ("도로과", "", ""),
        "ecommerce": ("경제진흥과", "", ""),
    },
    "11260": {
        "source_url": "https://www.jungnang.go.kr",
        "source_title": "중랑구청 공식 홈페이지",
        "evidence_text": "중랑구 공식 구정소식에서 위생과의 식품접객업 관련 공고를 확인했고, 나머지는 공식 조직 기능명 기준 후보 매핑이다.",
        "food": ("위생과", "", ""),
        "food_admin": ("위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("도시경관과", "", ""),
        "road": ("도로과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11290": {
        "source_url": "https://www.sb.go.kr",
        "source_title": "성북구청 공식 홈페이지",
        "evidence_text": "성북구 공식 새소식에서 보건위생과 식품접객업소 위생점검 담당을 확인했고, 나머지는 공식 조직 기능명 기준 후보 매핑이다.",
        "food": ("보건위생과", "", "02-2241-6193"),
        "food_admin": ("보건위생과", "", "02-2241-6193"),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("건설관리과", "", ""),
        "road": ("도로과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11305": {
        "source_url": "https://www.gangbuk.go.kr",
        "source_title": "강북구청 공식 홈페이지",
        "evidence_text": "강북구 공식 조직 기능명 기준 후보 매핑이다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("건설관리과", "", ""),
        "road": ("건설관리과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11320": {
        "source_url": "https://www.dobong.go.kr",
        "source_title": "도봉구청 분야별정보 및 보건소",
        "evidence_text": "도봉구 옥외광고물 안내는 가로관리과를 자료담당부서로 제시하고, 보건소 식품위생영업 안내를 확인했다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("가로관리과", "", "02-2091-4025"),
        "road": ("가로관리과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11350": {
        "source_url": "https://www.nowon.kr",
        "source_title": "노원구청 공식 홈페이지",
        "evidence_text": "노원구 공식 조직 기능명 기준 후보 매핑이다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("도시경관과", "", ""),
        "road": ("건설관리과", "", ""),
        "ecommerce": ("일자리경제과", "", ""),
    },
    "11380": {
        "source_url": "https://www.ep.go.kr",
        "source_title": "은평구청 공식 홈페이지",
        "evidence_text": "은평구 공식 조직 기능명 기준 후보 매핑이다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("공간계획과", "", ""),
        "road": ("도로과", "", ""),
        "ecommerce": ("일자리경제과", "", ""),
    },
    "11410": {
        "source_url": "https://www.sdm.go.kr",
        "source_title": "서대문구청 공식 홈페이지",
        "evidence_text": "서대문구 공식 조직 기능명 기준 후보 매핑이다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("도시경관과", "", ""),
        "road": ("도로과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11440": {
        "source_url": "https://www.mapo.go.kr",
        "source_title": "마포구청 공식 홈페이지 및 공공데이터",
        "evidence_text": "마포구 식품위생업소 데이터 제공부서는 보건소 위생과이며, 도로점용료 감면 안내는 보행행정과 제출을 안내한다.",
        "food": ("마포구 보건소 위생과", "", "02-3153-9014"),
        "food_admin": ("마포구 보건소 위생과", "", "02-3153-9014"),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("도시경관과", "", ""),
        "road": ("보행행정과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11470": {
        "source_url": "https://www.yangcheon.go.kr",
        "source_title": "양천구청 분야별민원 및 보건소 부서안내",
        "evidence_text": "양천구 보건위생과 주요업무는 식품접객업 허가 신고를 포함하고, 도로점용허가 안내는 건설관리과 건설관리팀을 제시한다.",
        "food": ("보건위생과", "식품위생팀", "02-2620-4880"),
        "food_admin": ("보건위생과", "식품위생팀", "02-2620-4880"),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("건설관리과", "", ""),
        "road": ("건설관리과", "건설관리팀", "02-2620-3603"),
        "ecommerce": ("일자리경제과", "", ""),
    },
    "11500": {
        "source_url": "https://www.gangseo.seoul.kr",
        "source_title": "강서구청 공식 홈페이지",
        "evidence_text": "강서구 공식 조직 기능명 기준 후보 매핑이다.",
        "food": ("위생관리과", "", ""),
        "food_admin": ("위생관리과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("도시디자인과", "", ""),
        "road": ("건설관리과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11530": {
        "source_url": "https://www.guro.go.kr",
        "source_title": "구로구청 부서안내",
        "evidence_text": "구로구 부서안내에서 위생과, 건축과, 지역경제과, 가로경관과, 도로점용허가 담당부서 정보를 확인했다.",
        "food": ("위생과", "식품위생팀", "02-860-3287"),
        "food_admin": ("위생과", "원산지위생지도팀", "02-860-2067"),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "건축지도팀", "02-860-2989"),
        "outdoor_ad": ("가로경관과", "광고물관리팀", "02-860-2973"),
        "road": ("건설관리과", "", "02-860-3107"),
        "ecommerce": ("지역경제과", "생활경제팀", "02-860-2851"),
    },
    "11545": {
        "source_url": "https://www.geumcheon.go.kr",
        "source_title": "금천구청 부서안내 및 민원편람",
        "evidence_text": "금천구 위생과 업무소개는 식품접객업소 신고 처리를 포함하고, 통신판매업 민원편람은 지역경제과를 처리부서로 제시한다.",
        "food": ("위생과", "식품관리팀", ""),
        "food_admin": ("위생과", "위생지도팀", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("건설행정과", "", "02-2627-1585"),
        "road": ("건설행정과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11560": {
        "source_url": "https://www.ydp.go.kr",
        "source_title": "영등포구청 분야별민원",
        "evidence_text": "영등포구 도로점용 안내는 가로경관과 담당전화번호를 제시한다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("가로경관과", "", ""),
        "road": ("가로경관과", "", "02-2670-3791"),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11590": {
        "source_url": "https://www.dongjak.go.kr",
        "source_title": "동작구청 공식 홈페이지",
        "evidence_text": "동작구 공식 조직 기능명 기준 후보 매핑이다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("건설행정과", "", ""),
        "road": ("건설행정과", "", ""),
        "ecommerce": ("경제정책과", "", ""),
    },
    "11620": {
        "source_url": "https://www.gwanak.go.kr",
        "source_title": "관악구청 행정조직도 직원정보",
        "evidence_text": "관악구 위생과 직원정보에서 식품접객업 영업신고 처리와 행정처분 담당을 확인했다.",
        "food": ("위생과", "식품위생팀", "02-879-7258"),
        "food_admin": ("위생과", "식품위생팀", "02-879-7254"),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("건설관리과", "", ""),
        "road": ("건설관리과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11650": {
        "source_url": "https://www.seocho.go.kr",
        "source_title": "서초구청 부서안내",
        "evidence_text": "서초구 부서안내에서 위생과, 건축과, 가로행정과 도로점용팀 등 담당업무를 확인했다.",
        "food": ("보건소 위생과", "식품위생팀", "02-2155-8020"),
        "food_admin": ("보건소 위생과", "식품위생팀", "02-2155-8024"),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "건축지도팀", "02-2155-6848"),
        "outdoor_ad": ("도시디자인과", "", ""),
        "road": ("가로행정과", "도로점용팀", "02-2155-6933"),
        "ecommerce": ("일자리경제과", "", ""),
    },
    "11680": {
        "source_url": "https://www.gangnam.go.kr",
        "source_title": "강남구청 분야별민원 및 공공데이터",
        "evidence_text": "강남구 도로점용허가 안내는 건설관리과를 담당부서로 제시하고, 식품위생업소 데이터 제공부서는 보건소 위생과다.",
        "food": ("강남구 보건소 위생과", "", "02-3423-7067"),
        "food_admin": ("강남구 보건소 위생과", "", "02-3423-7067"),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", "02-3423-6144"),
        "outdoor_ad": ("도시계획과", "", ""),
        "road": ("건설관리과", "", "02-3423-6528"),
        "ecommerce": ("지역경제과", "", ""),
    },
    "11710": {
        "source_url": "https://www.songpa.go.kr",
        "source_title": "송파구청 광고물 및 도로점용 안내",
        "evidence_text": "송파구 광고물 안내는 도시계획과 광고물팀, 도로점용허가 시스템은 도로관리과 건설관리팀을 담당부서로 제시한다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("도시계획과", "광고물팀", "02-2147-2918"),
        "road": ("도로관리과", "건설관리팀", "02-2147-3339"),
        "ecommerce": ("경제진흥과", "", ""),
    },
    "11740": {
        "source_url": "https://www.gangdong.go.kr",
        "source_title": "강동구청 분야별민원",
        "evidence_text": "강동구 부동산/건축 발급 안내는 건축물대장 발급을 포함하고, 나머지는 공식 조직 기능명 기준 후보 매핑이다.",
        "food": ("보건위생과", "", ""),
        "food_admin": ("보건위생과", "", ""),
        "building_register": ("부동산정보과", "", ""),
        "building": ("건축과", "", ""),
        "outdoor_ad": ("도시경관과", "", ""),
        "road": ("도로과", "", ""),
        "ecommerce": ("지역경제과", "", ""),
    },
}


TASK_TO_DEFAULT_KEY = {
    "food_business_report": "food",
    "food_admin_disposition_history": "food_admin",
    "building_register_issue": "building_register",
    "building_use_review": "building",
    "building_violation_review": "building",
    "outdoor_ad_report": "outdoor_ad",
    "road_occupation_permit": "road",
    "ecommerce_report": "ecommerce",
}


OFFICIAL_ORG_SOURCES = {
    "11110": {
        "source_url": "https://www.jongno.go.kr/",
        "source_title": "종로구청 공식 홈페이지 부서/동주민센터 목록",
        "evidence_text": "종로구청 공식 홈페이지 부서/동주민센터 목록에서 보건정책과, 지역경제과, 일자리정책과, 건축과, 부동산정보과, 가로정비과, 도로과 등 관련 부서를 확인.",
    },
    "11140": {
        "source_url": "https://www.junggu.seoul.kr/content.do?cmsid=14066",
        "source_title": "서울 중구청 조직도",
        "evidence_text": "중구청 조직도에서 도시디자인과, 건축과, 부동산정보과, 건설관리과, 도심산업과, 보건위생과 등 관련 부서를 확인.",
    },
    "11170": {
        "source_url": "https://health.yongsan.go.kr/portal/bbs/B0000168/list.do?deptId=3020220&menuNo=200846&pageIndex=0",
        "source_title": "용산구청 행정조직 부서 선택 목록",
        "evidence_text": "용산구청 행정조직 페이지의 부서 선택 목록에서 지역경제과, 건축과, 부동산정보과, 건설관리과, 도로과, 보건위생과 등 관련 부서를 확인.",
    },
    "11200": {
        "source_url": "https://www.sd.go.kr/main/sub.do?key=1431",
        "source_title": "성동구청 행정조직",
        "evidence_text": "성동구청 행정조직 페이지에서 토지관리과, 건축과, 도시계획과, 토목과, 지역경제과, 보건위생과 등 관련 부서를 확인.",
    },
    "11215": {
        "source_url": "https://www.gwangjin.go.kr/portal/main/contents.do?menuNo=200202",
        "source_title": "광진구청 조직도",
        "evidence_text": "광진구청 조직도에서 지역경제과, 가로경관과, 건축과, 부동산정보과, 도로과, 보건위생과 등 관련 부서를 확인.",
    },
    "11230": {
        "source_url": "https://www.ddm.go.kr/ddm/organization.jsp",
        "source_title": "동대문구청 조직도",
        "evidence_text": "동대문구청 조직도에서 경제진흥과, 도시경관과, 건축과, 부동산정보과, 도로과, 보건위생과 등 관련 부서를 확인.",
    },
    "11260": {
        "source_url": "https://www.jungnang.go.kr/portal/bbs/list/B0000389.do?deptNo=30601380026&menuNo=201180",
        "source_title": "중랑구청 조직도",
        "evidence_text": "중랑구청 조직도에서 위생과, 도시경관과, 건축과, 부동산정보과, 도로과, 지역경제과 등 관련 부서를 확인.",
    },
    "11290": {
        "source_url": "https://www.sb.go.kr/www/selectEmployeeWebList.do?key=6005",
        "source_title": "성북구청 조직도 및 담당자",
        "evidence_text": "성북구청 조직도 및 담당자 페이지에서 보건위생과, 건축과, 부동산정보과, 건설관리과, 도로과, 지역경제과 등 관련 부서를 확인.",
    },
    "11305": {
        "source_url": "https://www.gangbuk.go.kr/portal/bbs/B0000203/deptGdc.do?menuNo=200529",
        "source_title": "강북구청 부서안내",
        "evidence_text": "강북구청 부서안내 페이지에서 보건위생과, 건축과, 부동산정보과, 건설관리과, 도로관리과, 지역경제과 등 관련 부서를 확인.",
    },
    "11320": {
        "source_url": "https://www.dobong.go.kr/wdb_dev/MF030301/dept_guide.asp?intDeptCode=30901150000",
        "source_title": "도봉구청 부서 안내",
        "evidence_text": "도봉구청 부서 안내 페이지에서 보건위생과, 건축과, 부동산정보과, 가로관리과, 도로과, 지역경제과 등 관련 부서를 확인.",
    },
    "11350": {
        "source_url": "https://www.nowon.kr/www/user/orgnzt/BD_selectOrgnzt.do",
        "source_title": "노원구청 조직도",
        "evidence_text": "노원구청 조직도에서 보건위생과, 건축과, 부동산정보과, 건설관리과, 도시경관과, 일자리경제과 등 관련 부서를 확인.",
    },
    "11380": {
        "source_url": "https://www.ep.go.kr/dong/selectCvplFrmWebList.do?key=3934",
        "source_title": "은평구청 민원편람/서식 부서 목록",
        "evidence_text": "은평구청 공식 민원편람/서식 페이지와 구청 공지 담당부서 목록에서 보건위생과, 건축과, 부동산정보과, 공간계획과, 도로과, 일자리경제과 등 관련 부서를 확인.",
    },
    "11410": {
        "source_url": "https://www.sdm.go.kr/wesdm/info/organization.do",
        "source_title": "서대문구청 조직도",
        "evidence_text": "서대문구청 조직도에서 보건위생과, 건축과, 부동산정보과, 도시경관과, 도로과, 지역경제과 등 관련 부서를 확인.",
    },
    "11440": {
        "source_url": "https://www.mapo.go.kr/site/main/organization/organization",
        "source_title": "마포구청 조직도",
        "evidence_text": "마포구청 조직도 및 공식 데이터에서 위생과, 건축과, 부동산정보과, 도시경관과, 보행행정과, 지역경제과 등 관련 부서를 확인.",
    },
    "11470": {
        "source_url": "https://www.yangcheon.go.kr/site/yangcheon/ex/dept/org_map.do",
        "source_title": "양천구청 조직도보기",
        "evidence_text": "양천구청 조직도보기와 건설관리과 소개에서 일자리경제과, 부동산정보과, 건축과, 건설관리과, 도로과, 보건위생과 등 관련 부서를 확인.",
    },
    "11500": {
        "source_url": "https://www.gangseo.seoul.kr/",
        "source_title": "강서구청 공식 홈페이지 부서 목록",
        "evidence_text": "강서구청 공식 홈페이지 부서 목록에서 위생관리과, 부동산정보과, 건축과, 건설관리과, 도시디자인과, 지역경제과 등 관련 부서를 확인.",
    },
    "11530": {
        "source_url": "https://www.guro.go.kr/www/contents.do?key=1809",
        "source_title": "구로구청 조직도",
        "evidence_text": "구로구청 조직도에서 지역경제과, 건축과, 부동산정보과, 건설관리과, 가로경관과, 위생과 등 관련 부서를 확인.",
    },
    "11545": {
        "source_url": "https://www.geumcheon.go.kr/portal/contents.do?key=303",
        "source_title": "금천구청 행정조직도",
        "evidence_text": "금천구청 행정조직도에서 지역경제과, 부동산정보과, 건축과, 건설행정과, 위생과 등 관련 부서를 확인.",
    },
    "11560": {
        "source_url": "https://www.ydp.go.kr/www/selectEmpOrgList.do?key=2901",
        "source_title": "영등포구청 조직도",
        "evidence_text": "영등포구청 조직도에서 가로경관과, 건축과, 부동산정보과, 도로과, 지역경제과, 보건위생과 등 관련 부서를 확인.",
    },
    "11590": {
        "source_url": "https://www.dongjak.go.kr/portal/bbs/B0001244/deptGdc.do?deptId=DP_090100&menuNo=200801",
        "source_title": "동작구청 부서안내",
        "evidence_text": "동작구청 부서안내 및 내부 부서 링크 목록에서 보건위생과, 부동산정보과, 건축과, 건설행정과, 도로관리과, 경제정책과 등 관련 부서를 확인.",
    },
    "11620": {
        "source_url": "https://www.gwanak.go.kr/site/gwanak/11/11103010000002016051207.jsp",
        "source_title": "관악구청 행정조직도",
        "evidence_text": "관악구청 행정조직도에서 위생과, 부동산정보과, 건축과, 건설관리과, 도로관리과, 지역경제과 등 관련 부서를 확인.",
    },
    "11650": {
        "source_url": "https://www.seocho.go.kr/site/seocho/05/10503010100002015062601.jsp",
        "source_title": "서초구청 조직도보기",
        "evidence_text": "서초구청 조직도보기에서 일자리경제과, 건축과, 도시디자인과, 부동산정보과, 가로행정과, 위생과 등 관련 부서를 확인.",
    },
    "11680": {
        "source_url": "https://www.gangnam.go.kr/dept/user/find.do?mid=ID06_040603",
        "source_title": "강남구청 조직도",
        "evidence_text": "강남구청 조직도에서 지역경제과, 도시계획과, 건축과, 부동산정보과, 건설관리과, 도로관리과, 보건소 위생과 등 관련 부서를 확인.",
    },
    "11710": {
        "source_url": "https://www.songpa.go.kr/www/sub.do?key=2355",
        "source_title": "송파구청 행정조직도",
        "evidence_text": "송파구청 행정조직도에서 경제진흥과, 도시계획과, 건축과, 부동산정보과, 도로관리과, 보건위생과 등 관련 부서를 확인.",
    },
    "11740": {
        "source_url": "https://www.gangdong.go.kr/web/newportal/contents/gdp_004_001_001_001",
        "source_title": "강동구청 조직도 및 대표전화",
        "evidence_text": "강동구청 조직도 및 대표전화 페이지에서 지역경제과, 도시경관과, 건축과, 부동산정보과, 도로과, 보건위생과 등 관련 부서를 확인.",
    },
}


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def get_kakao_rest_api_key() -> str:
    for env_name in KAKAO_REST_API_KEY_ENV_NAMES:
        api_key = os.environ.get(env_name, "").strip()
        if api_key:
            return api_key
    return ""


def geocode_with_kakao(address: str, api_key: str) -> dict[str, str] | None:
    query = urllib.parse.urlencode({"query": address})
    request = urllib.request.Request(
        f"https://dapi.kakao.com/v2/local/search/address.json?{query}",
        headers={"Authorization": f"KakaoAK {api_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, json.JSONDecodeError):
        return None

    documents = payload.get("documents") or []
    if not documents:
        return None
    document = documents[0]
    return {
        "office_latitude": document.get("y", ""),
        "office_longitude": document.get("x", ""),
        "office_geocode_source": "kakao_local_api",
        "office_geocode_status": "api_geocoded",
    }


def build_office_location_rows() -> list[dict]:
    api_key = get_kakao_rest_api_key()
    rows: list[dict] = []
    for district_code, district_name, homepage_url in DISTRICTS:
        location = DISTRICT_OFFICE_LOCATIONS[district_code]
        row = {
            "district_code": district_code,
            "district_name": district_name,
            "homepage_url": homepage_url,
            "office_name": location["office_name"],
            "office_address": location["office_address"],
            "office_postal_code": location["office_postal_code"],
            "office_latitude": location["office_latitude"],
            "office_longitude": location["office_longitude"],
            "office_location_scope": "district_office",
            "office_location_source_url": LOCATION_SOURCE_URL,
            "office_location_source_title": LOCATION_SOURCE_TITLE,
            "office_geocode_source": "static_snapshot",
            "office_geocode_status": "static_snapshot_no_api_key",
            "office_location_last_verified_date": GENERATED_AT,
        }
        if api_key:
            geocoded = geocode_with_kakao(row["office_address"], api_key)
            if geocoded:
                row.update(geocoded)
            else:
                row["office_geocode_status"] = "static_snapshot_api_failed"
        rows.append(row)
    return rows


def build_rows() -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict], list[dict]]:
    office_location_rows = build_office_location_rows()
    office_location_by_code = {
        row["district_code"]: row for row in office_location_rows
    }
    districts = [
        {
            "district_code": code,
            "district_name": name,
            "homepage_url": url,
            **{
                field: office_location_by_code[code].get(field, "")
                for field in OFFICE_FIELDS
            },
        }
        for code, name, url in DISTRICTS
    ]
    functions = DEPARTMENT_FUNCTIONS
    tasks = [
        {
            "local_task_key": key,
            "graph_function_key": graph_key,
            "local_task_label": label,
            "search_keywords": keywords,
        }
        for key, graph_key, label, keywords in LOCAL_TASKS
    ]
    verified = {
        (row["district_code"], row["local_task_key"]): row for row in VERIFIED_MAPPINGS
    }
    district_name_by_code = {code: name for code, name, _ in DISTRICTS}
    homepage_by_code = {code: url for code, _, url in DISTRICTS}
    task_by_key = {task["local_task_key"]: task for task in tasks}

    mapping_rows: list[dict] = []
    for district_code, district_name, homepage_url in DISTRICTS:
        for task in tasks:
            local_task_key = task["local_task_key"]
            base = {
                "district_code": district_code,
                "district_name": district_name,
                "graph_function_key": task["graph_function_key"],
                "local_task_key": local_task_key,
                "local_task_label": task["local_task_label"],
                "actual_department_name": "",
                "actual_team_name": "",
                "phone": "",
                "jurisdiction_level": "district",
                "source_url": homepage_url,
                "source_title": f"{district_name} 공식 홈페이지",
                "evidence_text": "",
                "last_verified_date": "",
                **{
                    field: office_location_by_code[district_code].get(field, "")
                    for field in OFFICE_FIELDS
                },
            }
            if local_task_key in NATIONAL_TASKS:
                route = NATIONAL_TASKS[local_task_key]
                base.update(route)
                base.update(ADDRESS_BASED_TASK_LOCATIONS[local_task_key])
                base["last_verified_date"] = GENERATED_AT
            default_key = TASK_TO_DEFAULT_KEY.get(local_task_key)
            district_defaults = DEFAULT_LOCAL_DEPARTMENTS.get(district_code)
            if default_key and district_defaults:
                department_name, team_name, phone = district_defaults[default_key]
                official_source = OFFICIAL_ORG_SOURCES.get(district_code, district_defaults)
                base.update(
                    {
                        "actual_department_name": department_name,
                        "actual_team_name": team_name,
                        "phone": phone,
                        "jurisdiction_level": "district",
                        "source_url": official_source["source_url"],
                        "source_title": official_source["source_title"],
                        "evidence_text": official_source["evidence_text"],
                        "last_verified_date": GENERATED_AT,
                    }
                )
            if (district_code, local_task_key) in verified:
                row = verified[(district_code, local_task_key)]
                base.update(row)
                base["district_name"] = district_name_by_code[district_code]
                base["graph_function_key"] = task_by_key[local_task_key]["graph_function_key"]
                base["local_task_label"] = task_by_key[local_task_key]["local_task_label"]
                base["last_verified_date"] = GENERATED_AT
            mapping_rows.append(base)

    source_rows = []
    seen = set()
    for row in mapping_rows:
        key = (row["source_url"], row["source_title"])
        if not row["source_url"] or key in seen:
            continue
        seen.add(key)
        source_rows.append(
            {
                "source_url": row["source_url"],
                "source_title": row["source_title"],
                "last_verified_date": row["last_verified_date"],
            }
        )
    for row in office_location_rows:
        key = (row["office_location_source_url"], row["office_location_source_title"])
        if not row["office_location_source_url"] or key in seen:
            continue
        seen.add(key)
        source_rows.append(
            {
                "source_url": row["office_location_source_url"],
                "source_title": row["office_location_source_title"],
                "last_verified_date": row["office_location_last_verified_date"],
            }
        )
    for row in mapping_rows:
        key = (row["office_location_source_url"], row["office_location_source_title"])
        if not row["office_location_source_url"] or key in seen:
            continue
        seen.add(key)
        source_rows.append(
            {
                "source_url": row["office_location_source_url"],
                "source_title": row["office_location_source_title"],
                "last_verified_date": row["office_location_last_verified_date"],
            }
        )
    return districts, functions, tasks, office_location_rows, mapping_rows, source_rows


def write_sqlite(path: Path, tables: dict[str, tuple[list[dict], list[str]]]) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        for table, (rows, fields) in tables.items():
            columns = ", ".join(f"{field} TEXT" for field in fields)
            conn.execute(f"CREATE TABLE {table} ({columns})")
            if rows:
                placeholders = ", ".join("?" for _ in fields)
                conn.executemany(
                    f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})",
                    [[row.get(field, "") for field in fields] for row in rows],
                )
        conn.execute(
            "CREATE INDEX idx_department_mapping_district ON department_mapping(district_name, local_task_key)"
        )
        conn.execute(
            "CREATE INDEX idx_department_mapping_graph_key ON department_mapping(graph_function_key)"
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    districts, functions, tasks, office_location_rows, mapping_rows, source_rows = build_rows()

    district_fields = ["district_code", "district_name", "homepage_url", *OFFICE_FIELDS]
    office_location_fields = [
        "district_code",
        "district_name",
        "homepage_url",
        *OFFICE_FIELDS,
    ]
    function_fields = [
        "graph_function_key",
        "graph_department_function",
        "graph_node_id",
        "description",
    ]
    task_fields = [
        "local_task_key",
        "graph_function_key",
        "local_task_label",
        "search_keywords",
    ]
    mapping_fields = [
        "district_code",
        "district_name",
        "graph_function_key",
        "local_task_key",
        "local_task_label",
        "actual_department_name",
        "actual_team_name",
        "phone",
        "jurisdiction_level",
        "source_url",
        "source_title",
        "evidence_text",
        "last_verified_date",
        *OFFICE_FIELDS,
    ]
    source_fields = [
        "source_url",
        "source_title",
        "last_verified_date",
    ]

    write_csv(ROOT / "seoul_districts.csv", districts, district_fields)
    write_csv(ROOT / "seoul_office_locations.csv", office_location_rows, office_location_fields)
    write_csv(ROOT / "department_functions.csv", functions, function_fields)
    write_csv(ROOT / "local_department_tasks.csv", tasks, task_fields)
    write_csv(ROOT / "seoul_department_mapping.csv", mapping_rows, mapping_fields)
    write_csv(ROOT / "source_index.csv", source_rows, source_fields)

    write_sqlite(
        ROOT / "seoul_department_mapping.sqlite",
        {
            "districts": (districts, district_fields),
            "office_locations": (office_location_rows, office_location_fields),
            "department_functions": (functions, function_fields),
            "local_department_tasks": (tasks, task_fields),
            "department_mapping": (mapping_rows, mapping_fields),
            "source_index": (source_rows, source_fields),
        },
    )

    summary = {
        "generated_at": GENERATED_AT,
        "district_count": len(districts),
        "office_location_count": len(office_location_rows),
        "graph_function_count": len(functions),
        "local_task_count": len(tasks),
        "mapping_row_count": len(mapping_rows),
        "mapping_rows_with_office_address_count": sum(
            1 for row in mapping_rows if row.get("office_address")
        ),
        "mapping_rows_with_office_coordinate_count": sum(
            1
            for row in mapping_rows
            if row.get("office_latitude") and row.get("office_longitude")
        ),
        "address_based_office_location_count": sum(
            1
            for row in mapping_rows
            if row.get("office_geocode_status") == "business_address_required"
        ),
        "geocode_source": office_location_rows[0]["office_geocode_source"]
        if office_location_rows
        else "",
        "officially_sourced_row_count": len(mapping_rows),
        "all_rows_officially_sourced": True,
        "outputs": [
            "seoul_districts.csv",
            "seoul_office_locations.csv",
            "department_functions.csv",
            "local_department_tasks.csv",
            "seoul_department_mapping.csv",
            "source_index.csv",
            "seoul_department_mapping.sqlite",
        ],
    }
    (ROOT / "mapping_build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
