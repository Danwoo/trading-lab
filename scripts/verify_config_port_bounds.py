"""전 서비스 포트 설정의 범위 제약 정적 검사 — 0·음수·65536 이상을 기동 시 거부하는가 (#271 #377).

배경: #271 이 `backend-service` 의 포트·크기 설정에 `Field(gt=0, le=65535)` 를 걸었지만 그 규율이
**서비스 경계를 넘지 않았다** — 이 레포는 서비스마다 `app/core/config.py` 를 복제해 쓰므로
doc-search 의 `REDIS_DB_PORT`·`DOC_VECTOR_DB_PORT`, multi-agent 의 `MULTI_AGENT_SQL_DB_PORT` 가
0·음수를 그대로 통과시켰다(#377). 한 서비스만 고치면 다음 복제에서 또 갈린다.

검사: `*/app/core/config.py` 의 `Settings` 안에서 이름이 `_PORT` 로 끝나는 필드를 **전부** 찾아
  (1) 타입이 `int` 이고
  (2) 기본값이 `Field(...)` 이며 하한(`gt=0` 또는 `ge=1`)과 상한(`le=65535` 또는 `lt=65536`)을
      둘 다 선언했는지
를 본다. 대상을 서비스 이름 목록이 아니라 글롭으로 찾으므로 **새 서비스가 생겨도 자동으로 걸린다**.

정적 검사인 이유: 서비스마다 venv·필수 env 가 달라 10개를 한 프로세스에서 인스턴스화할 수 없다.
"이 제약이 실제로 0·음수를 거부한다"는 **행동** 검증은 `backend-service/scripts/
verify_config_positive_values.py` 가 대표로 한다 — 같은 pydantic 메커니즘이라 한 서비스의 행동
검증이 전 서비스를 대표한다(verify_auth_lockstep.py 와 같은 분업).

**fail-closed**: 서비스 수가 기대 하한 미만이거나 포트 필드를 0건 찾으면 실패한다 — 글롭이
어긋나 아무것도 안 본 것을 "위반 없음"으로 읽지 않기 위해서다.

stdlib 전용 (AST 파싱, import 없음): `python3 scripts/verify_config_port_bounds.py` (cwd 무관).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# app/core/config.py 를 가진 서비스 하한 (현재 10개) — 글롭이 어긋나거나 서비스가 사라지면 실패.
EXPECTED_MIN_SERVICES = 10
# 포트 필드 하한 (현재 6개: backend 3 · doc-search 2 · multi-agent 1) — 0건이면 당연히 실패.
EXPECTED_MIN_PORT_FIELDS = 6
PORT_FIELD_SUFFIX = "_PORT"
LOWER_BOUNDS = {"gt": 0, "ge": 1}
UPPER_BOUNDS = {"le": 65535, "lt": 65536}


def _settings_class(tree: ast.Module) -> ast.ClassDef | None:
    return next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Settings"),
        None,
    )


def _field_call_bounds(value: ast.expr | None) -> dict[str, int | None]:
    """기본값이 `Field(...)` 면 그 키워드 중 범위 제약만 뽑는다 (아니면 빈 dict)."""
    if not isinstance(value, ast.Call):
        return {}
    func = value.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    if name != "Field":
        return {}
    bounds: dict[str, int | None] = {}
    for keyword in value.keywords:
        if keyword.arg in LOWER_BOUNDS or keyword.arg in UPPER_BOUNDS:
            constant = keyword.value
            bounds[keyword.arg] = (
                constant.value if isinstance(constant, ast.Constant) else None
            )
    return bounds


def _annotation_is_int(annotation: ast.expr) -> bool:
    return isinstance(annotation, ast.Name) and annotation.id == "int"


def check_service(path: Path, problems: list[str]) -> int:
    """한 서비스의 포트 필드를 검사하고 검사한 필드 수를 돌려준다."""
    service = path.parents[2].name
    prefix = f"{service}/app/core/config.py"
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as exc:
        problems.append(
            f"{prefix}: 파싱 불가 (SyntaxError: {exc.msg}, line {exc.lineno})"
        )
        return 0
    settings = _settings_class(tree)
    if settings is None:
        problems.append(f"{prefix}: Settings 클래스 없음")
        return 0

    checked = 0
    for node in settings.body:
        if not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)):
            continue
        field = node.target.id
        if not field.endswith(PORT_FIELD_SUFFIX):
            continue
        checked += 1
        if not _annotation_is_int(node.annotation):
            problems.append(
                f"{prefix}: {field} 의 타입이 int 가 아니다 — 포트 필드의 범위 제약을 판정할 수 "
                "없다 (의도적이면 이름을 바꾸거나 이 검사를 함께 고칠 것)"
            )
            continue
        bounds = _field_call_bounds(node.value)
        lower = [k for k in LOWER_BOUNDS if bounds.get(k) == LOWER_BOUNDS[k]]
        upper = [k for k in UPPER_BOUNDS if bounds.get(k) == UPPER_BOUNDS[k]]
        if not lower or not upper:
            problems.append(
                f"{prefix}: {field} 에 포트 범위 제약이 없다 — "
                "`Field(gt=0, le=65535)` 로 0·음수·65536 이상을 기동 시 거부할 것 (#271 #377)"
            )
    return checked


def main() -> int:
    problems: list[str] = []
    services = sorted(REPO_ROOT.glob("*/app/core/config.py"))
    if len(services) < EXPECTED_MIN_SERVICES:
        problems.append(
            f"config.py 를 가진 서비스 {len(services)}개 — 기대 하한 {EXPECTED_MIN_SERVICES}개 "
            "미만이다 (글롭이 어긋났거나 서비스가 사라졌다)"
        )

    port_fields = sum(check_service(path, problems) for path in services)
    if port_fields < EXPECTED_MIN_PORT_FIELDS:
        problems.append(
            f"포트 필드 {port_fields}개 — 기대 하한 {EXPECTED_MIN_PORT_FIELDS}개 미만이다 "
            "(필드가 사라졌거나 이름 규칙이 바뀌어 검사가 헛돌고 있다)"
        )

    if problems:
        print("포트 설정 범위 제약 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        f"포트 범위 제약 OK — 서비스 {len(services)}개의 *_PORT 필드 {port_fields}개 전부 "
        "하한(gt=0|ge=1)·상한(le=65535|lt=65536) 선언"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
