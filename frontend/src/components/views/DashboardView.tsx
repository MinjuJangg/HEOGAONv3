import { Icon, type IconName } from "@/components/common/Icon";
import type { DashboardSection, DashboardSectionItem, DashboardView as DashboardViewModel, FlowActionId } from "@/types/flow";

export function DashboardView({
  view,
  onContinue,
  onAction,
  continueDisabled,
}: {
  view: DashboardViewModel;
  onContinue: () => void;
  onAction: (actionId: FlowActionId) => void;
  continueDisabled: boolean;
}) {
  const stats = [
    { label: "서류", value: view.summary.documents },
    { label: "확인 필요", value: `${view.summary.unknownFields}개` },
    { label: "답변", value: `${view.summary.answeredQuestions}개` },
  ];
  const sections = view.sections?.length ? view.sections : fallbackSections(view);

  return (
    <>
      <section className="question-card dashboard-hero">
        <h1 className="question-title">{view.title}</h1>
        <p className="question-sub">새로 생긴 일과 남은 일을 확인하세요.</p>
        <div className="dashboard-stat-strip" aria-label="진행 현황 수치">
          {stats.map((stat) => (
            <span className="dashboard-stat-chip" key={stat.label}>
              <strong>{stat.value}</strong>
              <small>{stat.label}</small>
            </span>
          ))}
        </div>
        <div className="dashboard-continue">
          <span className="dashboard-continue-copy">
            <small>다음 할 일</small>
            <strong>{view.nextActions[0] || view.nextButtonLabel}</strong>
          </span>
          <button className="dashboard-continue-button" type="button" disabled={continueDisabled} onClick={onContinue}>
            <span>{view.nextButtonLabel}</span>
            <Icon name="arrowRight" size={18} />
          </button>
        </div>
      </section>
      <div className="summary-view dashboard-view">
        {sections.map((section) => (
          <DashboardSectionView section={section} onAction={onAction} key={section.id} />
        ))}
      </div>
    </>
  );
}

function DashboardSectionView({ section, onAction }: { section: DashboardSection; onAction: (actionId: FlowActionId) => void }) {
  return (
    <section className={`dashboard-section dashboard-section--${section.id}`}>
      <div className="dashboard-section-head">
        <span className="dashboard-section-icon" aria-hidden="true"><Icon name={section.icon} /></span>
        <span className="dashboard-section-main">
          <span className="dashboard-section-title-row">
            <h2 className="dashboard-section-title">{section.title}</h2>
            {section.badge ? <span className="dashboard-section-badge">{section.badge}</span> : null}
          </span>
          {section.subtitle ? <span className="dashboard-section-subtitle">{section.subtitle}</span> : null}
        </span>
      </div>
      {section.items.length ? (
        <ul className="dashboard-work-list">
          {section.items.map((item) => <DashboardWorkItem item={item} onAction={onAction} key={item.id} />)}
        </ul>
      ) : (
        <p className="dashboard-empty">{section.empty || "표시할 항목이 없어요."}</p>
      )}
    </section>
  );
}

function DashboardWorkItem({ item, onAction }: { item: DashboardSectionItem; onAction: (actionId: FlowActionId) => void }) {
  const className = `dashboard-work-item dashboard-work-item--${item.tone}${item.actionId ? " dashboard-work-item--button" : ""}`;
  const content = (
    <>
      <span className="dashboard-work-marker" aria-hidden="true"><Icon name={iconForTone(item.tone)} /></span>
      <span className="dashboard-work-main">
        <span className="dashboard-work-title-row">
          <strong className="dashboard-work-title">{item.title}</strong>
          <span className={`dashboard-work-status dashboard-work-status--${item.tone}`}>{item.statusLabel}</span>
        </span>
        <span className="dashboard-work-description">{item.description}</span>
        {item.meta ? <span className="dashboard-work-meta">{item.meta}</span> : null}
      </span>
      {item.actionId ? <span className="dashboard-work-arrow" aria-hidden="true"><Icon name="arrowRight" size={17} /></span> : null}
    </>
  );

  if (item.actionId) {
    return (
      <li>
        <button className={className} type="button" onClick={() => onAction(item.actionId as FlowActionId)}>
          {content}
        </button>
      </li>
    );
  }

  return (
    <li className={className}>
      {content}
    </li>
  );
}

function iconForTone(tone: DashboardSectionItem["tone"]): IconName {
  if (tone === "updated") return "refresh";
  if (tone === "new") return "search";
  if (tone === "done") return "check";
  if (tone === "pending") return "message";
  return "fileCheck";
}

function fallbackSections(view: DashboardViewModel): DashboardSection[] {
  return [
    {
      id: "next_actions",
      title: "다음 할 일",
      subtitle: "위 항목부터 진행하세요.",
      icon: "list",
      badge: `${view.nextActions.length}개`,
      empty: "남은 할 일이 없어요.",
      items: view.nextActions.map((action, index) => ({
        id: `fallback-${index}`,
        title: action,
        description: "바로 처리할 항목입니다.",
        statusLabel: "대기",
        tone: "pending",
      })),
    },
  ];
}
