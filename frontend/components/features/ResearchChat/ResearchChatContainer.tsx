"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { showToast } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import { streamResearchChat } from "@/services/researchChat/researchChatService";
import { INITIAL, researchChatReducer, State } from "./researchChatReducer";
import { SessionListPanel } from "./SessionListPanel";
import { ConversationPanel } from "./ConversationPanel";

// 세션 트랜스크립트 localStorage 키 (D1: 새로고침 생존, 서버 세션 API 없음).
const STORAGE_KEY = "research-chat-sessions";

export default function ResearchChatContainer() {
  const [state, dispatch] = useReducer(researchChatReducer, INITIAL);
  const [streaming, setStreaming] = useState(false);
  const [statusText, setStatusText] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const hydratedRef = useRef(false); // 복원 완료 전에는 저장하지 않음(빈 상태로 덮어쓰기 방지)

  // 마운트 시 localStorage 복원 (하이드레이션 불일치 회피 — 클라이언트에서만).
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as State;
        if (Array.isArray(parsed.sessions)) dispatch({ type: "HYDRATE", state: parsed });
      }
    } catch {
      // 손상된 저장값 — 무시하고 빈 상태로 시작
    }
    hydratedRef.current = true;
  }, []);

  // 상태 영속 — 스트리밍 중에는 저장하지 않는다(토큰마다 쓰기 방지). 종료 시 최종 상태를 1회 저장.
  useEffect(() => {
    if (!hydratedRef.current || streaming) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // 용량 초과 등 — 영속 실패는 치명적이지 않음(현재 세션은 메모리에 유지)
    }
  }, [state, streaming]);

  const send = useCallback(
    async (question: string) => {
      if (streaming) return;
      let gid = state.activeGid;
      if (gid === null) {
        gid = Date.now();
        dispatch({ type: "NEW_SESSION", gid });
      }
      const targetGid = gid;

      dispatch({ type: "APPEND_USER_MSG", gid: targetGid, text: question });
      dispatch({ type: "START_ASSISTANT_MSG", gid: targetGid });
      setStreaming(true);
      setStatusText("요청을 처리하고 있습니다...");

      const controller = new AbortController();
      abortRef.current = controller;
      try {
        // gid 만 보내면 백엔드가 (email, gid) 로 멀티턴을 이어준다. switch 생략 = 전체 멀티에이전트(D4).
        await streamResearchChat(
          { gid: targetGid, question },
          {
            signal: controller.signal,
            onStatus: (text) => setStatusText(text),
            onDelta: (text) => dispatch({ type: "APPEND_DELTA", gid: targetGid, text }),
            onSources: (sources) => dispatch({ type: "SET_SOURCES", gid: targetGid, sources }),
            onTitle: (title) => dispatch({ type: "SET_TITLE", gid: targetGid, title }),
            onFollowUps: (followUps) => dispatch({ type: "SET_FOLLOWUPS", gid: targetGid, followUps }),
          },
        );
        dispatch({ type: "END_ASSISTANT_MSG", gid: targetGid });
      } catch (error) {
        dispatch({ type: "ABORT_ASSISTANT_MSG", gid: targetGid });
        if (!controller.signal.aborted) {
          showToast(getApiErrorMessage(error), "error");
        }
      } finally {
        setStreaming(false);
        setStatusText("");
        abortRef.current = null;
      }
    },
    [state.activeGid, streaming],
  );

  const abort = useCallback(() => abortRef.current?.abort(), []);

  const newSession = useCallback(() => {
    abortRef.current?.abort(); // 진행 중 스트림 중지
    dispatch({ type: "NEW_SESSION", gid: Date.now() });
  }, []);

  const selectSession = useCallback((gid: number) => dispatch({ type: "SELECT_SESSION", gid }), []);

  const deleteSession = useCallback(
    (gid: number) => {
      if (gid === state.activeGid && streaming) abortRef.current?.abort();
      dispatch({ type: "DELETE_SESSION", gid });
    },
    [state.activeGid, streaming],
  );

  const activeSession = state.sessions.find((s) => s.gid === state.activeGid) ?? null;

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1">
        <SplitPane orientation="horizontal" initialSizes={[24, 76]}>
          {[
            <SessionListPanel
              key="sessions"
              sessions={state.sessions}
              activeGid={state.activeGid}
              onSelect={selectSession}
              onNew={newSession}
              onDelete={deleteSession}
            />,
            <ConversationPanel
              key="conversation"
              session={activeSession}
              streaming={streaming}
              statusText={statusText}
              onSend={send}
              onAbort={abort}
            />,
          ]}
        </SplitPane>
      </div>
    </div>
  );
}
