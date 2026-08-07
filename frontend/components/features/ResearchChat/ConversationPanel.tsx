"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ResearchSession } from "@/schemas/researchChat/researchChat";
import { MessageBubble } from "./MessageBubble";

// 투자리서치 도메인 예시 질문 (빈 상태 — placeholder 아님, 실제 클릭 가능).
const EXAMPLES = [
  "업로드한 리서치 보고서 요약해줘",
  "이 종목 리스크 요인 정리해줘",
  "최근 실적 코멘트 근거와 함께",
  "밸류에이션 관련 언급 찾아줘",
  "투자의견 변화 짚어줘",
  "동종업계 비교 내용 있어?",
];

// 자동 스크롤을 강제할 하단 근접 임계값(px). 이 밖으로 올려 읽는 중이면 강제 스크롤 안 함.
const NEAR_BOTTOM_PX = 120;

interface Props {
  session: ResearchSession | null;
  streaming: boolean;
  statusText: string;
  onSend: (question: string) => void;
  onAbort: () => void;
}

/**
 * 대화 패널 — 메시지 리스트 + 입력창 + 스트리밍/중단. 입력창 텍스트만 로컬 상태.
 * 자동 스크롤은 사용자가 하단 근처에 있을 때만(near-bottom) — 과거를 읽는 중이면 방해하지 않는다(§7).
 */
export function ConversationPanel({ session, streaming, statusText, onSend, onAbort }: Props) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const atBottomRef = useRef(true); // 렌더 전 스크롤 위치 기억 (레이아웃 변경 전 판정)

  const messages = session?.messages ?? [];
  const isEmpty = messages.length === 0;
  const lastContent = messages[messages.length - 1]?.content ?? "";

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
  };

  // 메시지/토큰/상태문구가 늘어날 때, 사용자가 하단 근처였을 때만 따라 내려간다.
  useEffect(() => {
    if (atBottomRef.current) {
      requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth" }));
    }
  }, [messages.length, lastContent, statusText]);

  const submit = (question: string) => {
    const q = question.trim();
    if (!q || streaming) return;
    onSend(q);
    setInput("");
    atBottomRef.current = true; // 새 질문 전송 시 하단으로
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(input);
    }
  };

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex-shrink-0 border-b border-gray-100 px-4 py-2">
        <span className="text-sm font-medium text-gray-600">{session?.title || "투자리서치 챗"}</span>
      </div>

      <div ref={scrollRef} onScroll={handleScroll} className="min-h-0 flex-1 overflow-auto p-4">
        {isEmpty ? (
          <div className="flex h-full items-center justify-center text-gray-400">
            <div className="text-center" style={{ width: "min(100%, max(28rem, 70%))" }}>
              <svg
                className="mx-auto mb-3 h-10 w-10 text-gray-300"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
              <div className="mb-1 text-base font-medium text-gray-500">업로드한 리서치 문서를 근거로 물어보세요</div>
              <div className="mb-5 text-sm text-gray-400">아래 예시를 클릭하거나 직접 질문을 입력하세요</div>
              <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                {EXAMPLES.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => submit(example)}
                    className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5 text-left text-gray-600 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                  >
                    <span className="line-clamp-1">{example}</span>
                  </button>
                ))}
              </div>
              <p className="mt-5 text-xs text-gray-400">
                근거로 쓸 리서치 문서는 &lsquo;리서치 문서 관리&rsquo; 화면에서 업로드하세요.
              </p>
            </div>
          </div>
        ) : (
          <div role="log" aria-label="대화 내용" className="space-y-4">
            {messages.map((message, index) => (
              <MessageBubble
                key={index}
                message={message}
                streaming={streaming && index === messages.length - 1}
                statusText={statusText}
                onFollowUpClick={submit}
              />
            ))}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <div className="flex-shrink-0 px-4 pb-4 pt-2">
        <p aria-live="polite" className="mb-1.5 h-4 truncate text-[11px] text-gray-400">
          {streaming ? statusText : ""}
        </p>
        <label htmlFor="research-chat-input" className="sr-only">
          투자리서치 질문 입력
        </label>
        <div className="rounded-lg border border-gray-300 bg-gray-100 transition-colors focus-within:border-blue-400 focus-within:ring-1 focus-within:ring-blue-400">
          <textarea
            id="research-chat-input"
            ref={inputRef}
            className="w-full resize-none bg-transparent px-3 pb-1 pt-3 text-sm focus:outline-none"
            placeholder="예: 업로드한 리서치 보고서의 리스크 요인 정리해줘"
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <div className="flex items-center justify-end px-2 pb-2">
            {streaming ? (
              <button
                type="button"
                className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-red-500 text-white transition-colors hover:bg-red-600"
                onClick={onAbort}
                aria-label="생성 중지"
                title="생성 중지"
              >
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              </button>
            ) : (
              <button
                type="button"
                className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-blue-500 text-white transition-colors hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-40"
                onClick={() => submit(input)}
                disabled={!input.trim()}
                aria-label="전송"
                title="전송"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
