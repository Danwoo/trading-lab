"use client";

import { MarkdownRenderer } from "@/components/shared/ui";
import { ResearchMessage } from "@/schemas/researchChat/researchChat";
import { SourceCards } from "./SourceCards";

interface Props {
  message: ResearchMessage;
  streaming?: boolean; // 이 말풍선이 현재 스트리밍 중인지
  statusText?: string; // content 도착 전 진행 단계
  onFollowUpClick?: (question: string) => void; // 후속질문 칩 클릭
}

/**
 * user/assistant 말풍선. 근거·후속질문 슬롯 포함.
 * 근거(media)는 답변 토큰 전에 도착하므로 spinner 단계에서도 함께 보인다(§3.2).
 */
export function MessageBubble({ message, streaming, statusText, onFollowUpClick }: Props) {
  const isUser = message.role === "user";
  const hasSources = !isUser && !!message.sources?.length;
  const showFollowUps = !isUser && !streaming && !!message.followUps?.length;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={isUser ? "max-w-[80%]" : "w-full"}>
        <div className={`rounded-lg p-3 ${isUser ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-800"}`}>
          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : (
            <>
              {streaming && !message.content.trim() ? (
                <div className="flex items-center gap-2 text-sm text-gray-400" role="status">
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span>{statusText || "답변을 준비하고 있습니다..."}</span>
                </div>
              ) : (
                <>
                  <MarkdownRenderer content={message.content} />
                  {streaming && message.content && (
                    <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-gray-500 align-middle" />
                  )}
                </>
              )}
              {hasSources && <SourceCards sources={message.sources!} />}
            </>
          )}
        </div>
        {showFollowUps && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.followUps!.map((question, index) => (
              <button
                key={`${question}-${index}`}
                type="button"
                onClick={() => onFollowUpClick?.(question)}
                className="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs text-gray-600 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
              >
                {question}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
