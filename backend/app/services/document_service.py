from __future__ import annotations

import re
from typing import Any

from app.data.catalog import DOCUMENT_PRIORITY_RULES
from app.data.document_metadata import document_metadata_for
from app.services.document_directory import lookup_document_directory, lookup_processing_time, split_summary, unique_links
from app.services.document_writing_guide import build_writing_guide
from app.services.graph_rag_service import GraphRagService, graph_rag_service
from app.services.slot_utils import as_list, slot_value


EVIDENCE_LINK_MARKERS = ("easylaw.go.kr", "law.go.kr")
EXCLUDED_DOCUMENT_TITLE_TOKENS: tuple[str, ...] = ()
EXCLUDED_PREREQUISITE_TOKENS = ("신분증", "주민등록증", "운전면허증", "여권")
FOOD_BUSINESS_REPORT_ATTACHMENT_CHECKLIST = [
    {
        "title": "교육이수증 1부",
        "condition": "식품위생법 제41조제2항에 따라 미리 교육을 받은 경우",
    },
    {
        "title": "제조·가공하려는 식품의 유형 및 제조방법 설명서 1부",
        "condition": "식품위생법 시행령 제21조제2호 영업만 해당",
    },
    {
        "title": "시설사용계약서 1부",
        "condition": "식품운반업에서 차고 또는 세차장을 임대하는 경우",
    },
    {
        "title": "먹는물 수질검사기관의 수질검사(시험)성적서 1부",
        "condition": "수돗물이 아닌 지하수 등을 먹는 물, 조리, 세척 등에 사용하는 경우",
    },
    {
        "title": "유선 또는 도선사업 면허증 또는 신고필증 1부",
        "condition": "수상구조물에서 휴게음식점영업, 일반음식점영업, 제과점영업을 하는 경우",
    },
    {
        "title": "식품자동판매기의 종류 및 설치장소가 적힌 서류 1부",
        "condition": "2대 이상의 식품자동판매기를 설치하고 일련관리번호로 일괄 신고하는 경우",
    },
    {
        "title": "수상레저사업 등록증 1부",
        "condition": "수상레저사업장에서 휴게음식점영업, 일반음식점영업, 제과점영업을 하는 경우",
    },
    {
        "title": "국유재산 사용허가서 1부",
        "condition": "국유철도 정거장시설 또는 군사시설에서 해당 영업을 하는 경우",
    },
    {
        "title": "도시철도시설 사용계약 서류 1부",
        "condition": "도시철도 정거장시설에서 해당 영업을 하는 경우",
    },
    {
        "title": "예비군식당 운영계약 서류 1부",
        "condition": "군사시설에서 예비군식당 운영계약에 따라 일반음식점영업을 하는 경우",
    },
    {
        "title": "영업장과 연접하는 외부 장소 사용권 증빙 1부",
        "condition": "영업장 외부 장소를 영업장으로 함께 사용하려는 경우",
    },
    {
        "title": "이동용 음식판매 자동차·화물차 관련 서류 1부",
        "condition": "음식판매자동차 또는 소형·경형화물자동차로 영업하는 경우",
    },
    {
        "title": "어린이놀이시설 설치검사합격증 또는 정기시설검사합격증",
        "condition": "영업장에 어린이놀이시설을 설치하는 경우",
    },
    {
        "title": "공유주방 소재지, 면적 등 사용계약 서류 1부",
        "condition": "공유주방 운영업자의 공유주방을 사용하는 경우",
    },
    {
        "title": "마리나선박 대여업 등록증 1부",
        "condition": "마리나선박에서 해당 영업을 하는 경우",
    },
]


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
        if self.has_signage_signal(case):
            selected.append(self.document_from_rule("signage-report", "needs_check"))

        return self.enrich_documents(case, sorted(selected, key=lambda item: item["priority"]))

    def enrich_documents(self, case: dict[str, Any], documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        documents = self.documents_for_scope(case, documents)
        documents = self.filter_irrelevant_optional_documents(case, documents)
        documents = self.filter_excluded_documents(documents)
        graph_documents = self.graph_rag.build_documents(case) or []
        enriched: list[dict[str, Any]] = []
        for document in documents:
            title = self.display_title(str(document.get("title") or ""))
            graph_match = self.find_matching_document(graph_documents, title)
            merged = {**document, "title": title}
            if graph_match:
                for key in (
                    "prerequisites",
                    "unlocks",
                    "officialLinks",
                    "prepareInfo",
                    "steps",
                    "evidence",
                    "processingTime",
                    "dependsOn",
                    "recommendedStart",
                    "calendarLane",
                    "sequenceRank",
                    "priorityScore",
                ):
                    if graph_match.get(key) and not merged.get(key):
                        merged[key] = graph_match[key]
                if graph_match.get("prerequisites"):
                    merged["graphPrerequisites"] = graph_match["prerequisites"]
            enriched.append(self.apply_document_metadata(case, merged))
        for index, document in enumerate(enriched, start=1):
            document["priority"] = index
        return self.assign_document_dependencies(self.assign_preparation_tracks(enriched))

    @staticmethod
    def apply_document_metadata(case: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
        title = DocumentService.display_title(str(document.get("title") or ""))
        metadata = document_metadata_for(title)
        directory = lookup_document_directory(case, title)
        merged = {**document, "title": title}
        if metadata.get("forceStatus"):
            merged["status"] = metadata["forceStatus"]

        merged["issuer"] = directory.get("issuer") or metadata.get("issuer") or "해당 발급기관 확인 필요"
        merged["submitTo"] = directory.get("submitTo") or metadata.get("submitTo") or "관할 담당부서 확인 필요"
        merged["submissionPhase"] = directory.get("submissionPhase") or metadata.get("submissionPhase") or "제출 전 확인"
        merged["issueChannel"] = directory.get("issueChannel") or ""
        merged["issuerUrl"] = directory.get("issuerUrl") or ""
        merged["issuerLinkLabel"] = directory.get("issuerLinkLabel") or ""
        merged["submitUrl"] = directory.get("submitUrl") or ""
        merged["submitLinkLabel"] = directory.get("submitLinkLabel") or ""
        processing_time = DocumentService.processing_time_for(merged, directory)
        if processing_time:
            merged["processingTime"] = processing_time
            merged["processingProfileId"] = processing_time.get("profileId") or ""
            display = str(processing_time.get("display") or "").strip()
            if display and processing_time.get("profileId") != "not_found":
                merged["perceivedDuration"] = display
                if not merged.get("statutoryDeadline") or merged.get("statutoryDeadline") == "확인 필요":
                    merged["statutoryDeadline"] = display
            merged["scheduleBlockerType"] = processing_time.get("blockerType") or ""
            merged["schedulePriorityRank"] = processing_time.get("schedulePriorityRank") or 90

        blockers: list[str] = []
        for raw_item in metadata.get("blockingPrerequisites") or []:
            item = DocumentService.display_title(str(raw_item))
            if item and not DocumentService.is_excluded_prerequisite(item) and item not in blockers:
                blockers.append(item)
        if not (DocumentService.is_food_business_report_title(title) and blockers):
            for raw_item in split_summary(str(directory.get("prerequisiteSummary") or "")):
                item = DocumentService.display_title(str(raw_item))
                if item and not DocumentService.is_excluded_prerequisite(item) and item not in blockers:
                    blockers.append(item)
        merged["blockingPrerequisites"] = blockers
        merged["dependencyNote"] = ""

        if merged["blockingPrerequisites"]:
            merged["prerequisites"] = ", ".join(merged["blockingPrerequisites"])
            merged["prepareInfo"] = merged["blockingPrerequisites"]
        merged["prepareInfo"] = DocumentService.clean_prepare_info(merged.get("prepareInfo") or [])
        if not merged["prepareInfo"]:
            merged["prepareInfo"] = merged["blockingPrerequisites"]
        if DocumentService.is_food_business_report_title(title):
            merged["conditionalAttachments"] = DocumentService.merge_conditional_attachments(
                merged.get("conditionalAttachments") or [],
                FOOD_BUSINESS_REPORT_ATTACHMENT_CHECKLIST,
            )

        merged["officialLinks"] = DocumentService.links_for_display([
            *(merged.get("officialLinks") or []),
            *(directory.get("officialLinks") or []),
        ]) or [{"label": "정부24에서 확인", "url": "https://www.gov.kr"}]
        writing_guide = build_writing_guide(case, title)
        if writing_guide:
            merged["writingGuide"] = writing_guide
        return merged

    @classmethod
    def filter_excluded_documents(cls, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            document
            for document in documents
            if not cls.is_excluded_document_title(str(document.get("title") or ""))
        ]

    @classmethod
    def is_excluded_document_title(cls, title: str) -> bool:
        normalized = cls.normalized_title(title)
        return any(cls.normalized_title(token) in normalized for token in EXCLUDED_DOCUMENT_TITLE_TOKENS)

    @classmethod
    def is_excluded_prerequisite(cls, value: str) -> bool:
        normalized = cls.normalized_title(value)
        return any(cls.normalized_title(token) in normalized for token in EXCLUDED_PREREQUISITE_TOKENS)

    @classmethod
    def clean_prepare_info(cls, values: list[Any]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            item = cls.display_title(str(value or ""))
            if not item or cls.is_excluded_prerequisite(item) or item in cleaned:
                continue
            cleaned.append(item)
        return cleaned

    @classmethod
    def is_food_business_report_title(cls, title: str) -> bool:
        normalized = cls.normalized_title(title)
        if not normalized:
            return False
        return any(
            token in normalized
            for token in (
                "식품영업신고서",
                "식품관련영업신고",
                "식품영업신고",
            )
        ) or normalized == "영업신고서"

    @classmethod
    def merge_conditional_attachments(
        cls,
        existing_items: list[Any],
        checklist_items: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        merged: list[dict[str, str]] = []
        seen: set[str] = set()

        def append_item(title: str, condition: str = "") -> None:
            display_title = cls.display_title(title)
            key = cls.normalized_title(display_title)
            if not display_title or not key or key in seen:
                return
            seen.add(key)
            item = {"title": display_title}
            if condition:
                item["condition"] = condition.strip()
            merged.append(item)

        for item in existing_items:
            if isinstance(item, dict):
                append_item(str(item.get("title") or item.get("label") or ""), str(item.get("condition") or item.get("note") or ""))
            else:
                append_item(str(item or ""))
        for item in checklist_items:
            append_item(item.get("title") or "", item.get("condition") or "")
        return merged

    @staticmethod
    def links_for_display(links: list[dict[str, str]]) -> list[dict[str, str]]:
        deduped = unique_links(links)
        primary = [link for link in deduped if not DocumentService.is_evidence_only_link(link)]
        specific_primary = [link for link in primary if not DocumentService.is_generic_gov24_link(link)]
        if specific_primary:
            primary = specific_primary
        return (primary or deduped)[:4]

    @staticmethod
    def is_evidence_only_link(link: dict[str, str]) -> bool:
        url = str(link.get("url") or "")
        return any(marker in url for marker in EVIDENCE_LINK_MARKERS)

    @staticmethod
    def is_generic_gov24_link(link: dict[str, str]) -> bool:
        return str(link.get("url") or "").rstrip("/") == "https://www.gov.kr" and "정부24" in str(link.get("label") or "")

    @staticmethod
    def processing_time_for(document: dict[str, Any], directory: dict[str, Any]) -> dict[str, Any]:
        processing_time = document.get("processingTime") if isinstance(document.get("processingTime"), dict) else {}
        if processing_time and processing_time.get("display") and processing_time.get("profileId") != "not_found":
            return processing_time
        directory_processing = directory.get("processingTime") if isinstance(directory.get("processingTime"), dict) else {}
        if directory_processing and directory_processing.get("display") and directory_processing.get("profileId") != "not_found":
            return directory_processing
        id_processing = lookup_processing_time(str(document.get("title") or ""), str(document.get("id") or ""))
        if id_processing.get("profileId") != "not_found":
            return id_processing
        return processing_time or directory_processing or id_processing

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

    @staticmethod
    def display_title(title: str) -> str:
        value = re.sub(r"\s+", " ", title or "").strip()
        if not value:
            return ""
        value = re.sub(r"\s*[:：]\s*[^:：]*(?:해당\s*시|해당시|필요\s*시|필요시).*$", "", value).strip()
        value = re.sub(r"\s*[\(\[][^)\]]*(?:해당\s*시|해당시|필요\s*시|필요시)[^)\]]*[\)\]]\s*", "", value).strip()
        value = re.sub(r"\s+", " ", value).strip()
        return value or re.sub(r"\s+", " ", title or "").strip()

    @classmethod
    def assign_preparation_tracks(cls, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                **document,
                **cls.preparation_track_for(str(document.get("title") or ""), int(document.get("priority") or index)),
            }
            for index, document in enumerate(documents, start=1)
        ]

    @classmethod
    def preparation_track_for(cls, title: str, priority: int) -> dict[str, Any]:
        normalized = cls.normalized_title(title)
        if any(token in normalized for token in ["사업자등록"]):
            return cls.track("after-registration", "사업자등록", "영업신고증 발급 후 진행해요.", 3, "영업신고 후")
        if any(token in normalized for token in ["지위승계", "승계신고"]):
            return cls.track("food-report", "승계 신고", "기존 영업신고 정보를 새 영업자 기준으로 넘겨요.", 2, "영업신고")
        if any(token in normalized for token in ["영업신고서", "영업신고증", "식품접객업", "식품영업신고"]):
            return cls.track("food-report", "영업신고 접수", "선행 서류를 모아서 접수하고 신고증을 받아요.", 2, "영업신고")
        if any(token in normalized for token in ["간판", "옥외광고", "원색도안", "도로점용", "외부공간", "테이블"]):
            return cls.track("extra-permits", "간판·외부공간", "설치나 외부 사용 전에 별도 신고 여부를 확인해요.", 2, "부가 신고")
        if any(token in normalized for token in ["소방", "안전시설", "완비증명", "액화석유", "가스", "lpg"]):
            return cls.track("facility-check", "시설 확인", "면적, 층수, 설비 조건에 따라 필요 여부가 갈려요.", 1, "사전 준비")
        if any(token in normalized for token in ["위생교육", "건강진단", "보건증"]):
            return cls.track("health-hygiene", "위생교육·건강진단", "영업신고 전에 미리 준비해요.", 1, "사전 준비")
        if any(token in normalized for token in ["임대차", "사용권한", "사용승낙", "건물주", "관리인"]):
            return cls.track("basic-proof", "사용권한 증빙", "영업장 사용 권한을 먼저 정리해요.", 1, "사전 준비")
        if priority >= 7:
            return cls.track("after-registration", "마무리 등록", "앞 단계가 끝난 뒤 진행해요.", 3, "영업신고 후")
        return cls.track("basic-proof", "기본 증빙", "영업신고 전에 미리 준비할 수 있어요.", 1, "동시 준비")

    @staticmethod
    def track(track_id: str, title: str, description: str, phase: int, phase_title: str) -> dict[str, Any]:
        return {
            "trackId": track_id,
            "trackTitle": title,
            "trackDescription": description,
            "phase": phase,
            "phaseTitle": phase_title,
        }

    @classmethod
    def assign_document_dependencies(cls, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        document_ids = {str(document.get("id") or "") for document in documents}
        document_by_id = {str(document.get("id") or ""): document for document in documents}
        for document in documents:
            document_title = str(document.get("title") or "")
            depends_on: list[str] = []
            for raw_id in document.get("dependsOn") or []:
                dependency_id = str(raw_id or "")
                if dependency_id and dependency_id in document_ids and dependency_id != document.get("id"):
                    dependency = document_by_id.get(dependency_id) or {}
                    if cls.should_ignore_dependency(document_title, str(dependency.get("title") or ""), ""):
                        continue
                    depends_on.append(dependency_id)
            for prerequisite in document.get("blockingPrerequisites") or []:
                match = cls.find_document_by_token(documents, str(prerequisite))
                dependency_id = str((match or {}).get("id") or "")
                if dependency_id and dependency_id != document.get("id"):
                    if cls.should_ignore_dependency(document_title, str((match or {}).get("title") or ""), str(prerequisite)):
                        continue
                    depends_on.append(dependency_id)
            document["dependsOn"] = cls.unique_strings(depends_on)
        return documents

    @classmethod
    def should_ignore_dependency(cls, document_title: str, dependency_title: str, prerequisite: str) -> bool:
        title = cls.normalized_title(document_title)
        dependency = cls.normalized_title(dependency_title)
        prerequisite_key = cls.normalized_title(prerequisite)
        return "임대차" in title and (
            "사용승낙" in dependency
            or "건물대지사용" in dependency
            or "사용승낙" in prerequisite_key
        )

    def build_minju_documents(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        summary = ((case.get("minjuIntake") or {}).get("summary") or {})
        if not summary:
            return []

        judgement_docs = ((summary.get("aiJudgement") or {}).get("documentSummary") or {})
        judgement_schedule = ((summary.get("aiJudgement") or {}).get("scheduleSummary") or {})
        requirement_graph = (summary.get("requirementGraph") or {})
        graph_docs = (requirement_graph.get("documentPlan") or {})
        schedule_plan = requirement_graph.get("schedulePlan") or {}
        schedule_by_id = self.schedule_tasks_by_document_id(schedule_plan)
        schedule_order = self.schedule_order_maps(schedule_plan, judgement_schedule)
        buckets: list[tuple[str, list[Any]]] = [
            ("required", self.sort_items_by_schedule([*(graph_docs.get("requiredForSubmission") or []), *(judgement_docs.get("required") or [])], schedule_order)),
            ("conditional", self.sort_items_by_schedule([*(graph_docs.get("conditional") or []), *(judgement_docs.get("conditional") or [])], schedule_order)),
            ("later", self.sort_items_by_schedule([*(graph_docs.get("later") or []), *(judgement_docs.get("later") or [])], schedule_order)),
        ]

        documents: list[dict[str, Any]] = []
        seen: set[str] = set()
        for bucket, items in buckets:
            for item in items or []:
                title = self.title_from_minju_item(item)
                seen_key = self.normalized_title(title)
                if not title or not seen_key or seen_key in seen or self.is_reference_check_title(title):
                    continue
                seen.add(seen_key)
                documents.append(self.document_from_minju_item(item, bucket, len(documents) + 1, schedule_by_id))
        documents = self.documents_for_scope(case, documents)
        documents = self.filter_irrelevant_optional_documents(case, documents)
        return self.ensure_full_opening_documents(case, documents, schedule_order)

    def ensure_full_opening_documents(
        self,
        case: dict[str, Any],
        documents: list[dict[str, Any]],
        schedule_order: tuple[dict[str, tuple[int, int, int, int, int]], dict[str, tuple[int, int, int, int, int]]] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.is_full_opening_case(case):
            return documents

        base_sequence = [
            ("임대차계약서", "required", "임대차"),
            ("신분증", "required", "신분증"),
            ("위생교육 수료증", "required", "위생교육"),
            ("건강진단결과서", "required", "건강진단"),
            ("소방완비증명서", "conditional", "소방완비"),
            ("식품 영업 신고서", "required", "영업신고서"),
            ("식품접객업 영업신고증", "required", "영업신고증"),
            ("사업자등록증", "later", "사업자등록"),
        ]
        optional_index = 5
        if self.has_lpg_signal(case):
            base_sequence.insert(optional_index, ("액화석유가스 사용시설완성검사증명서", "required", "액화석유"))
            optional_index += 1
        if self.has_signage_signal(case):
            base_sequence.insert(optional_index, ("옥외광고물 표시허가 신청서 또는 신고서", "conditional", "옥외광고"))
            optional_index += 1
            base_sequence.insert(optional_index, ("간판 설치 위치 사진, 원색도안, 설계도", "conditional", "원색도안"))

        merged: list[dict[str, Any]] = []
        used_ids: set[str] = set()
        for title, bucket, token in base_sequence:
            existing = self.find_document_by_token(documents, token) or self.find_document_by_token(documents, title)
            existing_id = str((existing or {}).get("id") or "")
            if existing and existing_id not in used_ids:
                merged.append({**existing, "priority": len(merged) + 1})
                used_ids.add(existing_id)
            else:
                merged.append(self.document_from_minju(title, bucket, len(merged) + 1))

        for document in documents:
            if not self.is_reference_check_title(document["title"]) and not self.find_document_by_token(merged, document["title"]):
                merged.append({**document, "priority": len(merged) + 1})

        if schedule_order:
            merged = self.sort_documents_by_schedule(merged, schedule_order)
        for index, document in enumerate(merged, start=1):
            document["priority"] = index
        return merged

    @classmethod
    def unique_labels(cls, labels: list[Any]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for label in labels:
            title = cls.display_title(str(label or ""))
            key = cls.normalized_title(title)
            if not title or not key or key in seen:
                continue
            seen.add(key)
            result.append(title)
        return result

    @classmethod
    def title_from_minju_item(cls, item: Any) -> str:
        if isinstance(item, dict):
            value = item.get("label") or item.get("title") or item.get("name") or item.get("documentName") or item.get("id")
        else:
            value = item
        return cls.display_title(str(value or ""))

    @classmethod
    def schedule_tasks_by_document_id(cls, schedule_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for key in ("priorityQueue", "notRequired"):
            for item in schedule_plan.get(key) or []:
                if not isinstance(item, dict):
                    continue
                document_id = str(item.get("documentId") or "")
                if document_id:
                    by_id[document_id] = item
        return by_id

    @classmethod
    def schedule_order_maps(
        cls,
        schedule_plan: dict[str, Any],
        judgement_schedule: dict[str, Any],
    ) -> tuple[dict[str, tuple[int, int, int, int, int]], dict[str, tuple[int, int, int, int, int]]]:
        by_id: dict[str, tuple[int, int, int, int, int]] = {}
        by_title: dict[str, tuple[int, int, int, int, int]] = {}
        gms_by_id: dict[str, int] = {}
        gms_by_title: dict[str, int] = {}

        for index, item in enumerate(judgement_schedule.get("priority") or []):
            if not isinstance(item, dict):
                continue
            document_id = str(item.get("documentId") or item.get("id") or "").strip()
            title_key = cls.normalized_title(str(item.get("label") or item.get("title") or ""))
            if document_id:
                gms_by_id.setdefault(document_id, index)
            if title_key:
                gms_by_title.setdefault(title_key, index)

        def remember(item: dict[str, Any], index: int) -> None:
            rank = cls._int(item.get("sequenceRank"), (index + 1) * 10)
            document_id = str(item.get("documentId") or item.get("id") or "").strip()
            title_key = cls.normalized_title(str(item.get("label") or item.get("title") or ""))
            gms_index = gms_by_id.get(document_id, gms_by_title.get(title_key, 9990 + index))
            duration_units = cls.processing_duration_units(item.get("processingTime") or {})
            priority_score = cls._int(item.get("priorityScore"), 0)
            value = (rank, gms_index, -duration_units, -priority_score, index)
            if document_id and document_id not in by_id:
                by_id[document_id] = value
            if title_key and title_key not in by_title:
                by_title[title_key] = value

        for index, item in enumerate(schedule_plan.get("priorityQueue") or []):
            if isinstance(item, dict):
                remember(item, index)

        for index, item in enumerate(judgement_schedule.get("priority") or []):
            if not isinstance(item, dict):
                continue
            document_id = str(item.get("documentId") or item.get("id") or "").strip()
            title_key = cls.normalized_title(str(item.get("label") or item.get("title") or ""))
            value = (9990, index, 0, 0, 9990 + index)
            if document_id and document_id not in by_id:
                by_id[document_id] = value
            if title_key and title_key not in by_title:
                by_title[title_key] = value
        return by_id, by_title

    @classmethod
    def sort_items_by_schedule(
        cls,
        items: list[Any],
        schedule_order: tuple[dict[str, tuple[int, int, int, int, int]], dict[str, tuple[int, int, int, int, int]]],
    ) -> list[Any]:
        return [
            item
            for index, item in sorted(
                enumerate(items or []),
                key=lambda index_item: cls.schedule_item_key(index_item[1], index_item[0], schedule_order),
            )
        ]

    @classmethod
    def sort_documents_by_schedule(
        cls,
        documents: list[dict[str, Any]],
        schedule_order: tuple[dict[str, tuple[int, int, int, int, int]], dict[str, tuple[int, int, int, int, int]]],
    ) -> list[dict[str, Any]]:
        return [
            document
            for index, document in sorted(
                enumerate(documents or []),
                key=lambda index_document: cls.document_schedule_sort_key(index_document[1], index_document[0], schedule_order),
            )
        ]

    @classmethod
    def document_schedule_sort_key(
        cls,
        document: dict[str, Any],
        fallback_index: int,
        schedule_order: tuple[dict[str, tuple[int, int, int, int, int]], dict[str, tuple[int, int, int, int, int]]],
    ) -> tuple[int, int, int, int, int, int, int, int, int]:
        workflow_rank = cls.workflow_order_rank(str(document.get("title") or ""))
        return (
            cls.schedule_stage_rank(document),
            *cls.schedule_item_key(document, fallback_index, schedule_order),
            workflow_rank,
            fallback_index,
        )

    @classmethod
    def schedule_stage_rank(cls, document: dict[str, Any]) -> int:
        normalized = cls.normalized_title(str(document.get("title") or ""))
        blocker = str(document.get("scheduleBlockerType") or "")
        if "사업자등록" in normalized or blocker == "after_food_report":
            return 50
        if "영업신고증" in normalized or "식품접객업" in normalized:
            return 40
        if "영업신고서" in normalized and "영업신고증" not in normalized:
            return 35
        if "옥외광고" in normalized or "표시허가" in normalized or "표시신고" in normalized:
            return 30
        if bool(document.get("canPrepareBeforeInquiry")) or int(document.get("phase") or 1) <= 1:
            return 10
        return 20

    @classmethod
    def workflow_order_rank(cls, title: str) -> int:
        normalized = cls.normalized_title(title)
        if "임대차" in normalized:
            return 10
        if "사용승낙" in normalized or "건물대지사용" in normalized:
            return 20
        if "건강진단" in normalized or "보건증" in normalized:
            return 30
        if "위생교육" in normalized:
            return 40
        if any(token in normalized for token in ("소방", "안전시설", "완비증명")):
            return 50
        if any(token in normalized for token in ("액화석유", "가스완성검사", "lpg")):
            return 55
        if any(token in normalized for token in ("원색도안", "설계도", "위치사진")):
            return 60
        if any(token in normalized for token in ("옥외광고", "표시허가", "표시신고")):
            return 70
        if "영업신고서" in normalized and "영업신고증" not in normalized:
            return 80
        if "영업신고증" in normalized or "식품접객업" in normalized:
            return 90
        if "사업자등록" in normalized:
            return 100
        return 9990

    @classmethod
    def schedule_item_key(
        cls,
        item: Any,
        fallback_index: int,
        schedule_order: tuple[dict[str, tuple[int, int, int, int, int]], dict[str, tuple[int, int, int, int, int]]],
    ) -> tuple[int, int, int, int, int, int]:
        by_id, by_title = schedule_order
        document_id = str((item.get("id") if isinstance(item, dict) else "") or "").strip()
        if isinstance(item, dict):
            title = str(item.get("label") or item.get("title") or item.get("name") or item.get("documentName") or "")
        else:
            title = str(item or "")
        title_key = cls.normalized_title(title)
        rank = by_id.get(document_id) or by_title.get(title_key)
        if rank:
            return (*rank, fallback_index)
        return (9990, 9990 + fallback_index, 0, 0, fallback_index, fallback_index)

    @classmethod
    def unique_strings(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            if value and value not in result:
                result.append(value)
        return result

    @classmethod
    def processing_duration_units(cls, processing_time: dict[str, Any]) -> int:
        days = cls._int(processing_time.get("maxBusinessDays"), 0)
        minutes = cls._int(processing_time.get("maxMinutes"), 0)
        return days * 1440 + minutes

    @staticmethod
    def _int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def has_lpg_signal(case: dict[str, Any]) -> bool:
        conditions = set(str(item) for item in as_list(slot_value(case, "condition_screening")))
        if "lpg_use" in conditions:
            return True
        summary = ((case.get("minjuIntake") or {}).get("summary") or {}) or ((case.get("minjuDraft") or {}).get("summary") or {})
        facility = ((summary.get("slots") or {}).get("facility") or {})
        if facility.get("lpgUse") is True:
            return True
        text = f"{case.get('rawInput') or ''} {slot_value(case, 'business_activity') or ''}"
        return bool(re.search(r"\bLPG\b|LP\s*가스|액화석유가스|가스\s*화구|가스버너|가스레인지|가스렌지|화구|숯불", text, re.IGNORECASE))

    @classmethod
    def documents_for_scope(cls, case: dict[str, Any], documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if cls.is_signage_only_case(case):
            return cls.ensure_scope_documents(
                documents,
                [
                    ("옥외광고물 표시허가 신청서 또는 신고서", "required"),
                    ("간판 설치 위치 사진, 원색도안, 설계도", "required"),
                    ("건물/대지 사용 승낙서", "conditional"),
                ],
                include_tokens=["간판", "옥외광고", "원색도안", "설계도", "위치사진", "사용승낙", "사용 승낙", "건물/대지"],
                exclude_tokens=["위생교육", "건강진단", "보건증", "식품", "영업신고", "사업자등록", "소방", "외부공간", "도로점용"],
            )
        if cls.is_transfer_case(case):
            return cls.ensure_scope_documents(
                documents,
                [
                    ("영업자 지위승계 신고서", "required"),
                    ("기존 영업신고증", "required"),
                    ("양도·양수 계약서", "required"),
                    ("임대차계약서", "required"),
                    ("사업자등록 정정 또는 신규 등록", "later"),
                ],
                include_tokens=["승계", "양도", "양수", "기존 영업신고", "임대차", "사업자등록"],
                exclude_tokens=["식품 영업 신고서", "위생교육", "건강진단", "소방완비", "옥외광고", "간판", "도로점용", "외부공간"],
            )
        return documents

    @classmethod
    def ensure_scope_documents(
        cls,
        documents: list[dict[str, Any]],
        base_sequence: list[tuple[str, str]],
        include_tokens: list[str],
        exclude_tokens: list[str],
    ) -> list[dict[str, Any]]:
        scoped: list[dict[str, Any]] = []
        used_ids: set[str] = set()
        for title, bucket in base_sequence:
            existing = cls.find_document_by_token(documents, title)
            existing_id = str((existing or {}).get("id") or "")
            if existing and existing_id not in used_ids:
                scoped.append({**existing, "priority": len(scoped) + 1})
                used_ids.add(existing_id)
            else:
                scoped.append(cls.document_from_minju(title, bucket, len(scoped) + 1))

        for document in documents:
            title = str(document.get("title") or "")
            normalized = cls.normalized_title(title)
            if any(cls.normalized_title(token) in normalized for token in exclude_tokens):
                continue
            if include_tokens and not any(cls.normalized_title(token) in normalized for token in include_tokens):
                continue
            if not cls.find_document_by_token(scoped, title):
                scoped.append({**document, "priority": len(scoped) + 1})

        for index, document in enumerate(scoped, start=1):
            document["priority"] = index
        return scoped

    @classmethod
    def filter_irrelevant_optional_documents(cls, case: dict[str, Any], documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if cls.is_signage_only_case(case) or cls.is_transfer_case(case):
            return documents

        conditions = set(str(item) for item in as_list(slot_value(case, "condition_screening")))
        answered_fields = set(case.get("questionLoop", {}).get("answeredFields") or [])
        user_answered_conditions = "condition_screening" in answered_fields
        text = cls.condition_signal_text(case)
        has_signage = cls.has_signage_signal(case)
        has_outdoor = cls.has_outdoor_signal(case)
        has_lpg = (user_answered_conditions and "lpg_use" in conditions) or bool(re.search(r"\bLPG\b|가스", text, re.IGNORECASE))

        filtered: list[dict[str, Any]] = []
        for document in documents:
            title = str(document.get("title") or "")
            normalized = cls.normalized_title(title)
            if not has_signage and any(token in normalized for token in ["간판", "옥외광고", "원색도안", "설계도"]):
                continue
            if not has_outdoor and any(token in normalized for token in ["외부공간", "도로점용", "보도", "테이블", "사용면적도면"]):
                continue
            if not has_lpg and any(token in normalized for token in ["액화석유", "lpg", "가스완성검사"]):
                continue
            filtered.append(document)

        for index, document in enumerate(filtered, start=1):
            document["priority"] = index
        return filtered

    @staticmethod
    def condition_signal_text(case: dict[str, Any]) -> str:
        return f"{case.get('rawInput') or ''} {slot_value(case, 'business_activity') or ''}"

    @classmethod
    def has_signage_signal(cls, case: dict[str, Any]) -> bool:
        conditions = set(str(item) for item in as_list(slot_value(case, "condition_screening")))
        answered_fields = set(case.get("questionLoop", {}).get("answeredFields") or [])
        return cls.has_affirmative_signage(
            case,
            cls.condition_signal_text(case),
            conditions,
            "condition_screening" in answered_fields,
            "signboard_planned" in answered_fields,
        )

    @classmethod
    def has_outdoor_signal(cls, case: dict[str, Any]) -> bool:
        conditions = set(str(item) for item in as_list(slot_value(case, "condition_screening")))
        answered_fields = set(case.get("questionLoop", {}).get("answeredFields") or [])
        return cls.has_affirmative_outdoor(
            case,
            cls.condition_signal_text(case),
            conditions,
            "condition_screening" in answered_fields,
            "outdoor_space_planned" in answered_fields,
        )

    @staticmethod
    def has_negative_signage_signal(text: str) -> bool:
        return bool(
            re.search(
                r"(?:간판|옥외광고|표시허가|표시신고)(?:(?!노상|도로점용|외부|테라스|보도).){0,30}"
                r"(?:미정|아직|안\s*함|하지\s*않|없|기존\s*것|그대로|설치\s*안|설치하지|미설치|철거)",
                text,
            )
        )

    @staticmethod
    def has_positive_signage_signal(text: str) -> bool:
        return bool(
            re.search(
                r"(?:간판|옥외광고|표시허가|표시신고)[^.。]{0,35}"
                r"(?:설치(?!\s*안)|달|부착|신청|신고|허가|예정|할\s*거|할거|남기|진행)",
                text,
            )
        )

    @staticmethod
    def has_negative_outdoor_signal(text: str) -> bool:
        outdoor_subject = r"(?:옥외\s*노상|노상|야외|외부\s*공간|외부|가게\s*밖|테이블|테라스|보도|도로점용|도로|대기\s*의자)"
        return bool(
            re.search(
                outdoor_subject
                + r"[^.。]{0,45}(?:쓰지\s*않|사용하지\s*않|사용\s*안|안\s*씀|안\s*함|하지\s*않|설치\s*안|설치하지|미설치|없|미정)",
                text,
            )
        )

    @staticmethod
    def has_positive_outdoor_signal(text: str) -> bool:
        return bool(re.search(r"외부\s*테이블|가게\s*앞\s*테이블|보도\s*점용|도로점용|테라스|야외\s*테이블|노상\s*영업|대기\s*의자", text))

    @classmethod
    def has_affirmative_signage(
        cls,
        case: dict[str, Any],
        text: str,
        conditions: set[str],
        user_answered_conditions: bool,
        user_answered_signage: bool,
    ) -> bool:
        if user_answered_signage and slot_value(case, "signboard_planned") is True:
            return True
        if cls.has_positive_signage_signal(text):
            return True
        if cls.has_negative_signage_signal(text):
            return False
        if slot_value(case, "signboard_planned") is False:
            return False
        if slot_value(case, "signboard_planned") is True:
            return True
        if "none" in conditions:
            return False
        if re.search(r"간판|옥외광고|표시허가|표시신고", text):
            return True
        return user_answered_conditions and "signage_planned" in conditions and slot_value(case, "signboard_planned") is not False

    @classmethod
    def has_affirmative_outdoor(
        cls,
        case: dict[str, Any],
        text: str,
        conditions: set[str],
        user_answered_conditions: bool,
        user_answered_outdoor: bool,
    ) -> bool:
        if user_answered_outdoor and slot_value(case, "outdoor_space_planned") is True and not cls.has_negative_outdoor_signal(text):
            return True
        if cls.has_negative_outdoor_signal(text):
            return False
        if slot_value(case, "outdoor_space_planned") is False or "none" in conditions:
            return False
        if slot_value(case, "outdoor_space_planned") is True:
            return True
        if cls.has_positive_outdoor_signal(text):
            return True
        return user_answered_conditions and "outdoor_space_planned" in conditions and slot_value(case, "outdoor_space_planned") is not False

    @classmethod
    def is_full_opening_case(cls, case: dict[str, Any]) -> bool:
        if cls.is_signage_only_case(case) or cls.is_transfer_case(case):
            return False
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

    @classmethod
    def is_signage_only_case(cls, case: dict[str, Any]) -> bool:
        raw = str(case.get("rawInput") or "")
        business = str(slot_value(case, "business_activity") or "")
        text = f"{raw} {business}"
        has_signage = re.search(r"간판|옥외광고|표시허가|표시신고", text)
        partial_only = re.search(r"간판만|간판.*만|이미\s*운영|운영\s*중|영업신고(?:는|가)?\s*이미|기존.*가게", text)
        full_opening = re.search(r"창업|개업|새로\s*열|오픈|영업신고.*해야|신규", text)
        return bool(has_signage and partial_only and not full_opening)

    @staticmethod
    def is_transfer_case(case: dict[str, Any]) -> bool:
        takeover = slot_value(case, "takeover_type")
        raw = str(case.get("rawInput") or "")
        business = str(slot_value(case, "business_activity") or "")
        text = f"{raw} {business}"
        return takeover == "transfer" or bool(re.search(r"인수|승계|양도\s*양수|양도·양수|기존.*음식점", text))

    @staticmethod
    def find_document_by_token(documents: list[dict[str, Any]], token: str) -> dict[str, Any] | None:
        needle = DocumentService.normalized_title(DocumentService.display_title(token))
        for document in documents:
            title = DocumentService.normalized_title(str(document.get("title") or ""))
            if needle and title and (needle in title or title in needle):
                return document
            duplicate_groups = [
                ("사업자등록",),
                ("원색도안", "설계도"),
                ("사용승낙", "사용승낙서", "사용권한"),
                ("임대차",),
                ("신분증",),
            ]
            for group in duplicate_groups:
                if any(item in needle for item in group) and any(item in title for item in group):
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
        title = cls.display_title(title)
        status = "not_started" if bucket == "required" else ("needs_check" if bucket == "conditional" else "blocked")
        bucket_label = {
            "required": "영업신고 전에 준비해야 하는 서류",
            "conditional": "조건에 해당하면 준비해야 하는 서류",
            "later": "앞 단계가 끝난 뒤 진행하는 서류",
        }.get(bucket, "확인 필요")
        return {
            "id": cls._doc_id(title, priority),
            "title": title,
            "priority": priority,
            "reason": bucket_label,
            "status": status,
            "statutoryDeadline": "확인 필요",
            "perceivedDuration": "확인 필요",
            "prerequisites": "주소/API 판정과 현재 준비 서류 상태 확인",
            "unlocks": "다음 제출 단계",
            "officialLinks": [{"label": "정부24에서 확인", "url": "https://www.gov.kr"}],
            "prepareInfo": [title, bucket_label],
            "steps": ["발급처 확인", "제출처 확인", "선행서류 확인"],
            "canPrepareBeforeInquiry": bucket != "later",
        }

    @classmethod
    def document_from_minju_item(
        cls,
        item: Any,
        bucket: str,
        priority: int,
        schedule_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        title = cls.title_from_minju_item(item)
        document = cls.document_from_minju(title, bucket, priority)
        if not isinstance(item, dict):
            return document

        document_id = str(item.get("id") or "").strip()
        schedule_task = schedule_by_id.get(document_id, {})
        if document_id:
            document["id"] = document_id

        graph_status = str(item.get("status") or schedule_task.get("status") or "").strip()
        if graph_status:
            document["graphStatus"] = graph_status
            document["status"] = cls.status_for_minju_status(graph_status, bucket)

        if item.get("condition"):
            document["condition"] = item["condition"]
        if item.get("missingInputs"):
            document["missingInputs"] = item.get("missingInputs") or []
        if item.get("stage") or schedule_task.get("stage"):
            document["stage"] = item.get("stage") or schedule_task.get("stage")

        processing_time = item.get("processingTime") or schedule_task.get("processingTime")
        if isinstance(processing_time, dict) and processing_time:
            document["processingTime"] = processing_time

        for key in (
            "dependsOn",
            "recommendedStart",
            "calendarLane",
            "sequenceRank",
            "priorityScore",
        ):
            if schedule_task.get(key) not in (None, "", []):
                document[key] = schedule_task[key]
        return document

    @staticmethod
    def status_for_minju_status(status: str, bucket: str) -> str:
        if status in {"needs_input", "conditional_if_planned"}:
            return "needs_check"
        if status in {"later", "not_required_by_current_inputs"}:
            return "blocked"
        if status in {"required", "reference"}:
            return "not_started" if bucket != "later" else "blocked"
        return "not_started" if bucket == "required" else ("needs_check" if bucket == "conditional" else "blocked")

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
            "food-business-report": ["선행 서류 확인", "영업신고 접수", "접수 결과 확인"],
            "business-registration": ["영업신고증 준비", "세무서/홈택스 신청", "사업자등록증 발급 확인"],
            "fire-safety": ["대상 여부 확인", "현장 실사 일정 조율", "증명서 발급"],
            "lpg-certificate": ["시공 완료", "검사 신청", "필증 발급"],
            "signage-report": ["간판 자료 정리", "옥외광고물 허가·신고 여부 확인", "신고 결과 반영"],
        }
        return mapping.get(rule_id, ["필요 항목 확인", "공식 사이트 확인", "완료 표시"])


document_service = DocumentService()
