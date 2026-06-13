from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from precheck_common import (
    compact_address_key,
    extract_district,
    extract_neighborhood,
    first_value,
    normalize_space,
    seoul_sigungu_code,
)


ROOT = Path(__file__).resolve().parents[2]


def resolve_default_index() -> Path:
    env_value = (
        os.getenv("SEOUL_LOCALDATA_INDEX")
        or os.getenv("HEOGAON_LOCALDATA_INDEX")
        or os.getenv("LOCALDATA_SQLITE_PATH")
    )
    if env_value:
        return Path(env_value).expanduser()

    candidates = [
        ROOT / "data" / "processed" / "precheck" / "seoul_localdata.sqlite",
        Path.home() / "Desktop" / "New project 2" / "data" / "processed" / "precheck" / "seoul_localdata.sqlite",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DEFAULT_INDEX = resolve_default_index()
DEFAULT_CACHE = ROOT / "data" / "cache" / "precheck"

JUSO_URL = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
BUILDINGHUB_BASE_URL = "https://apis.data.go.kr/1613000/BldRgstHubService"
BUILDING_OPERATIONS = {
    "title": "getBrTitleInfo",
    "floor": "getBrFlrOulnInfo",
    "recap_title": "getBrRecapTitleInfo",
    "unit": "getBrExposPubuseAreaInfo",
    "land_zone": "getBrJijiguInfo",
}


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def env_or_fail(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"Missing {name}. Put it in the environment or .env before calling this command.")
    return value


def http_get_json(url: str, params: dict[str, Any]) -> dict:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    safe_url = url.split("?", 1)[0]
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "HEOGAON-precheck/0.1",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw_body = response.read()
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} from {safe_url}: {body[:300]}") from error

    body = raw_body.decode("utf-8", errors="replace")
    if not body.strip():
        raise RuntimeError(f"Empty response from {safe_url}. Check the service-specific key and the data.go.kr Swagger URL.")
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Non-JSON response from {safe_url}: {body[:300]}") from error


def normalize_address_with_juso(address: str, cache_dir: Path = DEFAULT_CACHE) -> dict:
    key = env_or_fail("JUSO_API_KEY")
    cache_path = cache_dir / "juso" / f"{stable_hash(key + ':' + address)}.json"
    if cache_path.exists():
        return read_json(cache_path)
    payload = http_get_json(
        JUSO_URL,
        {
            "confmKey": key,
            "currentPage": 1,
            "countPerPage": 10,
            "keyword": address,
            "resultType": "json",
        },
    )
    common = (payload.get("results") or {}).get("common") or {}
    if common.get("errorCode") in ("0", "E0000", None):
        write_json(cache_path, payload)
    return payload


def best_juso_result(payload: dict) -> dict:
    results = (((payload.get("results") or {}).get("juso")) or [])
    if not results:
        return {}
    return results[0]


def address_to_building_params(address: str, normalized: dict | None = None) -> dict:
    item = best_juso_result(normalized or {})
    adm_cd = str(item.get("admCd") or "")
    lot_main = str(item.get("lnbrMnnm") or "").zfill(4)
    lot_sub = str(item.get("lnbrSlno") or "").zfill(4)
    plat_gb = "1" if str(item.get("mtYn") or "0") == "1" else "0"
    if adm_cd:
        return {
            "sigunguCd": adm_cd[:5],
            "bjdongCd": adm_cd[5:],
            "platGbCd": plat_gb,
            "bun": lot_main,
            "ji": lot_sub,
            "roadAddr": item.get("roadAddr") or "",
            "jibunAddr": item.get("jibunAddr") or "",
            "bdMgtSn": item.get("bdMgtSn") or "",
        }

    district = extract_district(address)
    return {
        "sigunguCd": seoul_sigungu_code(address, district),
        "bjdongCd": "",
        "platGbCd": "",
        "bun": "",
        "ji": "",
        "roadAddr": "",
        "jibunAddr": "",
        "bdMgtSn": "",
    }


def fetch_buildinghub(operation: str, params: dict, cache_dir: Path = DEFAULT_CACHE) -> dict:
    service_key = env_or_fail("DATA_GO_KR_SERVICE_KEY")
    operation_name = BUILDING_OPERATIONS[operation]
    request_params = {
        "serviceKey": service_key,
        "_type": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "sigunguCd": params.get("sigunguCd"),
        "bjdongCd": params.get("bjdongCd"),
        "platGbCd": params.get("platGbCd"),
        "bun": params.get("bun"),
        "ji": params.get("ji"),
    }
    cache_key = stable_hash(operation + json.dumps(request_params, sort_keys=True, ensure_ascii=False))
    cache_path = cache_dir / "buildinghub" / operation / f"{cache_key}.json"
    if cache_path.exists():
        return read_json(cache_path)
    payload = http_get_json(f"{BUILDINGHUB_BASE_URL}/{operation_name}", request_params)
    write_json(cache_path, payload)
    return payload


