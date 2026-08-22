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

from services.backtest.engine import BarSeries, CostModel, Strategy, affordable_shares, run_single  # noqa: E402

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


def require_open_position(result, label: str):
    """열린 자리가 없으면 **사유를 남기고** None 을 준다 — `AttributeError` 는 무엇이 틀렸는지 안 적는다."""
    global CHECKED
    CHECKED += 1
    if result.open_position is None:
        FAILURES.append(f"{label}: 구간 끝에 열린 자리가 결과에 없다 (엔진이 버렸다)")
        return None
    return result.open_position


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
    # **버리지는 않는다** (#314). 청산한 척은 안 하되, 열린 자리를 통째로 흘리면 자산곡선의
    # 마지막 점(1,500)이 어디서 왔는지 화면이 설명할 근거를 잃는다.
    op = require_open_position(r, "①")
    if op is None:
        return
    check("① 열린 자리의 진입일", op.entry_ts, "2026-01-01")
    check("① 열린 자리는 청산되지 않았다", op.exit_ts, None)
    check("① 실현손익이 없다", op.realized_pnl, None)
    check("① 원장에 남길 것 = 청산 0건 + 열린 자리 1건", len(r.positions()), 1)


def test_costs_reduce_exactly() -> None:
    """② 비용을 넣으면 그만큼 정확히 줄어든다.

    수수료 1% · 슬리피지 0% · 매도세 0%, 100 에 사서 100 에 판다.
    한 주 값 = 100 × 1.01 = 101 → 1,000 으로 **9주**(9×101 = 909, 10주면 1,010 으로 모자란다).
    매수 뒤 현금 = 1,000 − 909 = 91
    매도 수령 = 9×100 − 9×100×0.01 = 891 → 최종 자산 = 91 + 891 = **982**

    기대값이 980.198019... 에서 982 로 바뀐 것은 체결이 소수점에서 1주 단위 정수로 바뀌었기
    때문이다 (#313 — 남는 현금 91 은 현금으로 남는다).
    """
    s = series([100, 100, 100])
    costs = CostModel(fee_rate=0.01, slippage_rate=0.0, sell_tax_rate=0.0)
    r = run_single(
        strategy=strategy_from({0}, {2}), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=costs
    )
    check("② 왕복 후 자산", r.final_equity, 982.0, tol=1e-9)
    check("② 거래 1건", len(r.trades), 1)
    check("② 수량은 정수 9주", r.trades[0].qty, 9.0)


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
    """④ 사고 팔면 왕복 비용만큼 손실.

    이 엔진은 한 봉에서 매수 뒤 다음 봉부터 매도를 본다(같은 봉 청산 없음).
    그래서 연속 두 봉으로 왕복을 만든다 — 가격이 같으면 손실은 비용뿐이다.
    수수료 0.5% → 한 주 값 100.5 → 1,000 으로 **9주**, 지출 904.5 → 현금 95.5
    매도 수령 = 900 − 4.5 = 895.5 → 최종 = 95.5 + 895.5 = **991**  (왕복 비용 9 만큼 손실)

    기대값이 990.0497... 에서 991 로 바뀐 것은 1주 단위 체결 때문이다 (#313).
    """
    s = series([100, 100])
    costs = CostModel(fee_rate=0.005, slippage_rate=0.0, sell_tax_rate=0.0)
    r = run_single(
        strategy=strategy_from({0}, {1}), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=costs
    )
    check("④ 왕복 비용만큼 손실", r.final_equity, 991.0, tol=1e-9)
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


def test_open_position_carries_entry_cost() -> None:
    """열린 자리는 **이미 치른 진입 비용**을 들고 나간다 — 「치른 비용 0원」의 뿌리다 (#314).

    수수료 1% · 슬리피지 0%, 100 에 매수 후 보유. 1주 단위 체결(#313)이라 주당 지출 101원으로
    1,000원에 살 수 있는 것은 9주다 — 진입 수수료 = 9 × 100 × 0.01 = 9.0.
    """
    s = series([100, 120, 150])
    costs = CostModel(fee_rate=0.01, slippage_rate=0.0, sell_tax_rate=0.0)
    r = run_single(
        strategy=strategy_from({0}, set()), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=costs
    )
    check("청산 거래는 0건", len(r.trades), 0)
    op = require_open_position(r, "열린 자리 진입 비용")
    if op is None:
        return
    check("열린 자리의 진입 수수료", op.fee, 9.0 * 100.0 * 0.01, tol=1e-9)
    check("매도세는 아직 안 물렸다", op.tax, 0.0)
    check("수량", op.qty, 9.0, tol=1e-9)


