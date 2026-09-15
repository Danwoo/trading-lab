// @vitest-environment jsdom
//
// #401 — 전략 둘을 실은 봇의 격자가 첫 전략만 훑는데, 폼도 격자도 리포트도 그 말을 안 했다.
//
// 「급등」·`surge` 문자열이 화면 어디에도 0건이었다. 그런데 그 봇의 규칙은 AND 라, 급등 제외를
// 빼고 돌린 성과는 **그 봇의 성과가 아니다.** 돌린 뒤에 알면 이미 늦으므로 **실행 전**에 말한다.
//
// 그려진 텍스트로 판정한다 — 상수를 비교하면 문구를 되돌려도 통과한다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

import { GridRunForm } from "@/components/features/Bench/GridRunForm";
import type { GridRunFormController } from "@/hooks/bench/useGridRunForm";
import type { BotDetailOut, BotStrategyOut } from "@/schemas/bot/bot";

afterEach(cleanup);

function strategy(key: string, name: string): BotStrategyOut {
  return {
    bot_strategy_id: 1,
    strategy_key: key,
    params: {},
    param_sources: {},
    weight: null,
    sort_order: 0,
    form: { key, name, timeframe: "1d", fields: [] },
    missing_reason: null,
  };
}

function bot(strategies: BotStrategyOut[]): BotDetailOut {
  return {
    bot_id: 18,
    bot_nm: "c5 전략둘 봇",
    combine_rule: "AND",
    universe_kind: "WATCHLIST",
    bot_role: "READONLY",
    use_at: "Y",
    param_sources: {},
    strategies,
  };
}

function renderForm(botDetail: BotDetailOut | null) {
  const controller: GridRunFormController = {
    botId: 18,
    strategy: botDetail?.strategies[0] ?? null,
    botDetail,
    botDetailError: null,
    form: {
      market: "KOSPI",
      symbol: "005930",
      period_from: "2023-08-21",
      period_to: "2026-08-20",
      initial_cash: 10_000_000,
    },
    axes: [],
    formError: null,
    comboCount: 0,
    changeBot: vi.fn(),
    changeField: vi.fn(),
    toggleAxis: vi.fn(),
    changeAxisSteps: vi.fn(),
    buildInput: vi.fn(() => null),
  };
  return render(<GridRunForm bots={[]} controller={controller} isRunning={false} onRun={vi.fn()} />);
}

const PULLBACK = strategy("ma_pullback", "이동평균 눌림목");
const SURGE = strategy("surge_exclusion", "급등 제외 필터");

describe("격자 폼이 빼고 도는 전략을 실행 전에 말한다", () => {
  it("전략 둘인 봇 — 무엇이 빠지는지 이름으로 말한다", () => {
    const { container } = renderForm(bot([PULLBACK, SURGE]));
    const shown = container.textContent ?? "";
    expect(shown).toContain("전략이 2개");
    expect(shown).toContain("급등 제외 필터");
  });

  it("그 결과가 이 봇의 성과가 아닌 이유까지 말한다", () => {
    const { container } = renderForm(bot([PULLBACK, SURGE]));
    expect(container.textContent ?? "").toContain("조건을 다 만족해야 사는 봇");
  });

  it("경고로 읽히게 role=alert 로 낸다 — 축 안내에 섞이면 안 읽힌다", () => {
    const { container } = renderForm(bot([PULLBACK, SURGE]));
    const alerts = [...container.querySelectorAll('[role="alert"]')].map((node) => node.textContent ?? "");
    expect(alerts.some((text) => text.includes("급등 제외 필터"))).toBe(true);
  });

  it("전략 하나인 봇에는 아무 말도 얹지 않는다", () => {
    const { container } = renderForm(bot([PULLBACK]));
    expect(container.textContent ?? "").not.toContain("하나만 돌립니다");
  });

  it("봇을 아직 안 골랐으면 말하지 않는다", () => {
    const { container } = renderForm(null);
    expect(container.textContent ?? "").not.toContain("하나만 돌립니다");
  });
});