def response_items(payload: dict) -> list[dict]:
    body = (payload.get("response") or {}).get("body") or {}
    items = (body.get("items") or {}).get("item") or []
    if isinstance(items, dict):
        return [items]
    return [item for item in items if isinstance(item, dict)]


def build_building_profile(address: str, offline_params: dict | None = None) -> dict:
    juso_payload = normalize_address_with_juso(address)
    params = address_to_building_params(address, juso_payload)
    if offline_params:
        params.update({k: v for k, v in offline_params.items() if v})
    if not all(params.get(key) for key in ["sigunguCd", "bjdongCd", "platGbCd", "bun", "ji"]):
        return {
            "status": "needs_address_normalization",
            "address": address,
            "normalized": best_juso_result(juso_payload),
            "buildingParams": params,
        }

    title_payload = fetch_buildinghub("title", params)
    floor_payload = fetch_buildinghub("floor", params)
    unit_payload = fetch_buildinghub("unit", params)
    land_zone_payload = fetch_buildinghub("land_zone", params)
    titles = response_items(title_payload)
    floors = response_items(floor_payload)
    units = response_items(unit_payload)
    zones = response_items(land_zone_payload)
    return {
        "status": "ok",
        "address": address,
        "normalized": best_juso_result(juso_payload),
        "buildingParams": params,
        "summary": summarize_building_records(titles, floors, units, zones),
        "records": {
            "title": titles,
            "floor": floors,
            "unit": units,
            "landZone": zones,
        },
    }


def summarize_building_records(titles: list[dict], floors: list[dict], units: list[dict], zones: list[dict]) -> dict:
    title = titles[0] if titles else {}
    floor_uses = sorted({str(item.get("mainPurpsCdNm") or item.get("etcPurps") or "").strip() for item in floors if item})
    unit_uses = sorted({str(item.get("mainPurpsCdNm") or item.get("etcPurps") or "").strip() for item in units if item})
    return {
        "mainPurpsCd": title.get("mainPurpsCd"),
        "mainPurpsCdNm": title.get("mainPurpsCdNm"),
        "etcPurps": title.get("etcPurps"),
        "totArea": title.get("totArea"),
        "vlRatEstmTotArea": title.get("vlRatEstmTotArea"),
        "grndFlrCnt": title.get("grndFlrCnt"),
        "ugrndFlrCnt": title.get("ugrndFlrCnt"),
        "useAprDay": title.get("useAprDay"),
        "floorUses": floor_uses,
        "unitUses": unit_uses,
        "landZones": sorted({str(item.get("jijiguCdNm") or item.get("etcJijigu") or "").strip() for item in zones if item}),
    }


def address_match_keys(address: str) -> list[str]:
    text = normalize_space(address)
    text = text.replace("서울시", "서울특별시")
    text = text.split(",", 1)[0]
    text = text.split("，", 1)[0]
    text = " ".join(part for part in text.split() if part)
    keys = [compact_address_key(text)]

    road_match = None
    for suffix in ("대로", "로", "길"):
        pattern = rf"(.+?[가-힣0-9]{suffix}\s*\d+(?:-\d+)?)"
        road_match = road_match or re.search(pattern, text)
    if road_match:
        keys.append(compact_address_key(road_match.group(1)))

    lot_match = re.search(r"(.+?[가-힣]+동\s*\d+(?:-\d+)?)", text)
    if lot_match:
        keys.append(compact_address_key(lot_match.group(1)))

    result: list[str] = []
    for key in keys:
        if key and len(key) >= 5 and key not in result:
            result.append(key)
    return result


