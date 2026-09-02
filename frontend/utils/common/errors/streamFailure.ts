// utils/common/errors/streamFailure.ts
//
// 스트리밍 대화(봇 만들기·리서치 챗)의 실패를 **사유 코드**로 옮긴다 (#423). #342 가 메일 발송에
// 세운 것과 같은 구조를 스트리밍 표면으로 넓힌 것이고, 새 방식이 아니다 — 봉투를 건너는 것은
// 이 닫힌 집합의 코드뿐이고 화면 문구는 받는 쪽이 자기 언어 표(`locale/*/apierrors.ts`)에서
// 고른다. 그래서 업스트림 URL·포트·소켓 오류 원문·스택이 화면에 실릴 자리가 없다.
//
// 왜 필요했나: 이 화면들은 **원인을 이미 알고 있었다.** 프록시는 「연결 자체가 안 됐다」를
// 알고, 봇 대화 서비스는 「키 인증이 거부됐다」를 안다. 그런데 그 사실이 5xx 봉투에 담겨
// `apierrors.ts` 의 5xx 차단에 걸리는 바람에 화면에는 「잠시 후 다시 시도해 주세요」만 남았다 —
// **다시 시도해도 안 되는** 실패에 재시도를 시켰다.
//
// 서버(프록시 라우트·bot-agent-service)와 클라이언트(`errors/apierrors.ts`)가 함께 쓰므로
// 순수 모듈이다 — env·next 를 물지 않는다.

export const STREAM_FAILURE_CODES = [
  /** 봇 대화 서비스(:8011)에 연결하지 못했다 — 처방은 기동이다. */
  "botAgent.service_unreachable",
  /** 키는 설정돼 있는데 인증이 거부됐다 — 처방은 키 교체다. */
  "botAgent.invalid_api_key",
  /** 그 밖의 이유로 대화 한 턴이 끝까지 가지 못했다. */
  "botAgent.turn_failed",
  /** 리서치 서비스(:8003)에 연결하지 못했다 — 처방은 기동이다. */
  "research.service_unreachable",
] as const;

export type StreamFailureCode = (typeof STREAM_FAILURE_CODES)[number];

/**
 * **HTTP 봉투로 발행되는** 사유와 그 상태.
 *
 * 여기 있는 둘만 프록시 라우트가 응답 자체로 낸다 — 업스트림에 **연결이 안 된** 경우라 스트림이
 * 시작조차 못 했고, 그래서 상태를 고를 수 있다. 나머지 사유(`invalid_api_key`·`turn_failed`)는
 * 스트림이 이미 열린 뒤에 정해지므로 **200 안의 `error` 이벤트**로만 발행된다 — 그 자리엔 상태가
 * 없다. 실제로 발행되지 않는 상태를 표에 남기면, 읽는 사람이 없는 경로를 있다고 읽는다.
 *
 * 화면 문구는 상태가 아니라 `code` 로 건너가므로 `apierrors.ts` 의 5xx 차단(서버가 쓴 문장을
 * 화면에 싣지 않는다)은 그대로 선다.
 */
export const STREAM_FAILURE_HTTP_STATUS = {
  "botAgent.service_unreachable": 503,
  "research.service_unreachable": 503,
} as const satisfies Partial<Record<StreamFailureCode, number>>;

/** HTTP 봉투로 낼 수 있는 사유 — `createStreamFailureResponse` 가 이 집합만 받는다. */
export type HttpStreamFailureCode = keyof typeof STREAM_FAILURE_HTTP_STATUS;

export function isStreamFailureCode(value: unknown): value is StreamFailureCode {
  return typeof value === "string" && (STREAM_FAILURE_CODES as readonly string[]).includes(value);
}

/**
 * 이 예외가 실어 온 사유 코드 — 없으면 null.
 *
 * `getApiErrorMessage` 가 문구를 고를 때도, 화면이 「이 실패는 배너로도 말해야 하는가」를
 * 가를 때도 같은 자리를 본다. 닫힌 집합에 없는 값은 통과시키지 않는다 — 서버가 아무 문자열이나
 * 실어 화면 분기를 바꾸는 손잡이를 만들지 않는다.
 */
export function getStreamFailureCode(error: unknown): StreamFailureCode | null {
  const code = (error as { response?: { data?: { code?: unknown } } })?.response?.data?.code;
  return isStreamFailureCode(code) ? code : null;
}

/**
 * 업스트림에 **연결 자체가 안 된** 실패인가 — 「응답이 이상하다」와 가른다.
 *
 * Node 의 `fetch`(undici)는 연결 실패를 `TypeError: fetch failed` 로 던지고 진짜 원인은
 * `cause` 에 넣는다. axios 경로는 `response` 없이 `code` 를 자기 몸에 단다. 둘 다 본다.
 * 원문(호스트·IP)은 여기서 버려진다 — 호출자는 참/거짓만 받는다.
 */
export function isUpstreamUnreachable(error: unknown): boolean {
  const CONNECT_CODES = new Set([
    "ECONNREFUSED",
    "ECONNRESET",
    "ETIMEDOUT",
    "EHOSTUNREACH",
    "ENETUNREACH",
    "ENOTFOUND",
    "EAI_AGAIN",
    "UND_ERR_CONNECT_TIMEOUT",
    "UND_ERR_SOCKET",
  ]);
  const candidates = [error, (error as { cause?: unknown })?.cause];
  for (const candidate of candidates) {
    const code = (candidate as { code?: unknown })?.code;
    if (typeof code === "string" && CONNECT_CODES.has(code)) return true;
    // AggregateError — 주소가 여럿(IPv4/IPv6)이면 undici 가 개별 오류를 묶어 낸다.
    const errors = (candidate as { errors?: unknown })?.errors;
    if (Array.isArray(errors) && errors.some((e) => typeof e?.code === "string" && CONNECT_CODES.has(e.code))) {
      return true;
    }
  }
  return false;
}
