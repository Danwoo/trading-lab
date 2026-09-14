"""#434 — 사용자가 치는 숫자 칸에 **상한이 있는가** (standalone, fail-closed).

## 왜 클래스로 보나

`alloc_per_symbol` 하나를 고쳤더니 같은 파일 안에 형제가 넷 더 있었다 —
`take_profit_pct`(상한 없음) · `stop_loss_pct`(자릿수 없음) · `max_positions` ·
`max_trades_per_day`(정수 상한 없음) · `initial_cash`(상한 없음). 인스턴스를 하나씩 고치면
다음에 새 칸이 생길 때 같은 구멍이 다시 난다.

저장 컬럼에는 **항상** 천장이 있다(`integer` 21억 · `Numeric(p,s)` 는 자릿수). 스키마가 그
천장을 안 적으면 넘는 값이 그대로 지나가 **DB 에서 500** 이 되고, 사용자가 받는 것은
「무엇이 왜 잘못됐다」가 아니라 빈 실패다. 그래서 요청 스키마의 숫자 칸은 예외 없이 상한을
선언한다 — 값이 얼마인지는 그 칸이 알고, 여기서는 **선언했는지**만 본다.

## 대상

`app/schemas/**` 의 `*In` 모델 전부(요청 바디 경계). 상속 필드도 포함된다.
검사한 모델·필드 수가 0이면 실패한다 — 「볼 것이 없었다」와 「위반이 없었다」는 다르다.

    uv run python tests/test_numeric_inputs_are_bounded.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"
sys.path.insert(0, str(APP))

from annotated_types import Le, Lt  # noqa: E402
from pydantic import BaseModel  # noqa: E402

#: 이 칸들은 상한이 뜻으로 정해지지 않는다 — 이유를 적고 면제한다. 비어 있어야 정상이다.
EXEMPT: dict[str, str] = {}


def request_models() -> list[type[BaseModel]]:
    """`app/schemas/**` 에 선언된 `*In` 모델 전부."""
    found: dict[str, type[BaseModel]] = {}
    for path in sorted(APP.glob("schemas/**/*.py")):
        if path.name == "__init__.py":
            continue
        module_name = ".".join(path.relative_to(APP).with_suffix("").parts)
        module = importlib.import_module(module_name)
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, BaseModel) and name.endswith("In"):
                found[f"{module_name}.{name}"] = obj
    return [found[k] for k in sorted(found)]


def is_numeric(annotation) -> bool:
    """`int`/`float` 또는 그 Optional — 문자열·리터럴·컨테이너는 아니다."""
    args = getattr(annotation, "__args__", None)
    if args:
        return any(a in (int, float) for a in args)
    return annotation in (int, float)


def has_upper_bound(field) -> bool:
    return any(isinstance(m, (Le, Lt)) for m in field.metadata)


def main() -> int:
    models = request_models()
    if not models:
        print("요청 스키마 0건 — glob 이 아무것도 못 찾았다 (경로 규약 변경?). 통과가 아니다.")
        return 1

    checked = 0
    missing: list[str] = []
    for model in models:
        for name, field in model.model_fields.items():
            if not is_numeric(field.annotation):
                continue
            checked += 1
            key = f"{model.__name__}.{name}"
            if key in EXEMPT or has_upper_bound(field):
                continue
            missing.append(key)

    if checked == 0:
        print(f"모델 {len(models)}개를 읽었으나 숫자 칸이 0건 — 판독이 깨졌다. 통과가 아니다.")
        return 1

    print(f"검사한 요청 스키마 {len(models)}개 · 숫자 칸 {checked}건 · 면제 {len(EXEMPT)}건")
    if missing:
        print("상한이 없는 숫자 칸:")
        for key in sorted(set(missing)):
            print(f"  - {key}")
        print(
            "  → 저장 컬럼의 천장을 `le=` 로 적으세요 (integer 는 QUANTITY_MAX, "
            "Numeric(6,2) 는 NUMERIC_6_2_MAX, 돈은 MONEY_MAX). 뜻으로 정해지지 않는 칸이면 "
            "EXEMPT 에 사유와 함께 넣으세요."
        )
        return 1
    print("판정: 사용자가 치는 숫자 칸이 전부 저장 컬럼 안쪽에서 거부된다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
