# services/market/market_service.py
from repositories.market.market_repository import MarketRepository
from schemas.market.market_schema import (
    MarketDataOut,
    MarketFxIn,
    MarketIndexIn,
    MarketOhlcIn,
    MarketQuoteIn,
    MarketSearchIn,
)
from utils.common.staged_search import staged_search


class MarketService:
    """시세·캔들·지수·환율·종목검색 데이터 조회 (순수 시장 데이터, LLM 없음)."""

    def __init__(self, market_repository: MarketRepository):
        self.market_repo = market_repository

    async def quote(self, params: MarketQuoteIn) -> MarketDataOut:
        return await self.market_repo.quote(params)

    async def ohlc(self, params: MarketOhlcIn) -> MarketDataOut:
        return await self.market_repo.ohlc(params)

    async def index(self, params: MarketIndexIn) -> MarketDataOut:
        return await self.market_repo.index(params)

    async def fx(self, params: MarketFxIn) -> MarketDataOut:
        return await self.market_repo.fx(params)

    async def search(self, params: MarketSearchIn) -> MarketDataOut:
        # 단계적 검색: 지정 시장 → 0건이면 시장 필터를 ALL 로 완화해 재검색
        relaxed = params.model_copy(update={"market": "ALL"})
        stages = [lambda: self.market_repo.search(params)]
        if relaxed.model_dump() != params.model_dump():
            stages.append(lambda: self.market_repo.search(relaxed))
        return await staged_search(stages)