def test_closed_run_has_no_open_position() -> None:
    """구간 끝에 자리가 없으면 `open_position` 은 `None` 이다 — 없는 자리를 만들지 않는다."""
    s = series([100, 110, 120])
    r = run_single(
        strategy=strategy_from({0}, {2}), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=FREE
    )
    check("청산 1건", len(r.trades), 1)
    check("열린 자리 없음", r.open_position, None)
    check("원장에 남길 것은 청산 1건뿐", len(r.positions()), 1)


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


def test_shares_are_whole() -> None:
    """⑤ 주식은 쪼개지지 않는다 — 남는 현금은 현금으로 남는다 (#313).

    초기자금 1,000 · 매수가 300 → 3주(900) 사고 현금 100 이 남는다.
    마지막 종가 400 → 3×400 + 100 = 1,300.  (소수점 체결이면 3.333…주로 1,333.33 이었다)
    """
    s = series([300, 400])
    r = run_single(
        strategy=strategy_from({0}, set()), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=FREE
    )
    check("⑤ 남는 현금은 현금으로 남는다", r.equity[-1].cash, 100.0)
    check("⑤ 보유 평가액 = 3주 × 400", r.equity[-1].gross_exposure, 1200.0)
    check("⑤ 최종 자산", r.final_equity, 1300.0)


def test_initial_cash_changes_the_verdict() -> None:
    """⑥ 시작 자금이 판정을 바꾼다 — 표시용 배수가 아니다 (#313).

    종가 300 → 600, 비용 0.
      시작 자금 1,000 → 3주 + 현금 100 → 3×600 + 100 = 1,900  → +90.0%
      시작 자금   900 → 3주 + 현금   0 → 3×600       = 1,800  → +100.0%

    소수점 체결이면 둘 다 정확히 +100% 로 같았다 — 그 「같음」이 이 이슈의 증상이었다.
    """
    s = series([300, 600])
    rich = run_single(
        strategy=strategy_from({0}, set()), params={}, series=s, rows=s.rows(), initial_cash=1000.0, costs=FREE
    )
    poor = run_single(
        strategy=strategy_from({0}, set()), params={}, series=s, rows=s.rows(), initial_cash=900.0, costs=FREE
    )
    check("⑥ 1,000 으로 시작한 수익률", (rich.final_equity - 1000.0) / 1000.0 * 100, 90.0)
    check("⑥ 900 으로 시작한 수익률", (poor.final_equity - 900.0) / 900.0 * 100, 100.0)
    check("⑥ 두 수익률이 다르다", (rich.final_equity - 1000.0) / 1000.0 == (poor.final_equity - 900.0) / 900.0, False)


def test_too_expensive_means_no_trade() -> None:
    """⑦ 한 주 값이 시작 자금보다 크면 거래 0건 — 못 사는 것을 산 척하지 않는다 (#313).

    189,700원짜리 한 주를 100,000원으로는 못 산다. 매수 신호가 나도 체결은 없고,
    자산은 초기자금 그대로다 (소수점 체결이면 0.527주를 샀다).
    """
    s = series([189700, 200000])
    r = run_single(
        strategy=strategy_from({0}, set()), params={}, series=s, rows=s.rows(), initial_cash=100000.0, costs=FREE
    )
    check("⑦ 거래 0건", len(r.trades), 0)
    check("⑦ 자산 = 초기자금", r.final_equity, 100000.0)
    check("⑦ 현금 그대로", r.equity[-1].cash, 100000.0)
    check("⑦ 보유 종목 없음", r.equity[-1].position_count, 0)


def test_affordable_shares_edges() -> None:
    """살 수 있는 주식 수의 경계 — 0주·딱 떨어짐·부동소수 잔재."""
    check("한 주도 못 사면 0주", affordable_shares(99.0, 100.0), 0)
    check("딱 떨어지면 다 산다", affordable_shares(1000.0, 100.0), 10)
    check("단가가 0 이면 0주", affordable_shares(1000.0, 0.0), 0)
    check("현금이 0 이면 0주", affordable_shares(0.0, 100.0), 0)
    # 7 × 0.7 = 4.8999999999999995 라 나눗셈이 6주로 떨어진다 — 잔재 때문에 한 주를 잃지 않는다.
    check("부동소수 잔재로 한 주를 잃지 않는다", affordable_shares(7 * 0.7, 0.7), 7)


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
