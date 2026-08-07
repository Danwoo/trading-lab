from clients.market.market_client import MarketClient
from core.exceptions import BadRequestError
from schemas.market.market_schema import (
    MarketDataOut,
    MarketFxIn,
    MarketIndexIn,
    MarketOhlcIn,
    MarketQuoteIn,
    MarketSearchIn,
)


class MarketRepository:
    def __init__(self, market_client: MarketClient):
        self.client = market_client

    @staticmethod
    def _parse(raw: dict) -> tuple[list[dict], int]:
        # 벤더 레벨 오류(잘못된 파라미터·키 미등록 등)를 빈 결과로 위장하지 않고 즉시 노출
        if isinstance(raw, dict) and raw.get("error"):
            raise BadRequestError(f"시세 API 오류: {raw.get('error')}")
        items = (raw or {}).get("items", []) or []
        if isinstance(items, dict):
            items = [items]
        try:
            total = int((raw or {}).get("total", len(items)) or 0)
        except (TypeError, ValueError):
            total = len(items)
        return [i for i in items if i], total

    async def quote(self, params: MarketQuoteIn) -> MarketDataOut:
        raw = await self.client.quote(symbol=params.symbol)
        data, total = self._parse(raw)
        return MarketDataOut(data=data, total_count=total)

    async def ohlc(self, params: MarketOhlcIn) -> MarketDataOut:
        raw = await self.client.ohlc(symbol=params.symbol, interval=params.interval, count=params.count)
        data, total = self._parse(raw)
        return MarketDataOut(data=data, total_count=total)

    async def index(self, params: MarketIndexIn) -> MarketDataOut:
        raw = await self.client.index(index_code=params.index_code)
        data, total = self._parse(raw)
        return MarketDataOut(data=data, total_count=total)

    async def fx(self, params: MarketFxIn) -> MarketDataOut:
        raw = await self.client.fx(pair=params.pair)
        data, total = self._parse(raw)
        return MarketDataOut(data=data, total_count=total)

    async def search(self, params: MarketSearchIn) -> MarketDataOut:
        raw = await self.client.search(keyword=params.keyword, market=params.market, count=params.count)
        data, total = self._parse(raw)
        return MarketDataOut(data=data, total_count=total)
