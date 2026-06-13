import { BrandLogo } from "@/components/shell/BrandLogo";

export function AnalysisLoadingScreen() {
  return (
    <section className="screen active analysis-loading-screen" data-screen="analysis-loading" role="status" aria-live="polite">
      <div className="analysis-loading-main">
        <BrandLogo />
        <div className="analysis-loading-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <h1 className="analysis-loading-title">AI가 분석 중이에요</h1>
        <p className="analysis-loading-sub">필요한 질문과 서류를 찾고 있어요.</p>
        <div className="analysis-loading-track" aria-hidden="true">
          <span />
        </div>
      </div>
    </section>
  );
}
