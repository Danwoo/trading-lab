"""백테스트 엔진 — 한 조합을 정확히 돌려 결과를 남긴다 (#200).

## 이 파일이 무엇이 아닌가

**저장소에 손대지 않는다.** 캔들은 호출자가 이미 메모리에 올려서 넘긴다.

그 경계가 이 파일의 존재 이유다. 스펙 §6 의 실측이:

    20×20=400조합 · KR 전종목 10년(686만 bar)
      로드 1회 + 인메모리 400회  →  약 4.9분
      조합마다 DB 재조회         →  약 83분     ← I/O 가 계산의 16배

「로드 1회 + 인메모리 N회」를 주석으로 부탁하면 지켜지지 않는다. **엔진이 저장소를 아예
모르게** 해서 구조로 강제한다 — 조합 루프 안에서 DB 를 부르려면 이 층 밖으로 나가야 한다.
`scripts/verify_backtest_engine_purity.py` 가 그 경계를 지킨다.

## 컬럼 지향(SoA)

`backend-service` 에 numpy·pandas 가 없다. 686만 행에서 행 지향 1.81GB vs 컬럼 지향
0.35GB 라, 캔들은 `BarSeries` 처럼 **필드별 리스트**로 들고 다닌다.

## 계산 정의

스펙 §8.5.1 이 검산으로 잡은 정의를 따른다. 특히 **비용은 왕복 0.015% 수준 + 증권거래세
(매도만)** 다 — 위탁수수료 0.15% 는 10배 오차였고, 그 오차가 "연 비용 원금의 145%" 경고를
만들었다. 기본값을 여기 박지 않고 호출자가 넘긴다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class BarSeries:
    """한 종목의 캔들 — **컬럼 지향**. 필드마다 같은 길이의 리스트다."""

    instrument_id: int
    dt: list[str]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    volume: list[float]

    def __post_init__(self) -> None:
        lengths = {len(self.dt), len(self.open), len(self.high), len(self.low), len(self.close), len(self.volume)}
        if len(lengths) != 1:
            raise ValueError(f"캔들 컬럼 길이가 어긋난다: {lengths}")

        # **시간 순서를 계약으로 못 박는다.** 전략의 `indicators`·`entry`·`exit` 는 전부
        # 「오래된 것부터」를 전제로 index 를 읽는다 — 역순이나 중복이 섞이면 예외 없이
        # 틀린 곡선이 그려진다. 공급자(`bar_service`)에게 암묵적으로 맡기면 그 계약은
        # 코드 어디에도 없는 것이다.
        for i in range(1, len(self.dt)):
            if self.dt[i] <= self.dt[i - 1]:
                raise ValueError(
                    f"캔들이 오래된 것부터 정렬돼 있지 않다 (index {i}: {self.dt[i - 1]!r} 다음에 {self.dt[i]!r})"
                )

    def __len__(self) -> int:
        return len(self.dt)

    def rows(self) -> list[dict]:
        """전략 규약이 요구하는 행 지향 표현.

        전략의 `indicators(bars, params)` 가 `bar["close"]` 로 읽으므로 여기서만 변환한다 —
        **조합마다 다시 만들지 말고 한 번 만들어 재사용하라**(호출자 책임).
        """
        return [
            {
                "dt": self.dt[i],
                "open": self.open[i],
                "high": self.high[i],
                "low": self.low[i],
                "close": self.close[i],
                "volume": self.volume[i],
            }
            for i in range(len(self.dt))
        ]


@dataclass(frozen=True)
class CostModel:
    """비용 가정. 기본값을 두지 않는다 — 실행마다 무엇을 가정했는지 남아야 한다."""

    fee_rate: float  # 편도 수수료율 (왕복이면 두 번 물린다)
    slippage_rate: float  # 체결 미끄러짐
    sell_tax_rate: float  # 증권거래세 — **매도에만** 붙는다

    def buy_cost(self, notional: float) -> float:
        return notional * (self.fee_rate + self.slippage_rate)

    def sell_cost(self, notional: float) -> float:
        return notional * (self.fee_rate + self.slippage_rate + self.sell_tax_rate)


@dataclass
class Trade:
    instrument_id: int
    side: str
    entry_ts: str
    entry_price: float
    qty: float
    exit_ts: str | None = None
    exit_price: float | None = None
    fee: float = 0.0
    slippage: float = 0.0
    #: 증권거래세 — **매도에만** 붙는다. `sell_cost` 안에서만 차감되면 「얼마를 세금으로
    #: 냈는지」를 아무도 못 세어, 화면이 비용 격차를 말할 수 없다 (#271).
    tax: float = 0.0
    realized_pnl: float | None = None
    mae: float | None = None  # 보유 중 최대 미실현 손실
    mfe: float | None = None  # 보유 중 최대 미실현 이익


@dataclass
class CashEvent:
    dt: str
    event_kind: str  # initial · deposit · withdraw · fee · trade
    amount: float
    note: str | None = None


@dataclass
class EquityPoint:
    dt: str
    equity: float
    cash: float
    position_count: int
    gross_exposure: float


@dataclass
class RunResult:
    """엔진이 남기는 것 전부 — 스펙 §6 의 네 테이블 + 현금 원장에 그대로 대응한다."""

    equity: list[EquityPoint] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    signals: list[dict] = field(default_factory=list)
    cash_events: list[CashEvent] = field(default_factory=list)

    @property
    def final_equity(self) -> float:
        return self.equity[-1].equity if self.equity else 0.0


class Strategy:
    """전략 규약(`strategies/*.py`)의 얇은 어댑터.

    규약을 바꾸지 않는다 — 봇 저장(#150)이 그 규약에 물려 있다.
    """

    def __init__(self, module) -> None:
        for name in ("STRATEGY", "indicators", "entry", "exit"):
            if not hasattr(module, name):
                raise ValueError(f"전략 규약 위반: {name} 가 없다")
        self.module = module
        self.key: str = module.STRATEGY["key"]
        self.version: str = str(module.STRATEGY.get("version", "1"))


def run_single(
    *,
    strategy: Strategy,
    params: dict,
    series: BarSeries,
    rows: list[dict],
    initial_cash: float,
    costs: CostModel,
) -> RunResult:
    """한 종목 · 한 조합을 돌린다.

    `rows` 를 따로 받는 이유는 **격자 실행에서 재사용**하기 위해서다 — 조합마다 행 지향
    변환을 다시 하면 그것이 곧 새 병목이 된다.

    **매수 조건이 없으면 매매도 없다**(스펙 §8.5.1). 이 함수는 신호가 없으면 초기자금을
    그대로 유지한다 — 0 이 아니다.
    """
    if len(series) == 0:
        return RunResult()

    result = RunResult()
    result.cash_events.append(CashEvent(dt=series.dt[0], event_kind="initial", amount=initial_cash))

    indicators = strategy.module.indicators(rows, params)

    cash = initial_cash
    open_trade: Trade | None = None

    for index in range(len(series)):
        price = series.close[index]
        today = series.dt[index]
        ctx = {"index": index, "params": params, "indicators": indicators, "bars": rows}

        if open_trade is None:
            entered = bool(strategy.module.entry(ctx))
            result.signals.append(
                {
                    "dt": today,
                    "instrument_id": series.instrument_id,
                    "conditions": {"entry": entered},
                    "passed": entered,
                }
            )
            if entered and price > 0:
                # 비용을 감당할 수 있는 만큼만 산다 — 현금보다 많이 사면 원장이 안 닫힌다.
                unit = price * (1 + costs.fee_rate + costs.slippage_rate)
                qty = cash / unit if unit > 0 else 0.0
                if qty > 0:
                    notional = price * qty
                    cost = costs.buy_cost(notional)
                    cash -= notional + cost
                    open_trade = Trade(
                        instrument_id=series.instrument_id,
                        side="long",
                        entry_ts=today,
                        entry_price=price,
                        qty=qty,
                        fee=notional * costs.fee_rate,
                        slippage=notional * costs.slippage_rate,
                        mae=0.0,
                        mfe=0.0,
                    )
                    result.cash_events.append(CashEvent(dt=today, event_kind="trade", amount=-(notional + cost)))
        else:
            # MAE/MFE — 「얼마나 물렸다 살아났나」. 보유 중 매 봉에서 갱신한다.
            move = (price - open_trade.entry_price) * open_trade.qty
            open_trade.mae = min(open_trade.mae or 0.0, move)
            open_trade.mfe = max(open_trade.mfe or 0.0, move)

            # **청산 평가도 남긴다.** 스펙 R3 는 거래 목록의 한 행에서 「진입/청산 봉으로
            # 스크롤해 그 시점 신호 근거 표시」를 요구한다 — 진입만 남기면 R3 의 절반이
            # 영구히 빈다. 청산이 안 일어난 봉도 「왜 안 팔았나」의 근거다.
            exited = bool(strategy.module.exit(ctx))
            result.signals.append(
                {"dt": today, "instrument_id": series.instrument_id, "conditions": {"exit": exited}, "passed": exited}
            )

            if exited:
                notional = price * open_trade.qty
                cost = costs.sell_cost(notional)
                cash += notional - cost
                open_trade.exit_ts = today
                open_trade.exit_price = price
                open_trade.fee += notional * costs.fee_rate
                open_trade.slippage += notional * costs.slippage_rate
                open_trade.tax += notional * costs.sell_tax_rate
                entry_notional = open_trade.entry_price * open_trade.qty
                open_trade.realized_pnl = (notional - cost) - (entry_notional + costs.buy_cost(entry_notional))
                result.trades.append(open_trade)
                result.cash_events.append(CashEvent(dt=today, event_kind="trade", amount=notional - cost))
                open_trade = None

        held = open_trade.qty * price if open_trade else 0.0
        result.equity.append(
            EquityPoint(
                dt=today,
                equity=cash + held,
                cash=cash,
                position_count=1 if open_trade else 0,
                gross_exposure=held,
            )
        )

    # 구간 끝에 열려 있는 것은 청산하지 않는다 — 청산한 척하면 없는 거래를 만든 것이다.
    # 자산곡선의 마지막 점이 평가액으로 남고, 그 거래는 `trades` 에 들어가지 않는다.
    return result


def quantize(value: float, places: int = 4) -> Decimal:
    """DB Numeric 에 넣기 전 자리수 고정. 부동소수 잔재가 원장을 흔들지 않게."""
    return Decimal(repr(value)).quantize(Decimal(10) ** -places)
