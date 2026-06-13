import type { DecisionBlock } from "@/types/flow";

export type IconName =
  | "arrowRight"
  | "back"
  | "building2"
  | "check"
  | "close"
  | "copy"
  | "edit"
  | "fan"
  | "fileCheck"
  | "help"
  | "home"
  | "list"
  | "message"
  | "monitor"
  | "phone"
  | "refresh"
  | "search"
  | "signpost"
  | "store"
  | "utensils";

const paths: Record<IconName, string> = {
  arrowRight: '<path d="M7 12h11M14 7l5 5-5 5" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>',
  back: '<path d="M15 19l-7-7 7-7" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>',
  building2: '<path d="M5 21V5a2 2 0 012-2h10a2 2 0 012 2v16M3 21h18M9 7h.01M15 7h.01M9 11h.01M15 11h.01M9 15h.01M15 15h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  check: '<path d="M20 6L9 17l-5-5" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
  close: '<path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.3" stroke-linecap="round"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M16 8V6a2 2 0 00-2-2H6a2 2 0 00-2 2v8a2 2 0 002 2h2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  edit: '<path d="M4 17.5V21h3.5L20.8 8.7l-3.5-3.5L4 17.5zM18 5.5l3 3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  fan: '<circle cx="12" cy="12" r="2" stroke="currentColor" stroke-width="1.9"/><path d="M12 10c.9-3.4 2.6-5.2 4.2-4.4 1.6.8 1.7 3.3-.4 5.6M13.8 13c3.4.9 5.2 2.6 4.4 4.2-.8 1.6-3.3 1.7-5.6-.4M10.2 13C6.8 12.1 5 10.4 5.8 8.8c.8-1.6 3.3-1.7 5.6.4M12 14c-.9 3.4-2.6 5.2-4.2 4.4-1.6-.8-1.7-3.3.4-5.6" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
  fileCheck: '<path d="M7 3h7l4 4v14H7a2 2 0 01-2-2V5a2 2 0 012-2z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M14 3v5h5M9 14l2 2 4-5" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
  help: '<path d="M12 17h.01M9.5 9a2.5 2.5 0 114 2.1c-.9.5-1.5 1.2-1.5 2.4" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="currentColor" stroke-width="2.2"/>',
  home: '<path d="M3 11l9-8 9 8M5 10v9a1 1 0 001 1h3v-6h8v6h3a1 1 0 001-1v-9M7 22h10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  list: '<path d="M5 6h14M5 12h14M5 18h9" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
  message: '<path d="M5 5h14a2 2 0 012 2v8a2 2 0 01-2 2H9l-5 4v-4H5a2 2 0 01-2-2V7a2 2 0 012-2z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/>',
  monitor: '<rect x="3" y="4" width="18" height="12" rx="2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M8 21h8"/><path d="M12 17v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M7 21h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  phone: '<path d="M22 16.92V20a2 2 0 0 1-2.18 2C11.35 21.83 2.17 12.65 2.17 3.18A2 2 0 0 1 4.16 1h3.11a2 2 0 0 1 2 1.72l.6 2.4a2 2 0 0 1-1.1 2.25l-1.33.53a11.36 11.36 0 0 0 4.61 4.61l.53-1.33a2 2 0 0 1 2.25-1.1l2.4.6A2 2 0 0 1 23 8.88v3.11a2 2 0 0 1-1.08 1.76l-2.2.8a1 1 0 0 1-1.12-.38 16 16 0 0 1-2.13-3.18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  refresh: '<path d="M21 12a8.96 8.96 0 01-2.4 6.1L18 16M3 12a8.96 8.96 0 012.4-6.1L6 8M8 3.5V8h4.5M16 21v-4.5h-4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  search: '<circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2"/><path d="M20 20l-3.5-3.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  signpost: '<path d="M12 21V4M6 6h11l2 2-2 2H6V6zM18 13H7l-2 2 2 2h11v-4z" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
  store: '<path d="M4 10h16l-1.2-5.2A1 1 0 0017.8 4H6.2a1 1 0 00-1 .8L4 10z" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M5 10v9h14v-9M9 19v-5h6v5M4 10c0 1.2 1 2.2 2.2 2.2S8.4 11.2 8.4 10c0 1.2 1 2.2 2.2 2.2s2.2-1 2.2-2.2c0 1.2 1 2.2 2.2 2.2s2.2-1 2.2-2.2c0 1.2 1 2.2 2.2 2.2S20 11.2 20 10" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
  utensils: '<path d="M6 3h12M8 3v8a4 4 0 008 0V3M5 21h14M9 17h6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
};

export function Icon({ name, size = 22 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" dangerouslySetInnerHTML={{ __html: paths[name] }} />;
}

export function ArrowUpIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 19V5M5.5 11.5L12 5l6.5 6.5" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function iconForOption(optionId: string): IconName {
  if (optionId.includes("yes") || optionId.includes("cook")) return "utensils";
  if (optionId.includes("no") || optionId === "none") return "check";
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
  if (type === "needs_department_check") return "message";
  if (type === "needs_user_decision") return "help";
  return "search";
}

