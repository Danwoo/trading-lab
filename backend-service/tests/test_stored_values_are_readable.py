"""#434 — 이미 **저장된 값**을 화면이 읽을 수 있는가 (standalone, fail-closed).

## 왜 이 그물이 따로 있나

상한은 들어오는 값을 막으려고 건다. 그런데 이 레포의 엔티티는 입력과 출력이 **같은
베이스**를 쓴다(`class BotOut(Bot, CommonEntity)` · `class BotCreateIn(Bot)`). 그래서 입력에
상한을 걸면 출력이 조용히 같이 물려받고, **규칙이 생기기 전에 저장된 행**을 읽는 순간
응답 검증에서 터진다.

터지는 자리가 나쁘다 — 목록 응답은 `BotsOut.items: list[BotOut]` 이라 한 행만 넘겨도
**리스트 전체가 500** 이 되어 멀쩡한 나머지까지 안 보인다. 침묵하던 옛 값이 장애로
승격되는 것이고, 사용자는 고칠 기회조차 잃는다. 그래서 읽기는 있는 그대로 낸다 —
고치는 것은 그 값을 화면에서 본 사용자의 몫이다.

`test_numeric_inputs_are_bounded.py` 와 한 쌍이다: **들어오는 것은 막고, 저장된 것은 보인다.**

## 대상

`app/schemas/**` 의 `*Out` 모델 전부. 상속 필드도 포함된다. 검사한 모델·필드 수가 0이면
실패한다 — 「볼 것이 없었다」와 「위반이 없었다」는 다르다.

    uv run python tests/test_stored_values_are_readable.py
"""

from __future__ import annotations

from annotated_types import Ge, Gt, Le, Lt
from pydantic import BaseModel
from schema_survey import is_numeric, models_named

BOUNDS = (Ge, Gt, Le, Lt)

#: 저장될 수 없는 값을 내는 칸 — 계산으로만 만들어져 DB 를 거치지 않는다. 사유를 적고 면제한다.
EXEMPT: dict[str, str] = {}

TIMESTAMP = "2026-08-01T09:00:00+00:00"
AUDIT = {"reg_dt": TIMESTAMP, "reg_id": "x", "mod_dt": TIMESTAMP, "mod_id": "x"}


def response_models() -> list[type[BaseModel]]:
    """`app/schemas/**` 에 선언된 `*Out` 모델 전부."""
    return models_named("Out")


def structural_check() -> tuple[int, list[str]]:
    """출력 모델의 숫자 칸에 상·하한이 남아 있는지 — 클래스 전수."""
    models = response_models()
    if not models:
        return 0, ["응답 스키마 0건 — glob 이 아무것도 못 찾았다 (경로 규약 변경?)"]

    checked = 0
    bounded: list[str] = []
    for model in models:
        for name, field in model.model_fields.items():
            if not is_numeric(field.annotation):
                continue
            checked += 1
            key = f"{model.__name__}.{name}"
            if key in EXEMPT:
                continue
            if any(isinstance(m, BOUNDS) for m in field.metadata):
                bounded.append(key)

    if checked == 0:
        return 0, [f"모델 {len(models)}개를 읽었으나 숫자 칸이 0건 — 판독이 깨졌다"]

    print(f"검사한 응답 스키마 {len(models)}개 · 숫자 칸 {checked}건 · 면제 {len(EXEMPT)}건")
    return checked, bounded


def behavioral_check() -> list[str]:
    """실제로 옛 값을 담은 행을 읽어 본다 — 저장 컬럼 안쪽이면 통과해야 한다.

    값은 전부 그 컬럼이 담을 수 있는 것이다: `alloc_per_symbol`·`avg_price`·`target_price`
    는 `Numeric(18,2)`, `quantity` 는 `integer`.
    """
    from schemas.bot.bot_schema import BotOut  # noqa: PLC0415
    from schemas.portfolio.portfolio_schema import HoldingOut  # noqa: PLC0415
    from schemas.watchlist.watchlist_schema import WatchlistOut  # noqa: PLC0415

    cases = [
        (
            "상한(100%)을 넘겨 저장된 봇의 종목당 비중",
            lambda: BotOut(bot_id=1, bot_nm="옛봇", alloc_per_symbol=5000.0, **AUDIT),
        ),
        (
            "MONEY_MAX 를 넘겨 저장된 평단",
            lambda: HoldingOut(portfolio_id="p", ticker="005930", holding_nm="종목", avg_price=5e15, **AUDIT),
        ),
        (
            "음수로 저장된 보유 수량",
            lambda: HoldingOut(portfolio_id="p", ticker="005930", holding_nm="종목", quantity=-3, **AUDIT),
        ),
        ("MONEY_MAX 를 넘겨 저장된 목표가", lambda: WatchlistOut(ticker="005930", target_price=5e15, **AUDIT)),
    ]
    failures = []
    for label, build in cases:
        try:
            build()
        except Exception as error:  # noqa: BLE001
            failures.append(f"{label}: {type(error).__name__}")
    print(f"옛 값 읽기 {len(cases)}건 중 {len(cases) - len(failures)}건 통과")
    return failures


def main() -> int:
    checked, bounded = structural_check()
    failures = behavioral_check() if checked else []

    if not checked:
        for line in bounded:
            print(f"{line}. 통과가 아니다.")
        return 1

    problems = False
    if bounded:
        problems = True
        print("출력 모델에 남은 상·하한:")
        for key in sorted(set(bounded)):
            print(f"  - {key}")
        print(
            "  → 그 베이스를 `without_input_bounds(...)` 로 감싸 출력용 베이스를 만드세요. "
            "DB 를 거치지 않는 계산값이면 EXEMPT 에 사유와 함께 넣으세요."
        )
    if failures:
        problems = True
        print("저장된 값을 읽다 거부됨:")
        for line in failures:
            print(f"  - {line}")

    if problems:
        return 1
    print("판정: 저장 컬럼 안쪽의 값은 상한이 생긴 뒤에도 전부 읽힌다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
