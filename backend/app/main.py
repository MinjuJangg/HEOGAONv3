import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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


def _building_params(address: dict[str, Any] | None) -> dict[str, str] | None:
    if not address:
        return None
    bcode = str(address.get("b_code") or "")
    main = str(address.get("main_address_no") or "").strip()
    if len(bcode) < 10 or not main:
        return None
    return {
        "sigunguCd": bcode[:5],
        "bjdongCd": bcode[5:10],
        "platGbCd": "1" if address.get("mountain_yn") == "Y" else "0",
        "bun": main.zfill(4),
        "ji": str(address.get("sub_address_no") or "0").strip().zfill(4),
    }


def _building_params_from_juso(item: dict[str, Any]) -> dict[str, str] | None:
    adm_cd = str(item.get("admCd") or "")
    main = str(item.get("lnbrMnnm") or "").strip()
    if len(adm_cd) < 10 or not main:
        return None
    return {
        "sigunguCd": adm_cd[:5],
        "bjdongCd": adm_cd[5:10],
        "platGbCd": "1" if str(item.get("mtYn") or "0") == "1" else "0",
        "bun": main.zfill(4),
        "ji": str(item.get("lnbrSlno") or "0").strip().zfill(4),
    }


def _search_kakao_address(keyword: str, api_key: str) -> list[dict[str, Any]]:
    url = f"https://dapi.kakao.com/v2/local/search/address.json?{urlencode({'query': keyword, 'size': 10})}"
    request = Request(url, headers={"Authorization": f"KakaoAK {api_key}"})
    with urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))

    results = []
    for item in payload.get("documents") or []:
        address = item.get("address") or {}
        road = item.get("road_address") or {}
        label = road.get("address_name") or item.get("address_name") or address.get("address_name") or ""
        if not label:
            continue
        results.append(
            {
                "label": label,
                "roadAddress": road.get("address_name") or "",
                "jibunAddress": address.get("address_name") or item.get("address_name") or "",
                "buildingName": road.get("building_name") or "",
                "zoneNo": road.get("zone_no") or "",
                "buildingParams": _building_params(address),
            }
        )
    return results


def _search_juso_address(keyword: str, api_key: str) -> list[dict[str, Any]]:
    url = "https://business.juso.go.kr/addrlink/addrLinkApi.do?" + urlencode(
        {
            "confmKey": api_key,
            "currentPage": "1",
            "countPerPage": "10",
            "keyword": keyword,
            "resultType": "json",
        }
    )
    with urlopen(url, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))

    common = (payload.get("results") or {}).get("common") or {}
    if str(common.get("errorCode") or "0") != "0":
        raise RuntimeError(common.get("errorMessage") or common.get("errorCode") or "JUSO address search failed")

    results = []
    for item in (payload.get("results") or {}).get("juso") or []:
        label = item.get("roadAddr") or item.get("jibunAddr") or ""
        if not label:
            continue
        results.append(
            {
                "label": label,
                "roadAddress": item.get("roadAddr") or "",
                "jibunAddress": item.get("jibunAddr") or "",
                "buildingName": item.get("bdNm") or "",
                "zoneNo": item.get("zipNo") or "",
                "buildingParams": _building_params_from_juso(item),
            }
        )
    return results


@app.get("/api/address/search")
def address_search_endpoint(query: str):
    keyword = query.strip()
    if not keyword:
        return {"results": []}

    errors = []

    kakao_key = os.getenv("KAKAO_REST_API_KEY") or os.getenv("KAKAO_API_KEY")
    if kakao_key:
        try:
            results = _search_kakao_address(keyword, kakao_key)
            if results:
                return {"results": results, "source": "kakao"}
        except Exception as exc:
            errors.append(f"kakao: {exc}")
    else:
        errors.append("kakao: missing key")

    juso_key = os.getenv("JUSO_API_KEY")
    if juso_key:
        try:
            return {"results": _search_juso_address(keyword, juso_key), "source": "juso"}
        except Exception as exc:
            errors.append(f"juso: {exc}")
    else:
        errors.append("juso: missing key")

    raise HTTPException(status_code=502, detail="; ".join(errors))


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
