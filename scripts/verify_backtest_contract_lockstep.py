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
경로 필터 없이 도는 `repo-scans.yml` 의 `test: repo-scan` 잡이 실행한다.

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
PAIRS = ("GridCellOut", "GridOut", "GridAxisOut", "GridCellMetrics", "RunReportOut", "ExecutionAssumptionsOut")
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

    if compared == 0:
        print("::error::대조한 인터페이스가 0건입니다 — fail-closed 종료")
        return 1

    print(f"대조한 인터페이스 {compared}쌍 · 서비스가 만드는 칸 키 {len(cell_keys)}개")
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
