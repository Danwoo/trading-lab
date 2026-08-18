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

from services.backtest.metrics import (  # noqa: E402
    Metric,
    compute,
    drawdown_amount,
    longest_underwater,
    max_drawdown,
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
    m = by_key(compute(equity_dt=dates(4), equity=equity, trades=[], round_trip_cost_rate=0.0), "longest_underwater")
    check("메트릭 note 가 말한다", m.note, "아직 회복 중")


def test_short_sample_is_not_annualized() -> None:
    """표본이 짧으면 연환산하지 않는다 — 대신 구간 총수익률이 온다.

    스펙: 26일 구간을 연환산하면 57.8% 가 나온다.
    """
    equity = [1000.0 + i * 5 for i in range(26)]
    ms = compute(equity_dt=dates(26), equity=equity, trades=[], round_trip_cost_rate=0.0)
    cagr = by_key(ms, "cagr")
    check("CAGR 은 없다", cagr.value, None)
    check("이유를 말한다", "연환산하지 않습니다" in (cagr.absent_reason or ""), True)
    total = by_key(ms, "total_return")
    check("구간 총수익률이 대신 온다", total.value, 12.5)  # 1125/1000 − 1 = 12.5%


def test_long_sample_is_annualized() -> None:
    """1년 이상이면 연환산한다. 2년에 자산 2배 → CAGR ≈ 41.42%."""
    dts = ["2024-01-01", "2026-01-01"]
    ms = compute(equity_dt=dts, equity=[1000.0, 2000.0], trades=[], round_trip_cost_rate=0.0)
    cagr = by_key(ms, "cagr")
    check("CAGR 계산됨", cagr.value is not None, True)
    check("CAGR 값", cagr.value, (2.0 ** (365 / 731.0) - 1) * 100, tol=0.5)


def test_calmar_absent_when_cagr_absent() -> None:
    """CAGR 이 없으면 Calmar 도 없다 — 없는 계산을 한 척하지 않는다."""
    equity = [1000.0, 1200.0, 900.0]
    ms = compute(equity_dt=dates(3), equity=equity, trades=[], round_trip_cost_rate=0.0)
    calmar = by_key(ms, "calmar")
    check("Calmar 없음", calmar.value, None)
    check("이유가 CAGR 부재", "연환산 수익률이 없어" in (calmar.absent_reason or ""), True)


def test_no_trades_is_not_zero_percent() -> None:
    """거래 0건이면 승률은 `0%` 가 아니라 「거래 없음」이다 (스펙 §8.5.3)."""
    ms = compute(equity_dt=dates(3), equity=[1000.0, 1000.0, 1000.0], trades=[], round_trip_cost_rate=0.001)
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
        equity_dt=["2024-01-01", "2026-01-01"], equity=[1000.0, 1400.0], trades=[trade], round_trip_cost_rate=0.0015
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


def test_avg_trade_subtracts_round_trip_cost() -> None:
    """거래당 평균 수익에서 왕복 비용을 뺀다 — 「비용 먹고도 남나」가 질문이다.

    100 원에 10주(원금 1,000) 사서 실현손익 50 → 평균 5%.
    왕복 비용률 0.15% → 5 − 0.15 = 4.85%
    """
    trade = SimpleNamespace(realized_pnl=50.0, entry_price=100.0, qty=10.0)
    ms = compute(equity_dt=dates(3), equity=[1000.0, 1020.0, 1050.0], trades=[trade], round_trip_cost_rate=0.0015)
    check("평균 − 비용", by_key(ms, "avg_trade_vs_cost").value, 4.85, tol=1e-9)


def test_empty_equity_says_why() -> None:
    """자산곡선이 없으면 전 지표가 사유를 단다 — 0 으로 채우지 않는다."""
    ms = compute(equity_dt=[], equity=[], trades=[], round_trip_cost_rate=0.0)
    global CHECKED
    CHECKED += 1
    if not ms:
        FAILURES.append("빈 자산곡선에 지표가 하나도 없다 — 사유를 내야 한다")
        return
    for m in ms:
        CHECKED += 1
        if m.value is not None or not m.absent_reason:
            FAILURES.append(f"{m.key} 가 빈 곡선인데 값을 냈다")


def main() -> int:
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        fn()
    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < 30:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
