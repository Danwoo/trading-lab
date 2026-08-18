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
    combo_count,
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


def test_multi_axis_explosion_is_rejected_before_building() -> None:
    """**다축 조합 폭발** — 리뷰가 잡은 반례다.

    종전 검사는 단일 축에 `MAX_COMBOS+1` 만 넣어, 2축×1000값(100만 칸) 같은 입력을
    전혀 태우지 못했다. 그 입력은 상한의 500배를 **실제로 만든 뒤에야** 거부됐다
    (실측 1.11초). 이 앱은 `--workers=1` 이라 그동안 모든 요청이 함께 멈춘다.

    이제 만들기 전에 세고 거부한다 — 시간으로도 확인한다.
    """
    import time

    axes = (Axis("threshold", tuple(range(1000))), Axis("other", tuple(range(1000))))
    check("세기만 100만", combo_count(axes), 1_000_000)

    start = time.perf_counter()
    raises("다축 폭발", lambda: combinations(axes, {}), "전부 돌려봤다")
    elapsed = time.perf_counter() - start
    # 만들고 거부하면 1초대였다. 세고 거부하면 순간이다 — 넉넉히 0.1초로 잡는다.
    global CHECKED
    CHECKED += 1
    if elapsed > 0.1:
        FAILURES.append(f"거부에 {elapsed:.3f}초 걸렸다 — 만든 뒤에 거부하는 것 아닌가")


def test_count_without_building() -> None:
    """조합 수는 **만들지 않고** 셀 수 있다."""
    check("축 없음 → 1", combo_count(()), 1)
    check("2×3", combo_count((Axis("a", (1, 2)), Axis("b", (3, 4, 5)))), 6)
    check("3축", combo_count((Axis("a", (1, 2)), Axis("b", (1, 2)), Axis("c", (1, 2)))), 8)


def test_run_grid_rejects_before_building() -> None:
    """`run_grid` 도 같은 자리에서 막힌다 — 캔들을 올리기 전에."""
    axes = (Axis("threshold", tuple(range(100))), Axis("other", tuple(range(100))))
    raises(
        "run_grid 다축 폭발",
        lambda: run_grid(
            strategy=strategy_using("threshold"),
            axes=axes,
            base_params={},
            series=series(),
            initial_cash=1000.0,
            costs=FREE,
        ),
        "전부 돌려봤다",
    )


def test_duplicate_axis_values_are_folded() -> None:
    """**중복은 조합이 아니다** — 같은 값을 두 번 훑어도 칸이 늘지 않는다.

    늘어나면 `attempts_used` 가 실제 distinct 조합보다 부풀어, 「100가지를 돌려봤다 /
    45번이 한계」류의 자기모순이 그대로 재발한다(스펙 §8.5.2 — 이 모듈이 막으려던 그것).
    """
    a = Axis("threshold", (1, 2, 2, 3, 1))
    check("중복이 접힌다", a.values, (1, 2, 3))
    check("조합 수도 접힌 값 기준", combo_count((a,)), 3)

    g = run_grid(
        strategy=strategy_using("threshold"),
        axes=(Axis("threshold", (0, 1, 1, 0)),),
        base_params={},
        series=series(),
        initial_cash=1000.0,
        costs=FREE,
    )
    check("격자 칸 2개", len(g.cells), 2)
    check("소비 시도도 2", g.attempts_used, 2)


def test_400_combinations_within_budget() -> None:
    """**#202 완료 조건** — 합성 데이터로 400조합을 돌려 걸린 시간을 적는다.

    스펙 §5 의 예산은 「실행·전체 재계산 >1s 진행 표시, >10s 완료 예상」이다. 400조합이
    10초를 넘으면 「완료 예상」을 띄워야 하는 구간이므로, 그 경계를 그물로 못박는다.

    실측(2026-08-18, 실전략 ma_pullback · 1500봉 · 20×20): **1.4초 · 칸당 3.5ms**.
    상한을 8초로 두는 이유 — 실측의 5배 여유. 이보다 느려지면 「로드 1회 + 인메모리 N회」가
    깨졌는지 먼저 의심할 자리다(조합마다 DB 를 다시 읽으면 16배가 된다).
    """
    import datetime as _dt
    import time

    n = 1500
    start = _dt.date(2020, 1, 1)
    closes = [100.0 + 20 * ((i % 61) / 61 - 0.5) + i * 0.01 for i in range(n)]
    s = BarSeries(
        instrument_id=1,
        dt=[(start + _dt.timedelta(days=i)).isoformat() for i in range(n)],
        open=list(closes),
        high=list(closes),
        low=list(closes),
        close=list(closes),
        volume=[1000.0] * n,
    )
    axes = (Axis("threshold", tuple(range(20))), Axis("other", tuple(range(20))))

    t0 = time.perf_counter()
    g = run_grid(
        strategy=strategy_using("threshold"), axes=axes, base_params={}, series=s, initial_cash=10_000_000, costs=FREE
    )
    elapsed = time.perf_counter() - t0

    check("400조합", len(g.cells), 400)
    check("소비 시도 400", g.attempts_used, 400)
    check("전부 성공", all(c.ok for c in g.cells), True)

    global CHECKED
    CHECKED += 1
    if elapsed > 8.0:
        FAILURES.append(
            f"400조합에 {elapsed:.1f}초 걸렸다 (상한 8초) — 「로드 1회 + 인메모리 N회」가 깨졌는지 확인하라"
        )


def main() -> int:
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        fn()
    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < 32:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
