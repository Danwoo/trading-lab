"use client";

import { create } from "zustand";

/**
 * 적재본이 **실제로 덮는 마지막 거래일** — 캔들을 읽은 자리가 쓰고, 신선도를 말하는 자리가 읽는다.
 *
 * ## 왜 저장소인가
 *
 * 배지(`useQuoteFreshness`)와 차트(`ChartPanel`)는 형제 컴포넌트다. 배지가 캔들을 직접 읽으려고
 * `useLoadedSeries` 를 한 번 더 부르면 **두 소비자가 같은 `group` 을 쓰게 되고**, 한쪽의 정리가
 * `requestQueue.abortGroup(group)` 으로 다른 쪽의 요청을 취소한다. 그래서 읽는 자리를 늘리지 않고,
 * 이미 읽은 값을 여기 놓는다.
 *
 * ## 왜 필요한가 (#402)
 *
 * 배지는 종전에 적재 **실행 시각**을 「데이터가 덮는 마지막 날」로 말했다 — 실측에서
 * `시세 · 08-23 · 2일 낡음` 이라 적었는데 08-23 은 **일요일**이라 캔들이 있을 수 없는 날이고,
 * 같은 스택의 DB 는 `max(trade_date) = 2026-08-21` 이었다. 적재 요청이 기간을 안 실으면
 * `period_to` 가 NULL 이라, 폴백이 실행 시각을 집었기 때문이다.
 */

/** 종목 하나의 적재본 신선도 키 — 시장:티커. 주기로 가르지 않는다(분봉이 일봉 응답을 바꾼다). */
export function coverageKey(market: string, ticker: string): string {
  return `${market}:${ticker}`;
}

interface CoverageState {
  /** 키 → 그 종목 적재본의 마지막 거래일(`YYYY-MM-DD`). 읽은 적이 없으면 없다. */
  lastTradeDate: Record<string, string>;
  /** 캔들을 읽은 자리가 알린다. 빈 적재본(캔들 0건)은 **지우지 않는다** — 「모른다」와 「없다」는 다르다. */
  publish(key: string, tradeDate: string | null): void;
}

export const useCoverageStore = create<CoverageState>((set) => ({
  lastTradeDate: {},
  publish: (key, tradeDate) =>
    set((state) =>
      tradeDate === null || state.lastTradeDate[key] === tradeDate
        ? state
        : { lastTradeDate: { ...state.lastTradeDate, [key]: tradeDate } },
    ),
}));

/** 그 종목 적재본의 마지막 거래일 — 아직 읽은 적이 없으면 `null`(모른다). */
export function useLoadedCoverage(key: string | null): string | null {
  return useCoverageStore((state) => (key === null ? null : (state.lastTradeDate[key] ?? null)));
}

/** 캔들에서 마지막 거래일을 읽는다 — 일봉은 `YYYY-MM-DD`, 분봉은 datetime 이라 앞 10자를 쓴다. */
export function lastTradeDateOf(candles: { time: string }[]): string | null {
  const days = candles.map((candle) => candle.time.slice(0, 10)).filter((day) => day.length === 10);
  if (days.length === 0) return null;
  return days.reduce((latest, day) => (day > latest ? day : latest));
}
