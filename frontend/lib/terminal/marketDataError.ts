import { EndpointNotReadyError } from "./errors";

export type MarketDataErrorOutcome = { kind: "placeholder" } | { kind: "error"; error: Error };

/**
 * 세 갈래 훅이 공유하는 유일한 경계: `EndpointNotReadyError` 만 임시 데이터로 흡수하고,
 * 그 외 예외는 흡수하지 않고 그대로 올린다 (NFR-001 — 임시 데이터로 뭉뚱그리면 진짜 장애가
 * 조용히 숨는다). 훅 자체는 렌더 테스트 없이(jsdom 미도입) 이 순수 함수로 경계를 검증한다.
 */
export function classifyMarketDataError(error: unknown): MarketDataErrorOutcome {
  if (error instanceof EndpointNotReadyError) {
    return { kind: "placeholder" };
  }
  return { kind: "error", error: error instanceof Error ? error : new Error(String(error)) };
}
