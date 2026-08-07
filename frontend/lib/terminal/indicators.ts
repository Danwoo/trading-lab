import type { Candle } from "@/services/terminal/marketService";

/**
 * 단순 이동평균(SMA). **기간보다 짧은 구간은 결과에서 제외한다** — 앞을 0 으로 채우면 차트에
 * 실제로 없던 값이 선으로 그려진다(#242 O6 계약). `candles` 가 오름차순(과거→최근)이라고
 * 가정한다 — 호출자(차트 패널)가 이미 그 순서로 받는다.
 */
export function simpleMovingAverage(candles: Candle[], period: number): Array<{ time: string; value: number }> {
  if (period <= 0) return [];

  const result: Array<{ time: string; value: number }> = [];
  for (let i = period - 1; i < candles.length; i += 1) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j += 1) {
      sum += candles[j].close;
    }
    result.push({ time: candles[i].time, value: sum / period });
  }
  return result;
}
