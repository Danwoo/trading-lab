"""일괄 시세 조회 (갈래 3 — 필요할 때 REST). **구독 API 를 갖지 않는다** (MD-AD-19).

이 클래스에 `subscribe`·`on_tick` 류 메서드가 없는 것이 계약이다. 사이드바 패널 N개가 같은
종목을 동시에 열어도 외부 호출은 TTL 안에서 한 번이다 — NFR-009(종목 전환 시 응답성)와
NFR-007(한도 초과 금지)이 이 캐시 하나에서 갈린다.

`market` 별로 어느 소스에 물어볼지는 아래 표가 정한다. 소스 이름 문자열이 서비스에 나오지만
이것은 **레지스트리 조회 키**이지 `providers.<소스>` import 가 아니다 — 어댑터 코드에 대한
의존이 아니므로 경계는 유지된다(구현설계 §5.2 #1 의 대상은 import 다).
"""

import time

from core.logger import logger
from providers import get_provider
from providers.base import ProviderKeyMissing, ProviderResponseInvalid, RateLimitExhausted
from services.data_key.data_key_service import DataKeyService

# 시장별 시세 소스 — MD-AD-17("시장마다 정본 소스 하나")을 조회 축에도 그대로 적용한다.
QUOTE_SOURCE_BY_MARKET: dict[str, str] = {
    "NASDAQ": "alpaca",
    "NYSE": "alpaca",
    "AMEX": "alpaca",
    "KOSPI": "data_go_kr",
    "KOSDAQ": "data_go_kr",
    "KONEX": "data_go_kr",
}

# 캐시 수명(초). 사이드바가 여러 패널에서 같은 종목을 겹쳐 여는 창을 덮을 만큼만 짧게 둔다.
CACHE_TTL_SECONDS = 5.0


class QuoteBatchService:
    def __init__(self, data_key_service: DataKeyService):
        self.data_key_service = data_key_service
        self._cache: dict[tuple[str, str], tuple[float, dict]] = {}
        # 외부 호출 횟수 — TTL 이 실제로 호출을 줄이는지 증명하는 계수기다.
        self.upstream_calls = 0

    async def quotes(self, workspace_id: int | None, symbols: list[tuple[str, str]]) -> dict:
        """일괄 조회 + TTL 캐시. `async` 인 이유는 외부 네트워크 I/O 라서다 — DB 메서드를 sync 로
        두는 룰 12 는 DB I/O 에 대한 것이고, 이 서비스는 DB 를 만지지 않는다."""
        now = time.monotonic()
        wanted = [(market.upper(), symbol.upper()) for market, symbol in symbols]

        items: list[dict] = []
        unavailable: dict[str, str] = {}
        misses: dict[str, list[str]] = {}

        for key in wanted:
            cached = self._cache.get(key)
            if cached and now - cached[0] < CACHE_TTL_SECONDS:
                items.append(cached[1])
                continue
            misses.setdefault(key[0], []).append(key[1])

        sources: set[str] = set()
        for market, market_symbols in misses.items():
            source = QUOTE_SOURCE_BY_MARKET.get(market)
            if source is None:
                for symbol in market_symbols:
                    unavailable[f"{market}:{symbol}"] = f"{market} 시장의 시세 소스가 정해지지 않았습니다"
                continue
            sources.add(source)
            api_key = self.data_key_service.get_key(workspace_id, source)
            provider = get_provider(source, api_key)
            try:
                self.upstream_calls += 1
                quotes = await provider.fetch_quotes([(market, symbol) for symbol in market_symbols])
            except (ProviderKeyMissing, ProviderResponseInvalid, RateLimitExhausted) as exc:
                reason = str(exc)
                if isinstance(exc, ProviderKeyMissing):
                    reason = f"{reason} ({self.data_key_service.unavailable_reason(source)})"
                for symbol in market_symbols:
                    unavailable[f"{market}:{symbol}"] = reason
                logger.info(f"일괄 시세 조회 불가 — {market} {len(market_symbols)}종목: {reason}")
                continue

            returned = set()
            for quote in quotes:
                row = {
                    "market": quote.market,
                    "symbol": quote.symbol,
                    "price": float(quote.price),
                    "change": float(quote.change),
                    "change_rate": float(quote.change_rate),
                    "volume": int(quote.volume),
                    "asof": quote.asof.isoformat(timespec="seconds"),
                }
                self._cache[(quote.market, quote.symbol)] = (now, row)
                items.append(row)
                returned.add(quote.symbol)
            for symbol in market_symbols:
                if symbol not in returned:
                    unavailable[f"{market}:{symbol}"] = "소스가 이 종목의 시세를 반환하지 않았습니다"

        return {
            "items": items,
            "total_count": len(items),
            "source": ",".join(sorted(sources)) or None,
            "unavailable": unavailable,
        }
