from __future__ import annotations

import re
from typing import Any


DOCUMENT_METADATA: list[dict[str, Any]] = [
    {
        "tokens": ["임대차", "사용권한"],
        "issuer": "임대인, 건물주 또는 관리인",
        "submitTo": "관할 구청 위생과 영업신고 접수 창구",
        "submissionPhase": "영업신고 전",
        "blockingPrerequisites": ["건물주/관리인 동의", "점포 계약 또는 사용 승낙 확정"],
        "dependencyNote": "영업신고증을 신청할 때 점포 사용 권한을 증명하는 핵심 선행서류예요.",
    },
    {
        "tokens": ["신분증"],
        "issuer": "본인 보유",
        "submitTo": "구청 영업신고, 세무서/홈택스 사업자등록 등 본인확인 창구",
        "submissionPhase": "각 신청 접수 시",
        "blockingPrerequisites": [],
        "dependencyNote": "대표자 본인 확인용으로 대부분의 접수 단계에 같이 필요해요.",
    },
    {
        "tokens": ["위생교육"],
        "issuer": "한국외식산업협회, 한국휴게음식업중앙회 등 업종별 위생교육기관",
        "submitTo": "관할 구청 위생과 영업신고 접수 창구",
        "submissionPhase": "영업신고 전",
        "blockingPrerequisites": ["업종 유형 확정", "대표자 정보"],
        "dependencyNote": "영업신고증 발급 전에 준비해야 하는 선행 수료증이에요.",
    },
    {
        "tokens": ["건강진단", "보건증"],
        "issuer": "보건소 또는 지정 의료기관",
        "submitTo": "관할 구청 위생과 영업신고 접수 창구",
        "submissionPhase": "영업신고 전",
        "blockingPrerequisites": ["대표자/종사자 신분증", "검진 진행"],
        "dependencyNote": "식품 취급 영업신고 전에 제출해야 하는 선행 결과서예요.",
    },
    {
        "tokens": ["소방완비", "안전시설"],
        "issuer": "관할 소방서",
        "submitTo": "관할 구청 위생과 영업신고 접수 창구",
        "submissionPhase": "해당 면적/층수 조건이면 영업신고 전",
        "blockingPrerequisites": ["면적/층수 기준 확인", "소방시설 설치 또는 현장 확인"],
        "dependencyNote": "대상 시설이면 영업신고증 발급 전에 먼저 필요해요.",
    },
    {
        "tokens": ["영업신고서", "식품 영업 신고서"],
        "issuer": "신청인이 작성",
        "submitTo": "관할 구청 위생과",
        "submissionPhase": "영업신고 접수 시",
        "blockingPrerequisites": ["임대차계약서 또는 사용권한 증빙", "신분증", "위생교육 수료증", "건강진단결과서"],
        "dependencyNote": "선행서류를 모아 영업신고증 발급을 신청하는 접수 서식이에요.",
    },
    {
        "tokens": ["영업신고증", "식품접객업"],
        "issuer": "관할 구청 위생과",
        "submitTo": "세무서/홈택스 사업자등록 신청 시 선행 제출자료로 사용",
        "submissionPhase": "사업자등록 전",
        "blockingPrerequisites": ["영업신고서 접수", "임대차계약서 또는 사용권한 증빙", "위생교육 수료증", "건강진단결과서", "소방완비증명서"],
        "dependencyNote": "사업자등록증 발급 전에 먼저 받아야 하는 핵심 선행 결과물이에요.",
    },
    {
        "tokens": ["사업자등록"],
        "issuer": "국세청 홈택스 또는 관할 세무서",
        "submitTo": "국세청/세무서",
        "submissionPhase": "영업신고증 발급 후, 사업개시일부터 20일 이내",
        "blockingPrerequisites": ["영업신고증", "임대차계약서", "대표자 신분증"],
        "dependencyNote": "영업신고증이 먼저 있어야 안정적으로 신청할 수 있는 후행 단계예요.",
        "forceStatus": "blocked",
    },
    {
        "tokens": ["옥외광고", "간판", "표시허가", "표시신고"],
        "issuer": "신청인이 작성, 간판업체가 도면/원색도안 보조",
        "submitTo": "관할 구청 옥외광고물 담당부서 또는 도시경관/건설관리 부서",
        "submissionPhase": "간판 설치 전",
        "blockingPrerequisites": ["간판 종류/크기/위치 확정", "건물주 또는 관리인 사용 승낙", "간판 도안/설계도"],
        "dependencyNote": "허가/신고 대상 간판이면 설치 전에 담당부서 확인과 접수가 필요해요.",
    },
    {
        "tokens": ["사용 승낙", "사용승낙", "소유자", "관리인", "건물"],
        "issuer": "건물주, 소유자 또는 관리인",
        "submitTo": "구청 위생과, 옥외광고물 담당부서, 도로점용 담당부서 중 해당 창구",
        "submissionPhase": "해당 신청 전",
        "blockingPrerequisites": ["설치/사용 위치 확정", "소유자 또는 관리인 동의"],
        "dependencyNote": "간판, 외부공간, 영업장 사용권한 확인에 반복해서 쓰이는 선행 동의서예요.",
    },
    {
        "tokens": ["원색도안", "설계도", "위치 사진", "간판 설치"],
        "issuer": "간판업체, 디자이너 또는 신청인",
        "submitTo": "관할 구청 옥외광고물 담당부서",
        "submissionPhase": "간판 허가/신고 접수 시",
        "blockingPrerequisites": ["간판 종류/크기/위치 확정", "건물주 또는 관리인 사용 승낙"],
        "dependencyNote": "간판 허가/신고서에 붙는 첨부자료예요.",
    },
    {
        "tokens": ["외부공간", "도로점용", "사용 면적", "위치도"],
        "issuer": "신청인 또는 시공/설계 보조업체",
        "submitTo": "관할 구청 도로점용/건설관리 담당부서",
        "submissionPhase": "외부 테이블 또는 도로/보도 사용 전",
        "blockingPrerequisites": ["외부공간 위치", "사용 면적", "건물주/관리인 승낙", "보도/도로 점용 여부 확인"],
        "dependencyNote": "가게 앞 테이블이 보도나 도로를 쓰면 별도 점용 확인이 필요해요.",
    },
]


def document_metadata_for(title: str) -> dict[str, Any]:
    normalized = _normalize(title)
    for item in DOCUMENT_METADATA:
        if any(_normalize(token) in normalized for token in item["tokens"]):
            return {
                "issuer": item["issuer"],
                "submitTo": item["submitTo"],
                "submissionPhase": item["submissionPhase"],
                "blockingPrerequisites": item["blockingPrerequisites"],
                "dependencyNote": item["dependencyNote"],
                **({"forceStatus": item["forceStatus"]} if item.get("forceStatus") else {}),
            }
    return {
        "issuer": "신청인 또는 해당 발급기관",
        "submitTo": "관할 담당부서 확인 필요",
        "submissionPhase": "제출 전 확인",
        "blockingPrerequisites": [],
        "dependencyNote": "공식 안내 기준으로 발급처와 제출처를 최종 확인해야 해요.",
    }


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").lower()
