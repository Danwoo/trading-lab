#!/usr/bin/env python3
"""격자가 **단일 점을 만들지 않고**, 훑는 것도 시도로 세는지 확인한다 (#202).

cd backend-service && APP_ENV=development uv run python tests/test_backtest_grid.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from services.backtest.engine import BarSeries, CostModel, Strategy  # noqa: E402
from services.backtest.grid import (  # noqa: E402
    MAX_COMBOS,
    Axis,
    axes_from_spec,
    combinations,
    run_grid,
)

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def raises(name: str, fn, fragment: str) -> None:
    global CHECKED
    CHECKED += 1
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        if fragment not in str(exc):
            FAILURES.append(f"{name}: 사유에 {fragment!r} 가 없다 — {exc}")
        return
    FAILURES.append(f"{name}: 던지지 않았다")


def series(n: int = 12) -> BarSeries:
    import datetime as dt

    start = dt.date(2026, 1, 1)
    closes = [100.0 + (i % 5) * 3 for i in range(n)]
    return BarSeries(
        instrument_id=1,
        dt=[(start + dt.timedelta(days=i)).isoformat() for i in range(n)],
        open=list(closes),
        high=list(closes),
        low=list(closes),
        close=list(closes),
        volume=[1000.0] * n,
    )


def strategy_using(param_name: str) -> Strategy:
    """파라미터 값에 따라 다르게 사는 전략 — 칸마다 결과가 달라야 격자가 의미 있다."""
    module = SimpleNamespace(
        STRATEGY={
            "key": "grid_fixture",
            "name": "격자",
            "timeframe": "1d",
            "params": [{"name": param_name}, {"name": "other"}],
        },
        indicators=lambda bars, params: {},
        entry=lambda ctx: ctx["index"] == ctx["params"].get("threshold", 0),
        exit=lambda ctx: ctx["index"] >= ctx["params"].get("threshold", 0) + 3,
    )
    return Strategy(module)


FREE = CostModel(fee_rate=0.0, slippage_rate=0.0, sell_tax_rate=0.0)


def test_grid_has_no_single_point() -> None:
    """축이 있으면 결과가 **여러 칸**이다 — 단일 점은 존재하지 않는다 (D-Q1)."""
    g = run_grid(
        strategy=strategy_using("threshold"),
        axes=(Axis("threshold", (0, 1, 2)),),
        base_params={},
        series=series(),
        initial_cash=1000.0,
        costs=FREE,
    )
    check("칸 수", len(g.cells), 3)
    check("shape", g.shape, (3,))
    check("전부 성공", all(c.ok for c in g.cells), True)


def test_two_axes_make_product() -> None:
    """두 축이면 곱집합이다."""
    g = run_grid(
        strategy=strategy_using("threshold"),
        axes=(Axis("threshold", (0, 1)), Axis("other", (10, 20, 30))),
        base_params={},
        series=series(),
        initial_cash=1000.0,
        costs=FREE,
    )
    check("칸 수 2×3", len(g.cells), 6)
    check("shape", g.shape, (2, 3))


def test_attempts_equal_cells() -> None:
    """**격자를 훑는 것도 시도다** (§8.5.2).

    프로토타입은 "100가지를 돌려봤다"면서 "45번이 한계"라고 했다 — 100 > 45.
    칸 수가 곧 소비한 시도여야 그 자기모순이 사라진다.
    """
    g = run_grid(
        strategy=strategy_using("threshold"),
        axes=(Axis("threshold", (0, 1, 2, 3)),),
        base_params={},
        series=series(),
        initial_cash=1000.0,
        costs=FREE,
    )
    check("소비 시도 = 칸 수", g.attempts_used, len(g.cells))
    check("칸 4개", g.attempts_used, 4)


def test_cells_differ() -> None:
    """칸마다 파라미터가 다르다 — 같은 계산을 N 번 하는 것이 아니다."""
    g = run_grid(
        strategy=strategy_using("threshold"),
        axes=(Axis("threshold", (0, 2, 4)),),
        base_params={},
        series=series(),
        initial_cash=1000.0,
        costs=FREE,
    )
    values = sorted(c.params["threshold"] for c in g.cells)
    check("훑은 값", values, [0, 2, 4])
    check("칸을 찾을 수 있다", g.cell_at({"threshold": 2}) is not None, True)


def test_base_params_carry() -> None:
    """축이 아닌 파라미터는 모든 칸에 그대로 실린다."""
    g = run_grid(
        strategy=strategy_using("threshold"),
        axes=(Axis("threshold", (0, 1)),),
        base_params={"other": 99},
        series=series(),
        initial_cash=1000.0,
        costs=FREE,
    )
    check("기본 파라미터가 모든 칸에", all(c.params["other"] == 99 for c in g.cells), True)


def test_one_bad_cell_does_not_kill_grid() -> None:
    """한 칸이 터져도 격자를 버리지 않는다 — 어느 칸이 문제인지가 남아야 한다."""
    module = SimpleNamespace(
        STRATEGY={"key": "boom", "name": "폭발", "timeframe": "1d", "params": [{"name": "t"}]},
        indicators=lambda bars, params: (_ for _ in ()).throw(RuntimeError("나쁜 값")) if params["t"] == 1 else {},
        entry=lambda ctx: False,
        exit=lambda ctx: False,
    )
    g = run_grid(
        strategy=Strategy(module),
        axes=(Axis("t", (0, 1, 2)),),
        base_params={},
        series=series(),
        initial_cash=1000.0,
        costs=FREE,
    )
    check("칸은 3개 그대로", len(g.cells), 3)
    check("성공 2 · 실패 1", (sum(c.ok for c in g.cells), sum(not c.ok for c in g.cells)), (2, 1))
    bad = [c for c in g.cells if not c.ok][0]
    check("사유가 남는다", "나쁜 값" in (bad.failed_reason or ""), True)
    check("어느 칸인지 안다", bad.params["t"], 1)


def test_empty_axis_is_rejected() -> None:
    """값이 없는 축은 축이 아니다."""
    raises("빈 축", lambda: Axis("x", ()), "훑을 것이 없으면")


def test_unknown_param_is_rejected() -> None:
    """선언에 없는 파라미터를 훑으려 하면 **조용히 무시하지 않는다.**

    오타가 「그 축은 안 돌았다」로 넘어가면 격자가 실제로 무엇을 훑었는지 화면과 어긋난다.
    """
    specs = [{"name": "ma_period"}, {"name": "pullback_pct"}]
    raises("선언에 없는 축", lambda: axes_from_spec(specs, {"ma_perod": [1, 2]}), "ma_perod")
    check("선언된 것은 통과", len(axes_from_spec(specs, {"ma_period": [1, 2]})), 1)


def test_over_cap_is_rejected_not_truncated() -> None:
    """상한을 넘으면 **조용히 자르지 않고** 던진다.

    잘라서 도는 것은 「전부 돌려봤다」가 아니다 — 그렇게 말하면 §8.5.2 의 자기모순이 된다.
    """
    big = tuple(range(MAX_COMBOS + 1))
    raises(
        "상한 초과",
        lambda: run_grid(
            strategy=strategy_using("threshold"),
            axes=(Axis("threshold", big),),
            base_params={},
            series=series(),
            initial_cash=1000.0,
            costs=FREE,
        ),
        "전부 돌려봤다",
    )


def test_no_axes_is_one_cell() -> None:
    """축이 없으면 기본 파라미터 한 칸 — **빈 격자는 없다.**"""
    check("축 0개 → 조합 1개", len(combinations((), {"a": 1})), 1)


def main() -> int:
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        fn()
    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < 18:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
