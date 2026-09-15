import type { EquityPointOut } from "@/schemas/backtest/backtest";

/** 엔진이 **실제로 훑은** 구간 — 요청 구간과 다를 수 있다. */
export interface ScannedRange {
  from: string;
  to: string;
  /** 자산곡선의 점 수 = 훑은 봉 수 */
  bars: number;
}

/** `dt` 가 시각까지 실어 와도 화면이 읽는 것은 날짜다. */
function dateOf(dt: string): string {
  return dt.slice(0, 10);
}

/**
 * 자산곡선에서 실제로 훑은 구간을 읽는다 — 점이 없으면 `null`.
 *
 * 리포트 머리는 **요청 구간**(`run.period_from ~ run.period_to`)을 적는데, 적재본이 그보다
 * 짧으면 엔진은 있는 만큼만 훑는다. 그 차이가 지금은 연환산 주석 한 줄에서만 새어 나와,
 * 3년을 요청하고 361일을 훑은 실행이 화면에서는 3년짜리 검증으로 읽힌다 — **표본 길이를
 * 세 배로 착각한다.**
 *
 * 없는 값을 지어내지 않는다: 곡선이 비면 `null` 이고, 화면은 「훑은 구간 없음」이라 적는다.
 */
export function scannedRange(equity: EquityPointOut[]): ScannedRange | null {
  const points = equity.filter((point) => typeof point?.dt === "string" && point.dt.length >= 10);
  if (points.length === 0) return null;
  const dates = points.map((point) => dateOf(point.dt)).sort();
  return { from: dates[0], to: dates[dates.length - 1], bars: points.length };
}

/** 요청한 구간을 다 훑었나 — 두 끝이 같아야 참이다. */
export function coversRequest(scanned: ScannedRange | null, from: string, to: string): boolean {
  return scanned !== null && scanned.from === from && scanned.to === to;
}
