// #402 — 배지가 「적재본이 덮는 마지막 날」이라며 **적재를 돌린 시각**을 말했다.
//
// 실측: 배지가 `시세 · 08-23 · 2일 낡음` 이라 적었는데 08-23 은 **일요일**이라 캔들이 있을 수
// 없는 날이고, 같은 스택의 DB 는 `max(trade_date) = 2026-08-21` 이었다. 적재 요청이 기간을
// 안 실어 `period_to` 가 NULL 이면 폴백이 `finished_dt`(실행 시각)를 집었기 때문이다.
import { beforeEach, describe, expect, it } from "vitest";

import { coverageKey, lastTradeDateOf, useCoverageStore, useLoadedCoverage } from "@/stores/terminal/coverageStore";

const candle = (time: string) => ({ time, open: 1, high: 1, low: 1, close: 1, volume: 1 });

beforeEach(() => {
  useCoverageStore.setState({ lastTradeDate: {} });
});

describe("캔들에서 마지막 거래일을 읽는다", () => {
  it("일봉은 날짜 그대로", () => {
    expect(lastTradeDateOf([candle("2026-08-20"), candle("2026-08-21")])).toBe("2026-08-21");
  });

  it("순서가 뒤섞여 와도 가장 늦은 날이다", () => {
    expect(lastTradeDateOf([candle("2026-08-21"), candle("2026-08-19")])).toBe("2026-08-21");
  });

  it("분봉은 앞 10자가 거래일이다", () => {
    expect(lastTradeDateOf([candle("2026-08-21T15:30:00")])).toBe("2026-08-21");
  });

  it("캔들이 없으면 지어내지 않는다", () => {
    expect(lastTradeDateOf([])).toBeNull();
  });
});

describe("저장소는 모르는 것을 덮어쓰지 않는다", () => {
  it("읽은 적이 없으면 null 이다 — 「모른다」와 「없다」를 가른다", () => {
    expect(useLoadedCoverage.length).toBe(1); // 훅 시그니처가 키를 받는다
    expect(useCoverageStore.getState().lastTradeDate).toEqual({});
  });

  it("알린 값이 키별로 남는다", () => {
    const key = coverageKey("KOSPI", "005930");
    useCoverageStore.getState().publish(key, "2026-08-21");
    expect(useCoverageStore.getState().lastTradeDate[key]).toBe("2026-08-21");
  });

  it("빈 적재본(null)은 이미 아는 값을 지우지 않는다 — 조회가 잠깐 비어도 배지가 모른다로 돌아가지 않게", () => {
    const key = coverageKey("KOSPI", "005930");
    useCoverageStore.getState().publish(key, "2026-08-21");
    useCoverageStore.getState().publish(key, null);
    expect(useCoverageStore.getState().lastTradeDate[key]).toBe("2026-08-21");
  });

  it("종목마다 따로 센다 — 한 종목을 읽었다고 다른 종목을 아는 척하지 않는다", () => {
    useCoverageStore.getState().publish(coverageKey("KOSPI", "005930"), "2026-08-21");
    expect(useCoverageStore.getState().lastTradeDate[coverageKey("NASDAQ", "AAPL")]).toBeUndefined();
  });
});
