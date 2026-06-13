import { Icon } from "@/components/common/Icon";
import type { DiagnosisGuidance, DiagnosisView as DiagnosisViewModel } from "@/types/flow";

const FLOOR_UNIT_HINT_RE = /(?:지하\s*)?\d+\s*층|[A-Za-z]?\d{1,5}\s*호/;
const FLOOR_FOLLOWUP_RE = /몇\s*층|실제로\s*몇\s*층|층수|층\s*\/\s*호수|층과\s*호수|호수|호실/;

export function DiagnosisView({ view }: { view: DiagnosisViewModel }) {
  const guidance = view.guidance;
  const buildingItems = guidance?.hideBuildingSummary ? [] : visibleItems(guidance?.buildingItems ?? []);
  const questionsToAsk = guidance?.hideQuestionsSummary ? [] : visibleItems(guidance?.questionsToAsk ?? []);
  const hasGuidance = Boolean(guidance && (guidance.suitabilitySummary || guidance.summary || buildingItems.length || questionsToAsk.length));

  return (
    <>
      <section className="question-card">
        <h1 className="question-title">{view.title}</h1>
        <p className="question-sub">{view.headline}</p>
      </section>
      <div className="summary-view">
        {hasGuidance && guidance ? <SuitabilityCard guidance={guidance} buildingItems={buildingItems} /> : null}
        {questionsToAsk.length ? (
          <ListCard title={guidance?.questionsTitle || "추가로 확인할 정보가 더 있어요"} icon="help" items={questionsToAsk} />
        ) : null}
      </div>
    </>
  );
}

function SuitabilityCard({ guidance, buildingItems }: { guidance: DiagnosisGuidance; buildingItems: string[] }) {
  return (
    <section className="summary-review">
      <div className="summary-review-title-row">
        <span aria-hidden="true"><Icon name={guidance.suitability === "blocked" ? "close" : "check"} /></span>
        <h2 className="summary-review-title">{guidance.suitabilityTitle || "가능성 판단"}</h2>
      </div>
      <p className="summary-review-subtitle">{guidance.suitabilitySummary || guidance.summary}</p>
      {buildingItems.length ? <BuildingLedgerSummary items={buildingItems} /> : null}
    </section>
  );
}

