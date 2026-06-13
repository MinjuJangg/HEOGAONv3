import { Icon, type IconName } from "@/components/common/Icon";

export function ListSection({ title, icon, items, empty }: { title: string; icon: IconName; items: string[]; empty: string }) {
  return (
    <section className="summary-review">
      <div className="summary-review-title-row">
        <span aria-hidden="true"><Icon name={icon} /></span>
        <h2 className="summary-review-title">{title}</h2>
      </div>
      {items.length ? (
        <ul className="missing-summary-list">
          {items.map((item) => (
            <li className="missing-summary-item" key={item}>
              <span className="missing-summary-icon" aria-hidden="true"><Icon name={icon} /></span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="missing-summary-empty">{empty}</p>
      )}
    </section>
  );
}
