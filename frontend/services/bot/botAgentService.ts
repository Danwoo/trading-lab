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
  /** 대화가 폼을 채운다 — 값은 도구 호출로만 온다(글에서 파싱하지 않는다). */
  | { type: "proposal"; strategy_key: string; params: Record<string, unknown>; note: string | null }
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
      reasons: [
        "봇 대화 서비스(:8011)가 떠 있지 않습니다 — process-compose 에 없어 손으로 띄웁니다.",
        "cd bot-agent-service/app && APP_ENV=development uv run uvicorn main:app --reload --port 8011",
      ],
      strategies_dir: "",
    };
  }
};

/** 지금 폼에 들어 있는 값 — 대화가 자기 기억이 아니라 **폼**을 읽게 한다 (스펙 §8.6.1). */
export interface BotFormState {
  strategy_key: string | null;
  params: Record<string, unknown>;
}

/**
 * 대화 한 턴을 스트리밍한다. 이벤트는 오는 대로 `onEvent` 로 흘린다.
 *
 * 세션 id 를 안 보낸다 — 이어갈 대화는 **서버가 신원으로** 고른다(남의 대화를 이어받는
 * 손잡이를 만들지 않는다).
 */
export const streamBotAgent = async (
  message: string,
  onEvent: (event: BotAgentEvent) => void,
  options?: { form?: BotFormState; signal?: AbortSignal },
): Promise<void> => {
  await fetchSSE<BotAgentEvent>({
    url: BASE_URL,
    body: { message, form: options?.form },
    onChunk: onEvent,
    signal: options?.signal,
  });
};
