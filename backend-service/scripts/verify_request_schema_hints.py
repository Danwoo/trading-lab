#!/usr/bin/env python3
"""요청 본문 스키마의 필드에 `description` 이 있는지 센다 — fail-closed (외부 의존 없음).

## 왜 있나

422 응답에 「무엇을 넣어야 하는지」를 싣는 배선은 이미 있다 —
`app/core/exception_handler.py` 의 `_body_field_hints()` 가 본문 모델의
`model_fields[*].description` 을 읽어 `hint` 로 실어 주고, 프론트
`utils/common/errors/apierrors.ts` 가 그 `hint` 를 **행동을 말하는 쪽**으로 우선한다.
프레임워크 영문(`Input should be greater than 0`)은 같은 파일이 이미 막는다.

그래서 `description` 이 비면 배선이 다 있어도 사용자가 받는 답은
「입력 데이터를 확인해주세요.」 한 줄이다 (#292). 그 빈칸은 타입체커도 린터도 안 잡는다 —
`Field(..., gt=0)` 는 완전히 정상인 코드다. 그물이 없으면 채운 만큼 다시 빈다.

## 무엇을 세나

**요청 본문으로 쓰이는 모델의 최상위 필드**만 센다. 이유는 `_body_field_hints()` 가
그것만 읽기 때문이다 — 안내는 `loc[1]`(본문 최상위 필드명)으로 찾으므로, 중첩 모델
(`QuoteBatchIn.symbols` 안의 `QuoteSymbolIn.market`)의 `description` 은 응답에 닿지 않는다.
세는 대상과 쓰이는 대상을 같게 둔다.

본문 모델은 라우터에서 뽑는다 — `app/routers/**/*.py` 를 AST 로 읽어 엔드포인트 인자의
타입 이름을 모으고, 그것이 `app/schemas/**/*_schema.py` 의 pydantic 모델이면 본문 모델이다.
이름 규칙(`*In`)에 기대지 않으므로 규칙을 벗어난 모델도 잡힌다.

`model_fields` 로 세므로 **상속받은 필드도 포함**된다 (`BotCreateIn` 은 `Bot` 의 필드를
같이 받는다) — pydantic 이 실제로 검증하는 집합과 같다.

앱(`main`)을 import 하지 않는다. `core.config.Settings` 가 `.env` 를 요구해 러너에서
죽기 때문이다. 스키마 모듈은 순수 pydantic 이라 단독으로 import 된다.

## 상한 — 늘지도 줄지도 못한다

`MISSING_CAP` 은 「`description` 없는 필드」의 수를 **정확히** 박는다.

- **늘면 실패한다** — 새 필드가 안내 없이 들어오면 빨개진다. 늘리려면 상한을 올려야 하고,
  그 한 줄이 리뷰에 보인다.
- **줄어도 실패한다** — 채우고 상한을 안 내리면, 그만큼 새 빈칸이 조용히 들어올 여유가
  생긴다. 상한 방식의 유일한 우회로가 그것이라 막는다. 줄였으면 상한도 같이 내린다.

실행: `uv run python scripts/verify_request_schema_hints.py` (cwd=backend-service).
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"
ROUTERS = APP / "routers"
SCHEMAS = APP / "schemas"

sys.path.insert(0, str(APP))

#: 스캔 대상이 통째로 사라지면(경로 변경·리네임) 조용히 초록이 되지 않게 하는 하한.
#: 정당하게 줄였다면 하한도 함께 내린다.
MIN_ROUTER_FILES = 10
MIN_SCHEMA_MODULES = 10
MIN_BODY_MODELS = 15

#: `description` 이 없는 요청 본문 필드의 수. **정확히** 이 값이어야 한다 — 머리 주석 「상한」 참조.
MISSING_CAP = 0


def _fail(message: str) -> None:
    print(f"::error::{message}")


def load_schema_models() -> tuple[dict[str, type], int]:
    """`app/schemas/**/*_schema.py` 의 pydantic 모델을 `이름 → 클래스` 로 모은다."""
    from pydantic import BaseModel

    models: dict[str, type] = {}
    modules = sorted(SCHEMAS.rglob("*_schema.py"))
    for path in modules:
        dotted = path.relative_to(APP).with_suffix("").as_posix().replace("/", ".")
        module = importlib.import_module(dotted)
        for name, obj in vars(module).items():
            if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
                models.setdefault(name, obj)
    return models, len(modules)


def annotation_names(node: ast.AST) -> list[str]:
    """어노테이션에서 최상위 타입 이름을 뽑는다 (`Annotated[X, ...]` 는 X)."""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Subscript):
        value = node.value
        if isinstance(value, ast.Name) and value.id == "Annotated":
            inner = node.slice
            first = inner.elts[0] if isinstance(inner, ast.Tuple) and inner.elts else inner
            return annotation_names(first)
    return []


def collect_body_model_names() -> tuple[set[str], int]:
    """라우터 엔드포인트 인자의 타입 이름을 모은다."""
    names: set[str] = set()
    files = sorted(ROUTERS.rglob("*.py"))
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                if arg.annotation is not None:
                    names.update(annotation_names(arg.annotation))
    return names, len(files)


def main() -> int:
    for name, directory in (("ROUTERS", ROUTERS), ("SCHEMAS", SCHEMAS)):
        if not directory.is_dir():
            _fail(f"스캔 대상 디렉터리가 없습니다: {name} = {directory}")
            _fail("경로가 바뀌었을 수 있습니다 — 이 스크립트의 ROUTERS·SCHEMAS 를 함께 고치세요.")
            return 1

    models, module_count = load_schema_models()
    candidate_names, router_count = collect_body_model_names()

    if router_count < MIN_ROUTER_FILES:
        _fail(f"라우터 파일을 {router_count}건 수집했습니다 (하한 {MIN_ROUTER_FILES}) — fail-closed 종료")
        return 1
    if module_count < MIN_SCHEMA_MODULES:
        _fail(f"스키마 모듈을 {module_count}건 수집했습니다 (하한 {MIN_SCHEMA_MODULES}) — fail-closed 종료")
        return 1

    body_models = {name: models[name] for name in sorted(candidate_names) if name in models}

    if len(body_models) < MIN_BODY_MODELS:
        _fail(f"요청 본문 모델을 {len(body_models)}건 찾았습니다 (하한 {MIN_BODY_MODELS}) — fail-closed 종료")
        _fail("라우터가 본문을 받는 방식이 바뀌었을 수 있습니다 — annotation_names() 를 확인하세요.")
        return 1

    missing: list[str] = []
    field_count = 0
    for name, model in body_models.items():
        for field_name, field in model.model_fields.items():
            field_count += 1
            if not field.description:
                missing.append(f"{name}.{field_name}")

    print(
        f"라우터 {router_count}건 · 스키마 모듈 {module_count}건 검사 · "
        f"요청 본문 모델 {len(body_models)}건 / 최상위 필드 {field_count}건 · "
        f"description 없음 {len(missing)}건 (상한 {MISSING_CAP})"
    )
    print(f"본문 모델: {', '.join(body_models)}")
    print()

    if len(missing) > MISSING_CAP:
        _fail(f"description 없는 요청 본문 필드 {len(missing)}건 — 상한 {MISSING_CAP}건을 넘었습니다:")
        for item in missing:
            _fail(f"  · {item}")
        _fail(
            "무엇이 유효한지(범위·단위·고를 수 있는 값)를 Field(description=...) 에 적으세요. "
            "본은 app/schemas/ingest/ingest_schema.py 입니다."
        )
        return 1

    if len(missing) < MISSING_CAP:
        _fail(
            f"description 없는 필드가 {len(missing)}건으로 상한 {MISSING_CAP}건보다 적습니다 — "
            f"MISSING_CAP 을 {len(missing)} 로 내리세요."
        )
        _fail("상한을 안 내리면 그만큼 새 빈칸이 조용히 들어올 여유가 남습니다.")
        return 1

    print(f"판정: description 없는 요청 본문 필드 {len(missing)}건 (상한 {MISSING_CAP} 과 일치)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
