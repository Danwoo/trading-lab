// @vitest-environment jsdom
//
// #398 (이 레포 이슈 — https://github.com/Danwoo/trading-lab/issues/398) — **「칸 수」에 상한을 넘긴
// 값을 치면 폼이 그 자리에서 되돌리고, 실행은 요청으로 이어진다.**
//
// 실측(이슈 본문): 「평균선 기간」 칸 수에 `99` → Tab → 「격자 실행」. 폼은 `891칸 — … 시도 891회를
// 씁니다.` 라고 약속했는데, 누르면 요청 0건·콘솔 0건·`role=alert` 0건이었다. 입력의 네이티브
// `max=9` 위반이라 제출이 `onSubmit` 에 닿기 전에 브라우저 단에서 막힌 것이다 — 폼이 선언한 상한과
// 상태가 받는 상한이 따로 놀았다.
//
// 같은 클래스의 재발 조건은 둘이다. ㉠ 상태가 범위 밖 값을 받는다. ㉡ 폼의 네이티브 `min`/`max` 가
// 상태의 범위와 다른 숫자를 말한다. 어느 쪽이든 「약속은 크게, 제출은 침묵」이 다시 난다. 그래서
// 진짜 훅(`useGridRunForm`)에 진짜 폼(`GridRunForm`)을 물려 사용자가 치는 대로 관통해 본다.
//
// 배치: 훅 + 폼 + 프리미티브(`NumberBox`)를 관통하는 회귀라 tests/regressions/ 에 둔다.

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { GridRunForm } from "@/components/features/Bench/GridRunForm";
import { useGridRunForm } from "@/hooks/bench/useGridRunForm";
import { STEPS_MAX, STEPS_MIN } from "@/lib/bench/sweep";
import type { BacktestGridIn } from "@/schemas/backtest/backtest";
import { selectBot } from "@/services/bot/botService";

vi.mock("@/services/bot/botService", () => ({ selectBot: vi.fn() }));

// 이슈가 재현한 봇과 같은 모양 — 축 둘(기간 5~120 · 눌림 깊이 0.5~15, 0.5 간격).
const A_BOT = {
  bot_id: 1,
  strategies: [
    {
      bot_strategy_id: 1,
      strategy_key: "ma_pullback",
      params: { ma_period: 20, dip_pct: 3 },
      param_sources: {},
      weight: null,
      sort_order: 0,
      form: {
        key: "ma_pullback",
        name: "이동평균 눌림목",
        timeframe: "1d",
        fields: [
          { name: "ma_period", label: "평균선 기간", control: "number", default: 20, min: 5, max: 120, step: 1, unit: "일" },
          { name: "dip_pct", label: "눌림 깊이", control: "number", default: 3, min: 0.5, max: 15, step: 0.5, unit: "%" },
        ],
      },
      missing_reason: null,
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.mocked(selectBot).mockReset();
});

function Harness({ onRun }: { onRun: (input: BacktestGridIn) => void }) {
  const controller = useGridRunForm();
  return <GridRunForm bots={[{ bot_id: 1, bot_nm: "봇" } as never]} controller={controller} isRunning={false} onRun={onRun} />;
}

async function givenFormWithBot() {
  vi.mocked(selectBot).mockResolvedValue(A_BOT as never);
  const onRun = vi.fn<(input: BacktestGridIn) => void>();
  const view = render(<Harness onRun={onRun} />);
  // 봇 선택은 드롭다운 프리미티브의 몫이 아니라 훅의 계약이다 — 훅을 직접 부르는 대신, 폼이 준 봇을
  // 고르는 것과 같은 경로(`changeBot`)를 페이지가 타듯 `?bot=` 로 탄다.
  return { onRun, ...view };
}

/**
 * 축 fieldset 안의 칸 수 입력 전부. **0건이면 실패다** — 축이 안 그려졌는데 초록이면 아무것도
 * 안 본 것이다. 몇 건을 봤는지 출력에 남긴다.
 */
function stepsInputs(container: HTMLElement): HTMLInputElement[] {
  const inputs = Array.from(container.querySelectorAll<HTMLInputElement>('fieldset input[type="number"]'));
  expect(inputs.length, "칸 수 입력이 0건 — 축이 안 그려져 아무것도 검사하지 못했다").toBeGreaterThan(0);
  console.log(`#398 검사한 칸 수 입력: ${inputs.length}건`);
  return inputs;
}

describe("#398 — 칸 수 상한을 넘긴 입력은 그 자리에서 눌리고, 실행은 요청으로 이어진다", () => {
  it("폼이 선언한 네이티브 범위와 상태가 받는 범위가 같은 숫자다", async () => {
    window.history.replaceState({}, "", "/bench?bot=1");
    const { container } = await givenFormWithBot();
    await waitFor(() => expect(screen.getByText("평균선 기간", { exact: false })).toBeTruthy());

    for (const input of stepsInputs(container)) {
      expect(input.min).toBe(String(STEPS_MIN));
      expect(input.max).toBe(String(STEPS_MAX));
    }
  });

  it("99 를 치면 칸이 상한을 보이고, 브라우저 판정도 유효하며, 약속한 칸 수가 상한 안이다", async () => {
    window.history.replaceState({}, "", "/bench?bot=1");
    const user = userEvent.setup();
    const { container } = await givenFormWithBot();
    await waitFor(() => expect(screen.getByText("평균선 기간", { exact: false })).toBeTruthy());
    const [period] = stepsInputs(container);

    await user.clear(period);
    await user.type(period, "99");
    await user.tab();

    expect(period.value).toBe(String(STEPS_MAX));
    // 네이티브 제약 위반이 남아 있으면 제출이 `onSubmit` 전에 조용히 막힌다 — 그 길이 닫혔는지 본다.
    expect(period.validity.valid).toBe(true);
    const promised = screen.getByText(/\d+칸 —/).textContent ?? "";
    const combos = Number(/(\d+)칸/.exec(promised)?.[1]);
    expect(combos).toBeLessThanOrEqual(STEPS_MAX * STEPS_MAX);
  });

  it("그 상태로 「격자 실행」을 누르면 요청이 만들어지고, 축마다 값이 상한을 넘지 않는다", async () => {
    window.history.replaceState({}, "", "/bench?bot=1");
    const user = userEvent.setup();
    const { container, onRun } = await givenFormWithBot();
    await waitFor(() => expect(screen.getByText("평균선 기간", { exact: false })).toBeTruthy());
    await user.type(screen.getByPlaceholderText("005930 또는 AAPL"), "005930");
    const [period, dip] = stepsInputs(container);
    await user.clear(period);
    await user.type(period, "99");
    await user.clear(dip);
    await user.type(dip, "59");

    await act(async () => {
      await user.click(screen.getByRole("button", { name: "격자 실행" }));
    });

    expect(onRun).toHaveBeenCalledTimes(1);
    const sweep = onRun.mock.calls[0][0].sweep;
    expect(Object.keys(sweep)).toEqual(["ma_period", "dip_pct"]);
    for (const values of Object.values(sweep)) expect(values.length).toBeLessThanOrEqual(STEPS_MAX);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
