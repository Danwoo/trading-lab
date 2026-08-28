// @vitest-environment jsdom
//
// 한 조합의 리포트 (#203) — 지표 순서(D-Q2)와 「유도 경로 없는 숫자 금지」(§8.5.3)가
// 화면에서 지켜지는지.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

import { RunReportView } from "@/components/features/Bench/RunReportView";
import type { MetricOut, OpenPositionOut, RunReportOut, TradeOut } from "@/schemas/backtest/backtest";

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
      costless_summary: { final_equity: 1080000, return_pct: 8, trade_count: 3 },
      status: "succeeded",
      failed_reason: null,
      finished_dt: null,
    },
    equity: [
      { dt: "2026-01-02", equity: 1000000, cash: 1000000, position_count: 0, gross_exposure: 0 },
      { dt: "2026-01-03", equity: 1010000, cash: 1010000, position_count: 0, gross_exposure: 0 },
    ],
    trades: [],
    execution_assumptions: {
      order_unit: "1주 정수 내림 · 남는 현금은 현금으로 남습니다",
      fill_price: "신호가 난 그 봉의 종가 · 체결 지연 없음",
      liquidity_cap: "없음 · 그 봉의 거래량을 넘는 주문도 전량 체결됩니다",
      adj_policy: "unadjusted · 선언값입니다 (실제로 쓴 캔들의 조정 정책과 대조하지 않습니다)",
      stale_reason: null,
    },
    open_position: null,
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

