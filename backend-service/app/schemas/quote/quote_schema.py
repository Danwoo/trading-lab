"""일괄 시세 스키마 (갈래 3). **구독 필드가 없다** — 이 응답은 요청-응답 스냅샷이다."""

from pydantic import BaseModel, Field


class QuoteBatchIn(BaseModel):
    """`[["NASDAQ","AAPL"], ...]` 대신 객체 목록으로 받는다 — 튜플 순서를 외우게 하지 않는다."""

    symbols: list["QuoteSymbolIn"] = Field(
        ...,
        max_length=100,
        description="조회할 종목 — 한 번에 100개까지. 항목마다 market(시장 코드)과 symbol(종목 코드)을 "
        '객체로 적습니다: [{"market": "KOSPI", "symbol": "005930"}]',
    )


class QuoteSymbolIn(BaseModel):
    market: str = Field(..., description="시장 코드 (예: 'KOSPI', 'NASDAQ').")
    symbol: str = Field(..., description="종목 코드. 시장은 market 에 따로 적습니다.")


class QuoteOut(BaseModel):
    market: str
    symbol: str
    price: float
    change: float
    change_rate: float
    volume: int
    asof: str


class QuotesOut(BaseModel):
    items: list[QuoteOut]
    total_count: int
    source: str | None = None
    # 조회하지 못한 종목과 그 사유 — 없는 값을 0 으로 뭉개지 않는다(FR-021).
    unavailable: dict[str, str] = Field(default_factory=dict)


QuoteBatchIn.model_rebuild()
