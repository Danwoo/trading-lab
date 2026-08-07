"use client";

import { MarkdownRenderer } from "@/components/shared/ui";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  scopeKey?: string; // 이 턴이 전송된 검색 조건 식별자 (history 경계 판정용 — 화면 표시 안 함)
}

interface Props {
  message: ChatMessage;
  streaming?: boolean; // 이 말풍선이 현재 스트리밍 중인지
  statusText?: string; // content 도착 전 진행 단계
}

export function MessageBubble({ message, streaming, statusText }: Props) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={isUser ? "max-w-[80%]" : "w-full"}>
        <div className={`rounded-lg p-3 ${isUser ? "bg-blue-500 text-white" : "bg-gray-100 text-gray-800"}`}>
          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : streaming && !message.content.trim() ? (
            <div className="flex items-center gap-2 text-gray-400 text-sm">
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span>{statusText || "답변을 준비하고 있습니다..."}</span>
            </div>
          ) : (
            <>
              <MarkdownRenderer content={message.content} />
              {streaming && message.content && (
                <span className="inline-block w-0.5 h-4 bg-gray-500 ml-0.5 align-middle animate-pulse" />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
