// @vitest-environment jsdom
//
// 파라미터 민감도 격자 (#203, 스펙 D-Q1) — 칸의 뜻이 화면에 그대로 남는지.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ParamGrid } from "@/components/features/Bench/ParamGrid";
import type { GridOut } from "@/schemas/backtest/backtest";

afterEach(cleanup);

/** 2축(ma_period × pullback_pct) 2×2 격자 — cells 는 첫 축이 바깥 루프인 product 순서다. */
function grid(overrides: Partial<GridOut> = {}): GridOut {
  return {
    shape: [2, 2],
    axes: [
      { name: "ma_period", values: [10, 20] },
      { name: "pullback_pct", values: [1, 3] },
    ],
    cells: [
      {
        run_id: 1,
        params: { ma_period: 10, pullback_pct: 1 },
        status: "succeeded",
        failed_reason: null,
        final_equity: 1100,
        metrics: {
          longest_underwater: 14,
          still_underwater: false,
          mdd_pct: -22,
          total_return_pct: 10.0,
          closed_trades: 4,
          open_positions: 0,
          absent_reason: null,
        },
      },
      {
        run_id: 2,
        params: { ma_period: 10, pullback_pct: 3 },
        status: "succeeded",
        failed_reason: null,
        final_equity: 900,
        metrics: {
          longest_underwater: 3,
          still_underwater: false,
          mdd_pct: -4,
          total_return_pct: -10.0,
          closed_trades: 4,
          open_positions: 0,
          absent_reason: null,
        },
      },
      {
        run_id: 3,
        params: { ma_period: 20, pullback_pct: 1 },
        status: "succeeded",
        failed_reason: null,
        final_equity: 1050,
        metrics: {
          longest_underwater: 6,
          still_underwater: false,
          mdd_pct: -9,
          total_return_pct: 5.0,
          closed_trades: 4,
          open_positions: 0,
          absent_reason: null,
        },
      },
      {
        run_id: 4,
        params: { ma_period: 20, pullback_pct: 3 },
        status: "failed",
        failed_reason: "전략이 값을 거부했다",
        final_equity: null,
        // 실패한 칸은 계산할 곡선이 없다 — 지표도 없다.
        metrics: null,
      },
    ],
    attempts_used: 4,
    initial_cash: 1000,
    ...overrides,
  };
}

