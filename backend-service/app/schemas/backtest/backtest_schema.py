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


class GridCellMetricsOut(BaseModel):
    """격자 칸이 지고 다니는 **1급 지표** (#220).

    격자는 조합을 **고르는** 자리라, 4급(수익률)만 보이면 「가장 많이 번 칸」이 가장 진해
    보이고 사용자는 그 칸을 고른다 — 스펙 D-Q2 가 뒤집어 놓은 순서와 정면으로 어긋난다.
    """

    #: 1급 — 전 고점 아래에 머문 최장 (봉).
    longest_underwater: float
    #: 끝에서 미회복인가 — 「아직 회복 중」을 화면이 밝힌다.
    still_underwater: bool
    #: 2급 — 그때의 고점 대비 최대 하락률 (%, 음수).
    mdd_pct: float
    #: 4급 — 구간 총수익률 (%). 버리지 않되 기본 채색이 아니다.
    total_return_pct: float | None = None


class GridCellOut(BaseModel):
    run_id: int
    params: dict[str, Any]
    status: str
    failed_reason: str | None = None
    final_equity: float | None = None
    #: **이 필드가 없으면 응답에서 통째로 사라진다.** 서비스는 만들어 넣는데 응답 모델이
    #: 선언하지 않으면 FastAPI 가 버리고, 화면은 채색 값을 못 구해 **성공한 칸을 전부
    #: 「실패」로 그린다** (#268 실측 — 25칸 전부). 프론트 `GridCellOut` 과 짝이다.
    metrics: GridCellMetricsOut | None = None


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
    tax: float
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
    #: 같은 조합을 비용 0으로 다시 돌린 요약. `None` 은 「격차 0」이 아니라 **대조군을 안 돌린
    #: 옛 실행**이다 — 화면이 그 둘을 갈라 말한다 (SC-007).
    costless_summary: dict[str, Any] | None
    status: str
    failed_reason: str | None
    finished_dt: str | None


class BotRunOut(BaseModel):
    """봇 이력의 한 줄 — 목록에 필요한 것만. 곡선·거래는 칸을 눌러 리포트로 간다."""

    run_id: int
    status: str
    strategy_key: str
    universe_def: dict[str, Any]
    period_from: str
    period_to: str
    attempt_no: int
    parent_run_id: int | None
    finished_dt: str | None


class BotRunListOut(BaseModel):
    items: list[BotRunOut]
    total_count: int


class RunReportOut(BaseModel):
    """한 조합의 리포트 — 곡선·거래·지표가 한 번에 온다 (칸 클릭은 계산이 아니라 조회다)."""

    run: RunSummaryOut
    equity: list[EquityPointOut]
    trades: list[TradeOut]
    metrics: list[MetricOut]
