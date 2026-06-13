from __future__ import annotations

import re
from typing import Any

from app.data.catalog import DOCUMENT_PRIORITY_RULES
from app.data.document_metadata import document_metadata_for
from app.services.document_directory import lookup_document_directory, split_summary, unique_links
from app.services.graph_rag_service import GraphRagService, graph_rag_service
from app.services.slot_utils import as_list, slot_value


# 서류별 정식 발급처 링크 오버라이드.
# DB(source_url)에는 법령 근거(easylaw 등) 링크가 섞여 있어, 실제 신청/발급
# 포털로 덮어쓴다. tokens 중 하나라도 제목에 포함되면 적용한다.
# - url/label: 발급처 링크와 표시 텍스트
# - note(선택): 랜딩 페이지에서 추가 조작이 필요할 때 보여줄 안내 문구
# 정부24에서 발급/신청 가능한 서류는 해당 민원의 정부24 딥링크로 연결한다.
ISSUER_LINK_OVERRIDES: list[dict[str, Any]] = [
    {
        "tokens": ("위생교육",),
        "url": "https://www.foodservice.or.kr/",
        "label": "위생교육신청 바로가기",
        "note": "페이지에서 '위생교육 수료증 발급' 메뉴를 찾아 클릭하면 돼요.",
    },
    {
        "tokens": ("건강진단",),
        "url": "https://www.gov.kr/portal/service/serviceInfo/135200000129",
        "label": "정부24 건강진단결과서 발급",
    },
    {
        "tokens": ("영업신고",),
        "url": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=14600000021&HighCtgCD=A09006&tp_seq=02",
        "label": "정부24 식품영업신고",
    },
    {
        "tokens": ("옥외광고",),
        "url": "https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=13100000152&HighCtgCD=A09006",
        "label": "정부24 옥외광고물 신고",
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
        if "signage_planned" in conditions:
            selected.append(self.document_from_rule("signage-report", "needs_check"))

        return self.enrich_documents(case, sorted(selected, key=lambda item: item["priority"]))

    def enrich_documents(self, case: dict[str, Any], documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        documents = self.documents_for_scope(case, documents)
        documents = self.filter_irrelevant_optional_documents(case, documents)
        graph_documents = self.graph_rag.build_documents(case) or []
        enriched: list[dict[str, Any]] = []
        for document in documents:
            title = self.display_title(str(document.get("title") or ""))
            graph_match = self.find_matching_document(graph_documents, title)
            merged = {**document, "title": title}
            if graph_match:
                for key in ("prerequisites", "unlocks", "officialLinks", "prepareInfo", "steps", "evidence"):
                    if graph_match.get(key) and not merged.get(key):
                        merged[key] = graph_match[key]
                if graph_match.get("prerequisites"):
                    merged["graphPrerequisites"] = graph_match["prerequisites"]
            enriched.append(self.apply_document_metadata(case, merged))
        for index, document in enumerate(enriched, start=1):
            document["priority"] = index
        return self.assign_preparation_tracks(enriched)

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
        merged["issuerNote"] = ""
        override_key = DocumentService.normalized_title(title)
        for override in ISSUER_LINK_OVERRIDES:
            if any(DocumentService.normalized_title(token) in override_key for token in override["tokens"]):
                merged["issuerUrl"] = override["url"]
                merged["issuerLinkLabel"] = override["label"]
                merged["issuerNote"] = override.get("note") or ""
                break
        merged["submitUrl"] = directory.get("submitUrl") or ""
        merged["submitLinkLabel"] = directory.get("submitLinkLabel") or ""

        blockers: list[str] = []
        for raw_item in metadata.get("blockingPrerequisites") or []:
            item = DocumentService.display_title(str(raw_item))
            if item and item not in blockers:
                blockers.append(item)
        for raw_item in split_summary(str(directory.get("prerequisiteSummary") or "")):
            item = DocumentService.display_title(str(raw_item))
            if item and item not in blockers:
                blockers.append(item)
        merged["blockingPrerequisites"] = blockers
        merged["dependencyNote"] = metadata.get("dependencyNote") or directory.get("prerequisiteSummary") or ""

        if merged["blockingPrerequisites"]:
            merged["prerequisites"] = ", ".join(merged["blockingPrerequisites"])
            merged["prepareInfo"] = merged["blockingPrerequisites"]
        if merged["dependencyNote"]:
            merged["unlocks"] = merged["dependencyNote"]

        merged["officialLinks"] = unique_links([
            *(merged.get("officialLinks") or []),
            *(directory.get("officialLinks") or []),
        ]) or [{"label": "정부24에서 확인", "url": "https://www.gov.kr"}]
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
            return cls.track("after-registration", "후속 등록", "영업신고증을 받은 뒤 진행해요.", 3, "이후 등록")
        if any(token in normalized for token in ["지위승계", "승계신고"]):
            return cls.track("food-report", "승계 신고", "기존 영업신고 정보를 새 영업자 기준으로 넘겨요.", 2, "영업신고")
        if any(token in normalized for token in ["영업신고서", "영업신고증", "식품접객업", "식품영업신고"]):
            return cls.track("food-report", "영업신고 접수", "선행 서류를 모아서 접수하고 신고증을 받아요.", 2, "영업신고")
        if any(token in normalized for token in ["간판", "옥외광고", "원색도안", "도로점용", "외부공간", "테이블"]):
            return cls.track("extra-permits", "간판·외부공간", "설치나 외부 사용 전에 별도 신고 여부를 확인해요.", 2, "부가 신고")
        if any(token in normalized for token in ["소방", "안전시설", "완비증명", "액화석유", "가스", "lpg"]):
            return cls.track("facility-check", "시설 조건", "면적, 층수, 설비 조건에 따라 필요 여부가 갈려요.", 1, "동시 준비")
        if any(token in normalized for token in ["위생교육", "건강진단", "보건증"]):
            return cls.track("health-hygiene", "보건·위생", "영업신고 전에 미리 준비할 수 있어요.", 1, "동시 준비")
        if any(token in normalized for token in ["임대차", "사용권한", "사용승낙", "신분증", "건물주", "관리인"]):
            return cls.track("basic-proof", "기본 증빙", "영업장 사용 권한과 본인 확인 자료를 먼저 정리해요.", 1, "동시 준비")
        if priority >= 7:
            return cls.track("after-registration", "후속 등록", "앞 단계가 끝난 뒤 진행해요.", 3, "이후 등록")
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

    def build_minju_documents(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        summary = ((case.get("minjuIntake") or {}).get("summary") or {})
        if not summary:
            return []

        judgement_docs = ((summary.get("aiJudgement") or {}).get("documentSummary") or {})
        graph_docs = ((summary.get("requirementGraph") or {}).get("documentPlan") or {})
        buckets: list[tuple[str, list[Any]]] = [
            ("required", self.unique_labels([*(judgement_docs.get("required") or []), *self._labels(graph_docs.get("requiredForSubmission"))])),
            ("conditional", self.unique_labels([*(judgement_docs.get("conditional") or []), *self._labels(graph_docs.get("conditional"))])),
            ("later", self.unique_labels([*(judgement_docs.get("later") or []), *self._labels(graph_docs.get("later"))])),
        ]

        documents: list[dict[str, Any]] = []
        seen: set[str] = set()
        for bucket, labels in buckets:
            for label in labels or []:
                title = self.display_title(str(label or ""))
                seen_key = self.normalized_title(title)
                if not title or not seen_key or seen_key in seen or self.is_reference_check_title(title):
                    continue
                seen.add(seen_key)
                documents.append(self.document_from_minju(title, bucket, len(documents) + 1))
        documents = self.documents_for_scope(case, documents)
        documents = self.filter_irrelevant_optional_documents(case, documents)
        return self.ensure_full_opening_documents(case, documents)

    def ensure_full_opening_documents(self, case: dict[str, Any], documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.is_full_opening_case(case):
            return documents

        base_sequence = [
            ("임대차계약서", "required", "임대차"),
            ("신분증", "required", "신분증"),
            ("위생교육 수료증", "required", "위생교육"),
            ("건강진단결과서", "required", "건강진단"),
            ("소방완비증명서", "conditional", "소방완비"),
            ("식품 영업 신고서", "required", "영업신고서"),
            ("식품접객업 영업신고증", "required", "영업신고"),
            ("사업자등록증", "later", "사업자등록"),
        ]
        if self.has_lpg_signal(case):
            base_sequence.insert(5, ("액화석유가스 사용시설완성검사증명서", "required", "액화석유"))

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
                    ("신분증", "required"),
                    ("사업자등록 정정 또는 신규 등록", "later"),
                ],
                include_tokens=["승계", "양도", "양수", "기존 영업신고", "임대차", "신분증", "사업자등록"],
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
        for title, bucket in base_sequence:
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
        user_answered_signage = "signboard_planned" in answered_fields
        user_answered_outdoor = "outdoor_space_planned" in answered_fields
        text = f"{case.get('rawInput') or ''} {slot_value(case, 'business_activity') or ''}"
        has_signage = cls.has_affirmative_signage(case, text, conditions, user_answered_conditions, user_answered_signage)
        has_outdoor = cls.has_affirmative_outdoor(case, text, conditions, user_answered_conditions, user_answered_outdoor)
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
    def has_affirmative_signage(
        case: dict[str, Any],
        text: str,
        conditions: set[str],
        user_answered_conditions: bool,
        user_answered_signage: bool,
    ) -> bool:
        if user_answered_signage and slot_value(case, "signboard_planned") is True:
            return True
        if re.search(r"간판[^.。]*(미정|아직|안\s*함|하지\s*않|없|기존\s*것|그대로)", text):
            return False
        if slot_value(case, "signboard_planned") is False or "none" in conditions:
            return False
        if slot_value(case, "signboard_planned") is True:
            return True
        if re.search(r"간판|옥외광고|표시허가|표시신고", text):
            return True
        return user_answered_conditions and "signage_planned" in conditions and slot_value(case, "signboard_planned") is not False

    @staticmethod
    def has_affirmative_outdoor(
        case: dict[str, Any],
        text: str,
        conditions: set[str],
        user_answered_conditions: bool,
        user_answered_outdoor: bool,
    ) -> bool:
        if user_answered_outdoor and slot_value(case, "outdoor_space_planned") is True:
            return True
        if re.search(r"(외부|가게\s*밖|테이블|테라스|보도|도로)[^.。]*(쓰지\s*않|사용하지\s*않|없|안\s*씀|미정)", text):
            return False
        if slot_value(case, "outdoor_space_planned") is False or "none" in conditions:
            return False
        if slot_value(case, "outdoor_space_planned") is True:
            return True
        if re.search(r"외부\s*테이블|가게\s*앞\s*테이블|보도|도로점용|테라스|대기\s*의자", text):
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
