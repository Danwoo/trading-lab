"""적재 잡 스키마. `tn_ingest_run` 이 요청·실행·이력을 겸하므로(M2-AD-12) 입력과 출력이 같은 표다."""

from typing import Literal

from pydantic import BaseModel, Field

JobKind = Literal["instrument_master", "daily_bar", "minute_bar"]
RunStatus = Literal["queued", "running", "succeeded", "failed", "rate_limited"]


class IngestRunCreateIn(BaseModel):
    """수동 적재 요청.

    각 필드의 형식은 **아래 `description` 이 정본**이다 — 그 문장이 OpenAPI 와 422 응답으로
    그대로 나간다. 여기에 같은 설명을 다시 쓰면 두 벌이 되고, 곧 서로 어긋난다.
    """

    source: str = Field(
        ...,
        max_length=30,
        description="소스 id — 등록된 이름만 받습니다 (예: 'toss', 'data_go_kr', 'sample'). "
        "무엇이 지금 열려 있는지는 GET /market-capability 가 답합니다.",
        examples=["toss"],
    )
    job_kind: JobKind = Field(
        ...,
        description="instrument_master(종목 목록) · daily_bar(일봉) · minute_bar(분봉) 중 하나.",
        examples=["daily_bar"],
    )
    scope: str = Field(
        ...,
        max_length=200,
        # 시장과 종목을 **한 문자열에** 합치는 것이 자연스러운 추측과 어긋난다 —
        # `market`/`symbol` 을 따로 보내는 시도가 실제로 두 번 있었다(#253).
        description="적재 범위. instrument_master 는 시장 하나('KOSPI'), "
        "daily_bar·minute_bar 는 시장과 종목을 콜론으로 합칩니다('KOSPI:005930,000660'). "
        "market·symbol 을 따로 보내는 필드는 없습니다.",
        examples=["KOSPI:005930,000660"],
    )
    # 예시에 **구체적인 날짜를 적지 않는다** — 작성일이 굳어 반년 뒤 OpenAPI 가 낡은 날짜를
    # 정답처럼 제시한다. 특히 `period_to` 는 「비우면 오늘」이라 예시와 설명이 서로 어긋난다.
    period_from: str | None = Field(
        default=None, description="적재 시작일 (YYYY-MM-DD). 비우면 소스·잡 종류의 기본 구간."
    )
    period_to: str | None = Field(default=None, description="적재 종료일 (YYYY-MM-DD). 비우면 오늘.")


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
