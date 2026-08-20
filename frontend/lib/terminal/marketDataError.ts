import type { Provenance } from "@/types/terminal/provenance";

import { EndpointNotReadyError } from "./errors";

/**
 * 백엔드 `unavailable_code` 의 값 — `backend-service/app/providers/base.py` 의
 * `CREDENTIAL_MISSING_CODE` 와 같은 문자열이어야 한다. 「키가 아직 없다」일 때만 화면이
 * 임시 데이터로 골조를 보여준다.
 */
export const CREDENTIAL_MISSING_CODE = "credential_missing";

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

/**
 * 사유가 붙은 빈 응답을 provenance 로 옮긴다.
 *
 * 「키가 아직 없다」(`credential_missing`)만 임시 데이터로 골조를 보여준다 — 결정 로그
 * 2026-07-28 「소스 미확보 패널은 골조는 만들고 임시 데이터임을 화면에 표시한다」. 사유는
 * `hint` 에 그대로 실어, 임시로 그린 화면에서도 「키를 넣어야 진짜 값이 온다」가 안 사라지게 한다.
 *
 * 코드가 없는 사유(제공 범위 밖·상류 장애·혼합)는 `unavailable` 그대로다. 여기서 문구를 보고
 * 가르지 않는 이유 — 문구만 바뀌어도 판정이 조용히 갈린다(그래서 백엔드가 코드를 준다).
 */
export function provenanceForUnavailable(reason: string, code: string | null): Provenance {
  if (code === CREDENTIAL_MISSING_CODE) {
    return { kind: "placeholder", source: "임시 데이터", hint: reason };
  }
  return { kind: "unavailable", reason, because: "no-source" };
}
