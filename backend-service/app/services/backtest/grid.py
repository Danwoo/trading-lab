"""격자 실행 — 단일 점을 만들지 않는다 (#202).

## 왜 격자가 기본인가 (스펙 D-Q1)

퀀트는 *"이 파라미터의 성과"* 를 궁금해하지 않는다. **"이 성과가 그 파라미터에만 붙어 있나"**
를 궁금해한다.

    첫 안:   실행 → 결과 1개 → (원하면) 민감도 맵
    확정:    실행 → 결과가 처음부터 이웃 격자        ← 단일 점은 존재하지 않는다

> **점 하나를 보여주는 화면을 만들지 않으면 과적합이 구조적으로 어려워진다** — 봉우리에
> 걸터앉은 것을 숨길 데가 없다.

## 이 모듈이 저장소를 모르는 이유

캔들은 호출자가 **한 번** 올려 넘긴다. 조합마다 DB 를 다시 읽으면 4.9분이 83분이 된다
(스펙 §6 실측 — I/O 가 계산의 16배). `verify_backtest_engine_purity.py` 가 그 경계를 지킨다.

## 시도 횟수 (스펙 §8.5.2)

프로토타입 화면이 *"설정 100가지를 전부 돌려봤습니다"* 라면서 *"45번까지가 한계"* 라고
경고했다. **100 > 45** 다. 게다가 격자 클릭이 시도 횟수를 안 올려, 100칸을 훑어 최고점을
골라도 *"앞으로 13번까지는 믿어도 됩니다"* 라고 말했다.

> **규칙: 사용자가 처음 평가하는 조합마다 시도 횟수가 오른다. 격자를 훑는 것도 시도다.**

그래서 이 모듈은 **격자를 만든 순간 그 칸 수만큼 시도가 늘었다고 본다** — 화면이 「전부
돌려봤다」고 말하려면 그 수가 한계 계산에도 들어가야 앞뒤가 맞는다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product

from services.backtest.engine import BarSeries, CostModel, RunResult, Strategy, run_single

#: 대조군의 비용 — **미반영 세계**. 이 하나가 SC-007 「반영 vs 미반영을 나란히」의 다른 한쪽이다.
FREE_COSTS = CostModel(fee_rate=0.0, slippage_rate=0.0, sell_tax_rate=0.0)

# 한 번에 도는 조합 수 상한. 스펙 §5 의 예산(실행·전체 재계산 >10s 는 완료 예상 표시)을
# 넘지 않게 하는 안전핀이지, 성능 목표가 아니다. 넘으면 **조용히 자르지 않고** 던진다 —
# 「전부 돌려봤다」고 말할 수 없는 결과를 그렇게 말하는 것이 §8.5.2 의 자기모순이다.
#
# **크기는 만들기 전에 센다.** 처음엔 곱집합을 다 만든 뒤에 길이를 봤는데, 그러면 2축×1000값
# 만으로 상한의 500배(100만 칸)를 **실제로 만든 뒤에야** 거부했다(실측 1.11초). 이 앱은
# `--workers=1` 이라 그동안 모든 HTTP 요청이 함께 멈춘다 — 안전핀이 안전핀 역할을 못 한 것이다.
#
# **대조군이 이 값을 밀어냈다** (SC-007). 칸마다 엔진을 두 번 도므로 상한에서의 소요가 두 배가
# 됐고, CI 러너 실측으로 2000칸이 13.0초 — 예산 밖이었다. `scripts/verify_grid_cost_budget.py`
# 가 그것을 잡아 이 값을 내리게 했다. 1200 은 그 러너에서 7.8초다.
MAX_COMBOS = 1200


@dataclass(frozen=True)
class Axis:
    """격자의 한 축 — 파라미터 하나가 훑는 값들."""

    name: str
    values: tuple

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError(f"축 {self.name} 에 값이 없다 — 훑을 것이 없으면 축이 아니다")
        # **중복은 조합이 아니다.** 같은 값을 두 번 훑으면 계산은 같은데 칸 수만 늘어,
        # `attempts_used` 가 실제 distinct 조합보다 부풀고 「100가지를 돌려봤다 / 45번이
        # 한계」류의 자기모순이 그대로 재발한다(스펙 §8.5.2 — 이 모듈이 막으려던 바로 그것).
        seen = []
        for v in self.values:
            if v not in seen:
                seen.append(v)
        if len(seen) != len(self.values):
            object.__setattr__(self, "values", tuple(seen))


@dataclass
class Cell:
    """격자 한 칸 — 파라미터 조합 하나와 그 결과."""

    params: dict
    result: RunResult
    failed_reason: str | None = None
    #: 같은 조합을 **비용 0으로 다시 돌린** 결과. 「비용을 안 냈다면 얼마였나」를 나눗셈으로
    #: 흉내내면 틀린다 — 비용이 현금을 깎아 체결 수량 자체가 달라지므로, 거래 수까지 갈린다.
    costless: RunResult | None = None

    @property
    def ok(self) -> bool:
        return self.failed_reason is None


@dataclass
class Grid:
    axes: tuple[Axis, ...]
    cells: list[Cell]
    base_params: dict

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(len(a.values) for a in self.axes)

    @property
    def attempts_used(self) -> int:
        """이 격자가 소비한 시도 횟수.

        **칸 수와 같다.** 격자를 훑는 것도 시도이므로(§8.5.2), 「100가지를 돌려봤다」와
        「45번이 한계」가 같은 화면에 뜨는 자기모순을 여기서 막는다.
        """
        return len(self.cells)

    def cell_at(self, params: dict) -> Cell | None:
        for cell in self.cells:
            if all(cell.params.get(k) == v for k, v in params.items()):
                return cell
        return None


def combo_count(axes: tuple[Axis, ...]) -> int:
    """조합 수를 **만들지 않고** 센다.

    곱셈 한 번이면 되는 것을 리스트를 다 만들어 `len()` 으로 재면, 상한을 넘는 입력일수록
    거부가 늦어진다 — 정확히 막아야 할 그 입력에서 가장 오래 걸린다.
    """
    if not axes:
        return 1
    return math.prod(len(axis.values) for axis in axes)


def combinations(axes: tuple[Axis, ...], base_params: dict) -> list[dict]:
    """축들의 곱집합. 축이 없으면 기본 파라미터 한 칸이다 — **빈 격자는 없다.**

    **크기를 먼저 확인하고 만든다.** 상한을 넘으면 한 칸도 만들지 않고 던진다.
    """
    total = combo_count(axes)
    if total > MAX_COMBOS:
        raise ValueError(
            f"조합이 {total:,}개다 — 한 번에 도는 상한은 {MAX_COMBOS:,}개다. "
            "축을 줄이거나 나눠 돌려라 (잘라서 도는 것은 「전부 돌려봤다」가 아니다)."
        )
    if not axes:
        return [dict(base_params)]
    out = []
    for values in product(*(axis.values for axis in axes)):
        params = dict(base_params)
        params.update(dict(zip((a.name for a in axes), values, strict=True)))
        out.append(params)
    return out


def run_grid(
    *,
    strategy: Strategy,
    axes: tuple[Axis, ...],
    base_params: dict,
    series: BarSeries,
    initial_cash: float,
    costs: CostModel,
) -> Grid:
    """격자 전체를 돈다 — **캔들을 한 번만 올린다.**

    `rows` 를 루프 **밖에서** 한 번 만든다. 조합마다 만들면 그 변환이 곧 새 병목이 된다
    (686만 행에서 행 지향 1.81GB vs 컬럼 지향 0.35GB).

    한 칸이 터져도 격자를 버리지 않는다 — 그 칸에 사유를 적고 나머지를 계속 돈다.
    파라미터 조합 중에 전략이 못 받는 값이 섞이는 것은 정상이고, 그때 격자 전체가
    사라지면 **어느 칸이 문제인지도 사라진다.**
    """
    combos = combinations(axes, base_params)  # 상한 초과는 여기서 **만들기 전에** 던진다

    rows = series.rows()  # ← 루프 밖. 이 한 줄이 이 모듈의 존재 이유다.
    cells: list[Cell] = []
    for params in combos:
        try:
            result = run_single(
                strategy=strategy,
                params=params,
                series=series,
                rows=rows,
                initial_cash=initial_cash,
                costs=costs,
            )
            cells.append(
                Cell(params=params, result=result, costless=_costless(strategy, params, series, rows, initial_cash))
            )
        except Exception as exc:  # noqa: BLE001 — 남의 전략 코드라 무엇이 터질지 모른다
            cells.append(Cell(params=params, result=RunResult(), failed_reason=str(exc)[:500]))

    return Grid(axes=axes, cells=cells, base_params=dict(base_params))


def _costless(strategy: Strategy, params: dict, series: BarSeries, rows, initial_cash: float) -> RunResult | None:
    """같은 조합을 **비용 0으로** 다시 돌린다. 같은 `rows` 를 재사용하므로 DB 를 더 읽지 않는다.

    **대조군 사고가 이 칸을 죽이지 않는다.** 비용을 낸 세계의 결과는 이미 나왔고, 못 구한 것은
    견줄 상대뿐이다 — 실패하면 `None` 을 주고 화면이 「모른다」로 답한다.
    """
    try:
        return run_single(
            strategy=strategy,
            params=params,
            series=series,
            rows=rows,
            initial_cash=initial_cash,
            costs=FREE_COSTS,
        )
    except Exception:  # noqa: BLE001 — 남의 전략 코드라 무엇이 터질지 모른다
        return None


def axes_from_spec(param_specs: list[dict], sweep: dict[str, list]) -> tuple[Axis, ...]:
    """전략이 선언한 파라미터 중 훑을 것만 축으로 세운다.

    선언에 없는 이름을 훑으려 하면 **조용히 무시하지 않고 던진다** — 오타가 「그 축은 안
    돌았다」로 조용히 넘어가면, 격자가 실제로 무엇을 훑었는지 화면 문구와 어긋난다.
    """
    declared = {spec["name"] for spec in param_specs}
    unknown = sorted(set(sweep) - declared)
    if unknown:
        raise ValueError(
            f"전략이 선언하지 않은 파라미터를 훑으려 한다: {', '.join(unknown)} "
            f"(선언된 것: {', '.join(sorted(declared)) or '없음'})"
        )
    return tuple(Axis(name=name, values=tuple(sweep[name])) for name in sorted(sweep))
