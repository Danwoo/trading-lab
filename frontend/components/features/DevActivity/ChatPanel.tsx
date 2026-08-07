"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { showToast } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import { streamChat } from "@/services/devActivity/devActivityService";
import { ChatRequest, ChatTurn } from "@/schemas/devActivity/devActivity";
import { MessageBubble, ChatMessage } from "./MessageBubble";

const EXAMPLES = [
  "어떤 계좌들이 있어?", // 계좌 목록
  "계좌주가 누구누구야?", // 계좌주 목록
  "연금 계좌 보여줘", // 계좌 목록(범위)
  "최근 2주간 거래가 있던 계좌는?", // 기간 내 활동 계좌(거래 집계)
  "이번 주 매매내역 요약해줘", // 거래 검색(이번주)
  "지난주에 한 거래 정리해줘", // 거래 검색(지난주)
  "이번 달 매도 거래만", // 거래 검색(이번달+유형)
  "최근 배당 입금 내역", // 활동 검색(키워드)
  "이번 주 가장 활발한 계좌는?", // 거래 집계
  "계좌주별 이번 주 거래량", // 거래+계좌주 집계
  "삼성전자 최근 매매 보여줘", // 거래 검색(특정 종목)
  "주식 자산군 최근 비중 변화 정리", // 활동 검색(자산군)
  "지난주에 체결된 주문 있어?", // 주문 검색(체결)
  "지금 미체결 주문 보여줘", // 주문 검색(대기)
  "홍길동 이번 주 활동 타임라인", // 계좌주 활동(named)
  "5월에 어떤 거래들 했어?", // 거래 검색(특정 월)
];

// 현재 ConditionBar/좌측 선택으로 확정된 검색 범위 (질문 전송 시 함께 보냄)
type ChatScope = Omit<ChatRequest, "question" | "history">;

interface Props {
  scope: ChatScope;
  summary: string; // "현재 적용 조건" 표시 문구
}

export function ChatPanel({ scope, summary }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const scrollToBottom = () => requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: "smooth" }));

  const send = async (question: string) => {
    const q = question.trim();
    if (!q || streaming) return;
    // 현재 검색 조건 식별자 — holders 는 선택 순서가 달라도 같은 조건이므로 정렬해 안정화 (순서 변동으로 맥락이 끊기지 않게)
    const scopeKey = JSON.stringify({ ...scope, holders: [...(scope.holders ?? [])].sort() });
    // 같은 검색 조건의 턴만 history 로 동봉 (조건별 독립 대화 스레드).
    // - 조건이 다른 턴은 다른 데이터셋 → 제외해 이전 "기록 없음"/결과가 새 조건 답변을 오염시키는 문제 방지
    // - 조건을 바꿨다 되돌아오면(A→B→A) 그 조건의 과거 맥락이 자연히 되살아남(resume)
    const history: ChatTurn[] = messages
      .filter((m) => m.content && m.scopeKey === scopeKey)
      .map((m) => ({ role: m.role, content: m.content }));
    setInput("");
    setStatus("질문 분석 중…");
    setMessages((prev) => [
      ...prev,
      { role: "user", content: q, scopeKey },
      { role: "assistant", content: "", scopeKey },
    ]);
    setStreaming(true);
    scrollToBottom();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamChat(
        { question: q, ...scope, history: history.slice(-8) }, // 전송 시점의 ConditionBar 조건 + 같은 조건 직전 대화(최근 N턴)
        {
          signal: controller.signal,
          onStatus: (text) => {
            setStatus(text);
            scrollToBottom();
          },
          onDelta: (text) => {
            setMessages((prev) => {
              if (!prev.length) return prev; // 새 대화로 초기화된 직후의 잔여 delta 무시
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, role: "assistant", content: last.content + text }; // scopeKey 보존
              return next;
            });
            scrollToBottom();
          },
        },
      );
    } catch (error) {
      if (controller.signal.aborted) {
        setMessages((prev) => (prev[prev.length - 1]?.content ? prev : prev.slice(0, -1)));
      } else {
        setMessages((prev) => prev.slice(0, -1));
        showToast(getApiErrorMessage(error), "error");
      }
    } finally {
      setStreaming(false);
      setStatus("");
      abortRef.current = null;
    }
  };

  const newChat = () => {
    abortRef.current?.abort(); // 진행 중이면 중지
    setMessages([]);
    setInput("");
    setStatus("");
    setStreaming(false);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="flex-shrink-0 flex items-center justify-between border-b border-gray-100 px-4 py-2">
        <span className="text-sm font-medium text-gray-600">포트폴리오 활동 챗</span>
        <button
          type="button"
          onClick={newChat}
          disabled={messages.length === 0 && !streaming}
          className="flex flex-shrink-0 items-center gap-1 rounded-md px-2.5 py-1 text-xs text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
          title="새 대화 시작 (대화 기록 초기화)"
        >
          <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          새 대화
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center" style={{ width: "min(100%, max(28rem, 70%))" }}>
              <svg
                className="w-10 h-10 mx-auto mb-3 text-gray-300"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
              <div className="text-base font-medium text-gray-500 mb-1">계좌·계좌주·거래내역을 물어보세요</div>
              <div className="text-sm text-gray-400 mb-5">아래 예시를 클릭하거나 직접 질문을 입력하세요</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    type="button"
                    onClick={() => send(ex)}
                    className="text-left px-4 py-2.5 bg-gray-50 hover:bg-blue-50 border border-gray-200 hover:border-blue-200 rounded-lg transition-colors text-gray-600 hover:text-blue-700"
                  >
                    <span className="line-clamp-1">{ex}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((m, i) => (
              <MessageBubble
                key={i}
                message={m}
                streaming={streaming && i === messages.length - 1}
                statusText={status}
              />
            ))}
            <div ref={endRef} />
          </div>
        )}
      </div>

      <div className="flex-shrink-0 px-4 pb-4 pt-2">
        <div className="text-[11px] text-gray-400 mb-1.5 truncate" title={summary}>
          현재 조건: <span className="text-gray-600">{summary}</span>
        </div>
        <div className="rounded-lg border border-gray-300 bg-gray-100 transition-colors focus-within:border-blue-400 focus-within:ring-1 focus-within:ring-blue-400">
          <textarea
            className="w-full resize-none bg-transparent px-3 pt-3 pb-1 text-sm focus:outline-none"
            placeholder="예: 지난주 연금 계좌 매매내역 요약해줘"
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={streaming}
          />
          <div className="flex items-center justify-end px-2 pb-2">
            {streaming ? (
              <button
                type="button"
                className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-red-500 text-white transition-colors hover:bg-red-600"
                onClick={() => abortRef.current?.abort()}
                title="생성 중지"
              >
                <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              </button>
            ) : (
              <button
                type="button"
                className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-blue-500 text-white transition-colors hover:bg-blue-600 disabled:cursor-not-allowed disabled:opacity-40"
                onClick={() => send(input)}
                disabled={!input.trim()}
                title="전송"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
