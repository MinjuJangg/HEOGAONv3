"use client";

import { useEffect, useState } from "react";
import { ArrowUpIcon } from "@/components/common/Icon";
import { BrandLogo } from "@/components/shell/BrandLogo";

const FOOD_SERVICE_PROMPTS = [
  "연남동에서 디저트 카페를 열고 싶어요",
  "음식점 자리를 인수해서 시작하려고 해요",
  "포장 전문 매장을 준비 중이에요",
  "카페에서 주류도 팔 수 있는지 알고 싶어요",
  "간판까지 같이 준비해야 해요",
  "배달 판매도 함께 할 예정이에요",
];

const PLACEHOLDER_ROTATE_MS = 2800;
const PLACEHOLDER_FADE_MS = 420;

export function LandingScreen({
  inputText,
  error,
  pending,
  onChange,
  onStart,
}: {
  inputText: string;
  error?: string;
  pending: boolean;
  onChange: (value: string) => void;
  onStart: () => void;
}) {
  const [promptIndex, setPromptIndex] = useState(0);
  const [placeholderFading, setPlaceholderFading] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const isEmpty = inputText.trim().length === 0;
  const rotatingPlaceholder = FOOD_SERVICE_PROMPTS[promptIndex];

  useEffect(() => {
    // Pause rotation while typing/focused, and never rotate for users who
    // requested reduced motion (the global CSS guard only stops the CSS fade,
    // not this JS-driven text swap).
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    if (!isEmpty || pending || isFocused || prefersReducedMotion) {
      setPlaceholderFading(false);
      return;
    }

    let fadeTimer: number | undefined;
    const rotateTimer = window.setInterval(() => {
      setPlaceholderFading(true);
      fadeTimer = window.setTimeout(() => {
        setPromptIndex((current) => (current + 1) % FOOD_SERVICE_PROMPTS.length);
        setPlaceholderFading(false);
      }, PLACEHOLDER_FADE_MS);
    }, PLACEHOLDER_ROTATE_MS);

    return () => {
      window.clearInterval(rotateTimer);
      if (fadeTimer) window.clearTimeout(fadeTimer);
    };
  }, [isEmpty, pending, isFocused]);

  return (
    <section className="screen active" data-screen="landing">
      <div className="landing-brand">
        <BrandLogo />
      </div>
      <div className="landing-main">
        <h1 className="hero-title">어떤 가게를 준비하나요?</h1>
        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            onStart();
          }}
        >
          <label className="sr-only" htmlFor="planInput">가게 준비 내용 입력</label>
          <textarea
            className={`composer-field${isEmpty && placeholderFading ? " is-rotating-placeholder" : ""}`}
            id="planInput"
            rows={1}
            placeholder={rotatingPlaceholder}
            maxLength={200}
            value={inputText}
            onChange={(event) => onChange(event.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
          />
          <button
            className="send-button"
            type="submit"
            disabled={pending || inputText.trim().length < 2}
            aria-label="시작하기"
            onClick={(event) => {
              event.preventDefault();
              onStart();
            }}
          >
            <ArrowUpIcon />
          </button>
        </form>
        {error ? <p className="collect-status error-text" role="alert">{error}</p> : null}
      </div>
    </section>
  );
}
