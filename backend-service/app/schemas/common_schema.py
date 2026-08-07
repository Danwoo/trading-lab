from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
