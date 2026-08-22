from typing import Any

from pydantic import BaseModel, Field


class BacktestRunIn(BaseModel):
    """단일 실행 입력. 격자가 기본(D-Q1)이라 이 경로는 격자의 한 칸을 다시 보는 자리다.

    각 필드의 형식은 **아래 `description` 이 정본**이다 — 그 문장이 OpenAPI 와 422 응답으로
    그대로 나간다 (#292).
    """

    strategy_key: str = Field(
        ...,
        max_length=40,
        description="전략 id — 등록된 전략의 키만 받습니다. 무엇이 지금 있는지는 "
        "GET /bot/strategy-catalog 가 답합니다.",
        examples=["sma_cross"],
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="전략 파라미터 — 이름 → 값. 그 전략이 선언한 이름만 받습니다(선언에 없는 이름은 거부). "
        "비우면 전략의 기본값.",
    )
    market: str = Field(
        ..., max_length=20, description="시장 코드 하나 (예: 'KOSPI', 'KOSDAQ', 'NASDAQ').", examples=["KOSPI"]
    )
    symbol: str = Field(..., max_length=20, description="종목 코드 하나. 시장은 market 에 따로 적습니다.")
    # 예시에 **구체적인 날짜를 적지 않는다** — 작성일이 굳어 반년 뒤 OpenAPI 가 낡은 날짜를 정답처럼 제시한다.
    period_from: str = Field(
        ...,
        max_length=10,
        description="검증 시작일 (YYYY-MM-DD). 적재된 캔들이 있는 구간만 돕니다 — 없으면 그 구간은 빈 채로 나옵니다.",
    )
    period_to: str = Field(
        ..., max_length=10, description="검증 종료일 (YYYY-MM-DD). 시작일보다 앞이면 훑을 봉이 없습니다."
    )
    initial_cash: float = Field(
        ...,
        gt=0,
        description="시작 자금 (원). 0 보다 커야 합니다 — 성과율의 분모라 0 이면 아무 지표도 못 냅니다.",
        examples=[10000000],
    )
    costs: dict[str, float] | None = Field(
        default=None,
        description="비용 가정 — fee_rate(수수료율) · slippage_rate(슬리피지율) · sell_tax_rate(매도세율) 중 "
        "덮어쓸 것만. 전부 비율이라 0.0015 가 0.15% 입니다. 비우면 기본 가정.",
    )
    bot_id: int | None = Field(default=None, description="이 실행을 매달 봇 id. 비우면 어느 봇에도 안 달립니다.")
    parent_run_id: int | None = Field(
        default=None,
        description="다시 보는 실행이면 그 원본 run_id. 계보로 이어져 「몇 번째 시도인가」가 남습니다. "
        "새 탐색이면 비웁니다.",
    )


class BacktestGridIn(BacktestRunIn):
    """격자 실행 입력. `sweep` 은 파라미터 이름 → 훑을 값 목록이다 (grid.axes_from_spec)."""

    sweep: dict[str, list[Any]] = Field(
        ...,
        min_length=1,
        description="훑을 축 — 파라미터 이름 → 값 목록. 최소 한 축은 있어야 하고, 이름은 그 전략이 "
        '선언한 것만 받습니다. 예: {"fast": [5, 10], "slow": [20, 60]}',
    )


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


class ExecutionAssumptionsOut(BaseModel):
    """이 결과가 무엇을 가정하고 체결했나 (#313).

    비용 3종만 밝히면 화면은 「이 셋만 가정했구나」로 읽힌다 — 체결 단위·체결가·유동성은
    비용보다 큰 왜곡인데 그 자리가 비어 있었다.
    """

    order_unit: str
    fill_price: str
    liquidity_cap: str
    adj_policy: str
    #: 지금 엔진의 가정과 **다른 모형으로 돌았던** 실행이면 그 사실. 아니면 `None`.
    stale_reason: str | None


class OpenPositionOut(BaseModel):
    """구간 끝에 청산되지 않고 남은 자리.

    자산곡선의 마지막 점은 이 자리의 **평가액**을 담는데 실현손익은 없다 — 그래서 「거래 0건」과
    「+268%」가 한 화면에 나란히 섰다. 이 필드가 없으면 화면은 그 모순을 설명할 근거가 없다.

    `entry_cost` 가 `None` 이면 진입 기록이 없는 옛 실행이다 — **0 원이 아니라 모르는 것**이고
    `absent_reason` 이 왜인지 말한다.
    """

    count: int
    #: 구간 끝 평가액 (원).
    value: float
    entry_ts: str | None
    entry_cost: float | None
    unrealized_pnl: float | None
    #: 이 실행의 총손익 중 미실현 비중 (%). 100 이면 성과 전부가 아직 안 판 자리다.
    unrealized_share_pct: float | None
    derived_from: str
    absent_reason: str | None = None


class RunReportOut(BaseModel):
    """한 조합의 리포트 — 곡선·거래·지표가 한 번에 온다 (칸 클릭은 계산이 아니라 조회다)."""

    run: RunSummaryOut
    equity: list[EquityPointOut]
    trades: list[TradeOut]
    metrics: list[MetricOut]
    execution_assumptions: ExecutionAssumptionsOut
    #: **이 필드를 선언하지 않으면 FastAPI 가 통째로 버린다** — 화면은 열린 자리를 영영 못 본다.
    open_position: OpenPositionOut | None = None
