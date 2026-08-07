from pydantic import BaseModel, Field
from schemas.common_schema import CommonEntity, TrimmedBaseModel


class Watchlist(TrimmedBaseModel):
    issuer_nm: str | None = Field(None, max_length=200)
    market: str | None = Field(None, max_length=20)
    sector: str | None = Field(None, max_length=100)
    currency: str | None = Field(None, max_length=5)
    target_price: float | None = Field(None, ge=0)
    alert_price: float | None = Field(None, ge=0)
    priority: str | None = Field(None, max_length=5)
    use_at: str | None = Field("Y", max_length=1)
    memo: str | None = Field(None, max_length=1300)
    atch_file_id: str | None = Field(None, max_length=20)


class WatchlistOut(Watchlist, CommonEntity):
    ticker: str


class WatchlistsOut(BaseModel):
    items: list[WatchlistOut]
    total_count: int


class WatchlistCreateIn(Watchlist):
    ticker: str = Field(..., max_length=20)


class WatchlistUpdateIn(Watchlist):
    pass
