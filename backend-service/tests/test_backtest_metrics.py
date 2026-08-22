#!/usr/bin/env python3
"""판정 지표가 **스펙 §8.5.1 의 정의대로** 계산되는지 확인한다 (#201).

그 표는 추측이 아니라 프로토타입을 떼어 실행해 찾은 **실제 버그 목록**이다. 그래서 각
케이스는 「잘못된 구현이면 무엇이 나오는가」를 함께 적는다 — 그 값이 나오면 되돌아간 것이다.

    cd backend-service && APP_ENV=development uv run python tests/test_backtest_metrics.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from services.backtest.engine import BarSeries, CostModel, Strategy, run_single  # noqa: E402
from services.backtest.metrics import (  # noqa: E402
    Metric,
    compute,
    drawdown_amount,
    longest_underwater,
    max_drawdown,
    summarize_open_position,
    window,
)

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected, tol: float = 1e-6) -> None:
    global CHECKED
    CHECKED += 1
    if isinstance(expected, float) and isinstance(actual, (int, float)):
        ok = abs(actual - expected) <= tol
    else:
        ok = actual == expected
    if not ok:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


class _Missing:
    """찾는 지표가 없을 때 크래시 대신 이것이 온다.

    `next(...)` 가 StopIteration 으로 죽으면 **무엇이 틀렸는지 아무도 못 읽는다** —
    빨간불은 뜨지만 사유가 안 나온다. 없는 것도 하나의 실패로 기록한다.
    """

    def __init__(self, key: str) -> None:
        self.key, self.value, self.absent_reason = key, "<지표 없음>", "<지표 없음>"
        self.derived_from, self.note, self.label, self.unit = "", None, key, ""


def by_key(metrics: list[Metric], key: str):
    for m in metrics:
        if m.key == key:
            return m
    FAILURES.append(f"지표 `{key}` 가 결과에 없다 (나온 것: {[m.key for m in metrics]})")
    return _Missing(key)


def dates(n: int, start_month: int = 1) -> list[str]:
    return [f"2026-{start_month:02d}-{i + 1:02d}" for i in range(n)]


def test_drawdown_amount_uses_peak_not_principal() -> None:
    """낙폭 금액은 **그때의 고점 평가액 × MDD** 다 — 원금 × MDD 가 아니다.

    원금 1,000 → 3,000 까지 오른 뒤 2,400 으로 하락.
      올바름: 고점 3,000 × −20% = −600
      잘못됨: 원금 1,000 × −20% = −200   ← 실측 36% 과소의 정체
    """
    equity = [1000.0, 2000.0, 3000.0, 2400.0]
    ratio, _, _ = max_drawdown(equity)
    check("MDD 비율", ratio, -0.2)
    check("낙폭 금액 = 고점 × MDD", drawdown_amount(equity), -600.0)
    check("원금 × MDD 가 아니다", drawdown_amount(equity) != -200.0, True)


def test_underwater_is_below_prior_peak_not_principal() -> None:
    """언더워터는 **전 고점 아래**에 머문 최장이다 — 원금 회복까지가 아니다.

    원금 1,000 → 3,000 → 2,000 이 5봉 지속 → 3,100 회복.
    원금(1,000)은 한참 위지만 그 트레이더는 5봉 물려 있었다.
      올바름: 5
      잘못됨: 0  (원금 위이므로 「물린 적 없음」)
    """
    equity = [1000.0, 3000.0, 2000.0, 2000.0, 2000.0, 2000.0, 2000.0, 3100.0]
    longest, still = longest_underwater(equity)
    check("전 고점 아래 최장", longest, 5)
    check("끝에서 회복됨", still, False)
    check("원금 기준이면 0 이었을 것", longest != 0, True)


def test_underwater_still_recovering() -> None:
    """끝에서 미회복이면 「아직 회복 중」을 명시한다."""
    equity = [1000.0, 1500.0, 1200.0, 1100.0]
    longest, still = longest_underwater(equity)
    check("미회복 길이", longest, 2)
    check("아직 회복 중", still, True)
    m = by_key(
        compute(
            equity_dt=dates(4),
            equity=equity,
            trades=[],
            round_trip_cost_rate=0.0,
            initial_cash=1000.0,
            sell_tax_rate=0.0,
            open_position=None,
            costless_summary=None,
        ),
        "longest_underwater",
    )
    check("메트릭 note 가 말한다", m.note, "아직 회복 중")


def test_short_sample_is_not_annualized() -> None:
    """표본이 짧으면 연환산하지 않는다 — 대신 구간 총수익률이 온다.

    스펙: 26일 구간을 연환산하면 57.8% 가 나온다.
    """
    equity = [1000.0 + i * 5 for i in range(26)]
    ms = compute(
        equity_dt=dates(26),
        equity=equity,
        trades=[],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0,
        open_position=None,
        costless_summary=None,
    )
    cagr = by_key(ms, "cagr")
    check("CAGR 은 없다", cagr.value, None)
    check("이유를 말한다", "연환산하지 않습니다" in (cagr.absent_reason or ""), True)
    total = by_key(ms, "total_return")
    check("구간 총수익률이 대신 온다", total.value, 12.5)  # 1125/1000 − 1 = 12.5%


def test_long_sample_is_annualized() -> None:
    """1년 이상이면 연환산한다. 2년에 자산 2배 → CAGR ≈ 41.42%."""
    dts = ["2024-01-01", "2026-01-01"]
    ms = compute(
        equity_dt=dts,
        equity=[1000.0, 2000.0],
        trades=[],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0,
        open_position=None,
        costless_summary=None,
    )
    cagr = by_key(ms, "cagr")
    check("CAGR 계산됨", cagr.value is not None, True)
    check("CAGR 값", cagr.value, (2.0 ** (365 / 731.0) - 1) * 100, tol=0.5)


def test_calmar_absent_when_cagr_absent() -> None:
    """CAGR 이 없으면 Calmar 도 없다 — 없는 계산을 한 척하지 않는다."""
    equity = [1000.0, 1200.0, 900.0]
    ms = compute(
        equity_dt=dates(3),
        equity=equity,
        trades=[],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0,
        open_position=None,
        costless_summary=None,
    )
    calmar = by_key(ms, "calmar")
    check("Calmar 없음", calmar.value, None)
    check("이유가 CAGR 부재", "연환산 수익률이 없어" in (calmar.absent_reason or ""), True)


def test_no_trades_is_not_zero_percent() -> None:
    """거래 0건이면 승률은 `0%` 가 아니라 「거래 없음」이다 (스펙 §8.5.3)."""
    ms = compute(
        equity_dt=dates(3),
        equity=[1000.0, 1000.0, 1000.0],
        trades=[],
        round_trip_cost_rate=0.001,
        initial_cash=1000.0,
        sell_tax_rate=0.0,
        open_position=None,
        costless_summary=None,
    )
    win = by_key(ms, "win_rate")
    check("승률 값이 없다", win.value, None)
    check("0.0 이 아니다", win.value != 0.0, True)
    check("「거래 없음」이라 말한다", "거래 없음" in (win.absent_reason or ""), True)


def test_every_metric_carries_derivation() -> None:
    """**모든** 지표가 유도 경로를 갖는다 (스펙 §8.5.3).

    근거 없이 정밀한 숫자는 근거 없이 뭉뚱그린 숫자보다 나쁘다.
    """
    trade = SimpleNamespace(realized_pnl=50.0, entry_price=100.0, qty=10.0)
    ms = compute(
        equity_dt=["2024-01-01", "2025-06-01", "2026-01-01"],
        equity=[1000.0, 1300.0, 1200.0],
        trades=[trade],
        round_trip_cost_rate=0.0015,
        initial_cash=1000.0,
        sell_tax_rate=0.0,
        open_position=None,
        costless_summary=None,
    )
    global CHECKED
    for m in ms:
        CHECKED += 1
        if not m.derived_from:
            FAILURES.append(f"{m.key} 에 유도 경로가 없다")
        CHECKED += 1
        if m.value is None and not m.absent_reason:
            FAILURES.append(f"{m.key} 가 값도 사유도 없다")


def test_metric_order_is_the_decided_one() -> None:
    """순서가 스펙 D-Q2 다 — 최장 미회복 기간이 맨 위."""
    trade = SimpleNamespace(realized_pnl=50.0, entry_price=100.0, qty=10.0)
    ms = compute(
        equity_dt=["2024-01-01", "2026-01-01"],
        equity=[1000.0, 1400.0],
        trades=[trade],
        round_trip_cost_rate=0.0015,
        initial_cash=1000.0,
        sell_tax_rate=0.0,
        open_position=None,
        costless_summary=None,
    )
    check("1급이 최장 미회복 기간", ms[0].key, "longest_underwater")
    keys = [m.key for m in ms]
    check("샤프는 뒤에 있다", keys.index("sharpe") > keys.index("mdd"), True)
    check("샤프가 최장 미회복보다 뒤", keys.index("sharpe") > keys.index("longest_underwater"), True)


def test_window_inherits_prior_peak() -> None:
    """구간을 잘라도 **구간 밖의 직전 고점을 이어받는다.**

    자산 1,000 → 2,000(고점) → 1,500 → 1,400. 구간을 3번째부터 자르면:
      올바름: 이어받은 고점 2,000 (이미 물려 있는 상태로 시작)
      잘못됨: 1,500 을 고점으로 리셋 → 낙폭이 실제보다 작아 보인다
    """
    dts = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    eq = [1000.0, 2000.0, 1500.0, 1400.0]
    wd, wv, inherited = window(dts, eq, "2026-01-03", "2026-01-04")
    check("자른 길이", len(wv), 2)
    check("이어받은 고점", inherited, 2000.0)
    check("리셋했다면 1500 이었을 것", inherited != 1500.0, True)


def test_avg_trade_is_realized_pnl_and_not_charged_twice() -> None:
    """거래당 평균은 **실현손익(순액) 그대로**다 — 왕복 비용률을 다시 빼지 않는다 (#312).

    이 케이스는 원래 `4.85` 를 기대했다(= 5 − 0.15). 그 기대가 엔진 계약과 어긋난다 —
    `engine` 의 `realized_pnl` 은 양쪽 비용을 이미 치른 뒤의 순액이라, 거기서 왕복 비용률을
    또 빼면 같은 비용을 두 번 문다. 기대값을 새 정의로 옮긴다.

    100 원에 10주(진입금액 1,000) 사서 실현손익 50 → 50 / 1,000 = 5.00%.
    왕복 비용률 0.15% 는 값에서 빼지 않고 `note` 로만 선다.
      이중 차감이면: 5 − 0.15 = 4.85%   ← 되돌아간 것이다
    """
    trade = SimpleNamespace(realized_pnl=50.0, entry_price=100.0, qty=10.0)
    ms = compute(
        equity_dt=dates(3),
        equity=[1000.0, 1020.0, 1050.0],
        trades=[trade],
        round_trip_cost_rate=0.0015,
        initial_cash=1000.0,
        sell_tax_rate=0.0,
        open_position=None,
        costless_summary=None,
    )
    metric = by_key(ms, "avg_trade_vs_cost")
    check("거래당 평균 = 실현손익 평균 ÷ 진입금액", metric.value, 5.0, tol=1e-9)
    check("이중 차감값이 아니다", metric.value != 4.85, True)
    # 유도 문구가 계산과 어긋나면 그것도 결함이다 (스펙 §8.5.3).
    check("유도 문구가 순액임을 말한다", "차감 후" in metric.derived_from, True)
    check("유도 문구가 다시 빼지 않는다", "− 왕복 비용률" in metric.derived_from, False)
    check("가정 비율은 note 로 선다", metric.note, "왕복 비용률 가정 0.150%")


def _one_trade_run(costs: CostModel):
    """100 원에 사서 110 원에 파는 거래 **1건**을 엔진으로 실제 돌린다.

    지표가 아니라 **엔진이 남긴 실현손익**을 입력으로 쓰기 위해서다 — 이 이슈(#312)의 결함은
    엔진과 지표의 계약이 어긋난 데서 났고, 손으로 만든 `SimpleNamespace` 로는 그 어긋남이
    영원히 안 잡힌다.
    """
    module = SimpleNamespace(
        STRATEGY={"key": "fixture", "name": "고정", "timeframe": "1d", "params": []},
        indicators=lambda bars, params: {},
        entry=lambda ctx: ctx["index"] == 0,
        exit=lambda ctx: ctx["index"] == 1,
    )
    closes = [100.0, 110.0, 110.0]
    series = BarSeries(
        instrument_id=1,
        dt=dates(3),
        open=list(closes),
        high=list(closes),
        low=list(closes),
        close=list(closes),
        volume=[1000.0] * 3,
    )
    return run_single(
        strategy=Strategy(module),
        params={},
        series=series,
        rows=series.rows(),
        initial_cash=1_000_000.0,
        costs=costs,
    )


def _avg_trade_metric(result, round_trip_cost_rate: float, sell_tax_rate: float):
    return by_key(
        compute(
            equity_dt=[p.dt for p in result.equity],
            equity=[p.equity for p in result.equity],
            trades=result.trades,
            round_trip_cost_rate=round_trip_cost_rate,
            initial_cash=1_000_000.0,
            sell_tax_rate=sell_tax_rate,
            costless_summary=None,
            open_position=None,
        ),
        "avg_trade_vs_cost",
    )


def test_avg_trade_moves_by_one_cost_not_two() -> None:
    """비용을 0 → 기본 → 소매로 올려도 이 지표는 **비용만큼 한 번** 움직인다 (#312).

    엔진은 진입금액 N 에 매수율 b, 청산금액 1.1N 에 매도율 s 를 물린다. 그래서
    거래당 평균 실현수익률은 손으로 이렇게 나온다:

        avg% = [1.1 × (1 − s) − (1 + b)] × 100

      비용 0     b=0        s=0        →  (1.1 − 1)                 × 100 = 10.0000%
      기본       b=0.00065  s=0.00245  →  (1.097305 − 1.00065)      × 100 =  9.6655%
      소매       b=0.0045   s=0.0063   →  (1.09307  − 1.0045)       × 100 =  8.8570%

    비용 0 대비 벌어진 폭이 곧 **실제로 치른 비용**이다 — 기본 0.3345p · 소매 1.1430p.
    왕복 비용률(기본 0.31% · 소매 1.08%) 을 값에서 또 빼면 그 폭이 두 배가 된다:
      이중 차감이면: 기본 9.3555% · 소매 7.7770%   ← 되돌아간 것이다
    """
    free = _avg_trade_metric(_one_trade_run(CostModel(fee_rate=0.0, slippage_rate=0.0, sell_tax_rate=0.0)), 0.0, 0.0)
    check("비용 0 세계의 거래당 평균", free.value, 10.0, tol=1e-8)

    # (왕복 비용률, 손으로 계산한 지표값, 비용 0 대비 벌어질 폭, 이중 차감이면 나올 값)
    worlds = (
        (
            "기본",
            CostModel(fee_rate=0.00015, slippage_rate=0.0005, sell_tax_rate=0.0018),
            0.0031,
            9.6655,
            0.3345,
            9.3555,
        ),
        ("소매", CostModel(fee_rate=0.0015, slippage_rate=0.003, sell_tax_rate=0.0018), 0.0108, 8.8570, 1.1430, 7.7770),
    )
    for name, costs, round_trip, expected, gap, double_charged in worlds:
        metric = _avg_trade_metric(_one_trade_run(costs), round_trip, costs.sell_tax_rate)
        check(f"{name} 비용 세계의 거래당 평균", metric.value, expected, tol=1e-8)
        check(f"{name} — 비용 0 대비 폭 = 실제 치른 비용", free.value - metric.value, gap, tol=1e-8)
        check(f"{name} — 이중 차감값이 아니다", abs(metric.value - double_charged) > 1e-6, True)
        # 폭이 왕복 비용률의 두 배 근처면 두 번 문 것이다. 한 번만 물었으면 1배 언저리다
        # (청산금액이 진입금액보다 크면 1배를 조금 넘는다 — 매도측 비용의 분모가 더 크다).
        check(
            f"{name} — 폭이 왕복 비용률의 1.5배를 넘지 않는다",
            (free.value - metric.value) < round_trip * 100 * 1.5,
            True,
        )


def test_empty_equity_says_why() -> None:
    """자산곡선이 없으면 전 지표가 사유를 단다 — 0 으로 채우지 않는다."""
    ms = compute(
        equity_dt=[],
        equity=[],
        trades=[],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0,
        open_position=None,
        costless_summary=None,
    )
    global CHECKED
    CHECKED += 1
    if not ms:
        FAILURES.append("빈 자산곡선에 지표가 하나도 없다 — 사유를 내야 한다")
        return
    for m in ms:
        CHECKED += 1
        if m.value is not None or not m.absent_reason:
            FAILURES.append(f"{m.key} 가 빈 곡선인데 값을 냈다")


def _cost_trade(*, fee: float, slippage: float, tax: float):
    """비용 3종을 실은 청산 거래. 100원 10주, 실현손익 50."""
    return SimpleNamespace(realized_pnl=50.0, entry_price=100.0, qty=10.0, fee=fee, slippage=slippage, tax=tax)


def test_cost_paid_sums_all_three_axes() -> None:
    """치른 비용 = 수수료 + 슬리피지 + **세금**.

    세 축 중 하나라도 안 넘어오면 그만큼 조용히 적게 나온다 — 실측으로 25거래에 0원이
    나왔던 자리다. 값 단언이 없으면 그 회귀가 다시 초록으로 지나간다.
    """
    trades = [_cost_trade(fee=1.5, slippage=5.0, tax=18.0), _cost_trade(fee=1.5, slippage=5.0, tax=18.0)]
    ms = compute(
        equity_dt=dates(3),
        equity=[990.0, 1020.0, 1050.0],
        trades=trades,
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0018,
        open_position=None,
        costless_summary=None,
    )
    check("치른 비용", by_key(ms, "cost_paid").value, 49.0)
    # 분모는 시작 자금 1,000 이지 `equity[0]`(=990) 이 아니다. 990 이면 4.9495… 가 나온다.
    check("비용이 먹은 수익률", by_key(ms, "cost_drag_pct").value, 4.9, tol=1e-9)


def test_cost_drag_denominator_is_initial_cash() -> None:
    """`equity[0]` 을 분모로 쓰면 첫 봉에서 진입한 run 이 이름과 다른 값을 낸다."""
    trades = [_cost_trade(fee=0.0, slippage=0.0, tax=10.0)]
    ms = compute(
        equity_dt=dates(2),
        equity=[500.0, 600.0],
        trades=trades,
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0018,
        open_position=None,
        costless_summary=None,
    )
    # 잘못된 구현(= equity[0]=500)이면 2.0 이 나온다.
    check("분모 = 시작 자금", by_key(ms, "cost_drag_pct").value, 1.0, tol=1e-9)


def test_old_run_without_tax_record_says_so() -> None:
    """세율이 걸려 있는데 청산 거래의 세금이 전부 0이면 **기록이 없는 것**이다.

    합계를 내면 세금(명시 비용의 절반 이상)을 뺀 값을 「증권거래세 포함」이라 읽어 준다.
    """
    trades = [_cost_trade(fee=1.5, slippage=5.0, tax=0.0)]
    ms = compute(
        equity_dt=dates(2),
        equity=[1000.0, 1050.0],
        trades=trades,
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0018,
        open_position=None,
        costless_summary=None,
    )
    for key in ("cost_paid", "cost_drag_pct"):
        m = by_key(ms, key)
        check(f"{key} 값 없음", m.value, None)
        global CHECKED
        CHECKED += 1
        if not m.absent_reason:
            FAILURES.append(f"{key} 가 옛 실행인데 사유 없이 비었다")


def test_zero_tax_rate_run_still_reports_cost() -> None:
    """세율이 0인 run 은 세금 0이 정상이다 — 옛 실행으로 오인하면 안 된다."""
    trades = [_cost_trade(fee=1.5, slippage=5.0, tax=0.0)]
    ms = compute(
        equity_dt=dates(2),
        equity=[1000.0, 1050.0],
        trades=trades,
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0,
        open_position=None,
        costless_summary=None,
    )
    check("세율 0 run 의 치른 비용", by_key(ms, "cost_paid").value, 6.5)


def test_cost_gap_is_the_rerun_difference() -> None:
    """격차 = **다시 돌린** 대조군 수익률 − 이 실행 수익률. 나눗셈이 아니다."""
    ms = compute(
        equity_dt=dates(3),
        equity=[1000.0, 1020.0, 1050.0],
        trades=[_cost_trade(fee=1.5, slippage=5.0, tax=18.0)],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0018,
        open_position=None,
        costless_summary={"final_equity": 1080.0, "return_pct": 8.0, "trade_count": 1},
    )
    # 이 실행 = (1050 − 1000) / 1000 = 5%. 대조군 8%. 격차 3p.
    check("비용 격차", by_key(ms, "cost_gap_pct").value, 3.0, tol=1e-9)


def test_cost_gap_derivation_names_both_worlds() -> None:
    """유도 문구가 **두 수익률을 다 적는다** — 어디서 온 격차인지 화면이 그대로 읽는다."""
    ms = compute(
        equity_dt=dates(3),
        equity=[1000.0, 1020.0, 1050.0],
        trades=[_cost_trade(fee=1.5, slippage=5.0, tax=18.0)],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0018,
        open_position=None,
        costless_summary={"final_equity": 1080.0, "return_pct": 8.0, "trade_count": 1},
    )
    derived = by_key(ms, "cost_gap_pct").derived_from or ""
    check("대조군 수익률을 적는다", "8.00%" in derived, True)
    check("이 실행 수익률을 적는다", "5.00%" in derived, True)


def test_broken_twin_is_not_called_an_old_run() -> None:
    """대조군이 **터진** 실행에 「옛 실행이니 다시 돌려라」고 하지 않는다 — 또 터진다."""
    ms = compute(
        equity_dt=dates(3),
        equity=[1000.0, 1020.0, 1050.0],
        trades=[_cost_trade(fee=1.5, slippage=5.0, tax=18.0)],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0018,
        open_position=None,
        costless_summary={"absent_reason": "대조군을 구하지 못했습니다 — 실행이 KeyError 으로 멈췄습니다"},
    )
    gap = by_key(ms, "cost_gap_pct")
    check("격차 값 없음", gap.value, None)
    check("사유가 실패를 말한다", "구하지 못했습니다" in (gap.absent_reason or ""), True)
    check("「옛 실행」이라 하지 않는다", "옛 실행" in (gap.absent_reason or ""), False)


def test_old_run_without_twin_is_absent_not_zero() -> None:
    """대조군을 안 돌린 옛 실행은 격차 0이 아니라 **모르는 것**이다."""
    ms = compute(
        equity_dt=dates(3),
        equity=[1000.0, 1020.0, 1050.0],
        trades=[_cost_trade(fee=1.5, slippage=5.0, tax=18.0)],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0018,
        open_position=None,
        costless_summary=None,
    )
    gap = by_key(ms, "cost_gap_pct")
    check("격차 값 없음", gap.value, None)
    check("사유가 옛 실행임을 말한다", "대조군" in (gap.absent_reason or ""), True)


# ── 구간 끝에 열린 자리 (#314) ───────────────────────────────────────────────
#
# 실측(이슈 #314): 005930 1년치에 `surge_exclusion` 을 돌리면 **청산 거래 0건 · 수익률
# +268.14% · 치른 비용 0원** 이 한 화면에 섰다. 성과 전부가 미실현인데 세 자리 어디도
# 그 사실을 말하지 않았다. 아래 값은 그 실행의 숫자를 그대로 쓴다.

OPEN_ENTRY_NOTIONAL = 9_993_504.22
OPEN_ENTRY_COST = 6_495.78
OPEN_FINAL_VALUE = 36_814_411.12


def _open_trade(*, entry_ts: str = "2025-08-05", qty: float = 1.0, notional: float, cost: float):
    """진입만 하고 청산되지 않은 자리 — **실현손익이 없다.**"""
    return SimpleNamespace(
        realized_pnl=None,
        entry_ts=entry_ts,
        entry_price=notional / qty,
        qty=qty,
        fee=cost,
        slippage=0.0,
        tax=0.0,
    )


def _issue_open_position():
    return summarize_open_position(
        position_count=1,
        gross_exposure=OPEN_FINAL_VALUE,
        trades=[_open_trade(notional=OPEN_ENTRY_NOTIONAL, cost=OPEN_ENTRY_COST)],
        initial_cash=10_000_000.0,
        final_equity=OPEN_FINAL_VALUE,
    )


def test_open_position_is_all_of_the_return() -> None:
    """성과 전부가 미실현이면 **100%** 라고 말한다 — 0% 도, 침묵도 아니다."""
    op = _issue_open_position()
    check("자리 수", op.count, 1)
    check("평가액", op.value, OPEN_FINAL_VALUE)
    check("진입일", op.entry_ts, "2025-08-05")
    check("진입에서 이미 치른 비용", op.entry_cost, OPEN_ENTRY_COST, tol=1e-9)
    # 26,814,411.12 = 36,814,411.12 − (9,993,504.22 + 6,495.78)
    check("미실현 손익", op.unrealized_pnl, 26_814_411.12, tol=1e-6)
    check("성과의 100% 가 미실현", op.unrealized_share_pct, 100.0, tol=1e-9)


def test_no_open_position_is_none_not_zero_row() -> None:
    """자리가 안 열렸으면 「0자리 열림」이 아니라 **할 말이 없는 것**이다."""
    check(
        "position_count 0 이면 None",
        summarize_open_position(
            position_count=0, gross_exposure=0.0, trades=[], initial_cash=1000.0, final_equity=1200.0
        ),
        None,
    )


def test_open_position_without_entry_record_says_so() -> None:
    """곡선은 자리가 있다는데 진입 기록이 없으면 **모르는 것**이다 — 지어내지 않는다."""
    op = summarize_open_position(
        position_count=1, gross_exposure=1500.0, trades=[], initial_cash=1000.0, final_equity=1500.0
    )
    check("자리는 안다", op.count, 1)
    check("진입 비용은 모른다", op.entry_cost, None)
    check("사유를 단다", "옛 실행" in (op.absent_reason or ""), True)


def test_open_position_entry_cost_enters_cost_paid() -> None:
    """**「치른 비용」이 열린 자리의 진입 비용을 센다** — 이슈의 「0원」이 여기서 갈린다.

    청산 거래 0건 + 열린 자리 1건(진입 비용 6,495.78원) → 0원이 아니라 6,495.78원.
    """
    op = _issue_open_position()
    ms = compute(
        equity_dt=["2025-08-01", "2026-08-19"],
        equity=[10_000_000.0, OPEN_FINAL_VALUE],
        trades=[_open_trade(notional=OPEN_ENTRY_NOTIONAL, cost=OPEN_ENTRY_COST)],
        round_trip_cost_rate=0.0031,
        initial_cash=10_000_000.0,
        sell_tax_rate=0.0018,
        costless_summary=None,
        open_position=op,
    )
    paid = by_key(ms, "cost_paid")
    check("치른 비용이 0원이 아니다", paid.value, OPEN_ENTRY_COST, tol=1e-9)
    check("유도가 열린 자리를 밝힌다", "열린 자리 1건의 진입 비용" in (paid.derived_from or ""), True)
    # 매도 비용은 아직 안 물렸다 — 그 사실을 유도 문구가 말해야 「왕복 비용을 다 셌다」로 안 읽힌다.
    check("매도 비용 미반영을 밝힌다", "매도 비용은 아직 안 물렸다" in (paid.derived_from or ""), True)


def test_open_position_without_record_blocks_cost_paid() -> None:
    """진입 비용을 모르는데 0원이라 답하지 않는다 — `tax_unrecorded` 와 같은 규약."""
    op = summarize_open_position(
        position_count=1, gross_exposure=1500.0, trades=[], initial_cash=1000.0, final_equity=1500.0
    )
    ms = compute(
        equity_dt=dates(2),
        equity=[1000.0, 1500.0],
        trades=[],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0018,
        costless_summary=None,
        open_position=op,
    )
    paid = by_key(ms, "cost_paid")
    check("값이 없다", paid.value, None)
    check("사유가 열린 자리를 말한다", "열린 자리" in (paid.absent_reason or ""), True)


def test_open_position_with_zero_sell_tax_is_not_called_old_run() -> None:
    """진입만 한 자리는 세금이 0인 게 정상이다 — 「세금 기록 없는 옛 실행」으로 오인하면 안 된다.

    `tax_unrecorded` 가 청산 거래만 보지 않고 전체를 보면, 진입만 한 실행이 **늘** 옛 실행이 되어
    치른 비용이 영영 안 나온다.
    """
    ms = compute(
        equity_dt=dates(2),
        equity=[1000.0, 1500.0],
        trades=[_open_trade(notional=990.0, cost=10.0)],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0018,
        costless_summary=None,
        open_position=summarize_open_position(
            position_count=1,
            gross_exposure=1500.0,
            trades=[_open_trade(notional=990.0, cost=10.0)],
            initial_cash=1000.0,
            final_equity=1500.0,
        ),
    )
    check("치른 비용이 나온다", by_key(ms, "cost_paid").value, 10.0, tol=1e-9)


def test_open_position_splits_no_trade_from_no_exit() -> None:
    """「거래 없음」과 「청산 안 함」을 가른다 — 진짜 0건과 구분되어야 한다."""
    op = _issue_open_position()
    ms = compute(
        equity_dt=["2025-08-01", "2026-08-19"],
        equity=[10_000_000.0, OPEN_FINAL_VALUE],
        trades=[_open_trade(notional=OPEN_ENTRY_NOTIONAL, cost=OPEN_ENTRY_COST)],
        round_trip_cost_rate=0.0031,
        initial_cash=10_000_000.0,
        sell_tax_rate=0.0018,
        costless_summary=None,
        open_position=op,
    )
    win = by_key(ms, "win_rate")
    check("승률은 여전히 값이 없다", win.value, None)
    check("「청산된 거래 없음」이라 말한다", "청산된 거래 없음" in (win.absent_reason or ""), True)
    check("열린 자리 건수를 말한다", "열린 자리 1건" in (win.absent_reason or ""), True)
    # 진짜 0건과 같은 문구면 가른 것이 아니다.
    check("진짜 0건 문구가 아니다", "거래 없음 — 청산된 거래가 0건입니다" == (win.absent_reason or ""), False)


def test_return_derivation_names_the_unrealized_part() -> None:
    """**수익률이 무엇 위에 서 있는지 유도 문구가 말한다** — 거래 0건인데 +268% 인 이유."""
    op = _issue_open_position()
    ms = compute(
        equity_dt=["2025-08-01", "2026-08-19"],
        equity=[10_000_000.0, OPEN_FINAL_VALUE],
        trades=[_open_trade(notional=OPEN_ENTRY_NOTIONAL, cost=OPEN_ENTRY_COST)],
        round_trip_cost_rate=0.0031,
        initial_cash=10_000_000.0,
        sell_tax_rate=0.0018,
        costless_summary=None,
        open_position=op,
    )
    cagr = by_key(ms, "cagr")
    check("CAGR 이 나온다 (구간 1년 이상)", cagr.value is not None, True)
    check("미실현을 유도가 밝힌다", "청산하지 않은 자리 1건의 평가액" in (cagr.derived_from or ""), True)
    check("평가액 숫자를 적는다", "36,814,411원" in (cagr.derived_from or ""), True)

    value = by_key(ms, "open_position_value")
    check("열린 자리 평가액이 지표로 온다", value.value, OPEN_FINAL_VALUE)
    share = by_key(ms, "unrealized_share_pct")
    check("미실현 비중이 지표로 온다", share.value, 100.0, tol=1e-9)


def test_short_sample_return_derivation_also_names_unrealized() -> None:
    """연환산하지 않는 짧은 구간은 「구간 총수익률」이 그 자리를 대신한다 — 거기도 밝힌다."""
    op = summarize_open_position(
        position_count=1,
        gross_exposure=1500.0,
        trades=[_open_trade(notional=990.0, cost=10.0)],
        initial_cash=1000.0,
        final_equity=1500.0,
    )
    ms = compute(
        equity_dt=dates(3),
        equity=[1000.0, 1200.0, 1500.0],
        trades=[_open_trade(notional=990.0, cost=10.0)],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0,
        costless_summary=None,
        open_position=op,
    )
    total = by_key(ms, "total_return")
    check("구간 총수익률이 미실현을 밝힌다", "청산하지 않은 자리 1건의 평가액" in (total.derived_from or ""), True)


def test_no_open_position_says_nothing_extra() -> None:
    """자리가 안 열렸으면 유도 문구에 미실현 이야기가 **붙지 않는다** — 없는 말을 하지 않는다."""
    ms = compute(
        equity_dt=dates(3),
        equity=[1000.0, 1020.0, 1050.0],
        trades=[_cost_trade(fee=1.5, slippage=5.0, tax=18.0)],
        round_trip_cost_rate=0.0,
        initial_cash=1000.0,
        sell_tax_rate=0.0018,
        costless_summary=None,
        open_position=None,
    )
    keys = [m.key for m in ms]
    check("열린 자리 지표가 없다", "open_position_value" in keys, False)
    check("미실현 비중 지표도 없다", "unrealized_share_pct" in keys, False)
    check("유도에 미실현 문구가 없다", "청산하지 않은 자리" in (by_key(ms, "total_return").derived_from or ""), False)


def main() -> int:
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        fn()
    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < 60:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
