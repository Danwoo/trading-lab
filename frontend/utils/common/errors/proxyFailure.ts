// utils/common/errors/proxyFailure.ts
//
// 프록시가 **업스트림에 닿지 못한** 실패를 사유 코드로 옮긴다 (#435 B-3). #342(메일)·#423
// (스트리밍)이 세운 것과 같은 구조를 **모든 프록시 라우트가 쓰는 공용 오류 봉투**로 넓힌
// 것이고, 새 방식이 아니다 — 봉투를 건너는 것은 이 닫힌 집합의 코드뿐이고 화면 문구는 받는
// 쪽이 자기 언어 표(`locale/*/apierrors.ts`)에서 고른다. 그래서 내부 호스트·포트·소켓 오류
// 원문이 화면에 실릴 자리가 없다.
//
// 왜 코드가 필요했나: 이 실패는 503 으로 나가는데, `apierrors.ts` 의 5xx 차단은 **서버가 쓴
// 문장**을 통째로 버린다. 그래서 봉투 안에 아무리 정확한 처방을 적어도 화면에는
// 「잠시 후 다시 시도해 주세요」만 남는다 — **다시 시도해도 안 되는** 실패에 재시도를 시킨다.
//
// 서버(`utils/common/api/responses.ts`)와 클라이언트(`errors/apierrors.ts`)가 함께 쓰므로
// 순수 모듈이다 — env·prisma·next 를 물지 않는다.

export const PROXY_FAILURE_CODES = [
  /** 부른 서비스에 연결 자체가 안 됐다 — 처방은 그 서비스의 기동·주소·포트 확인이다. */
  "proxy.upstream_unreachable",
] as const;

export type ProxyFailureCode = (typeof PROXY_FAILURE_CODES)[number];

export function isProxyFailureCode(value: unknown): value is ProxyFailureCode {
  return typeof value === "string" && (PROXY_FAILURE_CODES as readonly string[]).includes(value);
}

/**
 * 이 예외가 실어 온 사유 코드 — 없으면 null.
 *
 * 닫힌 집합에 없는 값은 통과시키지 않는다 — 서버가 아무 문자열이나 실어 화면 문구를 바꾸는
 * 손잡이를 만들지 않는다.
 */
export function getProxyFailureCode(error: unknown): ProxyFailureCode | null {
  const code = (error as { response?: { data?: { code?: unknown } } })?.response?.data?.code;
  return isProxyFailureCode(code) ? code : null;
}
