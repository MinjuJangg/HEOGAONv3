import { Icon } from "@/components/common/Icon";
import { BrandLogo } from "@/components/shell/BrandLogo";

export interface QuestionProgress {
  width: string;
  label: string;
  current: number;
  total: number;
  stages: Array<{ key: string; label: string }>;
}

export function QuestionHeader({
  progress,
  onBack,
  onHistory,
}: {
  progress: QuestionProgress;
  onBack: () => void;
  onHistory: () => void;
}) {
  return (
    <header className="question-header">
      <div className="question-header-top">
        <div className="header-left">
          <button className="icon-button" type="button" aria-label="처음으로 돌아가기" onClick={onBack}>
            <Icon name="back" />
          </button>
        </div>
        <BrandLogo />
        <div className="header-right">
          <button className="history-button" type="button" aria-label="진행 상황 보기" onClick={onHistory}>
            <Icon name="list" />
          </button>
        </div>
      </div>
      <div className="question-progress">
        <p className="question-progress-caption">
          <span className="question-progress-label">{progress.label}</span>
        </p>
        <div className="question-progress-track">
          {progress.stages.map((stage, index) => (
            <span
              className={`question-progress-segment${index + 1 < progress.current ? " is-complete" : ""}${index + 1 === progress.current ? " is-current" : ""}`}
              aria-label={stage.label}
              key={stage.key}
            />
          ))}
        </div>
        <div className="question-progress-stage-labels" aria-hidden="true">
          {progress.stages.map((stage, index) => (
            <span
              className={`question-progress-stage-label${index + 1 < progress.current ? " is-complete" : ""}${index + 1 === progress.current ? " is-current" : ""}`}
              key={stage.key}
            >
              {stage.label}
            </span>
          ))}
        </div>
      </div>
    </header>
  );
}