function trade(overrides: Partial<TradeOut> = {}): TradeOut {
  return {
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

  it("원화 실현손익은 정수로 찍는다 — 같은 표 안에서 소수 자릿수가 갈리지 않는다 (F7)", () => {
    // 실측(리포트 → 거래 목록): 비용이 비율이라 원 단위 정수 체결에도 소수가 남아
    // `+1,810,707.32` 와 `+281,622` 가 한 표 안에 섞였다. 원화는 `won()` 과 같은 규칙(반올림)이다.
    const mixed = report({
      trades: [
        trade({ trade_id: 1, realized_pnl: 1810707.32 }),
        trade({ trade_id: 2, realized_pnl: 281622 }),
        trade({ trade_id: 3, realized_pnl: -4123.5 }),
      ],
    });
    render(<RunReportView report={mixed} />);

    const section = screen.getByRole("region", { name: "거래 목록" });
    const pnl = within(section)
      .getAllByRole("row")
      .slice(1)
      .map((row) => within(row).getAllByRole("cell").at(-1)?.textContent?.trim());
    expect(pnl).toEqual(["+1,810,707", "+281,622", "−4,124"]);
  });

  it("자산·낙폭 곡선이 그림으로 서고 요지를 이름으로 갖는다 — 캔버스만 있으면 보조기술에 곡선이 없다 (F9)", () => {
    render(<RunReportView report={report()} />);

    const figure = screen.getByRole("img", { name: /자산곡선과 낙폭 곡선/ });
    const name = figure.getAttribute("aria-label") ?? "";
    expect(name).toContain("2026-01-02 ~ 2026-01-03");
    expect(name).toContain("시작 1,000,000원 → 끝 1,010,000원");
    expect(name).toContain("최대 낙폭 0%");
  });

  it("자산곡선이 없으면 빈 이름의 그림을 만들지 않는다", () => {
    render(<RunReportView report={report({ equity: [] })} />);

    expect(screen.queryByRole("img")).toBeNull();
    expect(document.body.textContent).toContain("자산곡선이 없습니다");
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

  it("체결 가정을 비용 가정과 같은 자리에서 읽어 준다 — 주문 단위·체결가·유동성·시작 자금 (#313)", () => {
    render(<RunReportView report={report()} />);

    const section = screen.getByRole("region", { name: "체결 가정" });
    const rows = within(section)
      .getAllByRole("term")
      .map((dt) => [dt.textContent, dt.nextElementSibling?.textContent]);
    expect(rows).toEqual([
      ["시작 자금", "1,000,000원"],
      ["주문 단위", "1주 정수 내림 · 남는 현금은 현금으로 남습니다"],
      ["체결가", "신호가 난 그 봉의 종가 · 체결 지연 없음"],
      ["유동성 상한", "없음 · 그 봉의 거래량을 넘는 주문도 전량 체결됩니다"],
      // 조정 정책은 선언값이다 — 실제 캔들과 대조하지 않는다는 것까지 말해야 사실이 된다.
      ["조정 정책", "unadjusted · 선언값입니다 (실제로 쓴 캔들의 조정 정책과 대조하지 않습니다)"],
    ]);
  });

  it("소수점 체결로 돌았던 옛 실행은 그 사실이 화면에 뜬다 (#313)", () => {
    const stale = report();
    stale.execution_assumptions = {
      ...stale.execution_assumptions,
      stale_reason:
        "이 실행은 소수점 체결로 돌았습니다 — 거래 3건의 수량이 정수가 아닙니다. 지금 엔진은 1주 단위라 다시 돌리면 결과가 달라집니다",
    };
    render(<RunReportView report={stale} />);

    expect(screen.getByRole("note").textContent).toContain("소수점 체결로 돌았습니다");
  });

  it("가정이 비어 있으면 0% 로 지어내지 않고 기록이 없다고 말한다", () => {
    const noCosts = report();
    noCosts.run = { ...noCosts.run, cost_assumptions: {} };
    render(<RunReportView report={noCosts} />);

    expect(document.body.textContent ?? "").toContain("비용 가정 — 기록되지 않았습니다");
  });

  it("반영 열이 **이 실행이 실제로 끝낸 자산**이다 — 시작 자금이 아니다 (SC-007)", () => {
    // 픽스처: 시작 1,000,000 · 끝난 자산 1,010,000 · 대조군 1,080,000 → 격차는 70,000 이다.
    // 반영 칸에 시작 자금을 그리면 80,000 으로 읽힌다 — 같은 화면이 두 격차를 말하게 된다.
    render(<RunReportView report={report()} />);

    const table = screen.getByRole("table", { name: /비용 미반영 대비/ });
    const row = within(table).getByRole("row", { name: /끝난 자산/ });
    const cells = within(row)
      .getAllByRole("cell")
      .map((c) => c.textContent?.trim());
    expect(cells).toEqual(["1,010,000", "1,080,000"]);

    const diff = within(table).getByRole("row", { name: /차이/ });
    expect(within(diff).getAllByRole("cell").at(-1)?.textContent?.trim()).toBe("70,000");
  });

  it("손실 실행에서도 반영 열이 시작 자금으로 보이지 않는다", () => {
    const lost = report();
    lost.equity = [
      { dt: "2026-01-02", equity: 1000000, cash: 1000000, position_count: 0, gross_exposure: 0 },
      { dt: "2026-01-03", equity: 940000, cash: 940000, position_count: 0, gross_exposure: 0 },
    ];
    render(<RunReportView report={lost} />);

    const table = screen.getByRole("table", { name: /비용 미반영 대비/ });
    const row = within(table).getByRole("row", { name: /끝난 자산/ });
    expect(within(row).getAllByRole("cell")[0].textContent?.trim()).toBe("940,000");
  });

  it("대조군이 없는 옛 실행은 격차 0인 척하지 않는다", () => {
    const old = report();
    old.run = { ...old.run, costless_summary: null };
    render(<RunReportView report={old} />);

    const text = document.body.textContent ?? "";
    expect(text).toContain("대조군을 돌리지 않은 옛 실행입니다");
    expect(screen.queryByRole("table", { name: /비용 미반영 대비/ })).toBeNull();
  });

  it("대조군이 터진 실행에 재실행을 권하지 않는다 — 같은 이유로 또 터진다", () => {
    const broken = report();
    broken.run = {
      ...broken.run,
      costless_summary: { absent_reason: "대조군을 구하지 못했습니다 — 실행이 KeyError 으로 멈췄습니다" },
    };
    render(<RunReportView report={broken} />);

    const text = document.body.textContent ?? "";
    expect(text).toContain("대조군을 구하지 못했습니다");
    expect(text).not.toContain("옛 실행");
    expect(text).not.toContain("다시 실행하면");
    expect(screen.queryByRole("table", { name: /비용 미반영 대비/ })).toBeNull();
  });

  it("아직 도는 실행에 재실행을 권하지 않는다", () => {
    const running = report();
    running.run = { ...running.run, status: "running", costless_summary: null };
    render(<RunReportView report={running} />);

    const text = document.body.textContent ?? "";
    expect(text).toContain("실행이 끝나면 채워집니다");
    expect(text).not.toContain("옛 실행");
  });

  // ── 구간 끝에 열린 자리 (#314) ──────────────────────────────────────────
  //
  // 실측: 거래 목록 0건 · 승률 「거래 없음」 · 치른 비용 0원 인데 수익률이 +268.14% 로 떴다.
  // 성과의 100%가 미실현인데 화면 어디도 그 사실을 말하지 않았다.

  function openPosition(overrides: Partial<OpenPositionOut> = {}): OpenPositionOut {
    return {
      count: 1,
      value: 36814411.12,
      entry_ts: "2025-08-05",
      entry_cost: 6495.78,
      unrealized_pnl: 26814411.12,
      unrealized_share_pct: 100,
      derived_from: "2025-08-05 진입 · 자산곡선 마지막 점의 평가액 36,814,411원 − 진입 원금 10,000,000원",
      absent_reason: null,
      ...overrides,
    };
  }

  it("열린 자리를 안고 끝난 실행은 그 사실을 문장으로 말한다", () => {
    render(<RunReportView report={report({ open_position: openPosition() })} />);

    const section = screen.getByRole("region", { name: "구간 끝에 열린 자리" });
    expect(section.textContent).toContain("구간 끝에 열린 자리 1건");
    expect(section.textContent).toContain("2025-08-05 진입");
    expect(section.textContent).toContain("36,814,411");
    expect(section.textContent).toContain("이 성과의 100% 가 아직 안 판 자리의 미실현 이익입니다");
  });

  it("미실현 비중이 음수면 「성과의 −5.7% 가 평가액」이라 하지 않고 깎고 있다고 말한다 (F8)", () => {
    // 실측(run 843, ma=5·pullback=0.5) — 평가액 12,420,000 < 진입 원금 12,566,163 인 열린 자리.
    const losing = openPosition({ value: 12420000, unrealized_pnl: -146163, unrealized_share_pct: -5.7 });
    render(<RunReportView report={report({ open_position: losing })} />);

    const section = screen.getByRole("region", { name: "구간 끝에 열린 자리" });
    expect(section.textContent).toContain("열린 자리가 이 성과를 5.7% 깎고 있습니다(미실현 손실)");
    expect(section.textContent).not.toContain("-5.7%");
    expect(section.textContent).not.toContain("−5.7%");
  });

  it("총손익도 손실이면 「이 손실의 N%」로 — 미실현 손실이 손실의 일부다 (F8)", () => {
    render(
      <RunReportView
        report={report({ open_position: openPosition({ unrealized_pnl: -100000, unrealized_share_pct: 40 }) })}
      />,
    );

    const section = screen.getByRole("region", { name: "구간 끝에 열린 자리" });
    expect(section.textContent).toContain("이 손실의 40% 가 아직 안 판 자리의 미실현 손실입니다");
  });

  it("손실 실행에서 열린 자리가 평가이익이면 「메우고 있다」로 (F8)", () => {
    render(
      <RunReportView
        report={report({ open_position: openPosition({ unrealized_pnl: 30000, unrealized_share_pct: -12.5 }) })}
      />,
    );

    const section = screen.getByRole("region", { name: "구간 끝에 열린 자리" });
    expect(section.textContent).toContain("열린 자리가 이 손실을 12.5% 메우고 있습니다(미실현 이익)");
  });

  it("열린 자리가 없으면 그 자리를 만들지 않는다", () => {
    render(<RunReportView report={report()} />);

    expect(screen.queryByRole("region", { name: "구간 끝에 열린 자리" })).toBeNull();
  });

  it("「청산 안 함」을 「거래 없음」으로 뭉개지 않는다 — 거래 목록이 둘을 가른다", () => {
    render(
      <RunReportView
        report={report({
          open_position: openPosition({
            entry_ts: null,
            entry_cost: null,
            unrealized_pnl: null,
            unrealized_share_pct: null,
            absent_reason: "열린 자리의 진입 기록이 없는 옛 실행입니다 — 다시 실행하면 채워집니다",
          }),
        })}
      />,
    );

    const section = screen.getByRole("region", { name: "거래 목록" });
    expect(section.textContent).toContain("청산된 거래 없음 — 구간 끝에 열린 자리 1건이 있습니다");
    expect(section.textContent).not.toContain("청산은커녕 진입도 없었습니다");
  });

  it("미실현 비중을 못 구하면 0% 라 하지 않고 사유를 낸다", () => {
    render(
      <RunReportView
        report={report({
          open_position: openPosition({
            unrealized_share_pct: null,
            absent_reason: "열린 자리의 진입 기록이 없는 옛 실행입니다 — 다시 실행하면 채워집니다",
          }),
        })}
      />,
    );

    const section = screen.getByRole("region", { name: "구간 끝에 열린 자리" });
    expect(section.textContent).toContain("진입 기록이 없는 옛 실행입니다");
    expect(section.textContent).not.toContain("0% 가 아직 안 판");
  });

  it("열린 자리가 거래 목록에 한 줄로 선다 — 미청산임이 행에서도 읽힌다", () => {
    render(
      <RunReportView
        report={report({
          open_position: openPosition(),
          trades: [
            {
              trade_id: 9,
              instrument_id: 10,
              side: "long",
              entry_ts: "2025-08-05",
              exit_ts: null,
              qty: 100,
              fill_price: 99935,
              exit_price: null,
              fee: 1499,
              slippage: 4996,
              tax: 0,
              realized_pnl: null,
              mae: null,
              mfe: null,
            },
          ],
        })}
      />,
    );

    const section = screen.getByRole("region", { name: "거래 목록" });
    expect(section.textContent).toContain("보유 중");
    expect(section.textContent).toContain("미청산");
  });

  it("실패한 실행은 지표를 지어내지 않고 사유를 낸다", () => {
    const failed = report();
    failed.run = { ...failed.run, status: "failed", failed_reason: "그 구간에 적재된 캔들이 없습니다" };
    render(<RunReportView report={failed} />);

    expect(screen.getByRole("alert").textContent).toContain("그 구간에 적재된 캔들이 없습니다");
    expect(screen.queryByRole("region", { name: "판정 지표" })).toBeNull();
  });
});
