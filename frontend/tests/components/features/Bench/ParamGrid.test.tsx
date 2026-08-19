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
        metrics: { longest_underwater: 14, still_underwater: false, mdd_pct: -22, total_return_pct: 10.0 },
      },
      {
        run_id: 2,
        params: { ma_period: 10, pullback_pct: 3 },
        status: "succeeded",
        failed_reason: null,
        final_equity: 900,
        metrics: { longest_underwater: 3, still_underwater: false, mdd_pct: -4, total_return_pct: -10.0 },
      },
      {
        run_id: 3,
        params: { ma_period: 20, pullback_pct: 1 },
        status: "succeeded",
        failed_reason: null,
        final_equity: 1050,
        metrics: { longest_underwater: 6, still_underwater: false, mdd_pct: -9, total_return_pct: 5.0 },
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
          metrics: { longest_underwater: 14, still_underwater: false, mdd_pct: -22, total_return_pct: 10.0 },
        },
        {
          run_id: 2,
          params: { ma_period: 20 },
          status: "succeeded",
          failed_reason: null,
          final_equity: 1200,
          metrics: { longest_underwater: 3, still_underwater: false, mdd_pct: -5, total_return_pct: 20.0 },
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

  it("채색 축을 바꾸면 화면 문구도 따라간다", async () => {
    const user = userEvent.setup();
    render(<ParamGrid grid={grid()} selectedRunId={null} onSelect={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "구간 총수익률" }));

    expect(screen.getByText(/「구간 총수익률」로 칠했습니다/)).toBeTruthy();
    expect(screen.getByText(/진할수록 많이 벌었습니다/)).toBeTruthy();
  });
});
