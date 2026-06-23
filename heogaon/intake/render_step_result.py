from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path
from typing import Any


INTAKE_DIR = Path(__file__).resolve().parent
if str(INTAKE_DIR) not in sys.path:
    sys.path.insert(0, str(INTAKE_DIR))

from intake_pipeline import build_intake_result  # noqa: E402


DEFAULT_TEXT = (
    "마포구 망원동에서 15평 카페를 창업하고 싶어요. "
    "음료와 디저트를 팔고 간판도 달 거예요. "
    "사업장 전체 주소는 서울특별시 마포구 포은로 63, 1층 101호이고 "
    "주류는 팔지 않아요. 벽면간판 가로 3m 세로 1m이고 건물주 승낙 받았어요."
)


def value(value_: Any, empty: str = "-") -> str:
    if value_ is None or value_ == "":
        return empty
    if isinstance(value_, bool):
        return "예" if value_ else "아니오"
    return str(value_)


def badge(text: str, tone: str = "neutral") -> str:
    return f'<span class="badge {tone}">{escape(value(text))}</span>'


def pill_list(items: list[Any], tone: str = "neutral") -> str:
    if not items:
        return '<span class="muted">없음</span>'
    return "".join(badge(str(item), tone) for item in items)


def detail_json(title: str, payload: Any) -> str:
    pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    return (
        "<details>"
        f"<summary>{escape(title)}</summary>"
        f"<pre>{escape(pretty)}</pre>"
        "</details>"
    )


