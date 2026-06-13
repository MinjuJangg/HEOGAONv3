from __future__ import annotations

import re
from typing import Any

from app.data.catalog import DOCUMENT_PRIORITY_RULES
from app.data.document_metadata import document_metadata_for
from app.services.graph_rag_service import GraphRagService, graph_rag_service
from app.services.slot_utils import as_list, slot_value


class DocumentService:
    def __init__(self, graph_rag: GraphRagService = graph_rag_service) -> None:
        self.graph_rag = graph_rag

    def build_documents(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        minju_documents = self.build_minju_documents(case)
        if minju_documents:
            return self.enrich_documents(case, minju_documents)

        graph_rag_documents = self.graph_rag.build_documents(case)
        if graph_rag_documents:
            return self.enrich_documents(case, graph_rag_documents)

        case.setdefault("ai", {})["documentsSource"] = "catalog"
        selected = [
            self.document_from_rule("health-check", "not_started"),
            self.document_from_rule("hygiene-education", "not_started"),
            self.document_from_rule("food-business-report", "needs_check"),
            self.document_from_rule("business-registration", "blocked"),
        ]

        conditions = set(as_list(slot_value(case, "condition_screening")))
        if slot_value(case, "on_site_consumption") is True or "lpg_use" in conditions:
            selected.append(self.document_from_rule("fire-safety", "needs_check"))
        if "lpg_use" in conditions:
            selected.append(self.document_from_rule("lpg-certificate", "needs_check"))
        if "signage_planned" in conditions:
            selected.append(self.document_from_rule("signage-report", "needs_check"))

        return self.enrich_documents(case, sorted(selected, key=lambda item: item["priority"]))

    def enrich_documents(self, case: dict[str, Any], documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        graph_documents = self.graph_rag.build_documents(case) or []
        enriched: list[dict[str, Any]] = []
        for document in documents:
            graph_match = self.find_matching_document(graph_documents, str(document.get("title") or ""))
            merged = {**document}
            if graph_match:
                for key in ("prerequisites", "unlocks", "officialLinks", "prepareInfo", "steps", "evidence"):
                    if graph_match.get(key) and not merged.get(key):
                        merged[key] = graph_match[key]
                if graph_match.get("prerequisites"):
                    merged["graphPrerequisites"] = graph_match["prerequisites"]
            enriched.append(self.apply_document_metadata(merged))
        for index, document in enumerate(enriched, start=1):
            document["priority"] = index
        return enriched

    @classmethod
    def apply_document_metadata(cls, document: dict[str, Any]) -> dict[str, Any]:
        metadata = document_metadata_for(str(document.get("title") or ""))
        merged = {**document}
        if metadata.get("forceStatus"):
            merged["status"] = metadata["forceStatus"]

        merged["issuer"] = metadata.get("issuer") or "해당 발급기관 확인 필요"
        merged["submitTo"] = metadata.get("submitTo") or "관할 담당부서 확인 필요"
        merged["submissionPhase"] = metadata.get("submissionPhase") or "제출 전 확인"
        merged["blockingPrerequisites"] = metadata.get("blockingPrerequisites") or []
        merged["dependencyNote"] = metadata.get("dependencyNote") or ""

        if merged["blockingPrerequisites"]:
            merged["prerequisites"] = ", ".join(merged["blockingPrerequisites"])
            merged["prepareInfo"] = merged["blockingPrerequisites"]
        if merged["dependencyNote"]:
            merged["unlocks"] = merged["dependencyNote"]
        return merged

    @classmethod
    def find_matching_document(cls, documents: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
        needle = cls.normalized_title(title)
        if not needle:
            return None
        for document in documents:
            candidate = cls.normalized_title(str(document.get("title") or ""))
            if candidate and (needle in candidate or candidate in needle):
                return document
        return None

    @staticmethod
    def normalized_title(title: str) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]+", "", title or "").lower()

    def build_minju_documents(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        summary = ((case.get("minjuIntake") or {}).get("summary") or {})
        if not summary:
            return []

        judgement_docs = ((summary.get("aiJudgement") or {}).get("documentSummary") or {})
        graph_docs = ((summary.get("requirementGraph") or {}).get("documentPlan") or {})
        buckets: list[tuple[str, list[Any]]] = [
            ("required", judgement_docs.get("required") or self._labels(graph_docs.get("requiredForSubmission"))),
            ("conditional", judgement_docs.get("conditional") or self._labels(graph_docs.get("conditional"))),
            ("later", judgement_docs.get("later") or self._labels(graph_docs.get("later"))),
        ]

        documents: list[dict[str, Any]] = []
        seen: set[str] = set()
        for bucket, labels in buckets:
            for label in labels or []:
                title = str(label or "").strip()
                if not title or title in seen or self.is_reference_check_title(title):
                    continue
                seen.add(title)
                documents.append(self.document_from_minju(title, bucket, len(documents) + 1))
        return self.ensure_full_opening_documents(case, documents)

    def ensure_full_opening_documents(self, case: dict[str, Any], documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.is_full_opening_case(case):
            return documents

        base_sequence = [
            ("임대차계약서", "required", "임대차"),
            ("신분증", "required", "신분증"),
            ("위생교육 수료증", "required", "위생교육"),
            ("건강진단결과서", "required", "건강진단"),
            ("소방완비증명서(해당 시)", "conditional", "소방완비"),
            ("식품 영업 신고서", "required", "영업신고서"),
            ("식품접객업 영업신고증", "required", "영업신고"),
            ("사업자등록증", "later", "사업자등록"),
        ]

        merged: list[dict[str, Any]] = []
        for title, bucket, token in base_sequence:
            merged.append(self.document_from_minju(title, bucket, len(merged) + 1))

        for document in documents:
            if not self.is_reference_check_title(document["title"]) and not self.find_document_by_token(merged, document["title"]):
                merged.append({**document, "priority": len(merged) + 1})

        for index, document in enumerate(merged, start=1):
            document["priority"] = index
        return merged

    @classmethod
    def is_full_opening_case(cls, case: dict[str, Any]) -> bool:
        raw = str(case.get("rawInput") or "")
        takeover = slot_value(case, "takeover_type")
        if takeover == "new_report":
            return True
        if re.search(r"창업|개업|오픈|열고|시작", raw):
            return True

        summary = ((case.get("minjuIntake") or {}).get("summary") or {}) or ((case.get("minjuDraft") or {}).get("summary") or {})
        judgement_docs = ((summary.get("aiJudgement") or {}).get("documentSummary") or {})
        graph_docs = ((summary.get("requirementGraph") or {}).get("documentPlan") or {})
        document_titles: list[str] = []
        for key in ("required", "conditional", "later"):
            document_titles.extend(str(item) for item in judgement_docs.get(key) or [])
        for key in ("requiredForSubmission", "conditional", "later"):
            document_titles.extend(cls._labels(graph_docs.get(key)))
        joined_titles = " ".join(document_titles)

        if "사업자등록" in joined_titles and ("영업신고" in joined_titles or "식품" in joined_titles):
            return True

        business = str(slot_value(case, "business_activity") or "")
        scope = " ".join(str(summary.get(key) or "") for key in ("intent", "scope", "serviceScope"))
        return bool(
            re.search(r"full|opening|startup|new|창업|개업", scope, re.IGNORECASE)
            and re.search(r"카페|음식|식품|휴게|일반음식", f"{business} {joined_titles}")
        )

    @staticmethod
    def find_document_by_token(documents: list[dict[str, Any]], token: str) -> dict[str, Any] | None:
        for document in documents:
            title = str(document.get("title") or "")
            if token in title or title in token:
                return document
        return None

    @staticmethod
    def is_reference_check_title(title: str) -> bool:
        normalized = re.sub(r"\s+", "", title)
        check_only_tokens = [
            "건축물대장",
            "위반건축물",
            "동일장소",
            "행정처분",
            "기존업소",
            "건축물용도",
        ]
        return any(token in normalized for token in check_only_tokens)

    @classmethod
    def document_from_minju(cls, title: str, bucket: str, priority: int) -> dict[str, Any]:
        status = "not_started" if bucket == "required" else ("needs_check" if bucket == "conditional" else "blocked")
        bucket_label = {
            "required": "제출 핵심 서류",
            "conditional": "조건 확인 후 준비",
            "later": "후순위/사후 단계",
        }.get(bucket, "확인 필요")
        return {
            "id": cls._doc_id(title, priority),
            "title": title,
            "priority": priority,
            "reason": f"minju 그래프/GMS 판단 결과: {bucket_label}",
            "status": status,
            "statutoryDeadline": "확인 필요",
            "perceivedDuration": "확인 필요",
            "prerequisites": "주소/API 판정과 현재 준비 서류 상태 확인",
            "unlocks": "다음 제출 또는 문의 단계",
            "officialLinks": [{"label": "정부24에서 확인", "url": "https://www.gov.kr"}],
            "prepareInfo": [title, bucket_label],
            "steps": ["준비 가능 여부 확인", "발급/수료/작성", "제출 전 최종 확인"],
            "canPrepareBeforeInquiry": bucket != "later",
        }

    @staticmethod
    def _labels(items: Any) -> list[str]:
        if not isinstance(items, list):
            return []
        labels: list[str] = []
        for item in items:
            if isinstance(item, dict):
                value = item.get("label") or item.get("name") or item.get("title")
            else:
                value = item
            if value:
                labels.append(str(value))
        return labels

    @staticmethod
    def _doc_id(title: str, priority: int) -> str:
        slug = re.sub(r"[^0-9A-Za-z가-힣]+", "-", title).strip("-").lower()
        return f"minju-doc-{priority}-{slug[:30]}" if slug else f"minju-doc-{priority}"

    def toggle_document(self, case: dict[str, Any], document_id: str | None, completed: bool) -> None:
        if not document_id:
            return
        completed_ids = set(case["completedDocumentIds"])
        if completed:
            completed_ids.add(document_id)
        else:
            completed_ids.discard(document_id)
        case["completedDocumentIds"] = sorted(completed_ids)
        for document in case["documents"]:
            if document["id"] == document_id:
                document["status"] = "completed" if completed else "not_started"

    def document_from_rule(self, rule_id: str, status: str) -> dict[str, Any]:
        rule = next(item for item in DOCUMENT_PRIORITY_RULES if item["id"] == rule_id)
        return {
            "id": rule["id"],
            "title": rule["title"],
            "priority": rule["priority"],
            "reason": rule["reason"],
            "status": status,
            "statutoryDeadline": rule["statutoryDeadline"],
            "perceivedDuration": rule["perceivedDuration"],
            "prerequisites": rule["prerequisites"],
            "unlocks": rule["unlocks"],
            "officialLinks": self.official_links_for(rule["id"]),
            "prepareInfo": self.prepare_info_for(rule["id"]),
            "steps": self.steps_for(rule["id"]),
            "canPrepareBeforeInquiry": rule["id"] in {"health-check", "hygiene-education", "building-ledger"},
        }

    @staticmethod
    def official_links_for(rule_id: str) -> list[dict[str, str]]:
        if rule_id == "building-ledger":
            return [{"label": "정부24 건축물대장", "url": "https://www.gov.kr"}]
        if rule_id == "food-business-report":
            return [{"label": "정부24 식품관련영업신고", "url": "https://www.gov.kr"}]
        return [{"label": "정부24에서 확인", "url": "https://www.gov.kr"}]

    @staticmethod
    def prepare_info_for(rule_id: str) -> list[str]:
        mapping = {
            "building-ledger": ["정확한 주소", "층수", "위반건축물 여부"],
            "health-check": ["창업자/종사자 이름", "검진기관", "발급일"],
            "hygiene-education": ["영업자 정보", "후보 업종", "수료기관"],
            "food-business-report": ["후보 영업신고 유형", "선행 서류 완료 여부", "영업장 정보"],
            "business-registration": ["영업신고증", "임대차계약서", "대표자 정보"],
            "fire-safety": ["면적", "층수", "시설 구조", "소방 설비 상태"],
            "lpg-certificate": ["가스 설비 시공 상태", "화구 종류", "검사 일정"],
            "signage-report": ["간판 위치", "크기", "조명 여부", "디자인 도면"],
        }
        return mapping.get(rule_id, ["신청 정보"])

    @staticmethod
    def steps_for(rule_id: str) -> list[str]:
        mapping = {
            "building-ledger": ["주소 확정", "건축물대장 조회", "용도와 위반 여부 확인"],
            "health-check": ["검진기관 확인", "검진 진행", "결과서 발급 후 보관"],
            "hygiene-education": ["교육 대상 확인", "온라인/오프라인 수료", "수료증 저장"],
            "food-business-report": ["선행 서류 확인", "보건소 위생과 문의", "영업신고 접수"],
            "business-registration": ["영업신고증 준비", "세무서/홈택스 신청", "사업자등록증 발급 확인"],
            "fire-safety": ["대상 여부 문의", "현장 실사 일정 조율", "증명서 발급"],
            "lpg-certificate": ["시공 완료", "검사 신청", "필증 발급"],
            "signage-report": ["간판 자료 정리", "옥외광고물 담당 문의", "허가·신고 여부 반영"],
        }
        return mapping.get(rule_id, ["필요 항목 확인", "공식 사이트 확인", "완료 표시"])


document_service = DocumentService()
