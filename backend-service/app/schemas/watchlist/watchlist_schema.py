from pydantic import BaseModel, Field
from schemas.common_schema import MONEY_MAX, CommonEntity, Money, TrimmedBaseModel


class Watchlist(TrimmedBaseModel):
    """관심종목 한 줄. 입력·출력이 이 베이스를 함께 쓴다.

    각 필드의 형식은 **아래 `description` 이 정본**이다 — 그 문장이 OpenAPI 와 422 응답으로
    그대로 나간다 (#292).
    """

    issuer_nm: str | None = Field(None, max_length=200, description="종목명 — 200자까지.")
    market: str | None = Field(
        None,
        max_length=20,
        description="시장 코드 — 공통코드 「관심종목 시장」(KOSPI · KOSDAQ · NASDAQ · NYSE)의 코드값. 20자까지.",
        examples=["KOSPI"],
    )
    sector: str | None = Field(
        None, max_length=100, description="섹터 — 공통코드 「관심종목 섹터」의 코드값(표시명이 아닙니다). 100자까지."
    )
    currency: str | None = Field(
        None,
        max_length=5,
        description="통화 코드 — 공통코드 「관심종목 통화」(KRW · USD)의 코드값. 5자까지.",
        examples=["KRW"],
    )
    target_price: Money | None = Field(
        None, ge=0, le=MONEY_MAX, description="목표가 — 0 이상, 소수점 둘째 자리까지. 단위는 currency 의 통화입니다."
    )
    alert_price: Money | None = Field(
        None, ge=0, le=MONEY_MAX, description="알림가 — 0 이상, 소수점 둘째 자리까지. 단위는 currency 의 통화입니다."
    )
    priority: str | None = Field(
        None,
        max_length=5,
        description="우선순위 — 공통코드 「관심종목 우선순위」의 코드값 '1'(높음) · '2'(중간) · '3'(낮음). 5자까지.",
        examples=["1"],
    )
    use_at: str | None = Field("Y", max_length=1, description="사용 여부 — 'Y'(사용) 또는 'N'(미사용). 한 글자입니다.")
    memo: str | None = Field(None, max_length=1300, description="메모 — 1300자까지.")
    atch_file_id: str | None = Field(
        None, max_length=20, description="첨부 파일 그룹 id — file 모듈이 발급한 값. 20자까지, 비우면 첨부 없음."
    )


class WatchlistOut(Watchlist, CommonEntity):
    ticker: str


class WatchlistsOut(BaseModel):
    items: list[WatchlistOut]
    total_count: int


class WatchlistCreateIn(Watchlist):
    ticker: str = Field(
        ...,
        max_length=20,
        description="종목 코드 — 20자까지. 시장은 market 에 따로 적습니다. 이미 담은 종목이면 거부됩니다.",
        examples=["005930"],
    )


class WatchlistUpdateIn(Watchlist):
    pass