def doc_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<tr><td colspan="3" class="muted">없음</td></tr>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{escape(value(item.get('label')))}</td>"
            f"<td>{escape(value(item.get('stage')))}</td>"
            f"<td>{escape(value(item.get('condition')))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def contact_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<tr><td colspan="4" class="muted">없음</td></tr>'
    rows = []
    for item in items:
        phone = item.get("phone") or ""
        phone_html = f'<a href="{escape(item.get("phoneHref") or "")}">{escape(phone)}</a>' if phone else "-"
        rows.append(
            "<tr>"
            f"<td>{escape(value(item.get('label')))}</td>"
            f"<td>{escape(value(item.get('departmentName')))}</td>"
            f"<td>{phone_html}</td>"
            f"<td>{escape(value(item.get('sourceTitle')))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def procedure_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<tr><td colspan="6" class="muted">없음</td></tr>'
    rows = []
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{escape(value(item.get('order')))}</td>"
            f"<td><strong>{escape(value(item.get('title')))}</strong><br><span class=\"muted\">{escape(value(item.get('timing')))}</span></td>"
            f"<td>{badge(item.get('status', 'active'), 'good' if item.get('status') == 'active' else 'warn' if item.get('status') == 'conditional_if_planned' else 'neutral')}</td>"
            f"<td>{pill_list(item.get('documents') or [], 'info')}</td>"
            f"<td>{pill_list(item.get('departments') or [], 'good')}</td>"
            f"<td>{'<br>'.join(escape(value(note)) for note in item.get('notes', [])) or '-'}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def route_cards(routes: list[dict[str, Any]]) -> str:
    if not routes:
        return '<p class="muted">후보 없음</p>'
    cards = []
    for route in routes:
        status = route.get("status", "")
        tone = "good" if status == "candidate" else "warn" if "blocked" in status else "neutral"
        reasons = "".join(f"<li>{escape(value(reason))}</li>" for reason in route.get("reasons", [])[:3])
        cards.append(
            '<div class="route">'
            f"<div>{badge(route.get('businessType', '-'), tone)} {badge(status, tone)} {badge('score ' + str(route.get('score', '-')))}</div>"
            f"<ul>{reasons}</ul>"
            "</div>"
        )
    return "".join(cards)


def script_cards(scripts: list[dict[str, Any]]) -> str:
    if not scripts:
        return '<p class="muted">생성된 문의 스크립트 없음</p>'
    cards = []
    for script in scripts[:3]:
        cards.append(
            '<div class="script-card">'
            f"<strong>{escape(value(script.get('subject')))}</strong>"
            f"<p>{escape(value(script.get('phoneScript')))}</p>"
            "</div>"
        )
    return "".join(cards)


def render_html(result: dict[str, Any]) -> str:
    slots = result["slots"]
    business = slots.get("business", {})
    address = slots.get("address", {})
    space = slots.get("space", {})
    facility = slots.get("facility", {})
    slot_meta = result.get("slotFilling", {}).get("meta", {})
    graph = result.get("requirementGraph", {})
    doc_plan = graph.get("documentPlan", {})
    dept_plan = graph.get("departmentPlan", {})
    external = result.get("externalChecks", {})
    building = external.get("buildingLedger", {})
    building_summary = building.get("summary") or {}
    past = external.get("pastBusinessLookup", {})
    decision = result.get("decisionEngine", {})
    judgement_packet = result.get("aiJudgement", {})
    judgement = judgement_packet.get("judgement", {})
    judgement_meta = judgement_packet.get("meta", {})
    inquiry = result.get("inquiryPackage", {})
    contacts = inquiry.get("contacts", [])
    scripts_packet = inquiry.get("scripts", {})
    scripts = scripts_packet.get("scripts", [])
    scripts_meta = scripts_packet.get("meta", {})
    missing = result.get("missingInfo", {})
    api_plan = result.get("apiPlan", {})

    required_docs = doc_plan.get("requiredForSubmission", [])
    conditional_docs = doc_plan.get("conditional", [])
    later_docs = doc_plan.get("later", [])
    procedure_plan = graph.get("procedurePlan", [])

    actions = [
        f"{item.get('id', '')}:{item.get('status', '')}"
        for item in graph.get("activatedActions", [])
    ]
    required_now = [item.get("label") for item in missing.get("requiredNow", [])]
    recommended = [item.get("label") for item in missing.get("recommendedNext", [])]
    later_questions = [item.get("label") for item in missing.get("later", [])]
    primary_depts = [item.get("label", "") for item in dept_plan.get("primary", [])]
    conditional_depts = [item.get("label", "") for item in dept_plan.get("conditional", [])]

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>허가온 Step Result</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172033;
      --muted: #687386;
      --line: #d9e1ec;
      --panel: #ffffff;
      --soft: #f5f8fb;
      --blue: #3867d6;
      --green: #20835d;
      --amber: #9d6500;
      --red: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Malgun Gothic", Arial, sans-serif;
      color: var(--ink);
      background: #edf2f7;
      line-height: 1.5;
    }}
    header {{
      padding: 28px 34px 22px;
      background: #fff;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    h2 {{ margin: 0 0 14px; font-size: 19px; }}
    h3 {{ margin: 18px 0 8px; font-size: 15px; }}
    main {{ padding: 22px 34px 46px; max-width: 1280px; margin: 0 auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .wide {{ grid-column: 1 / -1; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }}
    .step {{ color: var(--blue); font-weight: 800; font-size: 13px; margin-bottom: 4px; }}
    .muted {{ color: var(--muted); }}
    .kv {{ display: grid; grid-template-columns: 150px 1fr; gap: 8px 14px; }}
    .kv div:nth-child(odd) {{ color: var(--muted); }}
    .badge {{
      display: inline-block;
      margin: 0 6px 6px 0;
      padding: 3px 8px;
      border-radius: 999px;
      background: #eef2f7;
      color: #243044;
      font-size: 13px;
      font-weight: 650;
    }}
    .badge.good {{ background: #e7f5ef; color: var(--green); }}
    .badge.warn {{ background: #fff3d8; color: var(--amber); }}
    .badge.bad {{ background: #feeceb; color: var(--red); }}
    .badge.info {{ background: #e8efff; color: var(--blue); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-top: 1px solid var(--line); padding: 9px 8px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 700; background: var(--soft); }}
    .route, .script-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      margin-top: 10px;
      background: #fbfdff;
    }}
    .route ul {{ margin: 8px 0 0 18px; padding: 0; }}
    .script-card p {{ margin: 8px 0 0; white-space: pre-wrap; }}
    details {{
      margin-top: 12px;
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }}
    summary {{ cursor: pointer; color: var(--blue); font-weight: 700; }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #0f172a;
      color: #e5e7eb;
      padding: 14px;
      border-radius: 8px;
      font-size: 12px;
    }}
    @media (max-width: 860px) {{
      header, main {{ padding-left: 18px; padding-right: 18px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .kv {{ grid-template-columns: 120px 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>허가온 단계별 결과 화면</h1>
    <div class="muted">자연어 입력부터 API 조회, 그래프 기반 서류/부서, 문의 스크립트까지 한 번에 확인합니다.</div>
  </header>
  <main class="grid">
    <section class="wide">
      <div class="step">STEP 1</div>
      <h2>사용자 입력</h2>
      <p>{escape(result.get("inputText", ""))}</p>
    </section>

    <section>
      <div class="step">STEP 2</div>
      <h2>Slot Filling</h2>
      <div class="kv">
        <div>Intent</div><div>{badge(slots.get("intent"), "info")}</div>
        <div>Provider</div><div>{badge(slot_meta.get("provider", "rule"), "good" if slot_meta.get("provider") == "gms" else "neutral")} {badge("fallback" if slot_meta.get("fallbackUsed") else "direct", "warn" if slot_meta.get("fallbackUsed") else "good")}</div>
        <div>주소</div><div>{escape(value(address.get("full")))}</div>
        <div>API용 주소</div><div>{escape(value(address.get("lookupAddress")))}</div>
        <div>층/호</div><div>{escape(value(address.get("detail")))}</div>
        <div>업종 개념</div><div>{escape(value(business.get("concept")))}</div>
        <div>주류 판매</div><div>{badge("예" if business.get("liquorSales") else "아니오" if business.get("liquorSales") is False else "미정", "good" if business.get("liquorSales") is False else "warn")}</div>
        <div>면적</div><div>{escape(value(space.get("areaM2")))}㎡ / {escape(value(space.get("areaPyeong")))}평</div>
        <div>간판</div><div>{escape(value(facility.get("signboardType")))} {escape(value(facility.get("signboardSizeText"), ""))}</div>
      </div>
      <h3>업종 후보</h3>
      {route_cards(business.get("candidateRoutes", []))}
      {detail_json("slot 원본 보기", slots)}
    </section>

    <section>
      <div class="step">STEP 3</div>
      <h2>부족 정보</h2>
      <h3>지금 꼭 필요한 정보</h3>
      {pill_list([item for item in required_now if item], "bad")}
      <h3>다음에 받으면 좋은 정보</h3>
      {pill_list([item for item in recommended if item], "warn")}
      <h3>진행 중 체크할 정보</h3>
      {pill_list([item for item in later_questions if item], "neutral")}
      {detail_json("missingInfo 원본 보기", missing)}
    </section>

    <section>
      <div class="step">STEP 4</div>
      <h2>API 호출 계획</h2>
      <div class="kv">
        <div>주소 API</div><div>{badge("실행 가능" if api_plan.get("canRunAddressApi") else "보류", "good" if api_plan.get("canRunAddressApi") else "warn")}</div>
        <div>건축물대장</div><div>{badge("실행 가능" if api_plan.get("canRunBuildingLedgerApi") else "보류", "good" if api_plan.get("canRunBuildingLedgerApi") else "warn")}</div>
        <div>과거 업소 조회</div><div>{badge("실행 가능" if api_plan.get("canRunPastBusinessLookup") else "보류", "good" if api_plan.get("canRunPastBusinessLookup") else "warn")}</div>
        <div>판단 엔진</div><div>{badge("실행 가능" if api_plan.get("canRunDecisionEngine") else "보류", "good" if api_plan.get("canRunDecisionEngine") else "warn")}</div>
      </div>
      {detail_json("apiPlan 원본 보기", api_plan)}
    </section>

    <section>
      <div class="step">STEP 5</div>
      <h2>외부 조회 결과</h2>
      <div class="kv">
        <div>건축물대장</div><div>{badge(building.get("status"), "good" if building.get("status") == "ok" else "warn")}</div>
        <div>도로명</div><div>{escape(value(building.get("roadAddr")))}</div>
        <div>지번</div><div>{escape(value(building.get("jibunAddr")))}</div>
        <div>주용도</div><div>{escape(value(building_summary.get("mainPurpsCdNm")))}</div>
        <div>층별 용도</div><div>{pill_list(building_summary.get("floorUses") or [], "info")}</div>
        <div>과거 업소</div><div>{badge(past.get("status"), "good" if past.get("status") == "ok" else "warn")} {escape(str(past.get("count", 0)))}건</div>
      </div>
      {detail_json("externalChecks 원본 보기", external)}
    </section>

    <section>
      <div class="step">STEP 6</div>
      <h2>Decision Engine</h2>
      <div class="kv">
        <div>상태</div><div>{badge(decision.get("status"), "good" if decision.get("status") == "ok" else "warn")}</div>
        <div>모드</div><div>{escape(value(decision.get("mode")))}</div>
        <div>사유</div><div>{escape(value(decision.get("reason")))}</div>
      </div>
      {detail_json("decisionEngine 원본 보기", decision)}
    </section>

    <section class="wide">
      <div class="step">STEP 7</div>
      <h2>그래프 기반 서류/부서</h2>
      <div class="kv">
        <div>Scope</div><div>{badge(graph.get("scope"), "info")}</div>
        <div>Activated actions</div><div>{pill_list(actions, "info")}</div>
        <div>주 담당 부서</div><div>{pill_list(primary_depts, "good")}</div>
        <div>조건부 부서</div><div>{pill_list(conditional_depts, "warn")}</div>
      </div>
      <h3>권장 진행 순서</h3>
      <table><thead><tr><th>순서</th><th>해야 할 일</th><th>상태</th><th>관련 서류</th><th>문의 부서</th><th>메모</th></tr></thead><tbody>{procedure_rows(procedure_plan)}</tbody></table>
      <h3>필수 제출/준비 서류</h3>
      <table><thead><tr><th>서류</th><th>단계</th><th>조건</th></tr></thead><tbody>{doc_rows(required_docs)}</tbody></table>
      <h3>조건부 서류</h3>
      <table><thead><tr><th>서류</th><th>단계</th><th>조건</th></tr></thead><tbody>{doc_rows(conditional_docs)}</tbody></table>
      <h3>나중 단계</h3>
      <table><thead><tr><th>서류</th><th>단계</th><th>조건</th></tr></thead><tbody>{doc_rows(later_docs)}</tbody></table>
      {detail_json("requirementGraph 원본 보기", graph)}
    </section>

    <section>
      <div class="step">STEP 8</div>
      <h2>AI 최종 판단 패킷</h2>
      <div class="kv">
        <div>상태</div><div>{badge(judgement.get("decisionStatus"), "good" if judgement.get("decisionStatus") == "ready_for_final_guidance" else "warn")}</div>
        <div>Provider</div><div>{badge(judgement_meta.get("provider", "rule"), "good" if judgement_meta.get("provider") == "gms" else "neutral")} {badge("fallback" if judgement_meta.get("fallbackUsed") else "direct", "warn" if judgement_meta.get("fallbackUsed") else "good")}</div>
        <div>신뢰도</div><div>{escape(value(judgement.get("confidence")))}</div>
      </div>
      <p>{escape(value(judgement.get("summary")))}</p>
      <h3>바로 말할 수 있는 것</h3>
      {pill_list(judgement.get("canSayNow", []), "good")}
      <h3>아직 확정 못 하는 것</h3>
      {pill_list(judgement.get("cannotConfirmYet", []), "warn")}
      {detail_json("aiJudgement 원본 보기", judgement)}
    </section>

    <section>
      <div class="step">STEP 9</div>
      <h2>문의처/제출 가이드</h2>
      <p>{badge("script provider: " + value(scripts_meta.get("provider", "rule")), "good" if scripts_meta.get("provider") == "gms" else "neutral")} {badge("fallback" if scripts_meta.get("fallbackUsed") else "direct", "warn" if scripts_meta.get("fallbackUsed") else "good")}</p>
      <table><thead><tr><th>업무</th><th>부서</th><th>전화</th><th>출처</th></tr></thead><tbody>{contact_rows(contacts[:8])}</tbody></table>
      <h3>문의 스크립트</h3>
      {script_cards(scripts)}
      {detail_json("inquiryPackage 원본 보기", inquiry)}
    </section>
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an intake pipeline step-by-step HTML result.")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--output", type=Path, default=INTAKE_DIR / "step_result_demo.html")
    parser.add_argument("--slot-provider", choices=["rule", "gms"], default="rule")
    parser.add_argument("--judgement-provider", choices=["rule", "gms", "openai"], default="rule")
    parser.add_argument("--inquiry-provider", choices=["rule", "gms", "openai"], default="rule")
    parser.add_argument("--no-decision", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_intake_result(
        args.text,
        run_decision=not args.no_decision,
        slot_provider=args.slot_provider,
        judgement_provider=args.judgement_provider,
        inquiry_provider=args.inquiry_provider,
    )
    html = render_html(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
