from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from annotated_types import Ge, Gt, Le, Lt
from pydantic import AfterValidator, BaseModel, Field, create_model, field_validator

# 저장 컬럼이 정하는 한계 — 스키마가 이 선을 넘겨보내면 DB 에서 500 으로 터진다.
QUANTITY_MAX = 2_147_483_647  # integer
BIGINT_MAX = 9_223_372_036_854_775_807  # bigint
MONEY_MAX = 1e15  # Numeric(18,2) 안쪽의 보수적인 상한
NUMERIC_6_2_MAX = 9999.99  # Numeric(6,2) 컬럼이 담는 최대 — 넘기면 저장에서 500 이다
WEIGHT_MAX = NUMERIC_6_2_MAX
PERCENT_MAX = 100.0  # 비중·비율은 전체의 몫이라 100% 를 넘을 수 없다


def _reject_subunit(v: float | None) -> float | None:
    """소수점 셋째 자리 아래를 반올림하지 않고 거부한다.

    돈 컬럼은 둘째 자리까지만 담는다. 그냥 통과시키면 저장 시점에 조용히 반올림돼
    사용자가 넣지 않은 값이 보드에 남는다 — 바꿀 거면 바꾸기 전에 말해야 한다.
    """
    if v is None:
        return v
    try:
        exponent = Decimal(str(v)).as_tuple().exponent
    except InvalidOperation:
        return v
    if isinstance(exponent, int) and exponent < -2:
        raise ValueError("소수점 둘째 자리까지만 저장됩니다 — 셋째 자리 아래는 반올림하지 않고 거부합니다.")
    return v


Money = Annotated[float, AfterValidator(_reject_subunit)]


# 상·하한은 **들어오는 값**을 막는 규칙이다. 출력 모델이 같은 베이스로 그것을 물려받으면,
# 규칙이 생기기 전에 저장된 행을 읽는 순간 응답 검증에서 터진다.
_INPUT_BOUNDS = (Ge, Gt, Le, Lt)


def without_input_bounds(model: type[BaseModel], name: str) -> type[BaseModel]:
    """상·하한을 뗀 출력용 베이스를 만든다.

    목록은 한 행만 상한을 넘겨도 통째로 500 이 되어 멀쩡한 나머지까지 안 보인다. 이미
    저장된 값은 사용자가 화면에서 보고 고쳐야 하므로, 읽기는 있는 그대로 낸다.

    자릿수·길이 규칙은 떼지 않는다 — 이 값들이 사는 컬럼이 그 규칙보다 좁거나 같아서
    저장된 값을 거부할 수 없다. 컬럼보다 좁은 것은 상·하한뿐이다.
    """
    fields: dict[str, Any] = {}
    for field_name, info in model.model_fields.items():
        kept = [m for m in info.metadata if not isinstance(m, _INPUT_BOUNDS)]
        annotation = Annotated[tuple([info.annotation, *kept])] if kept else info.annotation
        options: dict[str, Any] = {"description": info.description, "examples": info.examples}
        if info.default_factory is not None:
            options["default_factory"] = info.default_factory
        else:
            options["default"] = info.default
        fields[field_name] = (annotation, Field(**options))
    relaxed = create_model(name, __base__=model.__bases__, **fields)
    relaxed.__doc__ = f"{model.__name__} 에서 상·하한을 뗀 출력용 베이스 — 저장된 것을 그대로 낸다."
    return relaxed


# 공통 엔티티 타입
class CommonEntity(BaseModel):
    rn: int | None = Field(None)
    reg_dt: str | None = Field(None)
    reg_id: str | None = Field(None, max_length=100)
    mod_dt: str | None = Field(None)
    mod_id: str | None = Field(None, max_length=100)


class TrimmedBaseModel(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class CreateOut(BaseModel):
    message: str = Field(default="등록이 완료되었습니다.")
    data: dict | None = Field(None)


class UpdateOut(BaseModel):
    message: str = Field(default="수정이 완료되었습니다.")


class DeleteOut(BaseModel):
    message: str = Field(default="삭제가 완료되었습니다.")


class MessageOut(BaseModel):
    """단순 메시지 응답"""

    message: str
    level: Literal["success", "warning", "info", "error"] = "success"  # 프론트 toast 레벨 (no-op·경고는 warning)
