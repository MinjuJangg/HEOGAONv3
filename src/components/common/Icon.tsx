import type { DecisionBlock } from "@/types/flow";

export type IconName =
  | "arrowRight"
  | "back"
  | "bag"
  | "building2"
  | "check"
  | "clock"
  | "close"
  | "coffee"
  | "copy"
  | "edit"
  | "fan"
  | "factory"
  | "fileCheck"
  | "help"
  | "home"
  | "list"
  | "lock"
  | "message"
  | "monitor"
  | "package"
  | "phone"
  | "refresh"
  | "search"
  | "signpost"
  | "store"
  | "utensils"
  | "wine";

// All glyphs share a single 2px stroke (Lucide reference weight) so the icon
// set reads as one consistent family across every screen. Keep stroke-width in
// sync when adding new icons.
const STROKE = 2;

const paths: Record<IconName, string> = {
  arrowRight: '<path d="M7 12h11M14 7l5 5-5 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  back: '<path d="M15 19l-7-7 7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  bag: '<path d="M6 2 3.5 6v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2V6L18 2H6z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M3.5 6h17M16 10a4 4 0 0 1-8 0" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  building2: '<path d="M4 21h16M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M9 7h.01M12 7h.01M15 7h.01M9 11h.01M12 11h.01M15 11h.01M9 15h.01M12 15h.01M15 15h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  check: '<path d="M20 6 9 17l-5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  clock: '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M12 7v5l3 2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  close: '<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  coffee: '<path d="M4 8h13v6a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V8z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M17 9h1.5a2.5 2.5 0 0 1 0 5H17M8 2.5V4.5M12.5 2.5V4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M16 8V6a2 2 0 00-2-2H6a2 2 0 00-2 2v8a2 2 0 002 2h2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  edit: '<path d="M12 20h9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  fan: '<path d="M8.5 14.5c0 2.2 1.6 4 3.8 4s3.9-1.7 3.9-4c0-1.6-.8-2.8-2.3-4.2-.7 1.7-1.7 2.3-2.6 2.4.6-2.6-.5-4.9-2.6-6.7.2 3-3.2 5-3.2 8.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  factory: '<path d="M3 21h18M5 21V10l5 3V9l5 3V7h4v14M8 17h.01M12 17h.01M16 17h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  fileCheck: '<path d="M9 3h6l2 2h3v16H4V5h3l2-2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 14l2 2 4-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  help: '<path d="M12 17h.01M9.5 9a2.5 2.5 0 114 2.1c-.9.5-1.5 1.2-1.5 2.4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" stroke-width="2"/>',
  home: '<path d="M3 11.5 12 4l9 7.5M5 10.5V20h5v-6h4v6h5v-9.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M3.5 6l1 1 2-2M3.5 12l1 1 2-2M3.5 18l1 1 2-2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M8 11V8a4 4 0 018 0v3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  message: '<path d="M21 11.5a7.5 7.5 0 0 1-7.5 7.5H8l-5 3 1.4-4.3A7.5 7.5 0 1 1 21 11.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M8 10h8M8 14h5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  monitor: '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/><path d="M3 12h18M12 3c2.3 2.4 3.5 5.4 3.5 9s-1.2 6.6-3.5 9M12 3c-2.3 2.4-3.5 5.4-3.5 9s1.2 6.6 3.5 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  package: '<path d="M21 8 12 3 3 8v8l9 5 9-5V8z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M3 8l9 5 9-5M12 13v8M7.5 5.5l9 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  phone: '<path d="M6.6 3.5 9 3a2 2 0 0 1 2.2 1.4l.8 2.7a2 2 0 0 1-.7 2.1l-1.4 1.1a12.8 12.8 0 0 0 4.8 4.8l1.1-1.4a2 2 0 0 1 2.1-.7l2.7.8A2 2 0 0 1 22 16l-.5 2.4a3 3 0 0 1-3.2 2.4C10.5 20 4 13.5 3.2 5.7a3 3 0 0 1 3.4-2.2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M18.2 12A6.5 6.5 0 0 0 7 7.4L4 10M5.8 12A6.5 6.5 0 0 0 17 16.6l3-2.6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  search: '<path d="M10.5 18a7.5 7.5 0 1 1 5.3-2.2L21 21" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M8 10.5h5M10.5 8v5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  signpost: '<path d="M12 21V4M5 5h11l3 3-3 3H5V5zM19 13H8l-3 3 3 3h11v-6z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  store: '<path d="M4 10h16l-1.2-4.8A1.6 1.6 0 0 0 17.3 4H6.7a1.6 1.6 0 0 0-1.5 1.2L4 10z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M5 10v10h14V10M9 20v-5h6v5M4 10c0 1.2 1 2.2 2.2 2.2S8.4 11.2 8.4 10c0 1.2 1 2.2 2.2 2.2s2.2-1 2.2-2.2c0 1.2 1 2.2 2.2 2.2s2.2-1 2.2-2.2c0 1.2 1 2.2 2.2 2.2S20 11.2 20 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  utensils: '<path d="M7 3v8M4 3v5a3 3 0 0 0 6 0V3M7 11v10M17 3c-2 1.6-3 3.8-3 6.5V13h4v8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  wine: '<path d="M7 3h10l-.7 6a4.3 4.3 0 0 1-8.6 0L7 3zM12 15v5M8 20h8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
};

export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" dangerouslySetInnerHTML={{ __html: paths[name] }} />;
}

export function ArrowUpIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 19V5M5.5 11.5L12 5l6.5 6.5" stroke="currentColor" strokeWidth={STROKE} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function iconForOption(optionId: string, field?: string): IconName {
  if (optionId === "unknown") return "help";
  if (optionId === "no" || optionId.includes("no") || optionId === "none") return "close";

  if (field === "liquor_sales" && optionId === "yes") return "wine";
  if (field === "signboard_planned" && optionId === "yes") return "signpost";
  if (field === "outdoor_space_planned" && optionId === "yes") return "store";
  if (field === "owner_consent" && optionId === "yes") return "fileCheck";
  if (field === "owner_consent" && optionId === "owner") return "home";
  if (optionId === "make_or_process") return "factory";
  if (optionId === "finished_goods") return "bag";

  if (optionId.includes("dessert") || optionId.includes("cafe") || optionId.includes("coffee")) return "coffee";
  if (optionId.includes("takeout") || optionId.includes("package") || optionId.includes("pickup")) return "bag";
  if (optionId.includes("alcohol") || optionId.includes("liquor") || optionId.includes("drink")) return "wine";
  if (optionId.includes("yes") || optionId.includes("cook")) return "utensils";
  if (optionId.includes("signage")) return "signpost";
  if (optionId.includes("outdoor")) return "store";
  if (optionId.includes("lpg")) return "fan";
  if (optionId.includes("online")) return "monitor";
  if (optionId.includes("transfer")) return "refresh";
  if (optionId.includes("new")) return "fileCheck";
  return "help";
}

export function iconForDecision(type: DecisionBlock["type"]): IconName {
  if (type === "ready_for_documents") return "fileCheck";
  if (type === "needs_user_decision") return "help";
  return "search";
}