describe("ParamGrid", () => {
  it("칸에 값과 단위가 붙는다 — 색만으로 뜻을 전하지 않는다 (디자인 시스템 §2.3)", () => {
    render(<ParamGrid grid={grid()} selectedRunId={null} onSelect={vi.fn()} />);

    expect(screen.getByRole("button", { name: /ma_period=10 · pullback_pct=1 — 최장 미회복 기간 14봉/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /ma_period=10 · pullback_pct=3 — 최장 미회복 기간 3봉/ })).toBeTruthy();
  });

  it("실패한 칸은 지어낸 숫자 대신 「실패」와 사유를 낸다", () => {
    render(<ParamGrid grid={grid()} selectedRunId={null} onSelect={vi.fn()} />);

    const failed = screen.getByRole("button", { name: /ma_period=20 · pullback_pct=3 — 실패/ });
    expect(failed.getAttribute("title")).toBe("전략이 값을 거부했다");
  });

  it("칸을 누르면 run_id 와 사람이 읽는 조합 이름이 올라간다 — 전파 규칙의 시작점", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<ParamGrid grid={grid()} selectedRunId={null} onSelect={onSelect} />);

    await user.click(screen.getByRole("button", { name: /수익률 \+10\.0%/ }));
    expect(onSelect).toHaveBeenCalledWith(1, "ma_period=10 · pullback_pct=1");
  });

  it("시도 수를 화면이 말한다 — 훑는 것도 시도다 (§8.5.2)", () => {
    render(<ParamGrid grid={grid()} selectedRunId={null} onSelect={vi.fn()} />);

    expect(screen.getByText(/시도 4회를 썼습니다/)).toBeTruthy();
  });

  it("고른 칸이 표시된다", () => {
    render(<ParamGrid grid={grid()} selectedRunId={1} onSelect={vi.fn()} />);

    expect(screen.getByRole("button", { name: /수익률 \+10\.0%/ }).getAttribute("aria-pressed")).toBe("true");
  });

  it("1축이면 한 줄 표다", () => {
    const oneAxis = grid({
      shape: [2],
      axes: [{ name: "ma_period", values: [10, 20] }],
      cells: [
        {
          run_id: 1,
          params: { ma_period: 10 },
          status: "succeeded",
          failed_reason: null,
          final_equity: 1100,
          metrics: {
            longest_underwater: 14,
            still_underwater: false,
            mdd_pct: -22,
            total_return_pct: 10.0,
            closed_trades: 4,
            open_positions: 0,
            absent_reason: null,
          },
        },
        {
          run_id: 2,
          params: { ma_period: 20 },
          status: "succeeded",
          failed_reason: null,
          final_equity: 1200,
          metrics: {
            longest_underwater: 3,
            still_underwater: false,
            mdd_pct: -5,
            total_return_pct: 20.0,
            closed_trades: 4,
            open_positions: 0,
            absent_reason: null,
          },
        },
      ],
      attempts_used: 2,
    });
    render(<ParamGrid grid={oneAxis} selectedRunId={null} onSelect={vi.fn()} />);

    // 채색 선택 버튼(3개)이 함께 있으므로 **칸만** 센다 — 칸은 조합 이름을 라벨에 갖는다.
    expect(screen.getAllByRole("button", { name: /ma_period=/ })).toHaveLength(2);
    expect(screen.getByRole("button", { name: /ma_period=20 — 최장 미회복 기간 3봉/ })).toBeTruthy();
  });

  // ── 채색 기준 (#220) ─────────────────────────────────────────────────────
  // 격자는 조합을 **고르는** 자리다. 4급 지표(수익률)로만 칠하면 「가장 많이 번 칸」이
  // 가장 진해 보이고, 리포트에서 1급을 볼 때는 이미 고른 뒤다.

  it("기본 채색이 1급 지표다 — 무엇으로 칠했는지 화면이 말한다", () => {
    render(<ParamGrid grid={grid()} selectedRunId={null} onSelect={vi.fn()} />);

    expect(screen.getByText(/「최장 미회복 기간」로 칠했습니다/)).toBeTruthy();
    expect(screen.getByText(/진할수록 나쁩니다/)).toBeTruthy();
  });

  it("가장 진한 칸이 가장 많이 번 칸과 다를 수 있다 — 이 이슈의 요지다", () => {
    render(<ParamGrid grid={grid()} selectedRunId={null} onSelect={vi.fn()} />);

    // 픽스처는 일부러 역순위다: 가장 많이 번 칸(+10%)이 미회복 기간은 가장 길다(14봉).
    // 채색이 1급이므로 그 칸이 가장 진하고, 라벨에 두 값이 함께 실린다.
    const worst = screen.getByRole("button", { name: /최장 미회복 기간 14봉/ });
    expect(worst.getAttribute("aria-label")).toContain("수익률 +10.0%");
  });

  // ── 거래 0건 칸 (#349) ───────────────────────────────────────────────────
  // 「거래가 없었다」와 「낙폭이 0 이었다」는 다른 사실이다. 0 으로 실어 그리면 그 칸이
  // 척도의 **가장 좋은 끝**에 놓여, 격자만 보고 고른 사람이 아무것도 하지 않는 봇을 고른다.

  /** 거래 0건 칸 하나를 섞은 격자 — 나머지 3칸은 위 픽스처와 같다. */
  function gridWithNoTradeCell(): GridOut {
    const base = grid();
    return {
      ...base,
      cells: [
        base.cells[0],
        base.cells[1],
        base.cells[2],
        {
          run_id: 5,
          params: { ma_period: 20, pullback_pct: 3 },
          status: "succeeded",
          failed_reason: null,
          final_equity: 1000,
          metrics: {
            longest_underwater: null,
            still_underwater: null,
            mdd_pct: null,
            total_return_pct: null,
            closed_trades: 0,
            open_positions: 0,
            absent_reason: "거래 없음 — 이 조합은 한 번도 사지 않았습니다. 성적을 낼 곡선이 없습니다",
          },
        },
      ],
    };
  }

  it("거래 0건 칸은 「거래 0건」이라 말하고 성적으로 칠해지지 않는다", () => {
    render(<ParamGrid grid={gridWithNoTradeCell()} selectedRunId={null} onSelect={vi.fn()} />);

    const cell = screen.getByRole("button", { name: /ma_period=20 · pullback_pct=3 — 거래 없음/ });
    expect(cell.textContent).toBe("거래 0건");
    // 채색은 인라인 backgroundColor 로만 들어간다 — 척도 밖이면 그 자리가 비어 있어야 한다.
    expect(cell.style.backgroundColor).toBe("");
    expect(cell.getAttribute("title")).toContain("성적 척도에서 뺐습니다");
  });

  it("세 채색 축 어디에서도 거래 0건 칸은 척도 밖이다 — 축마다 새는 자리가 없다", async () => {
    const user = userEvent.setup();
    render(<ParamGrid grid={gridWithNoTradeCell()} selectedRunId={null} onSelect={vi.fn()} />);

    // 화면이 내놓는 채색 축 전부를 훑는다 — 하나라도 늘면 이 검사가 함께 늘어난다.
    const axisLabels = ["최장 미회복 기간", "최대 낙폭", "구간 총수익률"];
    expect(screen.getAllByRole("button", { name: /^(최장 미회복 기간|최대 낙폭|구간 총수익률)$/ })).toHaveLength(
      axisLabels.length,
    );

    for (const axis of axisLabels) {
      await user.click(screen.getByRole("button", { name: axis }));
      const cell = screen.getByRole("button", { name: /ma_period=20 · pullback_pct=3 — 거래 없음/ });
      expect(cell.style.backgroundColor, `${axis} 축에서 거래 0건 칸이 칠해졌다`).toBe("");
      expect(cell.textContent).toBe("거래 0건");
    }
  });

  /**
   * 비교 기준 격자의 **셋째 칸을 「거래는 있었는데 값이 진짜 0」으로** 바꾼다.
   *
   * 이게 없으면 이 비교는 회귀를 못 가린다: 값 0 을 최댓값 집합에 넣든 빼든 `max(|v|)` 는
   * 그대로라 알파가 안 움직여, 고치기 전에도 초록이다. 진짜 0 인 칸을 넣어야 「거래 0건을
   * 거르려다 값 0 까지 거르는」 과잉 필터가 여기서 잡힌다.
   */
  function gridWithGenuineZeroCell(): GridOut {
    const base = grid();
    return {
      ...base,
      cells: [
        base.cells[0],
        base.cells[1],
        {
          ...base.cells[2],
          metrics: {
            longest_underwater: 0,
            still_underwater: false,
            mdd_pct: 0,
            total_return_pct: 0,
            closed_trades: 2,
            open_positions: 0,
            absent_reason: null,
          },
        },
        base.cells[3],
      ],
    };
  }

  it("거래가 있는 칸의 값이 진짜 0 이면 그 0 은 성적으로 칠해진다 — 과잉 필터가 아니다", () => {
    render(<ParamGrid grid={gridWithGenuineZeroCell()} selectedRunId={null} onSelect={vi.fn()} />);

    const zero = screen.getByRole("button", { name: /최장 미회복 기간 0봉/ });
    expect(zero.textContent).toBe("0봉");
    // 척도의 가장 좋은 끝(alpha 0.08)이 맞다 — 거래가 있었으니 그건 성적이다.
    expect(zero.style.backgroundColor).toBe("rgb(var(--market-down) / 0.08)");
    expect(zero.getAttribute("aria-label")).toContain("청산된 거래 2건");
  });

  it("거래 0건 칸이 섞여도 거래가 있는 칸의 채색은 그대로다 — 척도가 흔들리지 않는다", () => {
    const base = gridWithGenuineZeroCell();
    const shown = ["14봉", "3봉", "0봉"];

    const { unmount } = render(<ParamGrid grid={base} selectedRunId={null} onSelect={vi.fn()} />);
    const before = shown.map(
      (text) => screen.getByRole("button", { name: new RegExp(`최장 미회복 기간 ${text}`) }).style.backgroundColor,
    );
    expect(before.every((color) => color !== "")).toBe(true);
    unmount();

    // 같은 세 칸에 거래 0건 칸 하나를 더한 격자 — 세 칸의 색이 한 자리도 달라지면 안 된다.
    const withIdle: GridOut = { ...base, cells: [...base.cells.slice(0, 3), gridWithNoTradeCell().cells[3]] };
    render(<ParamGrid grid={withIdle} selectedRunId={null} onSelect={vi.fn()} />);
    const after = shown.map(
      (text) => screen.getByRole("button", { name: new RegExp(`최장 미회복 기간 ${text}`) }).style.backgroundColor,
    );
    expect(after).toEqual(before);
  });

  it("사유가 가림에 전부 지워져도 그 칸은 척도 밖에 남는다 — 「말할 수 없다」가 「없다」로 뒤집히지 않는다", () => {
    // `redactReason` 은 다듬은 뒤 빈 문구가 되면 null 을 돌려준다(공백뿐인 사유가 그렇다).
    // 판정이 그 결과 하나에 매달리면 그 칸이 척도로 되돌아온다 — 건수가 받쳐야 한다.
    const base = gridWithNoTradeCell();
    const redacted: GridOut = {
      ...base,
      cells: [
        ...base.cells.slice(0, 3),
        { ...base.cells[3], metrics: { ...base.cells[3].metrics!, absent_reason: "   " } },
      ],
    };
    render(<ParamGrid grid={redacted} selectedRunId={null} onSelect={vi.fn()} />);

    const cell = screen.getByRole("button", { name: /ma_period=20 · pullback_pct=3 — 거래 없음/ });
    expect(cell.style.backgroundColor).toBe("");
    expect(cell.textContent).toBe("거래 0건");
  });

  it("사유가 실린 칸은 값이 숫자로 와도 척도 밖이다 — 한쪽만 고쳐도 0 이 성적으로 새지 않는다", () => {
    // 백엔드는 지금 값 자리를 비워 보낸다. 그래도 화면은 `absent_reason` 을 **스스로** 보고
    // 걸러야 한다 — 어느 한쪽이 옛 규약(0 을 실어 보내기)으로 돌아가도 격자가 다시
    // 「아무것도 하지 않는 조합」을 1등으로 칠하면 안 된다 (#349).
    const base = gridWithNoTradeCell();
    const leaky: GridOut = {
      ...base,
      cells: [
        ...base.cells.slice(0, 3),
        {
          ...base.cells[3],
          metrics: {
            longest_underwater: 0,
            still_underwater: false,
            mdd_pct: 0,
            total_return_pct: 0,
            closed_trades: 0,
            open_positions: 0,
            absent_reason: "거래 없음 — 이 조합은 한 번도 사지 않았습니다. 성적을 낼 곡선이 없습니다",
          },
        },
      ],
    };
    render(<ParamGrid grid={leaky} selectedRunId={null} onSelect={vi.fn()} />);

    const cell = screen.getByRole("button", { name: /ma_period=20 · pullback_pct=3 — 거래 없음/ });
    expect(cell.style.backgroundColor).toBe("");
    expect(cell.textContent).toBe("거래 0건");
    // 「0봉」이라는 성적으로 읽히는 글자가 어디에도 없어야 한다.
    expect(cell.getAttribute("aria-label")).not.toContain("0봉");
  });

  it("칸이 거래 건수를 지고 다닌다 — 「1건으로 낸 성적」과 「25건으로 낸 성적」을 가른다", () => {
    render(<ParamGrid grid={gridWithNoTradeCell()} selectedRunId={null} onSelect={vi.fn()} />);

    const traded = screen.getByRole("button", { name: /최장 미회복 기간 14봉/ });
    expect(traded.getAttribute("aria-label")).toContain("청산된 거래 4건");
    expect(traded.getAttribute("title")).toContain("청산된 거래 4건");
  });

  it("척도에서 뺀 칸 수를 화면이 말한다 — 몇 칸으로 판단한 그림인지 알 수 있게", () => {
    render(<ParamGrid grid={gridWithNoTradeCell()} selectedRunId={null} onSelect={vi.fn()} />);

    expect(screen.getByText(/거래가 없던 1칸은 성적이 아니라 「거래 0건」으로 두어 척도에서 뺐습니다/)).toBeTruthy();
  });

  it("채색 축을 바꾸면 화면 문구도 따라간다", async () => {
    const user = userEvent.setup();
    render(<ParamGrid grid={grid()} selectedRunId={null} onSelect={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "구간 총수익률" }));

    expect(screen.getByText(/「구간 총수익률」로 칠했습니다/)).toBeTruthy();
    expect(screen.getByText(/진할수록 많이 벌었습니다/)).toBeTruthy();
  });
});
