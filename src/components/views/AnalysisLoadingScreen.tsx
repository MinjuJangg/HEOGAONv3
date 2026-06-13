import { Icon } from "@/components/common/Icon";
import { BrandLogo } from "@/components/shell/BrandLogo";

export function AnalysisLoadingScreen() {
  return (
    <section className="screen active analysis-loading-screen" data-screen="analysis-loading" role="status" aria-live="polite">
      <div className="analysis-loading-main">
        <BrandLogo />
        <div className="analysis-loading-mark" aria-hidden="true">
          <Icon name="search" size={30} />
        </div>
        <h1 className="analysis-loading-title">필요한 내용을 확인하고 있어요</h1>
        <p className="analysis-loading-sub">입력하신 내용을 바탕으로 필요한 서류와 진행 가능 여부를 살펴보고 있어요.</p>
        <div className="analysis-loading-bar" aria-hidden="true">
          <span />
        </div>
      </div>
    </section>
  );
}
