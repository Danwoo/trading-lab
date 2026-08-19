// schemas/backtest/backtest.ts
import { z } from "zod";
import { Optional, PositiveFloat, StrRange, array, object, record } from "@/lib/zod/helpers";

// 백엔드 계약: backend-service/app/schemas/backtest/backtest_schema.py
//   BacktestRunIn{strategy_key(40), params, market(20), symbol(20), period_from, period_to,
//                 initial_cash(>0), costs?, bot_id?, parent_run_id?}
//   BacktestGridIn = BacktestRunIn + sweep{이름 → 훑을 값 목록}

export const BacktestRunInSchema = object({
  strategy_key: StrRange(1, 40),
  // 값의 타입·범위는 전략 선언이 정하므로 여기서 좁히지 않는다 — 백엔드가 선언에 대해 검증한다.
  params: record(z.any()),
  market: StrRange(1, 20),
  symbol: StrRange(1, 20),
  period_from: StrRange(10, 10),
  period_to: StrRange(10, 10),
  initial_cash: PositiveFloat(),
  costs: Optional(record(z.number())),
  bot_id: Optional(z.number().int()),
  parent_run_id: Optional(z.number().int()),
});

export const BacktestGridInSchema = BacktestRunInSchema.extend({
  sweep: record(array(z.any()).min(1)),
});

export type BacktestRunIn = z.infer<typeof BacktestRunInSchema>;
export type BacktestGridIn = z.infer<typeof BacktestGridInSchema>;

export interface GridAxisOut {
  name: string;
  values: (number | string | boolean)[];
}

/**
 * 칸이 갖는 지표 — **격자는 조합을 고르는 자리라 1급이 여기 있어야 한다** (#220).
 *
 * 스펙 D-Q2: *"트레이더가 계좌를 닫는 이유는 샤프가 낮아서가 아니라 낙폭을 못 견뎌서다."*
 * 4급(수익률)로만 칠하면 「가장 많이 번 칸」이 가장 진해 보이고, 리포트를 열어 1급을 볼
 * 때는 이미 고른 뒤다.
 */
export interface GridCellMetrics {
  /** 1급 — 전 고점 아래에 머문 최장 (봉). */
  longest_underwater: number;
  /** 끝에서 미회복인가 — 「아직 회복 중」을 화면이 밝힌다. */
  still_underwater: boolean;
  /** 2급 — 그때의 고점 대비 최대 하락률 (%, 음수). */
  mdd_pct: number;
  /** 4급 — 구간 총수익률 (%). 버리지 않되 기본 채색이 아니다. */
  total_return_pct: number | null;
}

export interface GridCellOut {
  run_id: number;
  params: Record<string, unknown>;
  status: "succeeded" | "failed";
  failed_reason: string | null;
  final_equity: number | null;
  /** 실패한 칸은 null — 계산할 곡선이 없다. */
  metrics: GridCellMetrics | null;
}

export interface GridOut {
  shape: number[];
  axes: GridAxisOut[];
  cells: GridCellOut[];
  /** 격자를 훑는 것도 시도다 (스펙 §8.5.2) — 화면의 한계 계산이 이 수를 먹는다. */
  attempts_used: number;
  initial_cash: number;
}

/**
 * 지표 하나 — 값과 유도 경로가 항상 함께 간다 (스펙 §8.5.3).
 * `value` 가 null 이면 0 을 그리지 않고 `absent_reason` 을 그대로 낸다.
 */
export interface MetricOut {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  derived_from: string;
  absent_reason: string | null;
  note: string | null;
}

export interface EquityPointOut {
  dt: string;
  equity: number;
  cash: number;
  position_count: number;
  gross_exposure: number;
}

export interface TradeOut {
  trade_id: number;
  instrument_id: number;
  side: string;
  entry_ts: string;
  exit_ts: string | null;
  qty: number;
  fill_price: number;
  exit_price: number | null;
  fee: number;
  slippage: number;
  realized_pnl: number | null;
  mae: number | null;
  mfe: number | null;
}

export interface RunSummaryOut {
  run_id: number;
  bot_id: number | null;
  parent_run_id: number | null;
  attempt_no: number;
  strategy_key: string;
  strategy_version: string;
  params: Record<string, unknown>;
  universe_def: Record<string, unknown>;
  adj_policy: string;
  cost_assumptions: Record<string, number>;
  period_from: string;
  period_to: string;
  initial_cash: number;
  status: string;
  failed_reason: string | null;
  finished_dt: string | null;
}

/** 한 조합의 리포트 — 곡선·거래·지표가 한 번에 온다 (칸 클릭은 계산이 아니라 조회다). */
/** 봇 이력의 한 줄 — 목록에 필요한 것만. 곡선·거래는 칸을 눌러 리포트로 간다. */
export interface BotRunOut {
  run_id: number;
  status: string;
  strategy_key: string;
  universe_def: Record<string, unknown>;
  period_from: string;
  period_to: string;
  attempt_no: number;
  parent_run_id: number | null;
  finished_dt: string | null;
}

export interface BotRunListOut {
  items: BotRunOut[];
  total_count: number;
}

export interface RunReportOut {
  run: RunSummaryOut;
  equity: EquityPointOut[];
  trades: TradeOut[];
  metrics: MetricOut[];
}
