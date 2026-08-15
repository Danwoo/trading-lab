import { apiCall } from "@/utils/common/api/client";
import { fetchSSE } from "@/utils/common/api/sse";

// 프론트 프록시 경로(#146 컨벤션) → bot-agent-service prefix "/bot-agent"
const BASE_URL = "/api/external/bot-agent/bot-agent";

/** 대화를 걸 수 있는 상태인가. `ready=false` 면 `reasons` 가 비어 있지 않다. */
export interface BotAgentReadiness {
  ready: boolean;
  reasons: string[];
  strategies_dir: string;
}

/**
 * 대화 한 턴이 내는 이벤트. 정본은 `bot-agent-service/app/services/bot_agent/bot_agent_service.py`.
 * `unavailable` 은 **정상 응답**이다 — 키가 없을 때 조용히 비는 대신 이유를 담아 오는 것.
 */
export type BotAgentEvent =
  | { type: "text"; text: string }
  | { type: "tool"; name: string }
  | { type: "result"; subtype: string }
  | { type: "unavailable"; reasons: string[] }
  | { type: "error"; message: string };

/**
 * 준비 상태 조회. 서비스가 안 떠 있으면 예외가 아니라 **이유**로 바꿔 돌려준다 —
 * 로컬 배포 모드 전용 서비스라 「안 떠 있음」이 정상적인 상태 중 하나다.
 */
export const selectBotAgentReadiness = async (): Promise<BotAgentReadiness> => {
  try {
    const result = await apiCall<BotAgentReadiness>(`${BASE_URL}/readiness`, { method: "GET" });
    return result ?? { ready: false, reasons: ["대화 서비스가 응답하지 않았습니다."], strategies_dir: "" };
  } catch {
    return {
      ready: false,
      reasons: ["봇 대화 서비스에 연결하지 못했습니다 (로컬 배포 모드에서만 함께 뜹니다)."],
      strategies_dir: "",
    };
  }
};

/** 대화 한 턴을 스트리밍한다. 이벤트는 오는 대로 `onEvent` 로 흘린다. */
export const streamBotAgent = async (
  message: string,
  onEvent: (event: BotAgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> => {
  await fetchSSE<BotAgentEvent>({ url: BASE_URL, body: { message }, onChunk: onEvent, signal });
};
