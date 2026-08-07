"""적재 잡 스키마. `tn_ingest_run` 이 요청·실행·이력을 겸하므로(M2-AD-12) 입력과 출력이 같은 표다."""

from typing import Literal

from pydantic import BaseModel, Field

JobKind = Literal["instrument_master", "daily_bar", "minute_bar"]
RunStatus = Literal["queued", "running", "succeeded", "failed", "rate_limited"]


class IngestRunCreateIn(BaseModel):
    """수동 적재 요청.

    `scope` 형식은 잡 종류마다 다르다:
    - `instrument_master` → `"NASDAQ"` (시장 하나)
    - `daily_bar`·`minute_bar` → `"NASDAQ:AAPL,MSFT"` (시장 + 종목 목록)
    """

    source: str = Field(..., max_length=30)
    job_kind: JobKind
    scope: str = Field(..., max_length=200)
    period_from: str | None = None
    period_to: str | None = None


class IngestRunOut(BaseModel):
    rn: int | None = None
    run_id: int
    source: str
    job_kind: str
    scope: str | None = None
    period_from: str | None = None
    period_to: str | None = None
    status: str
    cursor: str | None = None
    written_rows: int | None = None
    skipped_rows: int | None = None
    failed_reason: str | None = None
    workspace_id: int | None = None
    started_dt: str | None = None
    finished_dt: str | None = None
    reg_dt: str | None = None
    reg_id: str | None = None
    mod_dt: str | None = None
    mod_id: str | None = None


class IngestRunsOut(BaseModel):
    items: list[IngestRunOut]
    total_count: int
