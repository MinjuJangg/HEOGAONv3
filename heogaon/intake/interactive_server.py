from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


INTAKE_DIR = Path(__file__).resolve().parent
if str(INTAKE_DIR) not in sys.path:
    sys.path.insert(0, str(INTAKE_DIR))

from intake_pipeline import build_intake_result  # noqa: E402
from prompt_debug import build_prompt_debug  # noqa: E402


DEFAULT_TEXT = (
    "마포구 망원동에서 15평 카페를 창업하고 싶어요. "
    "음료와 디저트를 팔고 간판도 달 거예요. "
    "사업장 전체 주소는 서울특별시 마포구 포은로 63, 1층 101호이고 "
    "주류는 팔지 않아요. 벽면간판 가로 3m 세로 1m이고 건물주 승낙 받았어요."
)


def html_escape(value: Any) -> str:
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def labels(items: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("label")) for item in items if item.get("label")]


def question_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in items:
        result.append(
            {
                "id": item.get("id"),
                "label": item.get("label") or item.get("id"),
                "question": item.get("question") or item.get("label") or item.get("id"),
                "reason": item.get("reason", ""),
                "examples": item.get("examples", []),
                "answerType": item.get("answerType", "text"),
            }
        )
    return result


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    slots = result.get("slots", {})
    graph = result.get("requirementGraph", {})
    document_plan = graph.get("documentPlan", {})
    inquiry = result.get("inquiryPackage", {})
    scripts = inquiry.get("scripts", {})
    external = result.get("externalChecks") or {}
    building = external.get("buildingLedger") or {}
    building_summary = building.get("summary") or {}
    judgement = result.get("aiJudgement", {})
    procedure = graph.get("procedurePlan", [])
    missing = result.get("missingInfo", {})
    try:
        prompt_debug = build_prompt_debug(result)
    except Exception as exc:
        prompt_debug = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "inputText": result.get("inputText"),
        "providers": {
            "slot": result.get("slotFilling", {}).get("meta", {}),
            "judgement": judgement.get("meta", {}),
            "inquiry": scripts.get("meta", {}),
            "inquiryPolicy": result.get("inquiryScriptPolicy", {}),
        },
        "slots": {
            "intent": slots.get("intent"),
            "address": slots.get("address"),
            "business": slots.get("business"),
            "space": slots.get("space"),
            "facility": slots.get("facility"),
        },
        "missingInfo": {
            "requiredNow": labels(missing.get("requiredNow", [])),
            "recommendedNext": labels(missing.get("recommendedNext", [])),
            "later": labels(missing.get("later", [])),
            "requiredNowQuestions": question_items(missing.get("requiredNow", [])),
            "recommendedNextQuestions": question_items(missing.get("recommendedNext", [])),
        },
        "api": {
            "plan": result.get("apiPlan"),
            "buildingLedgerStatus": building.get("status"),
            "pastBusinessStatus": (external.get("pastBusinessLookup") or {}).get("status"),
            "decisionEngineStatus": (result.get("decisionEngine") or {}).get("status"),
            "buildingSummary": {
                "roadAddr": building.get("roadAddr"),
                "jibunAddr": building.get("jibunAddr"),
                "mainPurpsCdNm": building_summary.get("mainPurpsCdNm"),
                "floorUses": building_summary.get("floorUses") or [],
                "landZones": building_summary.get("landZones") or [],
            },
        },
        "graph": {
            "scope": graph.get("scope"),
            "actions": graph.get("activatedActions", []),
            "procedurePlan": procedure,
            "requiredDocs": document_plan.get("requiredForSubmission", []),
            "conditionalDocs": document_plan.get("conditional", []),
            "laterDocs": document_plan.get("later", []),
            "departments": graph.get("departmentPlan", {}),
            "schedulePlan": graph.get("schedulePlan", {}),
        },
        "judgement": judgement.get("judgement", {}),
        "inquiry": {
            "district": inquiry.get("district"),
            "contacts": inquiry.get("contacts", []),
            "scripts": scripts.get("scripts", []),
            "onlineDraft": scripts.get("onlineDraft", {}),
        },
        "promptDebug": prompt_debug,
    }


