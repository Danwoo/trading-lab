// 리서치 챗 트랜스크립트 상태 — 순수 reducer (React·DOM·localStorage 의존 없음).
// 컨테이너에서 분리해 둔 이유는 줄 수가 아니라 테스트 가능성이다: 스트리밍 도중 끊김·중복 클릭 같은
// 불변식은 화면을 띄우지 않고 여기서만 재현·고정할 수 있다 (tests/components/features/ResearchChat/).

import { ResearchSession, ResearchSource } from "@/schemas/researchChat/researchChat";

export interface State {
  sessions: ResearchSession[];
  activeGid: number | null;
}

export type Action =
  | { type: "HYDRATE"; state: State }
  | { type: "NEW_SESSION"; gid: number }
  | { type: "SELECT_SESSION"; gid: number }
  | { type: "DELETE_SESSION"; gid: number }
  | { type: "APPEND_USER_MSG"; gid: number; text: string }
  | { type: "START_ASSISTANT_MSG"; gid: number }
  | { type: "APPEND_DELTA"; gid: number; text: string }
  | { type: "SET_SOURCES"; gid: number; sources: ResearchSource[] }
  | { type: "SET_TITLE"; gid: number; title: string }
  | { type: "SET_FOLLOWUPS"; gid: number; followUps: string[] }
  | { type: "END_ASSISTANT_MSG"; gid: number }
  | { type: "ABORT_ASSISTANT_MSG"; gid: number };

export const INITIAL: State = { sessions: [], activeGid: null };

// 한 세션의 messages 를 불변 갱신하는 헬퍼.
function updateSession(state: State, gid: number, update: (session: ResearchSession) => ResearchSession): State {
  return {
    ...state,
    sessions: state.sessions.map((s) => (s.gid === gid ? update(s) : s)),
  };
}

// 마지막 assistant 메시지를 불변 갱신.
function updateLastAssistant(
  session: ResearchSession,
  update: (message: ResearchSession["messages"][number]) => ResearchSession["messages"][number],
): ResearchSession {
  const messages = [...session.messages];
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "assistant") {
      messages[i] = update(messages[i]);
      return { ...session, messages };
    }
  }
  return session;
}

export function researchChatReducer(state: State, action: Action): State {
  switch (action.type) {
    case "HYDRATE":
      return action.state;

    case "NEW_SESSION": {
      if (state.sessions.some((s) => s.gid === action.gid)) {
        return { ...state, activeGid: action.gid }; // 같은 ms 중복 클릭 방어 — 새로 만들지 않음
      }
      const session: ResearchSession = { gid: action.gid, title: "", messages: [], createdAt: action.gid };
      return { sessions: [session, ...state.sessions], activeGid: action.gid };
    }

    case "SELECT_SESSION":
      return { ...state, activeGid: action.gid };

    case "DELETE_SESSION": {
      const sessions = state.sessions.filter((s) => s.gid !== action.gid);
      const activeGid = state.activeGid === action.gid ? (sessions[0]?.gid ?? null) : state.activeGid;
      return { sessions, activeGid };
    }

    case "APPEND_USER_MSG":
      return updateSession(state, action.gid, (s) => ({
        ...s,
        messages: [...s.messages, { role: "user", content: action.text }],
      }));

    case "START_ASSISTANT_MSG":
      return updateSession(state, action.gid, (s) => ({
        ...s,
        messages: [...s.messages, { role: "assistant", content: "" }],
      }));

    case "APPEND_DELTA":
      return updateSession(state, action.gid, (s) =>
        updateLastAssistant(s, (m) => ({ ...m, content: m.content + action.text })),
      );

    case "SET_SOURCES":
      return updateSession(state, action.gid, (s) =>
        updateLastAssistant(s, (m) => ({ ...m, sources: action.sources })),
      );

    case "SET_FOLLOWUPS":
      return updateSession(state, action.gid, (s) =>
        updateLastAssistant(s, (m) => ({ ...m, followUps: action.followUps })),
      );

    case "SET_TITLE":
      return updateSession(state, action.gid, (s) => ({ ...s, title: action.title }));

    case "END_ASSISTANT_MSG":
      // 백엔드 title 이벤트가 없었으면 첫 사용자 질문으로 세션 제목 보완.
      return updateSession(state, action.gid, (s) => {
        if (s.title) return s;
        const firstUser = s.messages.find((m) => m.role === "user");
        return firstUser ? { ...s, title: firstUser.content.slice(0, 40) } : s;
      });

    case "ABORT_ASSISTANT_MSG":
      // 부분 답변이 있으면 보존, 아무 내용/근거도 없으면 빈 말풍선 제거.
      return updateSession(state, action.gid, (s) => {
        const last = s.messages[s.messages.length - 1];
        if (last && last.role === "assistant" && !last.content.trim() && !last.sources?.length) {
          return { ...s, messages: s.messages.slice(0, -1) };
        }
        return s;
      });

    default:
      return state;
  }
}
