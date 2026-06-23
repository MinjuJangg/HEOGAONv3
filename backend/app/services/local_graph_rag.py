from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalDocumentRule:
    id: str
    title: str
    graph_names: tuple[str, ...]
    priority: int
    status: str
    statutory_deadline: str
    perceived_duration: str
    reason: str
    unlocks: str
    can_prepare_before_inquiry: bool
    condition: str = "always"


@dataclass(frozen=True)
class LocalInquiryRule:
    id: str
    title: str
    graph_names: tuple[str, ...]
    default_department: str
    reason: str
    questions: tuple[str, ...]
    condition: str = "always"


DOCUMENT_RULES: tuple[LocalDocumentRule, ...] = (
    LocalDocumentRule(
        id="building-ledger",
        title="건축물대장 확인",
        graph_names=(
            "건축물대장 확인(용도 및 위반 여부)",
            "건축물대장 발급 및 열람",
            "건축물대장 용도 확인",
            "건축물 용도 판정",
            "위반건축물 여부 확인",
        ),
        priority=1,
        status="needs_check",
        statutory_deadline="즉시",
        perceived_duration="즉시",
        reason="계약 전 건물 용도와 위반 여부를 확인해야 해요.",
        unlocks="임대차계약, 영업신고 검토",
        can_prepare_before_inquiry=True,
    ),
    LocalDocumentRule(
        id="health-check",
        title="건강진단결과서",
        graph_names=("건강진단결과서", "건강진단결과서 발급"),
        priority=2,
        status="not_started",
        statutory_deadline="즉시",
        perceived_duration="4~5일",
        reason="식품접객 영업신고 전에 종사자 건강진단결과서가 필요할 수 있어요.",
        unlocks="식품접객업 영업신고증",
        can_prepare_before_inquiry=True,
    ),
    LocalDocumentRule(
        id="hygiene-education",
        title="위생교육 수료증",
        graph_names=("위생교육 수료증", "위생교육 이수"),
        priority=3,
        status="not_started",
        statutory_deadline="즉시",
        perceived_duration="1일",
        reason="영업 종류에 맞는 위생교육 이수 여부를 확인해요.",
        unlocks="식품접객업 영업신고증",
        can_prepare_before_inquiry=True,
    ),
    LocalDocumentRule(
        id="food-business-report",
        title="식품접객업 영업신고증",
        graph_names=("식품접객업 영업신고증", "식품관련영업신고", "영업신고", "영업신고 신청", "영업신고증 발급"),
        priority=4,
        status="needs_check",
        statutory_deadline="즉시",
        perceived_duration="방문 시 즉시",
        reason="선행 서류와 건물 조건을 확인한 뒤 영업신고를 진행해요.",
        unlocks="사업자등록증, 간판 허가 신청",
        can_prepare_before_inquiry=False,
    ),
    LocalDocumentRule(
        id="fire-safety",
        title="안전시설등 완비증명서",
        graph_names=("안전시설등 완비증명서", "안전시설등 완비증명서 필요 여부 확인", "소방시설 현장 실사 준비"),
        priority=5,
        status="needs_check",
        statutory_deadline="3~7일",
        perceived_duration="5~7일",
        reason="면적, 층수, 다중이용업소 요건에 따라 필요 여부를 확인해야 해요.",
        unlocks="식품접객업 영업신고증",
        can_prepare_before_inquiry=False,
        condition="fire",
    ),
    LocalDocumentRule(
        id="lpg-certificate",
        title="액화석유가스 완성검사필증",
        graph_names=("액화석유가스 완성검사필증", "LPG 사용 여부 확인"),
        priority=6,
        status="needs_check",
        statutory_deadline="즉시",
        perceived_duration="3~5일",
        reason="LPG 등 가스 사용 시설이면 완성검사 대상 여부를 확인해요.",
        unlocks="식품접객업 영업신고증",
        can_prepare_before_inquiry=False,
        condition="lpg",
    ),
    LocalDocumentRule(
        id="business-registration",
        title="사업자등록증",
        graph_names=("사업자등록증", "사업자등록 신청", "사업자등록증 발급"),
        priority=7,
        status="blocked",
        statutory_deadline="20일 이내",
        perceived_duration="즉시~1일",
        reason="인허가 신고 업종은 영업신고증을 준비한 뒤 사업자등록을 진행해요.",
        unlocks="카드단말기, POS, 세금계산서 등 매출 활동",
        can_prepare_before_inquiry=False,
    ),
    LocalDocumentRule(
        id="signage-report",
        title="옥외광고물(간판) 허가 및 신고증",
        graph_names=("옥외광고물(간판) 허가 및 신고증", "옥외광고물 등의 표시허가(신고)", "간판 규격 위치 표시방법 확인"),
        priority=8,
        status="needs_check",
        statutory_deadline="7일 이내",
        perceived_duration="3~5일",
        reason="간판 위치, 크기, 표시방법이 허가·신고 기준에 맞는지 확인해요.",
        unlocks="합법적인 외부 간판 설치",
        can_prepare_before_inquiry=False,
        condition="signage",
    ),
    LocalDocumentRule(
        id="road-occupation",
        title="도로점용허가",
        graph_names=("도로점용허가", "도로점용허가 대상 확인", "도로 점용 위치 및 면적 확인"),
        priority=9,
        status="needs_check",
        statutory_deadline="확인 필요",
        perceived_duration="확인 필요",
        reason="외부 테이블이나 입간판이 공공 도로·보도를 점용하는지 확인해요.",
        unlocks="외부 공간 사용",
        can_prepare_before_inquiry=False,
        condition="outdoor",
    ),
    LocalDocumentRule(
        id="online-sales-report",
        title="통신판매업신고",
        graph_names=("통신판매업신고", "통신판매업"),
        priority=10,
        status="needs_check",
        statutory_deadline="확인 필요",
        perceived_duration="2~3일",
        reason="온라인 주문이나 택배 판매가 있으면 별도 신고 여부를 확인해요.",
        unlocks="온라인 판매",
        can_prepare_before_inquiry=False,
        condition="online",
    ),
)


