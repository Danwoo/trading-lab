import { describe, expect, it } from "vitest";
import { simpleMovingAverage } from "@/lib/terminal/indicators";
import type { Candle } from "@/services/terminal/marketService";

function makeCandles(closes: number[]): Candle[] {
  return closes.map((close, index) => ({
    time: `2026-01-${String(index + 1).padStart(2, "0")}`,
    open: close,
    high: close,
    low: close,
    close,
    volume: 1000,
  }));
}

describe("simpleMovingAverage", () => {
  it("기간 5, 캔들 10개 → 결과 6개 (앞을 0 으로 채우지 않는다)", () => {
    const candles = makeCandles([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    const result = simpleMovingAverage(candles, 5);
    expect(result).toHaveLength(6);
  });

  it("기간이 캔들 수보다 크면 결과 0개", () => {
    const candles = makeCandles([1, 2, 3]);
    const result = simpleMovingAverage(candles, 5);
    expect(result).toHaveLength(0);
  });

  it("값이 손계산과 일치한다 (캔들 3개·기간 3의 종가 평균)", () => {
    const candles = makeCandles([10, 20, 30]);
    const result = simpleMovingAverage(candles, 3);
    expect(result).toEqual([{ time: candles[2].time, value: 20 }]);
  });

  it("빈 배열 → 빈 배열", () => {
    expect(simpleMovingAverage([], 5)).toEqual([]);
  });
});
