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
  /** `code` 는 닫힌 집합의 사유 코드 — 화면 문구는 클라이언트 표가 고른다 (#423). */
  | { type: "error"; message: string; code?: string };

/**
 * 서비스가 안 떠 있을 때의 배너 문구.
 *
 * 준비 조회 실패와 **전송 실패**가 같은 말을 하게 하려고 한 자리에 둔다 — 종전에는 배너만
 * 「기동하라」를 알고 실패 턴은 「잠시 후 다시 시도」라고 말해 둘이 딴말을 했다 (#423 F4).
 */
export const BOT_AGENT_DOWN_REASONS = [
  "봇 대화 서비스(:8011)가 떠 있지 않습니다 — process-compose 에 없어 손으로 띄웁니다.",
  "cd bot-agent-service/app && APP_ENV=development uv run uvicorn main:app --reload --port 8011",
];

/**
 * 키가 **설정은 됐는데 인증이 거부됐을** 때의 배너 문구.
 *
 * 준비 조회는 키가 비었는지만 본다 — 「설정됨」이지 「유효함」이 아니다. 그 차이는 대화를 실제로
 * 걸어야 드러나고, 드러난 순간 화면이 그것을 말해야 한다 (#423 F5 — 종전에는 배너가 없었다).
 */
export const BOT_AGENT_KEY_REJECTED_REASONS = [
  "ANTHROPIC_API_KEY 는 설정돼 있지만 인증이 거부됐습니다 — 준비 상태 검사는 「설정됨」만 봅니다.",
  "키를 교체한 뒤 다시 보내세요 (.env 의 프로세스 환경변수).",
];

/**
 * 준비 상태 조회. 서비스가 안 떠 있으면 예외가 아니라 **이유**로 바꿔 돌려준다 —
 * 로컬 배포 모드 전용 서비스라 「안 떠 있음」이 정상적인 상태 중 하나다.
 */
export const selectBotAgentReadiness = async (): Promise<BotAgentReadiness> => {
  try {
    const result = await apiCall<BotAgentReadiness>(`${BASE_URL}/readiness`, { method: "GET" });
    return result ?? { ready: false, reasons: ["대화 서비스가 응답하지 않았습니다."], strategies_dir: "" };
  } catch {
    return { ready: false, reasons: BOT_AGENT_DOWN_REASONS, strategies_dir: "" };
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
