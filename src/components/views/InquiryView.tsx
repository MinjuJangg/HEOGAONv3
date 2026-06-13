"use client";

import { useState } from "react";
import { Icon, channelIcon, channelTitle } from "@/components/common/Icon";
import type { InquiryView as InquiryViewModel } from "@/types/flow";

export function InquiryView({
  view,
  value,
  onChange,
  onChannel,
}: {
  view: InquiryViewModel;
  value: string;
  onChange: (value: string) => void;
  onChannel: (channel: "phone" | "online" | "visit") => void;
}) {
  const task = view.task;
  const [copyStatus, setCopyStatus] = useState("");

  async function copyOnlineDraft() {
    try {
      await navigator.clipboard.writeText(view.onlineDraft.body);
      setCopyStatus("복사 완료");
    } catch {
      setCopyStatus("복사 실패");
    }
  }

  if (!task) {
    return (
      <section className="question-card">
        <h1 className="question-title">문의할 일이 없어요</h1>
      </section>
    );
  }

  if (view.mode === "channels") {
    return (
      <>
        <section className="question-card">
          <h1 className="question-title">{view.title}</h1>
        </section>
        <div className="summary-view">
          <section className="inquiry-contact-hero">
            <p className="inquiry-contact-eyebrow">담당 부서</p>
            <h2 className="inquiry-contact-name">{task.department}</h2>
            <p className="inquiry-contact-task">{task.reason}</p>
          </section>
          <section className="summary-review">
            <ul className="inquiry-method-list">
              {view.channels.map((channel) => (
                <li className="inquiry-method-item" key={channel.id}>
                  <button className="inquiry-method-button" type="button" onClick={() => onChannel(channel.id)}>
                    <span className="inquiry-method-icon" aria-hidden="true"><Icon name={channelIcon(channel.id)} /></span>
                    <span className="inquiry-method-main">
                      <span className="inquiry-method-title">{channel.title}</span>
                      <span className="inquiry-method-hint">{channel.description}</span>
                    </span>
                    <span className="inquiry-method-arrow"><Icon name="arrowRight" size={16} /></span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </>
    );
  }

  return (
    <>
      <section className="question-card">
        <h1 className="question-title">{channelTitle(view.mode)}</h1>
        <p className="question-sub">{task.title}</p>
      </section>
      <div className="summary-view">
        {view.mode === "phone" ? (
          <section className="summary-review">
            <div className="phone-card">
              <p className="phone-department">{task.department}</p>
              <a className="phone-number" href={task.phone || "tel:120"}>전화 연결</a>
              <p className="phone-task">{task.reason}</p>
            </div>
          </section>
        ) : null}
        {view.mode === "online" ? (
          <section className="summary-review">
            <div className="summary-review-title-row summary-review-title-row--with-action">
              <span aria-hidden="true"><Icon name="monitor" /></span>
              <h2 className="summary-review-title">문의 글</h2>
              <button className="online-copy-button" type="button" onClick={copyOnlineDraft}>
                <Icon name="copy" size={16} />
                <span>복사</span>
              </button>
            </div>
            <div className="detail-box">
              <textarea className="followup-field" value={view.onlineDraft.body} readOnly rows={9} />
            </div>
            <p className="online-copy-status" role="status" aria-live="polite">{copyStatus}</p>
          </section>
        ) : null}
        {view.mode === "visit" ? (
          <section className="summary-review">
            <div className="summary-review-title-row">
              <span aria-hidden="true"><Icon name="home" /></span>
              <h2 className="summary-review-title">방문할 곳</h2>
            </div>
            <p className="summary-review-subtitle">{task.visitHint}</p>
          </section>
        ) : null}
        <section className="summary-review">
          <div className="summary-review-title-row">
            <span aria-hidden="true"><Icon name="message" /></span>
            <h2 className="summary-review-title">물어볼 것</h2>
          </div>
          <ol className="phone-question-list">
            {task.questions.map((question, index) => (
              <li className="phone-question-item" key={question}>
                <span className="phone-question-index">{index + 1}</span>
                <span className="phone-question-text">{question}</span>
              </li>
            ))}
          </ol>
        </section>
        <section className="summary-review">
          <div className="summary-review-title-row">
            <span aria-hidden="true"><Icon name="edit" /></span>
            <h2 className="summary-review-title">받은 답변</h2>
          </div>
          <div className="detail-box">
            <textarea
              className="followup-field"
              value={value}
              onChange={(event) => onChange(event.target.value)}
              placeholder="받은 답변을 적어주세요."
              rows={6}
            />
          </div>
        </section>
      </div>
    </>
  );
}
