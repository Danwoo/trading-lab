// #434 (F37·F38) — 「종목당 비중」에 100,000 을 넣어도 통과했다.
//
// 비중은 전체의 몫이라 100% 를 넘을 수 없고, 저장 컬럼은 `Numeric(18,2)` 다. 막지 않으면
// 두 방향으로 샌다: 100,000% 가 보드에 그대로 남거나, `0.0000001` 이 INSERT 시 조용히
// `0.00` 으로 반올림돼 **사용자가 넣지 않은 값**이 된다.
//
// 이 그물은 프론트 zod 가 백엔드와 **같은 경계**를 갖는지만 본다 — 소수 자릿수는 백엔드가
// 사유와 함께 거부한다(`schemas/common_schema.py` 의 `Money`). 층이 어긋나면 화면은
// 통과시키고 저장에서 422 가 나 사용자가 두 번 왕복한다.
import { describe, expect, it } from "vitest";

import { BotCreateInSchema } from "@/schemas/bot/bot";
import { BacktestRunInSchema } from "@/schemas/backtest/backtest";

const BASE = {
  bot_nm: "테스트봇",
  combine_rule: "AND",
  universe_kind: "WATCHLIST",
  use_at: "Y",
  bot_role: "READONLY",
  params: {},
  param_sources: {},
  strategies: [{ strategy_key: "sma_cross", params: {}, param_sources: {} }],
};

const parse = (alloc_per_symbol: number) => BotCreateInSchema.safeParse({ ...BASE, alloc_per_symbol });

describe("종목당 비중은 0~100 밖으로 나가지 못한다", () => {
  it("100% 를 넘는 비중은 거부된다", () => {
    expect(parse(100_000).success).toBe(false);
    expect(parse(100.01).success).toBe(false);
  });

  it("음수 비중은 거부된다", () => {
    expect(parse(-1).success).toBe(false);
  });

  it("경계와 그 안쪽은 그대로 통과한다", () => {
    expect(parse(0).success).toBe(true);
    expect(parse(12.34).success).toBe(true);
    expect(parse(100).success).toBe(true);
  });

  it("백엔드와 같은 경계다 — 손절선과 한 규칙으로 읽힌다", () => {
    expect(BotCreateInSchema.safeParse({ ...BASE, stop_loss_pct: 100.01 }).success).toBe(false);
    expect(BotCreateInSchema.safeParse({ ...BASE, stop_loss_pct: 100 }).success).toBe(true);
  });
});

// 「종목당 비중」만 막고 옆 칸을 두면 같은 결함이 이름만 바꿔 남는다 — 저장 컬럼에 천장이 있는
// 칸은 **전부** 화면에서 먼저 거부한다. 백엔드 `tests/test_numeric_inputs_are_bounded.py` 가
// 같은 규칙을 스키마 전수로 본다.
describe("저장 컬럼에 천장이 있는 칸은 화면이 먼저 거부한다", () => {
  const bot = (over: Record<string, unknown>) => BotCreateInSchema.safeParse({ ...BASE, ...over }).success;

  it("익절선은 100% 를 넘을 수 있지만 컬럼(9999.99)은 못 넘는다", () => {
    expect(bot({ take_profit_pct: 200 })).toBe(true);
    expect(bot({ take_profit_pct: 9999.99 })).toBe(true);
    expect(bot({ take_profit_pct: 10000 })).toBe(false);
  });

  it("정수 칸은 integer 상한(21억)을 넘지 못한다", () => {
    expect(bot({ max_positions: 2_147_483_647 })).toBe(true);
    expect(bot({ max_positions: 2_147_483_648 })).toBe(false);
    expect(bot({ max_trades_per_day: 2_147_483_648 })).toBe(false);
  });

  it("정수 칸은 0 이하를 받지 않는다 — 백엔드가 gt=0 이다", () => {
    expect(bot({ max_positions: 0 })).toBe(false);
    expect(bot({ max_trades_per_day: -1 })).toBe(false);
  });

  it("시작 자금은 0 초과이고 저장 상한 안쪽이다", () => {
    const run = (initial_cash: number) =>
      BacktestRunInSchema.safeParse({
        strategy_key: "sma_cross",
        params: {},
        market: "KRX",
        symbol: "005930",
        period_from: "2026-01-01",
        period_to: "2026-06-30",
        initial_cash,
      }).success;
    expect(run(10_000_000)).toBe(true);
    expect(run(0)).toBe(false);
    expect(run(1e16)).toBe(false);
  });
});
