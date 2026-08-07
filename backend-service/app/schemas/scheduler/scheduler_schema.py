from typing import Literal

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, field_validator
from schemas.common_schema import CommonEntity, TrimmedBaseModel


class Scheduler(TrimmedBaseModel):
    scheduler_nm: str = Field(..., max_length=200)
    day_of_week: str = Field(default="mon", max_length=20)  # mon/tue/.../sun/* (APScheduler)
    hour: int = Field(default=9, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    period_weeks: Literal[1, 2, 4] = Field(default=1)  # 1=주간 2=격주 4=월간 (집계기간·N주마다 발송)
    use_at: str = Field(default="N", max_length=5)  # Y=활성(잡 등록)
    description: str | None = Field(None, max_length=1000)


class DayOfWeekValidatedIn(BaseModel):
    """입력 전용 믹스인 — 새 값만 검증. 응답/공유 베이스에는 얹지 않아 레거시 나쁜 행 읽기는 관대."""

    @field_validator("day_of_week", check_fields=False)
    @classmethod
    def validate_day_of_week(cls, v: str) -> str:
        # 매니저가 쓰는 CronTrigger 를 SoT 로 재사용 — 검증기·실사용 포맷 lockstep
        try:
            CronTrigger(day_of_week=v)
        except ValueError as e:
            raise ValueError("day_of_week 형식이 올바르지 않습니다. (예: mon, mon-fri, mon,wed,fri, *)") from e
        return v


class SchedulerOut(Scheduler, CommonEntity):
    scheduler_id: str


class SchedulersOut(BaseModel):
    items: list[SchedulerOut]
    total_count: int


class SchedulerCreateIn(Scheduler, DayOfWeekValidatedIn):
    scheduler_id: str = Field(..., max_length=20)


class SchedulerUpdateIn(Scheduler, DayOfWeekValidatedIn):
    pass


class SchedulerMemberOut(CommonEntity):
    scheduler_id: str
    account_id: str
    email: str
    name: str | None = None


class SchedulerMembersOut(BaseModel):
    items: list[SchedulerMemberOut]
    total_count: int


class SchedulerMemberIn(BaseModel):
    account_id: str = Field(..., max_length=100)
    email: str = Field(..., max_length=200)
    name: str | None = Field(None, max_length=200)