def index_html() -> str:
    api_ready = bool(os.getenv("JUSO_API_KEY")) and bool(os.getenv("DATA_GO_KR_SERVICE_KEY"))
    gms_ready = bool(os.getenv("GMS_API_KEY") or os.getenv("HEOGAON_GMS_API_KEY"))
    model = os.getenv("GMS_MODEL") or os.getenv("HEOGAON_GMS_MODEL") or "gpt-4.1"
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>허가온 Intake Runner</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI", "Malgun Gothic", Arial, sans-serif; color: #172033; background: #edf2f7; }}
    header {{ background: #fff; border-bottom: 1px solid #d9e1ec; padding: 24px 32px; }}
    h1 {{ margin: 0 0 8px; font-size: 25px; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 22px 32px 48px; }}
    textarea {{ width: 100%; min-height: 118px; resize: vertical; padding: 14px; border: 1px solid #b9c6d6; border-radius: 8px; font: inherit; line-height: 1.5; background: #fff; }}
    button {{ border: 0; border-radius: 8px; padding: 10px 16px; font-weight: 700; cursor: pointer; background: #3867d6; color: #fff; }}
    button.secondary {{ background: #eef2f7; color: #243044; }}
    section {{ background: #fff; border: 1px solid #d9e1ec; border-radius: 8px; padding: 16px; margin-top: 16px; }}
    .row {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .wide {{ grid-column: 1 / -1; }}
    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 13px; font-weight: 650; background: #eef2f7; color: #243044; margin: 0 5px 5px 0; }}
    .good {{ background: #e7f5ef; color: #20835d; }}
    .warn {{ background: #fff3d8; color: #9d6500; }}
    .bad {{ background: #feeceb; color: #b42318; }}
    .info {{ background: #e8efff; color: #3867d6; }}
    .muted {{ color: #687386; }}
    .kv {{ display: grid; grid-template-columns: 150px 1fr; gap: 8px 12px; }}
    .kv div:nth-child(odd) {{ color: #687386; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-top: 1px solid #d9e1ec; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f5f8fb; color: #687386; }}
    .followup-item {{ border-top: 1px solid #d9e1ec; padding: 12px 0; }}
    .followup-item label {{ display: block; font-weight: 750; margin-bottom: 4px; }}
    .followup-item input {{ width: 100%; padding: 9px 10px; border: 1px solid #b9c6d6; border-radius: 8px; font: inherit; }}
    .followup-item small {{ display: block; color: #687386; margin-top: 4px; }}
    pre {{ white-space: pre-wrap; overflow-wrap: anywhere; background: #0f172a; color: #e5e7eb; padding: 12px; border-radius: 8px; font-size: 12px; }}
    details {{ margin-top: 10px; }}
    summary {{ cursor: pointer; font-weight: 700; color: #3867d6; }}
    @media (max-width: 880px) {{ main, header {{ padding-left: 16px; padding-right: 16px; }} .grid {{ grid-template-columns: 1fr; }} .kv {{ grid-template-columns: 120px 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>허가온 Intake Runner</h1>
    <div class="row">
      <span class="badge {'good' if gms_ready else 'bad'}">GMS {'connected' if gms_ready else 'missing key'}</span>
      <span class="badge info">model {html_escape(model)}</span>
      <span class="badge {'good' if api_ready else 'warn'}">public API {'ready' if api_ready else 'env missing'}</span>
    </div>
  </header>
  <main>
    <section>
      <textarea id="query">{html_escape(DEFAULT_TEXT)}</textarea>
      <div class="row" style="margin-top: 10px;">
        <button id="run">실행</button>
        <button class="secondary" id="run-debug">토큰 디버그(rule)</button>
        <button class="secondary" id="clear">비우기</button>
        <span id="status" class="muted"></span>
      </div>
    </section>
    <div id="result"></div>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const esc = (v) => String(v ?? '').replace(/[&<>"]/g, (c) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
    const badge = (v, tone='') => `<span class="badge ${{tone}}">${{esc(v)}}</span>`;
    const listBadges = (arr, tone='') => (arr && arr.length ? arr.map(x => badge(x, tone)).join('') : '<span class="muted">없음</span>');
    const provider = (meta) => `${{badge(meta?.provider || '-', meta?.provider === 'gms' ? 'good' : '')}} ${{badge(meta?.fallbackUsed ? 'fallback' : 'direct', meta?.fallbackUsed ? 'warn' : 'good')}}`;
    const docRows = (items) => (items || []).map(x => `<tr><td>${{esc(x.label)}}</td><td>${{esc(x.stage)}}</td><td>${{esc(x.status)}}</td><td>${{esc(x.condition || '')}}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">없음</td></tr>';
    const procedureRows = (items) => (items || []).map(x => `<tr><td>${{esc(x.order)}}</td><td><b>${{esc(x.title)}}</b><br><span class="muted">${{esc(x.timing)}}</span></td><td>${{badge(x.status, x.status === 'active' ? 'good' : 'warn')}}</td><td>${{listBadges(x.documents || [], 'info')}}</td><td>${{listBadges(x.departments || [], 'good')}}</td></tr>`).join('') || '<tr><td colspan="5" class="muted">없음</td></tr>';
    const contactRows = (items) => (items || []).map(x => `<tr><td>${{esc(x.label)}}</td><td>${{esc(x.departmentName)}}</td><td>${{esc(x.phone || '-')}}</td></tr>`).join('') || '<tr><td colspan="3" class="muted">없음</td></tr>';
    const scriptCards = (items) => (items || []).map(x => `<section><b>${{esc(x.subject)}}</b><p>${{badge(x.departmentName || x.contact?.departmentName || '부서 매핑 없음', x.contactMapped ? 'good' : 'warn')}} ${{badge(x.phone || x.contact?.phone || '전화 없음')}}</p><p>${{esc(x.phoneScript || x.body || '')}}</p></section>`).join('') || '<p class="muted">없음</p>';
    const promptDebugRows = (debug) => {{
      if (!debug || debug.error) return `<tr><td colspan="7" class="bad">${{esc(debug?.error || 'debug unavailable')}}</td></tr>`;
      return (debug.calls || []).map(x => `<tr><td><b>${{esc(x.name)}}</b><br><span class="muted">${{esc(x.reason)}}</span></td><td>${{esc(x.requestedProvider)}} -> ${{esc(x.provider)}}</td><td>${{badge(x.sentToAi ? 'sent' : 'not sent', x.sentToAi ? 'good' : '')}}</td><td>${{esc(x.estimatedTokens)}}</td><td>${{esc(x.totalChars)}}</td><td>${{esc(x.systemChars)}}</td><td>${{esc(x.userChars)}}</td></tr>`).join('');
    }};
    const promptDebugDetails = (debug) => {{
      if (!debug || debug.error) return '';
      return (debug.calls || []).map(x => `<details><summary>${{esc(x.name)}} input preview ${{x.truncated ? '(truncated)' : ''}}</summary><p class="muted">keys: ${{esc((x.userTopLevelKeys || []).join(', '))}}</p><pre>${{esc(JSON.stringify(x.userFieldChars || {{}}, null, 2))}}</pre><pre>${{esc(x.preview)}}</pre></details>`).join('');
    }};
    let latestData = null;

    function followupForm(data) {{
      const required = data.missingInfo?.requiredNowQuestions || [];
      const recommended = data.missingInfo?.recommendedNextQuestions || [];
      const items = required.length ? required : recommended.slice(0, 3);
      if (!items.length) return '';
      const title = required.length ? '필수 부족정보 입력' : '추가하면 좋은 정보 입력';
      const helper = required.length
        ? '이 값을 채우면 주소/API/판단 엔진을 다시 돌려 최종 안내가 갱신됩니다.'
        : '필수는 아니지만 입력하면 서류와 문의처 안내가 더 정확해집니다.';
      return `<section class="wide" id="followup">
        <h2>${{title}}</h2>
        <p class="muted">${{helper}}</p>
        ${{items.map(item => `<div class="followup-item">
          <label for="fu-${{esc(item.id)}}">${{esc(item.question || item.label)}}</label>
          <input id="fu-${{esc(item.id)}}" data-label="${{esc(item.label || item.id)}}" data-question="${{esc(item.question || item.label || item.id)}}" placeholder="${{esc((item.examples || []).join(' / '))}}" />
          <small>${{esc(item.reason || '')}}</small>
        </div>`).join('')}}
        <button id="rerun-followup">추가정보 반영 후 다시 실행</button>
      </section>`;
    }}

    function bindFollowup() {{
      const button = document.getElementById('rerun-followup');
      if (!button) return;
      button.addEventListener('click', () => {{
        const answers = Array.from(document.querySelectorAll('#followup input'))
          .map(input => ({{ label: input.dataset.label, value: input.value.trim() }}))
          .filter(x => x.value);
        if (!answers.length) {{
          $('status').textContent = '추가정보를 하나 이상 입력해줘.';
          return;
        }}
        const addition = answers.map(x => `${{x.label}}: ${{x.value}}`).join('. ');
        const current = $('query').value.trim();
        $('query').value = `${{current}}\\n\\n[추가정보] ${{addition}}`;
        run();
      }});
    }}

    function render(data) {{
      latestData = data;
      const s = data.slots || {{}};
      const b = s.business || {{}};
      const a = s.address || {{}};
      const sp = s.space || {{}};
      const f = s.facility || {{}};
      const api = data.api || {{}};
      const graph = data.graph || {{}};
      const j = data.judgement || {{}};
      $('result').innerHTML = `
        <div class="grid">
          <section>
            <h2>STEP 2 Slot Filling</h2>
            <div class="kv">
              <div>Provider</div><div>${{provider(data.providers?.slot)}}</div>
              <div>Intent</div><div>${{badge(s.intent, 'info')}}</div>
              <div>지역 힌트</div><div>${{esc(a.raw || '-')}} ${{badge(a.quality || '-', a.quality === 'full' ? 'good' : 'warn')}}</div>
              <div>상세주소</div><div>${{esc(a.full || '-')}}</div>
              <div>API 주소</div><div>${{esc(a.lookupAddress || '-')}}</div>
              <div>업종</div><div>${{esc(b.concept)}} / ${{listBadges(b.candidateTypes || [], 'info')}}</div>
              <div>주류</div><div>${{badge(b.liquorSales === true ? '예' : b.liquorSales === false ? '아니오' : '미정', b.liquorSales === false ? 'good' : 'warn')}}</div>
              <div>면적</div><div>${{esc(sp.areaM2)}}㎡ / ${{esc(sp.areaPyeong)}}평</div>
              <div>간판</div><div>${{esc(f.signboardType || '-')}} ${{esc(f.signboardSizeText || '')}}</div>
            </div>
          </section>
          <section>
            <h2>STEP 3 부족 정보</h2>
            <h3>지금 꼭 필요한 정보</h3>${{listBadges(data.missingInfo?.requiredNow || [], 'bad')}}
            <h3>다음에 받으면 좋은 정보</h3>${{listBadges(data.missingInfo?.recommendedNext || [], 'warn')}}
            <h3>나중 체크</h3>${{listBadges(data.missingInfo?.later || [])}}
          </section>
          ${{followupForm(data)}}
          <section>
            <h2>STEP 5 API 조회</h2>
            <div class="kv">
              <div>건축물대장</div><div>${{badge(api.buildingLedgerStatus || '-', api.buildingLedgerStatus === 'ok' ? 'good' : 'warn')}}</div>
              <div>과거 업소</div><div>${{badge(api.pastBusinessStatus || '-', api.pastBusinessStatus === 'ok' ? 'good' : 'warn')}}</div>
              <div>Decision</div><div>${{badge(api.decisionEngineStatus || '-', api.decisionEngineStatus === 'ok' ? 'good' : 'warn')}}</div>
              <div>주용도</div><div>${{esc(api.buildingSummary?.mainPurpsCdNm)}}</div>
              <div>층별용도</div><div>${{listBadges(api.buildingSummary?.floorUses || [], 'info')}}</div>
              <div>보류 사유</div><div>${{esc(api.plan?.skipReason || '-')}}</div>
            </div>
          </section>
          <section>
            <h2>STEP 8 AI Judgement</h2>
            <div class="kv">
              <div>Provider</div><div>${{provider(data.providers?.judgement)}}</div>
              <div>Status</div><div>${{badge(j.decisionStatus || '-', j.decisionStatus === 'ready_for_final_guidance' ? 'good' : 'warn')}}</div>
              <div>Summary</div><div>${{esc(j.summary)}}</div>
            </div>
          </section>
          <section class="wide">
            <h2>STEP 7 권장 진행 순서</h2>
            <table><thead><tr><th>순서</th><th>해야 할 일</th><th>상태</th><th>서류</th><th>부서</th></tr></thead><tbody>${{procedureRows(graph.procedurePlan)}}</tbody></table>
          </section>
          <section class="wide">
            <h2>서류</h2>
            <h3>필수</h3><table><thead><tr><th>서류</th><th>단계</th><th>상태</th><th>조건</th></tr></thead><tbody>${{docRows(graph.requiredDocs)}}</tbody></table>
            <h3>조건부</h3><table><thead><tr><th>서류</th><th>단계</th><th>상태</th><th>조건</th></tr></thead><tbody>${{docRows(graph.conditionalDocs)}}</tbody></table>
          </section>
          <section>
            <h2>STEP 9 문의처</h2>
            <p>${{provider(data.providers?.inquiry)}}</p>
            <table><thead><tr><th>업무</th><th>부서</th><th>전화</th></tr></thead><tbody>${{contactRows(data.inquiry?.contacts)}}</tbody></table>
          </section>
          <section>
            <h2>문의 스크립트</h2>
            ${{scriptCards(data.inquiry?.scripts)}}
          </section>
          <section class="wide">
            <h2>Token / AI Input Debug</h2>
            <p class="muted">${{esc(data.promptDebug?.note || '')}}</p>
            <div class="row">
              ${{badge('actual AI calls: ' + (data.promptDebug?.actualAiCallCount ?? '-'), 'info')}}
              ${{badge('actual est. input tokens: ' + (data.promptDebug?.actualEstimatedInputTokens ?? '-'), 'warn')}}
              ${{badge('potential all-step tokens: ' + (data.promptDebug?.totalEstimatedInputTokens || '-'))}}
              ${{data.providers?.inquiryPolicy?.deferredAi ? badge('inquiry AI deferred', 'warn') : ''}}
            </div>
            <table><thead><tr><th>Call</th><th>Provider</th><th>AI send</th><th>Est. input tokens</th><th>Total chars</th><th>System chars</th><th>User chars</th></tr></thead><tbody>${{promptDebugRows(data.promptDebug)}}</tbody></table>
            ${{promptDebugDetails(data.promptDebug)}}
          </section>
          <section class="wide">
            <details><summary>전체 JSON 보기</summary><pre>${{esc(JSON.stringify(data, null, 2))}}</pre></details>
          </section>
        </div>`;
      bindFollowup();
    }}

    async function run(providers = {{ slotProvider: 'gms', judgementProvider: 'gms', inquiryProvider: 'gms' }}) {{
      const text = $('query').value.trim();
      if (!text) return;
      const usesAi = Object.values(providers).some(value => value === 'gms' || value === 'openai');
      $('status').textContent = usesAi ? 'GMS/API 실행 중...' : '토큰 디버그 실행 중...';
      $('run').disabled = true;
      $('run-debug').disabled = true;
      try {{
        const res = await fetch('/api/intake', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{ text, ...providers }})
        }});
        const data = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || 'request failed');
        render(data);
        $('status').textContent = '완료';
      }} catch (err) {{
        $('status').textContent = '오류: ' + err.message;
      }} finally {{
        $('run').disabled = false;
        $('run-debug').disabled = false;
      }}
    }}
    $('run').addEventListener('click', run);
    $('run-debug').addEventListener('click', () => run({{ slotProvider: 'rule', judgementProvider: 'rule', inquiryProvider: 'rule' }}));
    $('clear').addEventListener('click', () => {{ $('query').value = ''; $('result').innerHTML = ''; }});
  </script>
</body>
</html>"""


class IntakeHandler(BaseHTTPRequestHandler):
    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.send_html(index_html())
            return
        if parsed.path == "/api/intake":
            query = parse_qs(parsed.query)
            text = (query.get("text") or [""])[0]
            self.run_intake({"text": text})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/intake":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self.send_json({"error": "invalid JSON"}, 400)
            return
        self.run_intake(payload)

    def run_intake(self, payload: dict[str, Any]) -> None:
        text = str(payload.get("text") or "").strip()
        if not text:
            self.send_json({"error": "text is required"}, 400)
            return
        try:
            result = build_intake_result(
                text,
                run_decision=True,
                slot_provider=str(payload.get("slotProvider") or "gms"),
                judgement_provider=str(payload.get("judgementProvider") or "gms"),
                inquiry_provider=str(payload.get("inquiryProvider") or "gms"),
            )
            self.send_json(compact_result(result))
        except Exception as exc:
            self.send_json({"error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()}, 500)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    port = int(os.getenv("HEOGAON_INTAKE_PORT") or "8792")
    server = ThreadingHTTPServer(("127.0.0.1", port), IntakeHandler)
    print(f"http://127.0.0.1:{port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
