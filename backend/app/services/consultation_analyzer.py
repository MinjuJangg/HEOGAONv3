from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.integrations.llm_client import LlmClient, llm_client
from app.schemas.ai import ConsultationAnalysis
from app.services.output_guard import clean_text
from app.services.slot_utils import now_iso


class ConsultationAnalyzer:
    def __init__(self, llm: LlmClient = llm_client) -> None:
        self.llm = llm

    def analyze(self, case: dict[str, Any], answer_text: str) -> None:
        answer_text = clean_text(answer_text.strip())
        analysis = self._ai_analysis(case, answer_text) or self._rule_analysis(case, answer_text)

        for task in case["inquiryTasks"]:
            if task["status"] == "pending":
                task["status"] = "resolved"
                break

        new_tasks = [self._inquiry_task_from_candidate(candidate) for candidate in analysis.new_inquiry_candidates]
        existing_ids = {task["id"] for task in case["inquiryTasks"]}
        case["inquiryTasks"].extend(task for task in new_tasks if task["id"] not in existing_ids)
        case["answers"].append({
            "id": f"answer_{uuid4().hex[:10]}",
            "field": "consultation_answer",
            "question": "문의 답변",
            "answer": answer_text,
            "createdAt": now_iso(),
        })
        case["lastAnswerAnalysis"] = {
            "answerSummary": analysis.summary or "받은 답변을 저장했어요.",
            "resolvedItems": analysis.resolved_items,
            "newMissingFields": analysis.new_missing_fields,
            "newInquiryTasks": new_tasks,
            "nextAction": analysis.next_action,
        }
        case["ai"]["consultationSource"] = "llm" if analysis.confidence > 0.0 and self.llm.available else "rules"
        case["machineState"] = "ANSWER_REVIEW"

    def _ai_analysis(self, case: dict[str, Any], answer_text: str) -> ConsultationAnalysis | None:
        result = self.llm.generate_json(
            system_prompt=(
                "너는 담당부서 문의 답변을 요약하는 FollowupAgent다. "
                "상태 변경은 후보만 제시하고 허가 가능 여부를 단정하지 않는다. "
                "JSON만 반환한다."
            ),
            user_payload={
                "answerText": answer_text,
                "slots": case.get("slots", {}),
                "openInquiryTasks": case.get("inquiryTasks", []),
                "schema": {
                    "summary": "string",
                    "resolved_items": "string[]",
                    "new_missing_fields": "string[]",
                    "new_inquiry_candidates": [{"title": "string", "department": "string", "reason": "string"}],
                    "next_action": "ask_followup|inquiry|documents|dashboard",
                    "confidence": "number",
                },
            },
        )
        if not result:
            return None
        try:
            return ConsultationAnalysis.model_validate(result)
        except ValidationError:
            return None

    def _rule_analysis(self, case: dict[str, Any], answer_text: str) -> ConsultationAnalysis:
        resolved = []
        new_missing = []
        new_candidates = []
        next_action = "dashboard"

        if re.search(r"건축물|용도", answer_text):
            resolved.append("food_business_type")
        if re.search(r"간판|옥외광고", answer_text) and not any(task["id"] == "signage-check" for task in case["inquiryTasks"]):
            new_candidates.append({
                "title": "간판 신고 확인",
                "department": "옥외광고물 담당",
                "reason": "간판 확인이 새로 필요해요.",
            })
            next_action = "inquiry"
        if re.search(r"서류|준비|접수|신고", answer_text) and next_action == "dashboard":
            next_action = "documents"

        return ConsultationAnalysis(
            summary=answer_text or "받은 답변을 저장했어요.",
            resolved_items=resolved,
            new_missing_fields=new_missing,
            new_inquiry_candidates=new_candidates,
            next_action=next_action,
            confidence=0.0,
        )

    @staticmethod
    def _inquiry_task_from_candidate(candidate: Any) -> dict[str, Any]:
        def read(name: str, default: str = "") -> str:
            if hasattr(candidate, name):
                value = getattr(candidate, name)
                return str(value or default)
            if isinstance(candidate, dict):
                return str(candidate.get(name) or default)
            return default

        title = read("title", "추가 문의")
        department = read("department", "담당 부서 확인 필요")
        reason = read("reason")
        is_signage = "간판" in title or "광고" in department
        return {
            "id": "signage-check" if is_signage else f"followup-{uuid4().hex[:8]}",
            "title": title,
            "department": department,
            "phone": "tel:120",
            "onlineUrl": "https://www.epeople.go.kr/index.jsp",
            "visitHint": "구청 담당 창구",
            "reason": reason,
            "status": "pending",
            "questions": [f"{title}에 필요한 자료가 무엇인가요?"],
        }


consultation_analyzer = ConsultationAnalyzer()
