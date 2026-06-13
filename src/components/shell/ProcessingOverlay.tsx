import { useEffect, useState } from "react";

// LLM 호출처럼 응답이 오래 걸리는 처리 동안, 앱이 멈춘 듯 보이지 않도록
// 진행 중임을 보여주는 오버레이. 빠른 요청에서 깜빡이지 않게 살짝 지연 후 나타나고,
// 긴 처리 동안 안내 문구를 순환시켜 "살아있는" 느낌을 준다.
const MESSAGES = [
  "입력하신 내용을 살펴보고 있어요",
  "관련 인허가 기준을 확인하는 중이에요",
  "필요한 서류를 정리하고 있어요",
  "거의 다 됐어요, 잠시만 기다려 주세요",
];

const SHOW_DELAY_MS = 350;
const MESSAGE_INTERVAL_MS = 2400;

export function ProcessingOverlay({ active }: { active: boolean }) {
  const [visible, setVisible] = useState(false);
  const [messageIndex, setMessageIndex] = useState(0);

  // 빠른 요청에서 깜빡임 방지: active 가 잠깐 이상 지속될 때만 노출
  useEffect(() => {
    if (!active) {
      setVisible(false);
      setMessageIndex(0);
      return;
    }
    const timer = window.setTimeout(() => setVisible(true), SHOW_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [active]);

  // 노출 중일 때만 안내 문구 순환
  useEffect(() => {
    if (!visible) return;
    const interval = window.setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % MESSAGES.length);
    }, MESSAGE_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [visible]);

  if (!visible) return null;

  return (
    <div className="processing-overlay" role="status" aria-live="polite">
      <div className="processing-card">
        <div className="processing-dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <p className="processing-message">{MESSAGES[messageIndex]}</p>
        <div className="processing-bar" aria-hidden="true">
          <span />
        </div>
      </div>
    </div>
  );
}
