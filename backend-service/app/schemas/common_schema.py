from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator

# 저장 컬럼이 정하는 한계 — 스키마가 이 선을 넘겨보내면 DB 에서 500 으로 터진다.
QUANTITY_MAX = 2_147_483_647  # integer
MONEY_MAX = 1e15  # Numeric(18,2) 안쪽의 보수적인 상한
WEIGHT_MAX = 9999.99  # Numeric(6,2)


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
