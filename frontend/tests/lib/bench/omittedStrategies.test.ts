// #401 — 전략 둘을 실은 봇의 격자가 첫 전략만 훑는데, 화면 어디에도 그 말이 없었다.
//
// 같은 제품의 저장 경로는 이미 이 사실을 말하고 막는다(「이 봇에는 전략이 2개 실려 있는데 이
// 화면은 하나만 다룹니다」). 데이터가 지워지는 쪽에는 그물이 있고, **판정이 틀리는 쪽에는
// 없었다.** 이 그물은 검증 쪽도 같은 수준으로 말하는지 본다.
import { describe, expect, it } from "vitest";

import { omittedStrategies, omittedStrategyNotice, strategyName } from "@/lib/bench/omittedStrategies";
import type { BotDetailOut, BotStrategyOut } from "@/schemas/bot/bot";

function strategy(key: string, name: string | null): BotStrategyOut {
  return {
    bot_strategy_id: 1,
    strategy_key: key,
    params: {},
    param_sources: {},
    weight: null,
    sort_order: 0,
    form: name === null ? null : { key, name, timeframe: "1d", fields: [] },
    missing_reason: name === null ? "전략 파일이 없습니다" : null,
  };
}

function bot(strategies: BotStrategyOut[], combine_rule: BotDetailOut["combine_rule"] = "AND"): BotDetailOut {
  return {
    bot_id: 18,
    bot_nm: "c5 전략둘 봇",
    combine_rule,
    universe_kind: "WATCHLIST",
    bot_role: "READONLY",
    use_at: "Y",
    param_sources: {},
    strategies,
  };
}

const PULLBACK = strategy("ma_pullback", "이동평균 눌림목");
const SURGE = strategy("surge_exclusion", "급등 제외 필터");

describe("검증이 빼고 도는 전략", () => {
  it("전략이 하나면 빠지는 것이 없다", () => {
    expect(omittedStrategies(bot([PULLBACK]))).toEqual([]);
    expect(omittedStrategyNotice(bot([PULLBACK]))).toBeNull();
  });

  it("봇을 아직 안 골랐으면 말하지 않는다", () => {
    expect(omittedStrategyNotice(null)).toBeNull();
  });

  it("둘째부터가 빠진다", () => {
    expect(omittedStrategies(bot([PULLBACK, SURGE])).map((s) => s.strategy_key)).toEqual(["surge_exclusion"]);
  });
});

describe("빠졌다는 말", () => {
  it("몇 개 중 무엇을 돌리고 무엇이 빠지는지 이름으로 말한다 — 재현된 그 봇 그대로", () => {
    const notice = omittedStrategyNotice(bot([PULLBACK, SURGE]))!;
    expect(notice).toContain("전략이 2개");
    expect(notice).toContain("「이동평균 눌림목」 하나만 돌립니다");
    expect(notice).toContain("급등 제외 필터");
  });

  it("AND 는 「걸러 내던 자리까지 사고 든 결과」라고 말한다", () => {
    expect(omittedStrategyNotice(bot([PULLBACK, SURGE], "AND"))).toContain("조건을 다 만족해야 사는 봇");
  });

  it("OR·SCORE 는 다른 결과를 말한다 — 합치는 방법마다 흔들리는 방향이 다르다", () => {
    expect(omittedStrategyNotice(bot([PULLBACK, SURGE], "OR"))).toContain("하나만 만족해도 사는 봇");
    expect(omittedStrategyNotice(bot([PULLBACK, SURGE], "SCORE"))).toContain("가중합으로 판정하는 봇");
  });

  it("셋 이상이면 빠지는 것을 다 적는다", () => {
    const third = strategy("volume_filter", "거래량 필터");
    const notice = omittedStrategyNotice(bot([PULLBACK, SURGE, third]))!;
    expect(notice).toContain("전략이 3개");
    expect(notice).toContain("급등 제외 필터 · 거래량 필터");
  });

  it("전략 파일을 못 읽었으면 키라도 말한다 — 이름 없이 「빠졌다」만 남기지 않는다", () => {
    expect(strategyName(strategy("surge_exclusion", null))).toBe("surge_exclusion");
    expect(omittedStrategyNotice(bot([PULLBACK, strategy("surge_exclusion", null)]))).toContain("surge_exclusion");
  });
});
