#!/usr/bin/env python3
"""맥락이 「내가 잘한 건가」에 답하는지 확인한다 (#204).

**이슈가 든 시나리오를 실제로 만들어 태운다** — 전략이 이겼는데 동일가중이 거의 같으면
화면이 「유니버스가 좋았던 것」쪽으로 읽혀야 한다.

    cd backend-service && APP_ENV=development uv run python tests/test_backtest_context.py
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from services.backtest.context import (  # noqa: E402
    CLUSTER_THRESHOLD,
    MIN_CORRELATION_SAMPLES,
    cluster_concentration,
    correlation,
    equal_weight_universe,
)
from services.backtest.engine import BarSeries  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected, tol: float = 1e-6) -> None:
    global CHECKED
    CHECKED += 1
    ok = (
        abs(actual - expected) <= tol
        if isinstance(expected, float) and isinstance(actual, (int, float))
        else actual == expected
    )
    if not ok:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def make(iid: int, closes: list[float], start_day: int = 1) -> BarSeries:
    start = dt.date(2026, 1, 1) + dt.timedelta(days=start_day - 1)
    n = len(closes)
    return BarSeries(
        instrument_id=iid,
        dt=[(start + dt.timedelta(days=i)).isoformat() for i in range(n)],
        open=list(closes),
        high=list(closes),
        low=list(closes),
        close=list(closes),
        volume=[1000.0] * n,
    )


def test_equal_weight_two_symbols() -> None:
    """두 종목을 500씩 사서 보유 — 손으로 계산한 값과 일치한다.

    A: 100 → 120 (+20%)  · 500 → 600
    B: 50  → 55  (+10%)  · 500 → 550
    합계 1,150 (+15%)
    """
    b = equal_weight_universe([make(1, [100.0, 120.0]), make(2, [50.0, 55.0])], 1000.0)
    check("시작 자산", b.equity[0], 1000.0, tol=1e-9)
    check("끝 자산", b.equity[-1], 1150.0, tol=1e-9)
    check("총수익률 15%", b.total_return, 0.15, tol=1e-9)
    check("유도 경로가 있다", "2종목" in b.derived_from, True)


def test_the_issue_scenario() -> None:
    """**이슈가 든 그 상황** — 전략 +18% 인데 동일가중이 +17% 면 이긴 게 아니다.

    유니버스 3종목이 각각 +17% 근처로 올랐다. 전략이 +18% 를 냈어도 종목을 고른 능력이
    아니라 그 유니버스가 좋았던 것이다. 이 검사는 **동일가중이 그 사실을 드러내는지**를 본다.
    """
    universe = [
        make(1, [100.0, 117.0]),
        make(2, [200.0, 234.0]),
        make(3, [50.0, 58.5]),
    ]
    b = equal_weight_universe(universe, 1000.0)
    check("동일가중 +17%", b.total_return, 0.17, tol=1e-9)

    strategy_return = 0.18
    edge = strategy_return - (b.total_return or 0.0)
    check("초과분이 1%p 뿐", round(edge, 4), 0.01)
    # 「이겼다」가 아니라 「거의 같다」로 읽혀야 한다.
    check("초과분이 유니버스 수익의 10% 미만", edge < (b.total_return or 0) * 0.1, True)


def test_only_common_dates() -> None:
    """상장 구간이 다르면 **모두가 값을 가진 날만** 쓴다.

    빠진 날을 직전 값으로 메우면 없는 거래일을 만든 것이 된다.
    """
    a = make(1, [100.0, 110.0, 120.0], start_day=1)  # 1/1~1/3
    c = make(2, [50.0, 55.0], start_day=2)  # 1/2~1/3
    b = equal_weight_universe([a, c], 1000.0)
    check("공통 거래일 2일", len(b.dt), 2)
    check("첫날이 1/2", b.dt[0], "2026-01-02")


def test_no_overlap_says_why() -> None:
    """겹치는 날이 없으면 곡선을 지어내지 않고 사유를 남긴다."""
    a = make(1, [100.0, 110.0], start_day=1)
    c = make(2, [50.0, 55.0], start_day=10)
    b = equal_weight_universe([a, c], 1000.0)
    check("곡선 비어 있음", len(b.equity), 0)
    check("사유가 있다", "없습니다" in b.derived_from, True)


def test_correlation_needs_samples() -> None:
    """표본이 모자라면 상관을 **내지 않는다** — 0 이 아니라 None 이다.

    표본 3개짜리 상관계수는 숫자로는 나오지만 아무것도 말하지 않는다.
    """
    # **값을 변하게 만든다.** 처음엔 [0.01] * n 으로 썼는데 그러면 분산이 0이라
    # `var_a <= 0` 가드가 None 을 내, 표본 하한을 지워도 테스트가 통과했다 —
    # 엉뚱한 이유로 초록이던 자리다.
    short = [0.01 * (i % 3 - 1) for i in range(MIN_CORRELATION_SAMPLES - 1)]
    check("표본 부족 → None", correlation(short, short), None)
    enough = [0.01 * (i % 3 - 1) for i in range(MIN_CORRELATION_SAMPLES + 5)]
    check("충분하면 값이 나온다", correlation(enough, enough) is not None, True)


def test_flat_series_has_no_correlation() -> None:
    """움직이지 않은 종목과는 상관을 낼 수 없다 — 0 이 아니라 None."""
    flat = [0.0] * (MIN_CORRELATION_SAMPLES + 5)
    moving = [0.01 * (i % 3 - 1) for i in range(MIN_CORRELATION_SAMPLES + 5)]
    check("한쪽이 정지 → None", correlation(flat, moving), None)


def test_clusters_group_the_correlated() -> None:
    """같이 움직이는 종목이 한 덩어리가 된다.

    A·B 는 같은 파형(상관 1), C 는 반대 파형. → 2개 클러스터.
    """
    n = MIN_CORRELATION_SAMPLES + 10
    up = [100.0 + (i % 4) * 5 for i in range(n)]
    down = [100.0 - (i % 4) * 5 for i in range(n)]
    conc = cluster_concentration([make(1, up), make(2, up), make(3, down)])
    check("클러스터 2개", len(conc.clusters), 2)
    check("사유 없음(계산됨)", conc.absent_reason, None)
    biggest = conc.clusters[0]
    check("큰 덩어리가 2종목", len(biggest.instrument_ids), 2)
    check("유도 경로에 쌍 수가 있다", "쌍" in conc.derived_from, True)


def test_concentration_share() -> None:
    """「몇 % 집중」이 나온다 — 전부 한 덩어리면 100%."""
    n = MIN_CORRELATION_SAMPLES + 10
    same = [100.0 + (i % 4) * 5 for i in range(n)]
    conc = cluster_concentration([make(i, same) for i in (1, 2, 3, 4)])
    check("클러스터 1개", len(conc.clusters), 1)
    check("100% 집중", conc.top_share_pct, 100.0, tol=1e-9)


def test_short_history_says_why() -> None:
    """공통 거래일이 모자라면 **묶지 않고 사유를 남긴다.**"""
    short = [100.0, 101.0, 102.0]
    conc = cluster_concentration([make(1, short), make(2, short)])
    check("클러스터 없음", len(conc.clusters), 0)
    check("사유가 있다", "상관을 내지 않습니다" in (conc.absent_reason or ""), True)


def test_single_symbol_says_why() -> None:
    """종목이 하나면 묶을 것이 없다 — 0% 가 아니라 사유다."""
    conc = cluster_concentration([make(1, [100.0] * 30)])
    check("사유가 있다", "2개 미만" in (conc.absent_reason or ""), True)


def test_threshold_is_visible() -> None:
    """임계값이 유도 경로에 적힌다 — 사람이 그 값을 알고 읽어야 한다."""
    n = MIN_CORRELATION_SAMPLES + 10
    wave = [100.0 + (i % 4) * 5 for i in range(n)]
    conc = cluster_concentration([make(1, wave), make(2, wave)])
    check("임계값이 보인다", str(CLUSTER_THRESHOLD) in conc.derived_from, True)


def main() -> int:
    # **케이스가 터져도 나머지를 돈다.** 크래시로 멈추면 빨간불은 뜨지만 무엇이 왜 틀렸는지
    # 한 건밖에 안 나온다 — 파손 주입으로 확인하다 실제로 그렇게 겪었다.
    for name, fn in [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            global CHECKED
            CHECKED += 1
            FAILURES.append(f"{name} 이 터졌다: {type(exc).__name__}: {exc}")
    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < 20:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
