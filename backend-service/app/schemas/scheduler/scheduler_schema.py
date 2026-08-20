from typing import Literal

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, Field, field_validator
from schemas.common_schema import CommonEntity, TrimmedBaseModel


class Scheduler(TrimmedBaseModel):
    """발송 스케줄. 입력·출력이 이 베이스를 함께 쓴다.

    각 필드의 형식은 **아래 `description` 이 정본**이다 — 그 문장이 OpenAPI 와 422 응답으로
    그대로 나간다 (#292).
    """

    scheduler_nm: str = Field(..., max_length=200, description="스케줄 이름 — 200자까지.")
    day_of_week: str = Field(
        default="mon",
        max_length=20,
        description="발송 요일 — APScheduler 표기입니다. 하나(mon) · 범위(mon-fri) · 목록(mon,wed,fri) · "
        "전체(*) 를 받습니다. 20자까지.",
        examples=["mon-fri"],
    )
    hour: int = Field(default=9, ge=0, le=23, description="발송 시각의 시 — 0~23.")
    minute: int = Field(default=0, ge=0, le=59, description="발송 시각의 분 — 0~59.")
    period_weeks: Literal[1, 2, 4] = Field(
        default=1, description="발송 주기 — 1(주간) · 2(격주) · 4(월간) 중 하나. 집계 기간도 같이 정합니다."
    )
    use_at: str = Field(
        default="N",
        max_length=5,
        description="사용 여부 — 'Y' 면 잡을 등록해 실제로 발송하고, 'N' 이면 저장만 합니다.",
    )
    description: str | None = Field(None, max_length=1000, description="설명 — 1000자까지. 비워도 됩니다.")


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
    scheduler_id: str = Field(
        ..., max_length=20, description="스케줄 id — 직접 정하는 값입니다. 20자까지, 이미 있는 id 면 거부됩니다."
    )


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
    """이 스케줄이 보낼 대상 한 명."""

    account_id: str = Field(..., max_length=100, description="계정 id — 100자까지.")
    email: str = Field(..., max_length=200, description="받는 사람 이메일 주소 — 200자까지.")
    name: str | None = Field(None, max_length=200, description="받는 사람 이름 — 200자까지. 비워도 됩니다.")