function BuildingLedgerSummary({ items }: { items: string[] }) {
  return (
    <div className="building-ledger-summary" aria-label="건축물대장 확인 결과">
      <div className="building-ledger-summary-head">
        <span aria-hidden="true"><Icon name="building2" size={18} /></span>
        <h3>건축물대장 확인 결과</h3>
      </div>
      <dl className="building-ledger-summary-list">
        {items.map((item) => {
          const { label, value } = splitLedgerItem(item);
          return (
            <div className="building-ledger-summary-row" key={item}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

function ListCard({ title, icon, items }: { title: string; icon: Parameters<typeof Icon>[0]["name"]; items: string[] }) {
  return (
    <section className="summary-review">
      <div className="summary-review-title-row">
        <span aria-hidden="true"><Icon name={icon} /></span>
        <h2 className="summary-review-title">{title}</h2>
      </div>
      <ul className="missing-summary-list">
        {items.map((item) => (
          <li className="missing-summary-item" key={item}>
            <span className="missing-summary-icon" aria-hidden="true"><Icon name={icon} /></span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function visibleItems(items: string[]) {
  const visible = items
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item) => !looksLikeInternalStatus(item))
    .filter((item) => !looksLikeRedundantFloorQuestion(item));
  const result: string[] = [];
  const seen = new Set<string>();
  visible.forEach((item) => {
    const key = semanticQuestionKey(item);
    if (seen.has(key)) return;
    seen.add(key);
    result.push(item);
  });
  return result;
}

function semanticQuestionKey(item: string) {
  const compact = item.replace(/[\s.,:;!?/\\()[\]{}'"`~·ㆍ_-]+/g, "").toLowerCase();
  if (!compact) return "";
  if (/(건물주|관리인|소유자|대지소유자)/.test(compact) && /(승낙|동의|허락|사용권)/.test(compact)) {
    return "owner_consent";
  }
  if (compact.includes("간판")) {
    if (/(크기|면적|가로|세로|높이|길이|규격)/.test(compact)) return "signboard_size";
    if (compact.includes("종류") || (compact.includes("어떤") && /(설치|변경)/.test(compact))) return "signboard_type";
    if (/(위치|어디)/.test(compact)) return "signboard_location";
    if (/(설치|변경|바꿀|예정|계획)/.test(compact)) return "signboard_planned";
  }
  if (/(외부|테이블|테라스|보도|도로)/.test(compact)) {
    if (/(면적|크기|수량|몇개|몇대)/.test(compact)) return "outdoor_area";
    if (/(위치|어디|사유지|도로|보도)/.test(compact)) return "outdoor_location";
    if (/(사용|예정|계획|둘|두|좌석)/.test(compact)) return "outdoor_space_planned";
  }
  if (/(술|주류)/.test(compact)) return "liquor_sales";
  if (/(직접|조리|제조|가공|완제품)/.test(compact)) return "manufacturing_or_simple_sale";
  return compact;
}

function splitLedgerItem(item: string) {
  const dividerIndex = item.indexOf(":");
  if (dividerIndex < 0) {
    return { label: "확인 항목", value: item };
  }
  const label = item.slice(0, dividerIndex).trim();
  const rawValue = item.slice(dividerIndex + 1).trim();
  const value = label.includes("층별") ? cleanFloorUseSummary(rawValue) : rawValue;
  return { label: label || "확인 항목", value: value || "-" };
}

function cleanFloorUseSummary(value: string) {
  return groupFloorUseTexts(value
    .split(/\s*\/\s*/g)
    .map(cleanFloorUseText)
    .filter(Boolean))
    .join(" / ");
}

function cleanFloorUseText(value: string) {
  const text = value.replace(/\s+/g, " ").trim();
  if (!text) return "";
  const match = text.match(/^((?:지하\s*)?\d+\s*층|지\s*\d+\s*층|b\d+\s*층?|옥탑)\s+(.+)$/i);
  if (!match) return text;
  const floorLabel = match[1].replace(/\s+/g, "");
  const uses = compactBuildingUseBits(match[2].split(/\s+/g));
  return [floorLabel, ...uses].filter(Boolean).join(" ");
}

function compactBuildingUseBits(values: string[]) {
  const unique: string[] = [];
  values.forEach((value) => {
    const text = value.replace(/\s+/g, " ").trim();
    const key = normalizeUseKey(text);
    if (!text || !key) return;
    for (let index = 0; index < unique.length; index += 1) {
      const existingKey = normalizeUseKey(unique[index]);
      if (key === existingKey || existingKey.includes(key)) return;
      if (key.includes(existingKey)) {
        unique[index] = text;
        return;
      }
    }
    unique.push(text);
  });
  return unique;
}

function groupFloorUseTexts(values: string[]) {
  const groups: Array<{ key: string; floors: string[]; use: string }> = [];
  const passthrough: string[] = [];
  values.forEach((value) => {
    const parsed = parseFloorUseText(value);
    if (!parsed) {
      if (!passthrough.includes(value)) passthrough.push(value);
      return;
    }
    const { floor, use } = parsed;
    const key = normalizeUseKey(use);
    const existing = groups.find((group) => group.key === key);
    if (existing) {
      if (!existing.floors.includes(floor)) existing.floors.push(floor);
      return;
    }
    groups.push({ key, floors: [floor], use });
  });
  return [...groups.map((group) => `${group.floors.join("·")} ${group.use}`), ...passthrough];
}

function parseFloorUseText(value: string) {
  const text = value.replace(/\s+/g, " ").trim();
  const match = text.match(/^((?:지하\s*)?\d+\s*층|지\s*\d+\s*층|b\d+\s*층?|옥탑)\s+(.+)$/i);
  if (!match) return null;
  return { floor: match[1].replace(/\s+/g, ""), use: match[2].trim() };
}

function normalizeUseKey(value: string) {
  return value.replace(/[\s.,:;!?/\\()[\]{}'"`~·ㆍ_-]+/g, "").toLowerCase();
}

function looksLikeInternalStatus(item: string) {
  return /\b(active|conditional_if_planned|needs_address_normalization|not_run|skipped|missing_index)\b/.test(item)
    || /:\s*[a-z]+(?:_[a-z]+)+\b/.test(item);
}

function looksLikeRedundantFloorQuestion(item: string) {
  return FLOOR_UNIT_HINT_RE.test(item) && FLOOR_FOLLOWUP_RE.test(item);
}
