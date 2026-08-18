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
      },
      {
        run_id: 2,
        params: { ma_period: 10, pullback_pct: 3 },
        status: "succeeded",
        failed_reason: null,
        final_equity: 900,
      },
      {
        run_id: 3,
        params: { ma_period: 20, pullback_pct: 1 },
        status: "succeeded",
        failed_reason: null,
        final_equity: 1050,
      },
      {
        run_id: 4,
        params: { ma_period: 20, pullback_pct: 3 },
        status: "failed",
        failed_reason: "전략이 값을 거부했다",
        final_equity: null,
      },
    ],
    attempts_used: 4,
    initial_cash: 1000,
    ...overrides,
  };
}

describe("ParamGrid", () => {
  it("수익률에 부호가 항상 붙는다 — 색만으로 뜻을 전하지 않는다 (디자인 시스템 §2.3)", () => {
    render(<ParamGrid grid={grid()} selectedRunId={null} onSelect={vi.fn()} />);

    expect(screen.getByRole("button", { name: /ma_period=10 · pullback_pct=1 — 수익률 \+10\.0%/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /ma_period=10 · pullback_pct=3 — 수익률 −10\.0%/ })).toBeTruthy();
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
        { run_id: 1, params: { ma_period: 10 }, status: "succeeded", failed_reason: null, final_equity: 1100 },
        { run_id: 2, params: { ma_period: 20 }, status: "succeeded", failed_reason: null, final_equity: 1200 },
      ],
      attempts_used: 2,
    });
    render(<ParamGrid grid={oneAxis} selectedRunId={null} onSelect={vi.fn()} />);

    expect(screen.getAllByRole("button")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /ma_period=20 — 수익률 \+20\.0%/ })).toBeTruthy();
  });
});
