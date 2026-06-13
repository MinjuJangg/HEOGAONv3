from __future__ import annotations

import json
import re
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

from app.core.config import Settings, settings
from app.data.catalog import FLOW_SCHEMA_VERSION
from app.services.local_graph_rag import LocalGraphRagRetriever, local_graph_rag
from app.services.output_guard import clean_payload, mask_sensitive_text


class GraphRagService:
    """Thin boundary for permit documents, departments, evidence, and questions.

    The app keeps the state machine local. GraphRAG only expands domain data.
    If the remote service is not configured or returns an unusable shape, callers
    fall back to the local MVP catalog.
    """

    def __init__(
        self,
        config: Settings = settings,
        local_graph: LocalGraphRagRetriever = local_graph_rag,
    ) -> None:
        self.config = config
        self.local_graph = local_graph

    @property
    def available(self) -> bool:
        return self.config.graph_rag_available or self.local_graph.available

    def build_documents(self, case: dict[str, Any]) -> list[dict[str, Any]] | None:
        result = self._retrieve("documents", case)
        items = self._extract_list(result, "documents")
        documents = [
            document
            for index, item in enumerate(items)
            if (document := self._normalize_document(item, index))
        ]
        if not documents:
            return None
        self._mark_source(case, "documentsSource", "graph_rag")
        return sorted(documents, key=lambda item: item["priority"])

    def build_inquiry_tasks(self, case: dict[str, Any]) -> list[dict[str, Any]] | None:
        result = self._retrieve("inquiries", case)
        items = self._extract_list(result, "inquiryTasks", "tasks", "inquiries")
        tasks = [
            task
            for index, item in enumerate(items)
            if (task := self._normalize_inquiry_task(item, index))
        ]
        if not tasks:
            return None
        self._mark_source(case, "inquirySource", "graph_rag")
        return tasks

    def build_question_plan(self, case: dict[str, Any]) -> list[dict[str, Any]] | None:
        result = self._retrieve("questions", case)
        items = self._extract_list(result, "questions", "questionPlan")
        questions = [
            question
            for item in items
            if (question := self._normalize_question(item))
        ]
        if not questions:
            return None
        self._mark_source(case, "questionSource", "graph_rag")
        return questions

    def retrieve_evidence(self, case: dict[str, Any], topic: str) -> list[dict[str, Any]]:
        result = self._retrieve("evidence", case, extra={"topic": topic})
        items = self._extract_list(result, "evidence", "sources", "items")
        evidence = [
            item
            for raw_item in items
            if (item := self._normalize_evidence(raw_item))
        ]
        if evidence:
            self._mark_source(case, "evidenceSource", "graph_rag")
        return evidence

    def _retrieve(self, kind: str, case: dict[str, Any], extra: dict[str, Any] | None = None) -> Any:
        payload = {
            "kind": kind,
            "schemaVersion": FLOW_SCHEMA_VERSION,
            "case": self._case_payload(case),
        }
        if extra:
            payload.update(extra)

        remote_result = None
        if self.config.graph_rag_available:
            remote_result = self._retrieve_remote(kind, case, payload)
            if self._result_has_items(kind, remote_result):
                case.setdefault("ai", {})["graphRagBackend"] = "remote"
                return remote_result

        local_result = self.local_graph.retrieve(kind, case, extra=extra)
        if self._result_has_items(kind, local_result):
            case.setdefault("ai", {})["graphRagBackend"] = "local_files"
            return local_result

        return remote_result

    def _retrieve_remote(self, kind: str, case: dict[str, Any], payload: dict[str, Any]) -> Any:
        try:
            endpoint = f"{self.config.graph_rag_base_url}/retrieve"
            body = json.dumps(clean_payload(payload), ensure_ascii=False).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if self.config.graph_rag_api_key:
                headers["Authorization"] = f"Bearer {self.config.graph_rag_api_key}"

            http_request = request.Request(endpoint, data=body, headers=headers, method="POST")
            with request.urlopen(http_request, timeout=self.config.graph_rag_timeout_seconds) as response:
                data = response.read().decode("utf-8")
            return json.loads(data)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            self._warn(case, f"GraphRAG {kind} fallback: {exc.__class__.__name__}")
            return None

    @classmethod
    def _result_has_items(cls, kind: str, result: Any) -> bool:
        keys_by_kind = {
            "documents": ("documents",),
            "inquiries": ("inquiryTasks", "tasks", "inquiries"),
            "questions": ("questions", "questionPlan"),
            "evidence": ("evidence", "sources", "items"),
        }
        return bool(cls._extract_list(result, *keys_by_kind.get(kind, ("items",))))

    @staticmethod
    def _case_payload(case: dict[str, Any]) -> dict[str, Any]:
        return {
            "caseId": case.get("caseId"),
            "rawInput": mask_sensitive_text(case.get("rawInput", "")),
            "slots": case.get("slots", {}),
            "candidatePermits": case.get("candidatePermits", []),
            "answers": case.get("answers", []),
            "documents": case.get("documents", []),
            "inquiryTasks": case.get("inquiryTasks", []),
        }

    @staticmethod
    def _extract_list(value: Any, *keys: str) -> list[Any]:
        if isinstance(value, list):
            return value
        if not isinstance(value, dict):
            return []
        for key in keys:
            items = value.get(key)
            if isinstance(items, list):
                return items
        data = value.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in keys:
                items = data.get(key)
                if isinstance(items, list):
                    return items
        return []

    @classmethod
    def _normalize_document(cls, item: Any, index: int) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        title = cls._string(item.get("title") or item.get("name"))
        if not title:
            return None
        document_id = cls._string(item.get("id")) or cls._slug(title)
        return {
            "id": document_id,
            "title": title,
            "priority": cls._int(item.get("priority"), index + 1),
            "reason": cls._string(item.get("reason")) or "준비 필요 여부를 확인했어요.",
            "status": cls._status(item.get("status"), "not_started"),
            "statutoryDeadline": cls._string(item.get("statutoryDeadline") or item.get("legalDeadline")),
            "perceivedDuration": cls._string(item.get("perceivedDuration") or item.get("estimatedDuration") or item.get("duration")) or "확인 필요",
            "prerequisites": cls._string(item.get("prerequisites")) or "기본 신청 정보",
            "unlocks": cls._string(item.get("unlocks")) or "다음 인허가 절차",
            "officialLinks": cls._links(item.get("officialLinks") or item.get("links")),
            "prepareInfo": cls._strings(item.get("prepareInfo") or item.get("requiredInfo")) or ["신청 정보"],
            "steps": cls._strings(item.get("steps")) or ["필요 항목 확인", "공식 사이트 확인", "완료 표시"],
            "canPrepareBeforeInquiry": cls._bool(item.get("canPrepareBeforeInquiry"), item.get("status") != "blocked"),
            "evidence": cls._strings(item.get("evidence")),
        }

    @classmethod
    def _normalize_inquiry_task(cls, item: Any, index: int) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        title = cls._string(item.get("title") or item.get("name"))
        if not title:
            return None
        return {
            "id": cls._string(item.get("id")) or f"inquiry-{index + 1}-{cls._slug(title)}",
            "title": title,
            "department": cls._string(item.get("department")) or "담당 부서 확인 필요",
            "phone": cls._phone(item.get("phone")),
            "onlineUrl": cls._string(item.get("onlineUrl") or item.get("url")) or "https://www.epeople.go.kr/index.jsp",
            "visitHint": cls._string(item.get("visitHint")) or "관할 구청 민원 창구",
            "reason": cls._string(item.get("reason")) or "담당 부서 확인이 필요해요.",
            "status": cls._status(item.get("status"), "pending"),
            "questions": cls._strings(item.get("questions")) or [f"{title}은 어떤 기준으로 확인하면 되나요?"],
            "evidence": cls._strings(item.get("evidence")),
        }

    @classmethod
    def _normalize_question(cls, item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        field = cls._string(item.get("field") or item.get("fieldKey"))
        question = cls._string(item.get("question") or item.get("title"))
        if not field or not question:
            return None
        input_mode = cls._string(item.get("inputMode") or item.get("type")) or "free_text"
        if input_mode not in {"free_text", "single_select", "multi_select"}:
            input_mode = "free_text"

        normalized = {
            "field": field,
            "label": cls._string(item.get("label")) or field,
            "question": question,
            "why": cls._string(item.get("why") or item.get("description")),
            "inputMode": input_mode,
            "required": cls._bool(item.get("required"), True),
        }
        options = cls._options(item.get("options"))
        if options:
            normalized["options"] = options
        return normalized

    @classmethod
    def _normalize_evidence(cls, item: Any) -> dict[str, Any] | None:
        if isinstance(item, str):
            return {"title": item, "url": "", "excerpt": item}
        if not isinstance(item, dict):
            return None
        title = cls._string(item.get("title") or item.get("source") or item.get("label"))
        excerpt = cls._string(item.get("excerpt") or item.get("text"))
        if not title and not excerpt:
            return None
        return {
            "title": title or "근거",
            "url": cls._string(item.get("url")),
            "excerpt": excerpt,
        }

    @classmethod
    def _links(cls, value: Any) -> list[dict[str, str]]:
        links = []
        if isinstance(value, dict):
            value = [value]
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    links.append({"label": "공식 사이트", "url": item})
                elif isinstance(item, dict):
                    url = cls._string(item.get("url"))
                    if url:
                        links.append({
                            "label": cls._string(item.get("label") or item.get("title")) or "공식 사이트",
                            "url": url,
                        })
        return links or [{"label": "정부24에서 확인", "url": "https://www.gov.kr"}]

    @classmethod
    def _options(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        options = []
        for item in value:
            if isinstance(item, str):
                options.append({"id": cls._slug(item), "title": item})
            elif isinstance(item, dict):
                option_id = cls._string(item.get("id") or item.get("value") or item.get("title"))
                title = cls._string(item.get("title") or item.get("label") or item.get("value"))
                if option_id and title:
                    option = {"id": option_id, "title": title}
                    if "exclusive" in item:
                        option["exclusive"] = bool(item["exclusive"])
                    options.append(option)
        return options

    @staticmethod
    def _strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @staticmethod
    def _string(value: Any) -> str:
        return str(value).strip() if value not in (None, "") else ""

    @staticmethod
    def _int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on", "가능"}
        return bool(value)

    @staticmethod
    def _status(value: Any, default: str) -> str:
        status = str(value or default).strip()
        allowed = {"not_started", "needs_check", "blocked", "completed", "pending", "resolved"}
        return status if status in allowed else default

    @staticmethod
    def _phone(value: Any) -> str:
        phone = str(value or "").strip()
        if not phone:
            return "tel:120"
        if phone.startswith("tel:"):
            return phone
        digits = re.sub(r"[^0-9+]", "", phone)
        return f"tel:{digits}" if digits else "tel:120"

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", value).strip("-").lower()
        return slug or "item"

    @staticmethod
    def _mark_source(case: dict[str, Any], key: str, source: str) -> None:
        case.setdefault("ai", {})[key] = source

    @staticmethod
    def _warn(case: dict[str, Any], message: str) -> None:
        warnings = case.setdefault("ai", {}).setdefault("warnings", [])
        if message not in warnings:
            warnings.append(message)


graph_rag_service = GraphRagService()
