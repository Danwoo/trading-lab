import type { Candle } from "@/services/terminal/marketService";

/**
 * 임시 데이터 — **`provenance.kind === "placeholder"` 분기에서만 쓴다**(#242 O6 계약).
 * 실데이터 경로에서 이 모듈을 import 하면 위반이다(O7 이 룰로 만든다). 백엔드 계약이 없는 동안
 * 차트 패널의 겉모습(캔들·거래량·이동평균 겹침)을 증명하기 위한 영업일 120개짜리 시드 워크다.
 */
const CANDLE_COUNT = 120;
const START_PRICE = 74000;
const SEED = 20260801;

/** 결정적 의사난수 — 매 실행마다 같은 모양의 캔들이 나오게(디버깅 재현성). */
function createSeededRandom(seed: number): () => number {
  let state = seed % 2147483647;
  if (state <= 0) state += 2147483646;
  return () => {
    state = (state * 16807) % 2147483647;
    return (state - 1) / 2147483646;
  };
}

function isWeekend(date: Date): boolean {
  const day = date.getUTCDay();
  return day === 0 || day === 6;
}

/** 오늘부터 거꾸로 영업일(주말 제외) `CANDLE_COUNT`개를 골라 오름차순으로 돌려준다. */
function lastBusinessDays(count: number): Date[] {
  const dates: Date[] = [];
  const cursor = new Date();
  cursor.setUTCHours(0, 0, 0, 0);
  cursor.setUTCDate(cursor.getUTCDate() - 1); // 오늘은 아직 마감되지 않았을 수 있어 어제부터

  while (dates.length < count) {
    if (!isWeekend(cursor)) dates.push(new Date(cursor));
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return dates.reverse();
}

function buildSampleCandles(): Candle[] {
  const random = createSeededRandom(SEED);
  const dates = lastBusinessDays(CANDLE_COUNT);

  let price = START_PRICE;
  return dates.map((date) => {
    const changeRatio = (random() - 0.5) * 0.04; // ±2% 일중 변동
    const open = price;
    const close = Math.max(1, open * (1 + changeRatio));
    const high = Math.max(open, close) * (1 + random() * 0.01);
    const low = Math.min(open, close) * (1 - random() * 0.01);
    const volume = Math.round(500_000 + random() * 1_500_000);

    price = close;

    return {
      time: date.toISOString().slice(0, 10),
      open: Math.round(open),
      high: Math.round(high),
      low: Math.round(low),
      close: Math.round(close),
      volume,
    };
  });
}

export const SAMPLE_CANDLES: Candle[] = buildSampleCandles();
