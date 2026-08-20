#!/usr/bin/env python3
"""격자 한 칸의 실행 비용을 잰다 — 대조군을 함께 도는 값이 예산 안인지 확인한다.

`grid.MAX_COMBOS` 는 스펙 §5 의 「>10초면 완료 예상 표시」 예산에 걸린 안전핀이다. SC-007 이
칸마다 대조군을 한 번 더 돌게 만들었으므로, 그 상한이 여전히 예산 안인지 **실측으로** 답해야
한다. 이 스크립트가 그 답을 재현 가능하게 만든다.

**이 검사는 도는 기계의 속도를 잰다.** 개발 노트북과 CI 러너가 다르고, 그것이 의도다 — 느린
기계에서 예산을 넘으면 그 기계에서 빨간불이 나야 한다. 실측 차이가 실제로 판정을 갈랐다:
같은 상한(2000칸)이 노트북에서 7.8초, CI 러너에서 13.0초였다.

    cd backend-service && APP_ENV=development uv run python scripts/verify_grid_cost_budget.py
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import math
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from services.backtest.engine import BarSeries, CostModel, Strategy  # noqa: E402
from services.backtest.grid import MAX_COMBOS, axes_from_spec, run_grid  # noqa: E402

#: 스펙 §5 — 이 위로 가면 화면이 완료 예상을 띄워야 한다.
BUDGET_SECONDS = 10.0
BARS = 1500
#: 재는 축과 표본 크기. 축은 이 전략이 선언한 범위 전체를 고르게 훑는다.
SWEEP_PARAM = "ma_period"
SAMPLE_CELLS = 40


def _load(name: str):
    path = BACKEND.parent / "strategies" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _series(count: int) -> BarSeries:
    base = dt.date(2020, 1, 1)
    closes = [100 + 20 * math.sin(i / 17) + (i % 11) for i in range(count)]
    return BarSeries(
        instrument_id=1,
        dt=[str(base + dt.timedelta(days=i)) for i in range(count)],
        open=list(closes),
        high=[c * 1.02 for c in closes],
        low=[c * 0.98 for c in closes],
        close=list(closes),
        volume=[1000.0] * count,
    )


def main() -> int:
    module = _load("ma_pullback")
    series = _series(BARS)
    specs = list(module.STRATEGY.get("params") or [])
    # 훑지 않는 축은 **선언된 기본값**으로 채운다 — 안 채우면 전략이 KeyError 로 죽어
    # 「칸은 돌았는데 전부 실패」를 재는 꼴이 된다.
    base_params = {spec["name"]: spec.get("default") for spec in specs if spec["name"] != SWEEP_PARAM}
    # **표본을 아무렇게나 고르면 안 된다.** 칸당 비용은 파라미터 **값**에 따라 다르다 —
    # 실측: 같은 전략에서 5칸 6.76ms · 20칸 7.06ms · 40칸 8.21ms · 80칸 10.12ms 로, 훑는 값이
    # 커질수록 칸이 비싸진다. 작은 표본을 상한 배율로 외삽하면 그 편차가 그대로 증폭된다.
    #
    # 그래서 **선언 범위 전체를 고르게 훑는다** — 이 전략이 실제로 받을 수 있는 값의 분포다.
    axis = next(spec for spec in specs if spec["name"] == SWEEP_PARAM)
    low, high = int(axis["min"]), int(axis["max"])
    values = sorted({low + round(i * (high - low) / (SAMPLE_CELLS - 1)) for i in range(SAMPLE_CELLS)})
    axes = axes_from_spec(specs, {SWEEP_PARAM: values})
    costs = CostModel(fee_rate=0.00015, slippage_rate=0.0005, sell_tax_rate=0.0018)

    # 워밍업 — 첫 실행의 import·코드 캐시 비용을 측정에서 뺀다.
    run_grid(
        strategy=Strategy(module),
        axes=axes_from_spec(specs, {SWEEP_PARAM: [values[len(values) // 2]]}),
        base_params=base_params,
        series=series,
        initial_cash=1_000_000.0,
        costs=costs,
    )

    started = time.perf_counter()
    grid = run_grid(
        strategy=Strategy(module),
        axes=axes,
        base_params=base_params,
        series=series,
        initial_cash=1_000_000.0,
        costs=costs,
    )
    elapsed = time.perf_counter() - started
    cells = len(grid.cells)
    if cells == 0:
        print("::error::칸을 0개 돌았다 — 측정할 것이 없다 (fail-closed)", file=sys.stderr)
        return 1

    per_cell = elapsed / cells
    at_cap = per_cell * MAX_COMBOS
    ok = sum(1 for cell in grid.cells if cell.ok)
    twins = sum(1 for cell in grid.cells if cell.costless is not None)
    print(f"칸 {cells}개(성공 {ok}) · 봉 {BARS} · 대조군 {twins}개 → {elapsed:.3f}초 (칸당 {per_cell * 1000:.2f}ms)")
    print(f"상한 {MAX_COMBOS}칸 환산 {at_cap:.1f}초 · 예산 {BUDGET_SECONDS}초 (여유 {BUDGET_SECONDS - at_cap:.1f}초)")

    if ok != cells:
        reasons = {cell.failed_reason for cell in grid.cells if not cell.ok}
        print(f"::error::칸 {cells}개 중 {cells - ok}개가 실패했다 — 재는 대상이 없다: {reasons}", file=sys.stderr)
        return 1
    if twins != cells:
        print(f"::error::대조군이 {twins}/{cells} 개뿐이다 — SC-007 의 나란히가 성립하지 않는다", file=sys.stderr)
        return 1
    if at_cap > BUDGET_SECONDS:
        print(
            f"::error::상한 {MAX_COMBOS}칸이 예산 {BUDGET_SECONDS}초를 넘는다 ({at_cap:.1f}초) — "
            "MAX_COMBOS 를 낮추거나 화면이 완료 예상을 띄워야 한다",
            file=sys.stderr,
        )
        return 1
    print("판정: 상한이 예산 안이다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