INQUIRY_RULES: tuple[LocalInquiryRule, ...] = (
    LocalInquiryRule(
        id="food-business-type",
        title="영업신고 유형 확인",
        graph_names=("식품관련영업신고", "영업신고", "건축물대장 용도 확인"),
        default_department="식품위생 업무 담당부서",
        reason="가게 조건에 맞는 식품접객업 신고 유형과 선행 확인 항목을 확인해야 해요.",
        questions=(
            "제 가게는 어떤 영업신고 유형을 보면 될까요?",
            "건축물 용도나 객석 기준으로 더 확인할 서류가 있나요?",
            "지금 먼저 준비해도 되는 서류와 문의 후 준비할 서류가 무엇인가요?",
        ),
    ),
    LocalInquiryRule(
        id="liquor-business-type",
        title="주류 판매 가능 업종 확인",
        graph_names=("주류 판매 가능 업종 및 일반음식점 전환 여부 확인", "주류 판매 여부 확인"),
        default_department="식품위생 업무 담당부서",
        reason="주류 판매 계획이 있으면 일반음식점 등 가능한 업종을 확인해야 해요.",
        questions=(
            "주류 판매가 가능한 영업신고 유형은 무엇인가요?",
            "현재 계획한 업종에서 일반음식점 전환 검토가 필요한가요?",
        ),
        condition="liquor",
    ),
    LocalInquiryRule(
        id="fire-safety-check",
        title="안전시설등 완비증명서 대상 확인",
        graph_names=("안전시설등 완비증명서 필요 여부 확인", "안전시설등 완비증명서", "소방시설 현장 실사 준비"),
        default_department="소방 안전 업무 담당부서",
        reason="면적, 층수, 구조에 따라 소방 완비증명 대상 여부가 달라질 수 있어요.",
        questions=(
            "이 영업장이 안전시설등 완비증명서 대상인가요?",
            "현장 확인 전에 준비할 도면이나 서류가 있나요?",
        ),
        condition="fire",
    ),
    LocalInquiryRule(
        id="signage-check",
        title="간판 허가·신고 확인",
        graph_names=("옥외광고물 등의 표시허가(신고)", "간판 규격 위치 표시방법 확인"),
        default_department="옥외광고물 관리 업무 담당부서",
        reason="간판 설치 계획이 있으면 표시 허가·신고 기준을 확인해야 해요.",
        questions=(
            "제 간판은 허가와 신고 중 어느 절차가 필요한가요?",
            "도안, 사진, 설치 위치 중 어떤 자료를 먼저 준비하면 되나요?",
        ),
        condition="signage",
    ),
    LocalInquiryRule(
        id="road-occupation-check",
        title="외부 공간 사용 확인",
        graph_names=("도로점용허가", "도로 점용 위치 및 면적 확인"),
        default_department="도로점용 업무 담당부서",
        reason="외부 테이블이나 입간판이 공공 도로·보도에 걸치는지 확인해야 해요.",
        questions=(
            "이 외부 공간이 도로점용허가 대상인지 확인하려면 어떤 자료가 필요한가요?",
            "위치도와 평면도는 어느 수준으로 준비하면 되나요?",
        ),
        condition="outdoor",
    ),
    LocalInquiryRule(
        id="online-sales-check",
        title="통신판매업 신고 확인",
        graph_names=("통신판매업신고", "통신판매업"),
        default_department="통신판매 및 지역경제 업무 담당부서",
        reason="온라인 판매 계획이 있으면 통신판매업 신고 대상 여부를 확인해야 해요.",
        questions=(
            "온라인 주문이나 택배 판매가 통신판매업 신고 대상인가요?",
            "구매안전서비스 이용확인증 등 먼저 준비할 자료가 있나요?",
        ),
        condition="online",
    ),
    LocalInquiryRule(
        id="takeover-check",
        title="영업자 지위승계 확인",
        graph_names=("영업자 지위승계 신고", "기존 업소 행정처분 이력 확인"),
        default_department="식품위생 업무 담당부서",
        reason="기존 가게를 인수하면 지위승계와 행정처분 이력 확인이 필요할 수 있어요.",
        questions=(
            "기존 영업자의 지위승계 신고가 필요한 상황인가요?",
            "기존 업소 행정처분 이력은 어디에서 확인하나요?",
        ),
        condition="takeover",
    ),
)


