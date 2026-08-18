from typing import Any

from pydantic import BaseModel, Field


class BacktestRunIn(BaseModel):
    """단일 실행 입력. 격자가 기본(D-Q1)이라 이 경로는 격자의 한 칸을 다시 보는 자리다."""

    strategy_key: str = Field(..., max_length=40)
    params: dict[str, Any] = Field(default_factory=dict)
    market: str = Field(..., max_length=20)
    symbol: str = Field(..., max_length=20)
    period_from: str = Field(..., max_length=10)
    period_to: str = Field(..., max_length=10)
    initial_cash: float = Field(..., gt=0)
    costs: dict[str, float] | None = None
    bot_id: int | None = None
    parent_run_id: int | None = None


class BacktestGridIn(BacktestRunIn):
    """격자 실행 입력. `sweep` 은 파라미터 이름 → 훑을 값 목록이다 (grid.axes_from_spec)."""

    sweep: dict[str, list[Any]] = Field(..., min_length=1)


class RunCreatedOut(BaseModel):
    run_id: int
    status: str
    equity_rows: int
    trade_rows: int
    signal_rows: int
    cash_rows: int


class GridAxisOut(BaseModel):
    name: str
    values: list[Any]


class GridCellOut(BaseModel):
    run_id: int
    params: dict[str, Any]
    status: str
    failed_reason: str | None = None
    final_equity: float | None = None


class GridOut(BaseModel):
    shape: list[int]
    axes: list[GridAxisOut]
    cells: list[GridCellOut]
    # 격자를 훑는 것도 시도다 (스펙 §8.5.2) — 화면의 한계 계산이 이 수를 먹는다.
    attempts_used: int
    initial_cash: float


class MetricOut(BaseModel):
    """지표 하나 — 값과 유도 경로가 항상 함께 간다 (스펙 §8.5.3).

    `value` 가 없으면 `absent_reason` 이 왜인지 말하고, 화면은 그 문구를 그대로 쓴다.
    """

    key: str
    label: str
    value: float | None
    unit: str
    derived_from: str
    absent_reason: str | None = None
    note: str | None = None


class EquityPointOut(BaseModel):
    dt: str
    equity: float
    cash: float
    position_count: int
    gross_exposure: float


class TradeOut(BaseModel):
    trade_id: int
    instrument_id: int
    side: str
    entry_ts: str
    exit_ts: str | None
    qty: float
    fill_price: float
    exit_price: float | None
    fee: float
    slippage: float
    realized_pnl: float | None
    mae: float | None
    mfe: float | None


class RunSummaryOut(BaseModel):
    run_id: int
    bot_id: int | None
    parent_run_id: int | None
    attempt_no: int
    strategy_key: str
    strategy_version: str
    params: dict[str, Any]
    universe_def: dict[str, Any]
    adj_policy: str
    cost_assumptions: dict[str, float]
    period_from: str
    period_to: str
    initial_cash: float
    status: str
    failed_reason: str | None
    finished_dt: str | None


class RunReportOut(BaseModel):
    """한 조합의 리포트 — 곡선·거래·지표가 한 번에 온다 (칸 클릭은 계산이 아니라 조회다)."""

    run: RunSummaryOut
    equity: list[EquityPointOut]
    trades: list[TradeOut]
    metrics: list[MetricOut]
