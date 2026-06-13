"use client";

import { useState } from "react";
import { devViewLabels } from "@/lib/devMocks";
import type { ViewType } from "@/types/flow";

export function DevPanel({
  currentView,
  onLanding,
  onPreview,
}: {
  currentView: ViewType | "landing";
  onLanding: () => void;
  onPreview: (type: ViewType) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <aside className={`dev-panel${open ? " is-open" : ""}`} aria-label="로컬 개발 패널">
      <button className="dev-panel-toggle" type="button" onClick={() => setOpen((value) => !value)}>
        Dev
      </button>
      {open ? (
        <div className="dev-panel-body">
          <div className="dev-panel-head">
            <strong>Local preview</strong>
            <span>{currentView}</span>
          </div>
          <div className="dev-panel-grid">
            <button
              className={`dev-panel-action${currentView === "landing" ? " is-active" : ""}`}
              type="button"
              onClick={onLanding}
            >
              랜딩
            </button>
            {devViewLabels.map((item) => (
              <button
                className={`dev-panel-action${currentView === item.type ? " is-active" : ""}`}
                type="button"
                key={item.type}
                onClick={() => onPreview(item.type)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </aside>
  );
}
