// @vitest-environment jsdom
//
// 격자 폼이 「훑을 축」이 어디서 왔는지 말할 때 **사람 말로** 말하는가 (#319).
//
// 종전 문구는 「… 범위 선언에서 왔습니다」였다. 「선언」은 전략 파일의 코드 어휘라, 이 자리에서
// 막힌 사람에게 다음 걸음을 주지 못한다. 축이 없을 때 나오는 안내도 같은 말을 쓰고 있었다.
//
// 그려진 텍스트로 판정한다 — 상수를 비교하면 문구를 되돌려도 통과한다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

import { GridRunForm } from "@/components/features/Bench/GridRunForm";
import type { GridRunFormController } from "@/hooks/bench/useGridRunForm";
import type { BotStrategyOut } from "@/schemas/bot/bot";

afterEach(cleanup);

const STRATEGY: BotStrategyOut = {
  bot_strategy_id: 1,
  strategy_key: "ma_pullback",
  params: { ma_period: 20 },
  param_sources: {},
  weight: null,
  sort_order: 0,
  form: {
    key: "ma_pullback",
    name: "이동평균 눌림목",
    timeframe: "1d",
    fields: [{ name: "ma_period", label: "평균선 기간", control: "number", default: 20, min: 5, max: 60 }],
  },
  missing_reason: null,
};

function renderForm(axes: GridRunFormController["axes"]) {
  const controller: GridRunFormController = {
    botId: 1,
    strategy: STRATEGY,
    botDetailError: null,
    form: {
      market: "KOSPI",
      symbol: "005930",
      period_from: "2023-08-21",
      period_to: "2026-08-20",
      initial_cash: 10_000_000,
    },
    axes,
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

describe("격자 폼의 축 안내는 사람 말이다", () => {
  it("축이 있을 때 — 「선언」 없이 어디서 왔는지 말한다", () => {
    const { container } = renderForm([{ field: STRATEGY.form!.fields[0], enabled: true, steps: 5 }]);
    const shown = container.textContent ?? "";
    expect(shown).toContain("훑을 축"); // fail-closed — 이 자리가 안 그려지면 판정할 것이 없다
    expect(shown).not.toContain("선언");
  });

  it("축이 없을 때 — 그 안내도 「선언」을 쓰지 않는다", () => {
    const { container } = renderForm([]);
    const shown = container.textContent ?? "";
    expect(shown).toContain("범위를 정해 둔 숫자 파라미터가 없습니다");
    expect(shown).not.toContain("선언");
  });
});