class LocalGraphRagRetriever:
    """Read the checked-in HEOGAON graph package as a local GraphRAG source."""

    def __init__(self, root: Path | None = None) -> None:
        repo_root = root or Path(__file__).resolve().parents[3]
        self.graph_root = repo_root / "heogaon" / "graph"
        self.final_graph_root = self.graph_root / "output" / "final_graph"
        self.nodes_path = self.final_graph_root / "graph_nodes_high_precision.csv"
        self.edges_path = self.final_graph_root / "graph_edges_high_precision.csv"
        self.evidence_path = self.graph_root / "input" / "evidence" / "evidence_chunks_augmented.jsonl"
        self._edges: list[dict[str, str]] | None = None
        self._evidence_chunks: list[dict[str, Any]] | None = None

    @property
    def available(self) -> bool:
        return self.nodes_path.exists() and self.edges_path.exists()

    def retrieve(self, kind: str, case: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.available:
            return None
        if kind == "documents":
            documents = self.build_documents(case)
            return {"documents": documents, "source": "local_graph_rag"} if documents else None
        if kind == "inquiries":
            tasks = self.build_inquiry_tasks(case)
            return {"inquiryTasks": tasks, "source": "local_graph_rag"} if tasks else None
        if kind == "evidence":
            topic = str((extra or {}).get("topic") or "")
            evidence = self.search_evidence(case, topic)
            return {"evidence": evidence, "source": "local_graph_rag"} if evidence else None
        return None

    def build_documents(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        signals = self._signals(case)
        documents = []
        for rule in DOCUMENT_RULES:
            if not self._condition_applies(rule.condition, signals):
                continue
            related_edges = self._related_edges(rule.graph_names)
            prerequisite_edges = [
                edge
                for edge in related_edges
                if edge.get("predicate") in {"requires_prerequisite", "requires_document", "needs_check", "precedes"}
            ]
            prerequisites = self._object_names(prerequisite_edges, limit=4)
            evidence = self._evidence_from_edges(related_edges, limit=3)
            documents.append({
                "id": rule.id,
                "title": rule.title,
                "priority": rule.priority,
                "reason": rule.reason,
                "status": rule.status,
                "statutoryDeadline": rule.statutory_deadline,
                "perceivedDuration": rule.perceived_duration,
                "prerequisites": ", ".join(prerequisites) if prerequisites else "기본 신청 정보",
                "unlocks": rule.unlocks,
                "officialLinks": self._official_links(related_edges),
                "prepareInfo": prerequisites or self._fallback_prepare_info(rule),
                "steps": self._steps_for(rule, related_edges),
                "canPrepareBeforeInquiry": rule.can_prepare_before_inquiry,
                "evidence": evidence,
            })
        return sorted(documents, key=lambda item: item["priority"])

    def build_inquiry_tasks(self, case: dict[str, Any]) -> list[dict[str, Any]]:
        signals = self._signals(case)
        tasks = []
        for rule in INQUIRY_RULES:
            if not self._condition_applies(rule.condition, signals):
                continue
            related_edges = self._related_edges(rule.graph_names)
            department = self._department_for(rule.graph_names, rule.default_department)
            checks = self._object_names(
                [edge for edge in related_edges if edge.get("predicate") == "needs_check"],
                limit=3,
            )
            questions = list(rule.questions)
            questions.extend(f"{check}은 어떻게 확인하면 되나요?" for check in checks)
            tasks.append({
                "id": rule.id,
                "title": rule.title,
                "department": department,
                "phone": "tel:120",
                "onlineUrl": "https://www.epeople.go.kr/index.jsp",
                "visitHint": f"관할 구청 {department}",
                "reason": rule.reason,
                "status": "pending",
                "questions": self._dedupe(questions)[:4],
                "evidence": self._evidence_from_edges(related_edges, limit=2),
            })
        return tasks

    def search_evidence(self, case: dict[str, Any], topic: str) -> list[dict[str, str]]:
        query = " ".join(
            item
            for item in [
                topic,
                str(case.get("rawInput") or ""),
                " ".join(str(slot.get("value") or "") for slot in (case.get("slots") or {}).values() if isinstance(slot, dict)),
            ]
            if item
        )
        tokens = self._tokens(query)
        if not tokens:
            return []

        candidates: list[tuple[int, dict[str, str]]] = []
        for edge in self.seed_edges:
            text = " ".join(str(edge.get(key) or "") for key in ("subject_name", "object_name", "condition_text", "evidence_text", "title"))
            score = self._score(tokens, text)
            if score:
                candidates.append((score + 2, self._evidence_item_from_edge(edge)))

        for chunk in self.evidence_chunks:
            text = " ".join(str(chunk.get(key) or "") for key in ("title", "section_path", "text", "source_record_id"))
            score = self._score(tokens, text)
            if score:
                candidates.append((score, {
                    "title": str(chunk.get("title") or chunk.get("source_record_id") or "근거"),
                    "url": self._safe_url(str(chunk.get("source_url") or "")),
                    "excerpt": self._shorten(str(chunk.get("text") or "")),
                }))

        results = []
        seen = set()
        for _, item in sorted(candidates, key=lambda candidate: candidate[0], reverse=True):
            key = (item["title"], item["excerpt"])
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
            if len(results) >= 5:
                break
        return results

    @property
    def edges(self) -> list[dict[str, str]]:
        if self._edges is None:
            with self.edges_path.open("r", encoding="utf-8-sig", newline="") as file:
                self._edges = [dict(row) for row in csv.DictReader(file)]
        return self._edges

    @property
    def seed_edges(self) -> list[dict[str, str]]:
        return [edge for edge in self.edges if edge.get("edge_source") == "source_backed_seed"]

    @property
    def evidence_chunks(self) -> list[dict[str, Any]]:
        if self._evidence_chunks is None:
            chunks: list[dict[str, Any]] = []
            if self.evidence_path.exists():
                with self.evidence_path.open("r", encoding="utf-8") as file:
                    for line in file:
                        try:
                            chunks.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            self._evidence_chunks = chunks
        return self._evidence_chunks

    def _related_edges(self, graph_names: tuple[str, ...]) -> list[dict[str, str]]:
        names = {self._normalize_name(name) for name in graph_names}
        return [
            edge
            for edge in self.seed_edges
            if self._normalize_name(edge.get("subject_name", "")) in names
            or self._normalize_name(edge.get("object_name", "")) in names
        ]

    def _department_for(self, graph_names: tuple[str, ...], default: str) -> str:
        names = {self._normalize_name(name) for name in graph_names}
        for edge in self.seed_edges:
            if edge.get("predicate") != "handled_by":
                continue
            if self._normalize_name(edge.get("subject_name", "")) in names:
                department = edge.get("object_name", "").strip()
                if department:
                    return f"{department} 담당부서"
        return default

    @staticmethod
    def _signals(case: dict[str, Any]) -> dict[str, Any]:
        slots = case.get("slots") or {}

        def value(field: str) -> Any:
            slot = slots.get(field)
            return slot.get("value") if isinstance(slot, dict) else None

        raw = str(case.get("rawInput") or "")
        conditions = value("condition_screening")
        if not isinstance(conditions, list):
            conditions = [conditions] if conditions else []
        return {
            "raw": raw,
            "conditions": set(str(item) for item in conditions),
            "on_site": value("on_site_consumption") is True or bool(re.search(r"매장|홀|객석|좌석|먹고", raw)),
            "liquor": value("liquor_sales") is True or bool(re.search(r"주류|술|맥주|와인|소주", raw)),
            "takeover": value("takeover_type") == "transfer" or bool(re.search(r"인수|양도|승계", raw)),
            "signage": "signage_planned" in conditions or bool(re.search(r"간판|옥외광고", raw)),
            "outdoor": "outdoor_space_planned" in conditions or bool(re.search(r"테라스|외부 ?테이블|보도|도로점용|입간판", raw)),
            "lpg": "lpg_use" in conditions or bool(re.search(r"LPG|가스|화구", raw, flags=re.IGNORECASE)),
            "online": "online_sales_planned" in conditions or bool(re.search(r"온라인|택배|배달앱|통신판매", raw)),
        }

    @staticmethod
    def _condition_applies(condition: str, signals: dict[str, Any]) -> bool:
        if condition == "always":
            return True
        if condition == "fire":
            return bool(signals.get("on_site") or signals.get("lpg"))
        return bool(signals.get(condition))

    @staticmethod
    def _object_names(edges: list[dict[str, str]], limit: int) -> list[str]:
        names = []
        for edge in edges:
            name = (edge.get("object_name") or "").strip()
            if name and name not in names:
                names.append(name)
            if len(names) >= limit:
                break
        return names

    @classmethod
    def _evidence_from_edges(cls, edges: list[dict[str, str]], limit: int) -> list[str]:
        evidence = []
        for edge in edges:
            for key in ("condition_text", "evidence_text"):
                text = cls._shorten(edge.get(key) or "", max_length=180)
                if text and text not in evidence:
                    evidence.append(text)
                if len(evidence) >= limit:
                    return evidence
        return evidence

    @classmethod
    def _steps_for(cls, rule: LocalDocumentRule, edges: list[dict[str, str]]) -> list[str]:
        steps = []
        for edge in edges:
            if edge.get("predicate") == "precedes" and edge.get("subject_name"):
                steps.append(f"{edge['subject_name']} 후 {edge.get('object_name', '다음 단계')}로 진행")
        if steps:
            return cls._dedupe(steps)[:3]
        return [
            f"{rule.title} 대상 여부 확인",
            "공식 안내와 관할 부서 기준 확인",
            "필요 서류 준비 상태 표시",
        ]

    @staticmethod
    def _fallback_prepare_info(rule: LocalDocumentRule) -> list[str]:
        mapping = {
            "building-ledger": ["정확한 주소", "층수", "위반건축물 여부"],
            "health-check": ["창업자 및 종업원 인적사항", "보건소 또는 지정 의료기관"],
            "hygiene-education": ["영업자 정보", "업종별 교육기관"],
            "food-business-report": ["영업신고서", "건강진단결과서", "위생교육 수료증"],
            "business-registration": ["영업신고증", "임대차계약서", "사업자 인적사항"],
        }
        return mapping.get(rule.id, ["신청 정보", "관할 부서 확인"])

    @classmethod
    def _official_links(cls, edges: list[dict[str, str]]) -> list[dict[str, str]]:
        links = []
        for edge in edges:
            url = cls._safe_url(edge.get("source_url") or "")
            if not url:
                continue
            label = "정부24" if "gov.kr" in url else "생활법령" if "easylaw.go.kr" in url else "공식 근거"
            item = {"label": label, "url": url}
            if item not in links:
                links.append(item)
            if len(links) >= 2:
                break
        return links or [{"label": "정부24에서 확인", "url": "https://www.gov.kr"}]

    @classmethod
    def _evidence_item_from_edge(cls, edge: dict[str, str]) -> dict[str, str]:
        return {
            "title": edge.get("title") or edge.get("subject_name") or "근거",
            "url": cls._safe_url(edge.get("source_url") or ""),
            "excerpt": cls._shorten(edge.get("evidence_text") or edge.get("condition_text") or ""),
        }

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token.lower() for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", text)}

    @staticmethod
    def _score(tokens: set[str], text: str) -> int:
        lower_text = text.lower()
        return sum(1 for token in tokens if token in lower_text)

    @staticmethod
    def _normalize_name(value: str) -> str:
        return re.sub(r"\s+", "", value or "")

    @staticmethod
    def _dedupe(values: list[str] | tuple[str, ...]) -> list[str]:
        items = []
        for value in values:
            text = str(value).strip()
            if text and text not in items:
                items.append(text)
        return items

    @staticmethod
    def _safe_url(url: str) -> str:
        url = url.strip()
        if not url.startswith(("http://", "https://")) or "REDACTED" in url:
            return ""
        return url

    @staticmethod
    def _shorten(text: str, max_length: int = 220) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= max_length:
            return compact
        return compact[: max_length - 1].rstrip() + "…"


local_graph_rag = LocalGraphRagRetriever()
