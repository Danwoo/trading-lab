#!/usr/bin/env python3
"""격자 한 칸의 실행 비용을 잰다 — 대조군을 함께 도는 값이 예산 안인지 확인한다.

`grid.MAX_COMBOS` 는 스펙 §5 의 「>10초면 완료 예상 표시」 예산에 걸린 안전핀이다. SC-007 이
칸마다 대조군을 한 번 더 돌게 만들었으므로, 그 상한이 여전히 예산 안인지 **실측으로** 답해야
한다. 이 스크립트가 그 답을 재현 가능하게 만든다.

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
    base_params = {spec["name"]: spec.get("default") for spec in specs if spec["name"] != "ma_period"}
    axes = axes_from_spec(specs, {"ma_period": [5, 10, 20, 40, 60]})
    costs = CostModel(fee_rate=0.00015, slippage_rate=0.0005, sell_tax_rate=0.0018)

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
    print(f"상한 {MAX_COMBOS}칸 환산 {at_cap:.1f}초 · 예산 {BUDGET_SECONDS}초")

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
