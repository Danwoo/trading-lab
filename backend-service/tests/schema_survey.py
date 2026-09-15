"""스키마 전수 조사에 쓰는 판독 — 그물 둘이 같은 눈으로 본다.

`test_numeric_inputs_are_bounded.py`(들어오는 것은 막는다)와
`test_stored_values_are_readable.py`(저장된 것은 보인다)가 같은 필드 집합을 반대 방향으로
본다. 판독이 둘로 갈리면 한쪽이 안 보는 칸이 생기고, 그 칸은 **두 그물 다 초록인 채로**
샌다 — 실제로 그랬다: `Money | None` 을 숫자로 못 읽어 `alloc_per_symbol`·`take_profit_pct`·
`stop_loss_pct`·`target_price`·`alert_price` 가 전수에서 통째로 빠져 있었다.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Annotated, Union, get_args, get_origin

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"
sys.path.insert(0, str(APP))

from pydantic import BaseModel  # noqa: E402


def models_named(suffix: str) -> list[type[BaseModel]]:
    """`app/schemas/**` 에 선언된, 이름이 `suffix` 로 끝나는 모델 전부."""
    found: dict[str, type[BaseModel]] = {}
    for path in sorted(APP.glob("schemas/**/*.py")):
        if path.name == "__init__.py":
            continue
        module_name = ".".join(path.relative_to(APP).with_suffix("").parts)
        module = importlib.import_module(module_name)
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, BaseModel) and name.endswith(suffix):
                found[f"{module_name}.{name}"] = obj
    return [found[key] for key in sorted(found)]


def is_numeric(annotation) -> bool:
    """`int`/`float` 인가 — Optional 과 `Annotated` 를 벗겨 가며 본다.

    `Money = Annotated[float, ...]` 라 `Money | None` 은 겉만 보면 숫자가 아니다. 겉만 보면
    돈 칸이 전부 검사에서 빠진다.
    """
    if annotation in (int, float):
        return True
    origin = get_origin(annotation)
    if origin is Annotated:
        return is_numeric(get_args(annotation)[0])
    if origin is Union or origin is type(int | str):
        return any(is_numeric(arg) for arg in get_args(annotation))
    return False