def query_past_businesses(index_path: Path, address: str, limit: int = 30, business_type: str = "") -> dict:
    if not index_path.exists():
        return {"status": "missing_index", "index": str(index_path), "matches": []}
    keys = address_match_keys(address)
    if not keys:
        return {"status": "empty_address", "matches": []}

    match_clauses: list[str] = []
    where_params: list[Any] = []
    order_params: list[Any] = []
    exact_order_clauses: list[str] = []
    for key in keys:
        like = f"%{key}%"
        match_clauses.append("((road_key <> '' AND road_key LIKE ?) OR (lot_key <> '' AND lot_key LIKE ?))")
        where_params.extend([like, like])
        exact_order_clauses.append("(CASE WHEN road_key = ? OR lot_key = ? THEN 0 ELSE 1 END)")
        order_params.extend([key, key])

    where = "(" + " OR ".join(match_clauses) + ")"
    district = extract_district(address)
    neighborhood = extract_neighborhood(address)
    if district:
        where += " AND district = ?"
        where_params.append(district)
    if neighborhood:
        where += " AND (neighborhood = ? OR road_address LIKE ? OR lot_address LIKE ?)"
        where_params.extend([neighborhood, f"%{neighborhood}%", f"%{neighborhood}%"])
    if business_type:
        where += " AND canonical_business_type = ?"
        where_params.append(business_type)
    params = where_params + order_params + [limit]
    conn = sqlite3.connect(index_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
        SELECT canonical_business_type, license_no, license_date, status, detail_status, close_date,
               business_name, subtype, area_m2, road_address, lot_address, district, neighborhood, source_file
        FROM business_place
        WHERE {where}
        ORDER BY
          {" + ".join(exact_order_clauses)},
          CASE WHEN status LIKE '%영업%' OR detail_status LIKE '%영업%' THEN 0 ELSE 1 END,
          license_date DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    conn.close()
    return {
        "status": "ok",
        "queryAddress": address,
        "addressKeys": keys,
        "index": str(index_path),
        "matches": [dict(row) for row in rows],
    }


def classify_food_business(building_profile: dict | None, desired_business: str, liquor_sales: bool = False) -> dict:
    desired = normalize_space(desired_business)
    if liquor_sales and desired in {"휴게음식점영업", "제과점영업"}:
        return {
            "result": "blocked_or_switch_required",
            "reason": "주류 판매가 있으면 휴게음식점/제과점 단독 경로가 아니라 일반음식점영업 전환 검토가 필요합니다.",
            "recommendedBusinessType": "일반음식점영업",
        }

    summary = (building_profile or {}).get("summary") or {}
    use_text = " ".join(str(summary.get(key) or "") for key in ["mainPurpsCdNm", "etcPurps"])
    use_text += " " + " ".join(summary.get("floorUses") or [])
    allowed = "근린생활시설" in use_text or "음식점" in use_text
    needs_check = not use_text.strip()
    return {
        "result": "needs_building_check" if needs_check else ("likely_possible" if allowed else "needs_department_check"),
        "desiredBusinessType": desired,
        "buildingUseText": use_text.strip(),
        "reason": "건축물대장 용도에 근린생활시설/음식점 계열이 확인됩니다." if allowed else "건축물대장 용도와 영업장 면적 기준을 담당 부서에서 확인해야 합니다.",
    }


def cmd_query(args: argparse.Namespace) -> None:
    result = query_past_businesses(args.index, args.address, args.limit, args.business_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_normalize_address(args: argparse.Namespace) -> None:
    payload = normalize_address_with_juso(args.address)
    common = (payload.get("results") or {}).get("common") or {}
    result = {
        "address": args.address,
        "apiStatus": {
            "errorCode": common.get("errorCode"),
            "errorMessage": common.get("errorMessage"),
            "totalCount": common.get("totalCount"),
        },
        "best": best_juso_result(payload),
        "buildingParams": address_to_building_params(args.address, payload),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_building_profile(args: argparse.Namespace) -> None:
    result = build_building_profile(args.address)
    if args.output:
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_precheck(args: argparse.Namespace) -> None:
    past = query_past_businesses(args.index, args.address, args.limit, args.business_type)
    building = None
    if args.with_building_api:
        building = build_building_profile(args.address)
    classification = classify_food_business(building, args.business_type or "휴게음식점영업", args.liquor_sales)
    result = {
        "address": args.address,
        "building": building or {"status": "not_called", "reason": "pass --with-building-api after setting JUSO_API_KEY and DATA_GO_KR_SERVICE_KEY"},
        "businessClassification": classification,
        "pastBusinesses": past,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HEOGAON precheck CLI for Seoul LOCALDATA and BuildingHUB.")
    sub = parser.add_subparsers(dest="command", required=True)

    q = sub.add_parser("query-past-businesses", help="Search Seoul LOCALDATA by address.")
    q.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    q.add_argument("--address", required=True)
    q.add_argument("--business-type", default="")
    q.add_argument("--limit", type=int, default=30)
    q.set_defaults(func=cmd_query)

    n = sub.add_parser("normalize-address", help="Call Juso API and derive BuildingHUB params.")
    n.add_argument("--address", required=True)
    n.set_defaults(func=cmd_normalize_address)

    b = sub.add_parser("building-profile", help="Call Juso + BuildingHUB APIs and cache responses.")
    b.add_argument("--address", required=True)
    b.add_argument("--output", type=Path)
    b.set_defaults(func=cmd_building_profile)

    p = sub.add_parser("precheck", help="Compose address, building, business rule, and past-place checks.")
    p.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    p.add_argument("--address", required=True)
    p.add_argument("--business-type", default="휴게음식점영업")
    p.add_argument("--liquor-sales", action="store_true")
    p.add_argument("--with-building-api", action="store_true")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_precheck)

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
