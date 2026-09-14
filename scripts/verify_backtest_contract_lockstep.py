#!/usr/bin/env python3
"""백테스트 응답 계약의 lockstep — 프론트가 읽는 필드를 백엔드가 실제로 보내는가 (fail-closed).

## 왜 있나

`GridCellOut` 이 두 곳에 있다: 프론트 타입(`frontend/schemas/backtest/backtest.ts`)과 백엔드
응답 모델(`app/schemas/backtest/backtest_schema.py`). 백엔드 **서비스**는 `metrics` 를 만들어
넣는데 **응답 모델이 그 필드를 선언하지 않아** FastAPI 가 버렸다. 프론트의 채색 3종이 전부
`cell.metrics` 를 읽으므로 값이 항상 `null` 이 되고 — **성공한 칸 25개가 전부 「실패」로
그려졌다**(#268 실측). 화면도 서버도 각자는 멀쩡했고, 그 사이가 비어 있었다.

같은 클래스가 하루 전에도 있었다: 프론트가 `dataKind === "candles"` 를 찾는데 백엔드는 그 값을
낸 적이 없었다(#258). 두 번 났으면 그물을 놓을 자리다.

## 무엇을 보나

1. 프론트 인터페이스가 선언한 필드가 **백엔드 응답 모델에 다 있다** (없으면 응답에서 사라진다)
2. 백엔드 **서비스가 만드는 dict 의 키**가 응답 모델에 다 있다 (선언 안 하면 조용히 버려진다)

**fail-closed**: 대조한 인터페이스가 0건이거나 파일을 못 읽으면 실패한다. 검사한 수를 늘 출력한다.

**루트 `scripts/` 에 사는 이유**: 입력이 프론트와 백엔드에 걸쳐 있다. 경로 필터가 있는
워크플로에 두면 이 그물이 지켜야 할 바로 그 PR 클래스(프론트만 바뀐 PR)에서 skip 된다 (#331).
경로 필터 없이 도는 `ci.yml` 의 `test: repo` 잡이 실행한다.

실행: `python3 scripts/verify_backtest_contract_lockstep.py`
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend-service"

FRONT_TYPES = REPO_ROOT / "frontend" / "schemas" / "backtest" / "backtest.ts"
BACK_SCHEMA = BACKEND / "app" / "schemas" / "backtest" / "backtest_schema.py"
BACK_SERVICE = BACKEND / "app" / "services" / "backtest" / "backtest_service.py"

#: 짝지을 이름 — 프론트 인터페이스 ↔ 백엔드 모델. 이름이 같으면 짝이다.
PAIRS = (
    "GridCellOut",
    "GridOut",
    "GridAxisOut",
    "GridCellMetrics",
    "RunReportOut",
    "ExecutionAssumptionsOut",
    "OpenPositionOut",
    "BotRunOut",
)
#: 프론트 `GridCellMetrics` 의 백엔드 짝은 이름이 다르다 (Out 접미사 관례).
ALIASES = {"GridCellMetrics": "GridCellMetricsOut"}


def front_interface_fields(name: str, text: str) -> set[str] | None:
    match = re.search(rf"export interface {name} \{{(.*?)\n\}}", text, re.DOTALL)
    if match is None:
        return None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return set(re.findall(r"^\s*(\w+)\??\s*:", body, re.MULTILINE))


def back_model_fields(name: str, tree: ast.Module) -> set[str] | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return {
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            }
    return None


def service_cell_keys(tree: ast.Module) -> set[str]:
    """`cells_out.append({...})` 의 키 — 서비스가 실제로 만드는 것."""
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "append" or ast.unparse(node.func.value) != "cells_out":
            continue
        for arg in node.args:
            if isinstance(arg, ast.Dict):
                return {k.value for k in arg.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return set()


def service_cell_metric_dicts(tree: ast.Module) -> list[set[str]]:
    """`cell_metrics = {...}` 각각의 키 목록 — 칸 지표를 만드는 **모든 갈래**.

    갈래가 여럿인 것이 요점이다 (#349): 거래가 있던 칸과 거래 0건 칸이 서로 다른 dict 를
    만든다. **한 갈래라도 필드를 빠뜨리면** 그 칸의 응답에서 그 필드가 사라지고, 화면은
    「값 없음」과 「0」을 다시 못 가린다. 그래서 갈래마다 따로 대조한다.
    """
    out: list[set[str]] = []
    for node in ast.walk(tree):
        # **주석 있는 대입(`cell_metrics: dict = {...}`)도 받는다.** `ast.Assign` 만 보면
        # 한 갈래에 타입 주석을 붙이는 것만으로 그 갈래가 조용히 검사 밖으로 빠지고,
        # 나머지 갈래가 남아 있어 「갈래 0개」 fail-closed 에도 안 걸린다.
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == "cell_metrics" for t in targets):
            continue
        if isinstance(node.value, ast.Dict):
            out.append({k.value for k in node.value.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)})
    return out


#: 칸 지표를 만드는 갈래의 하한 — 「거래가 있던 칸」과 「거래 0건 칸」 둘이다 (#349).
#: 이보다 적으면 갈래 하나가 사라졌거나 수집이 못 찾은 것이고, 어느 쪽이든 검사가 죽은 것이다.
MIN_CELL_METRIC_BRANCHES = 2


def main() -> int:
    for path in (FRONT_TYPES, BACK_SCHEMA, BACK_SERVICE):
        if not path.is_file():
            print(f"::error::필수 파일이 없습니다: {path} — fail-closed 종료")
            return 1

    front_text = FRONT_TYPES.read_text(encoding="utf-8")
    schema_tree = ast.parse(BACK_SCHEMA.read_text(encoding="utf-8"))
    service_tree = ast.parse(BACK_SERVICE.read_text(encoding="utf-8"))

    failures: list[str] = []
    compared = 0
    for name in PAIRS:
        front = front_interface_fields(name, front_text)
        back_name = ALIASES.get(name, name)
        back = back_model_fields(back_name, schema_tree)
        if front is None:
            failures.append(f"프론트에 `{name}` 인터페이스가 없습니다 — 짝이 사라졌습니다")
            continue
        if back is None:
            failures.append(f"백엔드에 `{back_name}` 모델이 없습니다 — 짝이 사라졌습니다")
            continue
        compared += 1
        missing = sorted(front - back)
        if missing:
            failures.append(
                f"{name}: 프론트가 읽는데 백엔드 응답 모델에 없습니다 → 응답에서 사라집니다: {', '.join(missing)}"
            )

    cell_keys = service_cell_keys(service_tree)
    if not cell_keys:
        failures.append("서비스의 `cells_out.append({...})` 를 찾지 못했습니다 — 검사가 죽었습니다")
    else:
        declared = back_model_fields("GridCellOut", schema_tree) or set()
        dropped = sorted(cell_keys - declared)
        if dropped:
            failures.append(f"서비스가 만드는데 응답 모델이 선언하지 않아 **버려집니다**: {', '.join(dropped)}")

    # 칸 **지표**도 같은 규약이다 — 갈래마다 응답 모델의 필드를 전부 채워야 한다 (#349).
    metric_dicts = service_cell_metric_dicts(service_tree)
    metric_fields = back_model_fields("GridCellMetricsOut", schema_tree) or set()
    if len(metric_dicts) < MIN_CELL_METRIC_BRANCHES:
        failures.append(
            f"서비스의 `cell_metrics = {{...}}` 갈래가 {len(metric_dicts)}개뿐입니다 "
            f"(하한 {MIN_CELL_METRIC_BRANCHES}) — 검사가 죽었거나 「거래 0건」 갈래가 사라졌습니다"
        )
    elif not metric_fields:
        failures.append("백엔드에 `GridCellMetricsOut` 모델이 없습니다 — 짝이 사라졌습니다")
    else:
        for index, keys in enumerate(metric_dicts, start=1):
            dropped = sorted(keys - metric_fields)
            if dropped:
                failures.append(
                    f"칸 지표 {index}번째 갈래: 서비스가 만드는데 모델이 선언하지 않아 **버려집니다**: "
                    f"{', '.join(dropped)}"
                )
            unfilled = sorted(metric_fields - keys)
            if unfilled:
                failures.append(
                    f"칸 지표 {index}번째 갈래: 모델이 선언했는데 서비스가 안 채웁니다 — "
                    f"그 칸은 이 필드를 못 지고 갑니다: {', '.join(unfilled)}"
                )

    if compared == 0:
        print("::error::대조한 인터페이스가 0건입니다 — fail-closed 종료")
        return 1

    print(
        f"대조한 인터페이스 {compared}쌍 · 서비스가 만드는 칸 키 {len(cell_keys)}개 · "
        f"칸 지표 갈래 {len(metric_dicts)}개 × 필드 {len(metric_fields)}개"
    )
    if failures:
        print(f"::error::백테스트 계약 lockstep 위반 {len(failures)}건")
        for failure in failures:
            print(f"::error::  {failure}")
        print("::error::응답 모델이 선언하지 않은 필드는 FastAPI 가 버린다 — 화면은 그것을 null 로 본다.")
        return 1

    print("위반 0건 — 프론트가 읽는 필드를 백엔드가 다 보낸다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
