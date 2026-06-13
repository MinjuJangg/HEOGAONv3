from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import settings
from app.flow import CASES, apply_turn, create_case, envelope
from app.services.flow_service import FlowInputError


class TurnRequest(BaseModel):
    input: dict[str, Any]
    clientState: dict[str, Any] | None = None


app = FastAPI(title="Heogaon Flow V2", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True, "service": "heogaon-flow-v2"}


@app.post("/api/cases")
def create_case_endpoint(request: TurnRequest):
    input_payload = request.input
    if input_payload.get("type") != "natural_language":
        raise HTTPException(status_code=400, detail="첫 요청은 natural_language여야 합니다.")
    case = create_case(input_payload.get("text") or "")
    return envelope(case)


@app.post("/api/cases/{case_id}/turns")
def turn_endpoint(case_id: str, request: TurnRequest):
    if case_id not in CASES:
        raise HTTPException(status_code=404, detail="case를 찾을 수 없습니다.")
    try:
        case = apply_turn(case_id, request.input)
    except FlowInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return envelope(case)


@app.get("/api/cases/{case_id}")
def get_case_endpoint(case_id: str):
    case = CASES.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case를 찾을 수 없습니다.")
    return envelope(case)
