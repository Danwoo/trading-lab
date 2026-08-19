// @vitest-environment jsdom
//
// 한 조합의 리포트 (#203) — 지표 순서(D-Q2)와 「유도 경로 없는 숫자 금지」(§8.5.3)가
// 화면에서 지켜지는지.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

import { RunReportView } from "@/components/features/Bench/RunReportView";
import type { MetricOut, RunReportOut } from "@/schemas/backtest/backtest";

// jsdom 에는 캔버스가 없다 — 차트 팩토리는 브라우저 실측이 정본이고, 여기서는 데이터·문구만 본다.
vi.mock("@/lib/bench/equityChart", () => ({
  createEquityChart: vi.fn(() => ({ setSeries: vi.fn(), resize: vi.fn(), destroy: vi.fn() })),
}));

afterEach(cleanup);

function metric(overrides: Partial<MetricOut>): MetricOut {
  return {
    key: "k",
    label: "라벨",
    value: 1,
    unit: "%",
    derived_from: "자산곡선",
    absent_reason: null,
    note: null,
    ...overrides,
  };
}

function report(overrides: Partial<RunReportOut> = {}): RunReportOut {
  return {
    run: {
      run_id: 42,
      bot_id: 1,
      parent_run_id: null,
      attempt_no: 7,
      strategy_key: "ma_pullback",
      strategy_version: "1",
      params: { ma_period: 20 },
      universe_def: { market: "KOSPI", symbols: ["005930"] },
      adj_policy: "unadjusted",
      cost_assumptions: { fee_rate: 0.00015 },
      period_from: "2026-01-02",
      period_to: "2026-03-31",
      initial_cash: 1000000,
      status: "succeeded",
      failed_reason: null,
      finished_dt: null,
    },
    equity: [
      { dt: "2026-01-02", equity: 1000000, cash: 1000000, position_count: 0, gross_exposure: 0 },
      { dt: "2026-01-03", equity: 1010000, cash: 1010000, position_count: 0, gross_exposure: 0 },
    ],
    trades: [],
    metrics: [
      metric({
        key: "longest_underwater",
        label: "최장 미회복 기간",
        value: 14,
        unit: "봉",
        derived_from: "자산곡선 — 전 고점 아래에 머문 최장 구간",
      }),
      metric({ key: "mdd", label: "최대 낙폭", value: -22.1 }),
      metric({
        key: "win_rate",
        label: "승률",
        value: null,
        derived_from: "청산된 거래",
        absent_reason: "거래 없음 — 청산된 거래가 0건입니다",
      }),
      metric({
        key: "sharpe",
        label: "샤프",
        value: 1.1,
        unit: "",
        derived_from: "일별 수익률 60개 · 무위험수익률 0 가정",
      }),
    ],
    ...overrides,
  };
}

describe("RunReportView", () => {
  it("지표 순서는 서버(D-Q2)의 것이다 — 최장 미회복 기간이 맨 위, 샤프가 맨 뒤", () => {
    render(<RunReportView report={report()} />);

    const section = screen.getByRole("region", { name: "판정 지표" });
    const labels = within(section)
      .getAllByRole("term")
      .map((el) => el.textContent ?? "");
    expect(labels[0]).toContain("최장 미회복 기간");
    expect(labels[labels.length - 1]).toContain("샤프");
  });

  it("유도 경로가 값 옆에 선다 (§8.5.3)", () => {
    render(<RunReportView report={report()} />);

    expect(screen.getByText(/유도: 자산곡선 — 전 고점 아래에 머문 최장 구간/)).toBeTruthy();
  });

  it("값이 없으면 0 을 그리지 않고 absent_reason 을 그대로 낸다 — 거래 0건 승률은 「거래 없음」", () => {
    render(<RunReportView report={report()} />);

    expect(screen.getByText(/거래 없음 — 청산된 거래가 0건입니다/)).toBeTruthy();
    const section = screen.getByRole("region", { name: "판정 지표" });
    expect(section.textContent).not.toContain("0%");
  });

  it("거래가 없으면 목록 자리도 「거래 없음」을 말한다", () => {
    render(<RunReportView report={report()} />);

    const section = screen.getByRole("region", { name: "거래 목록" });
    expect(section.textContent).toContain("거래 없음");
  });

  it("실현손익에 부호가 붙는다 — 색만으로 뜻을 전하지 않는다 (§2.3)", () => {
    const withTrades = report({
      trades: [
        {
          trade_id: 1,
          instrument_id: 10,
          side: "BUY",
          entry_ts: "2026-01-02",
          exit_ts: "2026-01-10",
          qty: 3,
          fill_price: 100,
          exit_price: 110,
          fee: 0.1,
          slippage: 0.1,
          tax: 0.2,
          realized_pnl: 30,
          mae: null,
          mfe: null,
        },
      ],
    });
    render(<RunReportView report={withTrades} />);

    const section = screen.getByRole("region", { name: "거래 목록" });
    expect(section.textContent).toContain("+30");
  });

  it("비용 가정 3종을 그대로 읽어 준다 — 이 숫자들이 무엇 위에 서 있는지", () => {
    const withCosts = report();
    withCosts.run = {
      ...withCosts.run,
      cost_assumptions: { fee_rate: 0.00015, slippage_rate: 0.0005, sell_tax_rate: 0.0018 },
    };
    render(<RunReportView report={withCosts} />);

    const text = document.body.textContent ?? "";
    expect(text).toContain("수수료 0.015%");
    expect(text).toContain("슬리피지 0.050%");
    expect(text).toContain("증권거래세 0.180%");
  });

  it("가정이 비어 있으면 0% 로 지어내지 않고 기록이 없다고 말한다", () => {
    const noCosts = report();
    noCosts.run = { ...noCosts.run, cost_assumptions: {} };
    render(<RunReportView report={noCosts} />);

    expect(document.body.textContent ?? "").toContain("비용 가정 — 기록되지 않았습니다");
  });

  it("실패한 실행은 지표를 지어내지 않고 사유를 낸다", () => {
    const failed = report();
    failed.run = { ...failed.run, status: "failed", failed_reason: "그 구간에 적재된 캔들이 없습니다" };
    render(<RunReportView report={failed} />);

    expect(screen.getByRole("alert").textContent).toContain("그 구간에 적재된 캔들이 없습니다");
    expect(screen.queryByRole("region", { name: "판정 지표" })).toBeNull();
  });
});
