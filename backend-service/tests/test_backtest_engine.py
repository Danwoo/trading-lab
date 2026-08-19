#!/usr/bin/env python3
"""백테스트 엔진이 **손으로 계산한 값과 일치하는지** 확인한다 (#200).

## 왜 합성 캔들인가

실제 시세로는 「맞았는지」를 알 수 없다 — **틀린 엔진도 그럴듯한 곡선을 그린다.**
답을 아는 입력만이 엔진의 정확성을 증명한다.

각 케이스는 기대값을 **주석에 산식으로** 적는다. 기대값을 코드에서 다시 계산해 비교하면
같은 버그가 양쪽에 들어가 통과한다.

    cd backend-service && APP_ENV=development uv run python tests/test_backtest_engine.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from services.backtest.engine import BarSeries, CostModel, Strategy, run_single  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected, tol: float = 1e-6) -> None:
    global CHECKED
    CHECKED += 1
    ok = abs(actual - expected) <= tol if isinstance(expected, float) else actual == expected
    if not ok:
        FAILURES.append(f"{name}: 기대 {expected} · 실제 {actual}")


def series(closes: list[float]) -> BarSeries:
    n = len(closes)
    return BarSeries(
        instrument_id=1,
        dt=[f"2026-01-{i + 1:02d}" for i in range(n)],
        open=list(closes),
        high=list(closes),
        low=list(closes),
        close=list(closes),
        volume=[1000.0] * n,
    )


def strategy_from(entry_days: set[int], exit_days: set[int]) -> Strategy:
    """지정한 날에만 사고 파는 전략 — 규약 형태는 실제 전략과 같다."""
    module = SimpleNamespace(
        STRATEGY={"key": "fixture", "name": "고정", "timeframe": "1d", "params": []},
        indicators=lambda bars, params: {},
        entry=lambda ctx: ctx["index"] in entry_days,
        exit=lambda ctx: ctx["index"] in exit_days,
    )
    return Strategy(module)


FREE = CostModel(fee_rate=0.0, slippage_rate=0.0, sell_tax_rate=0.0)


def test_buy_and_hold() -> None:
    """① 한 종목 · 10봉 · 1일차 매수 후 보유 → 자산 = 초기자금 × (종가/매수가).

    초기자금 1,000 · 매수가 100 → 10주. 마지막 종가 150 → 10 × 150 = 1,500.
    """
    s = series([100, 110, 120, 130, 140, 145, 148, 149, 150, 150])
    r = run_single(
        strategy=strategy_from({0}, set()), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=FREE
    )
    check("① 매수 후 보유 최종 자산", r.final_equity, 1500.0)
    check("① 첫날 자산은 매수가 평가", r.equity[0].equity, 1000.0)
    check("① 미청산이므로 거래 기록 0건", len(r.trades), 0)
    check("① 현금은 0", r.equity[-1].cash, 0.0)


def test_costs_reduce_exactly() -> None:
    """② 비용을 넣으면 그만큼 정확히 줄어든다.

    수수료 1% · 슬리피지 0% · 매도세 0%, 100 에 사서 100 에 판다.
    매수: 현금 1,000 / (100 × 1.01) = 9.900990...주, 지출 = 수량×100 + 수량×100×0.01
    매도: 수량×100 − 수량×100×0.01
    최종 현금 = 1,000 − (N×100 × 1.01) + (N×100 × 0.99),  N = 1000/101
             = 1000 − 1000 + (1000/101)×100×0.99 = 980.198019...
    """
    s = series([100, 100, 100])
    costs = CostModel(fee_rate=0.01, slippage_rate=0.0, sell_tax_rate=0.0)
    r = run_single(
        strategy=strategy_from({0}, {2}), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=costs
    )
    check("② 왕복 후 자산", r.final_equity, (1000.0 / 101.0) * 100.0 * 0.99, tol=1e-6)
    check("② 거래 1건", len(r.trades), 1)


def test_no_signal_keeps_cash() -> None:
    """③ 매수 없이 끝나면 초기자금 그대로다 — 0 이 아니다.

    스펙 §8.5.1: 「매수 조건이 없으면 매매도 없다」.
    """
    s = series([100, 90, 80, 70])
    r = run_single(
        strategy=strategy_from(set(), set()), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=FREE
    )
    check("③ 자산 = 초기자금", r.final_equity, 1000.0)
    check("③ 거래 0건", len(r.trades), 0)
    check("③ 자산곡선은 그려진다", len(r.equity), 4)


def test_same_day_round_trip_loses_cost() -> None:
    """④ 같은 봉에 사고 팔면 왕복 비용만큼 손실.

    이 엔진은 한 봉에서 매수 뒤 다음 봉부터 매도를 본다(같은 봉 청산 없음).
    그래서 연속 두 봉으로 왕복을 만든다 — 가격이 같으면 손실은 비용뿐이다.
    수수료 0.5% 왕복 → 최종 = (1000/1.005) × 0.995 = 990.0497512...
    """
    s = series([100, 100])
    costs = CostModel(fee_rate=0.005, slippage_rate=0.0, sell_tax_rate=0.0)
    r = run_single(
        strategy=strategy_from({0}, {1}), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=costs
    )
    check("④ 왕복 비용만큼 손실", r.final_equity, (1000.0 / 1.005) * 0.995, tol=1e-6)
    check("④ 손실이다", r.final_equity < 1000.0, True)


def test_sell_tax_only_on_sell() -> None:
    """증권거래세는 **매도에만** 붙는다 (스펙 §8.5.1).

    수수료 0 · 슬리피지 0 · 매도세 1%. 100 에 사서 100 에 팔면 매도세만큼만 준다.
    매수 지출 = 1,000 (비용 0) → 10주. 매도 수령 = 1,000 × 0.99 = 990.
    """
    s = series([100, 100])
    costs = CostModel(fee_rate=0.0, slippage_rate=0.0, sell_tax_rate=0.01)
    r = run_single(
        strategy=strategy_from({0}, {1}), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=costs
    )
    check("매도세만 차감", r.final_equity, 990.0)
    # 차감만으로는 부족하다 — **얼마를 세금으로 냈는지 거래에 적혀야** 화면이 비용을 말한다.
    # 매도 대금 1,000 × 1% = 10. 이 단언이 없으면 `open_trade.tax += …` 를 지워도 초록이다.
    check("거래에 적힌 세금", r.trades[0].tax, 10.0)
    check("수수료는 0", r.trades[0].fee, 0.0)


def test_mae_mfe() -> None:
    """MAE/MFE — 보유 중 최대 미실현 손실·이익.

    100 에 10주 매수 후 80 → 120 → 100 에 청산.
    MAE = (80−100)×10 = −200 · MFE = (120−100)×10 = +200
    """
    s = series([100, 80, 120, 100])
    r = run_single(
        strategy=strategy_from({0}, {3}), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=FREE
    )
    check("MAE", r.trades[0].mae, -200.0)
    check("MFE", r.trades[0].mfe, 200.0)


def test_determinism() -> None:
    """같은 입력을 두 번 돌리면 같은 결과."""
    s = series([100, 105, 98, 110, 103])
    args = dict(strategy=strategy_from({0}, {3}), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=FREE)
    a, b = run_single(**args), run_single(**args)
    check("결정론 — 최종 자산", a.final_equity, b.final_equity)
    check("결정론 — 곡선 길이", len(a.equity), len(b.equity))


def test_cash_ledger_closes() -> None:
    """현금 원장이 닫힌다 — 이벤트 합이 최종 현금과 같다."""
    s = series([100, 120, 90])
    costs = CostModel(fee_rate=0.002, slippage_rate=0.001, sell_tax_rate=0.003)
    r = run_single(
        strategy=strategy_from({0}, {2}), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=costs
    )
    check("원장 합 = 최종 현금", sum(e.amount for e in r.cash_events), r.equity[-1].cash, tol=1e-9)
    check("초기자금 이벤트가 있다", r.cash_events[0].event_kind, "initial")


def test_empty_series() -> None:
    """캔들이 없으면 빈 결과 — 없는 계산을 한 척하지 않는다."""
    s = BarSeries(instrument_id=1, dt=[], open=[], high=[], low=[], close=[], volume=[])
    r = run_single(strategy=strategy_from({0}, set()), params={}, series=s, rows=[], initial_cash=1000.0, costs=FREE)
    check("빈 캔들 → 곡선 0점", len(r.equity), 0)
    check("빈 캔들 → 거래 0건", len(r.trades), 0)


def test_column_length_mismatch_raises() -> None:
    """컬럼 길이가 어긋나면 조용히 넘어가지 않는다."""
    global CHECKED
    CHECKED += 1
    try:
        BarSeries(instrument_id=1, dt=["a", "b"], open=[1.0], high=[1.0], low=[1.0], close=[1.0], volume=[1.0])
    except ValueError:
        return
    FAILURES.append("컬럼 길이 불일치가 통과했다")


def main() -> int:
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        fn()
    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < 20:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
