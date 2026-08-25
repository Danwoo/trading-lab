"""Alpaca 어댑터 — 미국 일봉·분봉·일괄 시세. 키가 없으면 `available=False` + 사유.

미국 차트가 지금 비어 있는 이유가 여기 한 줄로 모인다: **인증 불요 소스(SEC·OpenFIGI)는
가격을 주지 않고, 가격을 주는 소스(Alpaca)는 키를 요구한다.** 그 사실을 화면이 읽을 수 있게
capability 표로 내보내는 것이 이 어댑터의 현재 일이다.

종목 마스터는 이 소스가 아니라 시장별 정본이 낸다(MD-AD-17 — 시장마다 정본 소스 하나). 그래서
`list_instruments` 는 `available=False` + 사유로 둔다 — 두 소스가 같은 표를 채우면 어느 쪽이
정본인지가 데이터에서 사라진다. **정본이 어디인지는 시장마다 다르다** — 미국이라고 전부 SEC 가
아니라 AMEX 는 토스다(`CANONICAL_MASTER_SOURCE`).
"""

import datetime as dt

import httpx
from core.logger import logger

from providers import register_provider
from providers.alpaca import SOURCE
from providers.alpaca.client import AlpacaClient
from providers.alpaca.mapper import ADJUSTMENT_PARAM, SkippedRow, to_bar, to_quote
from providers.base import (
    CANONICAL_MASTER_SOURCE,
    CREDENTIAL_MISSING_HINT,
    ProviderKeyMissing,
    ProviderResponseInvalid,
    RateLimitExhausted,
    not_canonical_reason,
)
from providers.merge import merge_duplicate_bars
from providers.models import Capability, NormalizedBar, NormalizedInstrument, NormalizedQuote

#: 이 어댑터가 `capabilities()` 에 싣는 시장. 마스터는 시장별 정본이 따로 있어 여기서 내지 않는다.
MARKETS = ("NASDAQ", "NYSE", "AMEX")
_ENV_HINT = "Alpaca API Key ID 와 Secret 을 'KEYID:SECRET' 형식으로"
_NO_KEY_REASON = f"Alpaca API 키가 등록되지 않았습니다 — {CREDENTIAL_MISSING_HINT}"
#: 시장마다 정본이 다르므로 사유도 시장마다 만든다 — 「미국은 SEC」로 뭉뚱그리면 정본이
#: 옮겨간 시장이 빈 자리를 가리킨다(#351).
_MASTER_REASON_BY_MARKET = {
    market: not_canonical_reason(f"{market} 종목 마스터", CANONICAL_MASTER_SOURCE[market]) for market in MARKETS
}
#: 이 어댑터가 싣지 않는 시장을 물었을 때. 정본을 지목하지 않는다 — 모르는 시장의 정본은
#: 지어낼 수 없다.
_NOT_A_MARKET_REASON = f"Alpaca 가 다루는 시장에 없습니다 — 소스가 {'·'.join(MARKETS)} 만 받습니다"
_NO_ORDERBOOK_REASON = "Alpaca 무료 플랜은 심층 호가를 제공하지 않습니다"
_TIMEFRAME_BY_INTERVAL = {1: "1Min", 5: "5Min", 15: "15Min", 30: "30Min", 60: "1Hour"}


class AlpacaProvider:
    def __init__(self, api_key: str | None):
        self.api_key = (api_key or "").strip() or None
        self.last_skipped: list[str] = []

    def capabilities(self) -> list[Capability]:
        available = self.api_key is not None
        caps: list[Capability] = []
        for market in MARKETS:
            caps.append(
                Capability(
                    market=market,
                    data_kind="instrument_master",
                    available=False,
                    reason=_MASTER_REASON_BY_MARKET[market],
                )
            )
            for kind in ("daily_bar", "minute_bar", "quote"):
                caps.append(
                    Capability(
                        market=market,
                        data_kind=kind,
                        available=available,
                        reason=None if available else _NO_KEY_REASON,
                    )
                )
            caps.append(Capability(market=market, data_kind="orderbook", available=False, reason=_NO_ORDERBOOK_REASON))
        return caps

    def _client(self) -> AlpacaClient:
        if self.api_key is None:
            raise ProviderKeyMissing(SOURCE, _ENV_HINT)
        client = AlpacaClient(self.api_key)
        if not client.credentials_well_formed:
            raise ProviderKeyMissing(SOURCE, _ENV_HINT)
        return client

    async def _bars(self, symbol: str, params: dict, cursor: str) -> list[dict]:
        try:
            return await self._client().bars(symbol.upper(), params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RateLimitExhausted(cursor=cursor) from exc
            raise ProviderResponseInvalid(
                f"Alpaca 응답 상태 {exc.response.status_code}", http_status=exc.response.status_code
            ) from exc
        except httpx.DecodingError as exc:
            # 원문(영문)을 사유로 싣지 않는다 — 이 문자열은 화면까지 간다.
            raise ProviderResponseInvalid("Alpaca 응답을 해석하지 못했습니다 (형식이 바뀌었을 수 있습니다)") from exc

    def _normalize(self, items: list[dict], symbol: str, market: str) -> list[NormalizedBar]:
        bars: list[NormalizedBar] = []
        skipped: list[str] = []
        for item in items:
            try:
                bars.append(to_bar(item, symbol, market))
            except SkippedRow as exc:
                skipped.append(exc.reason)
        self.last_skipped = skipped
        if skipped:
            logger.info(f"[{SOURCE}] {symbol} 캔들 {len(skipped)}건 계약 밖 제외")
        return merge_duplicate_bars(bars, source=SOURCE)

    async def list_instruments(self, market: str) -> list[NormalizedInstrument]:
        raise ProviderResponseInvalid(_MASTER_REASON_BY_MARKET.get(market, _NOT_A_MARKET_REASON))

    async def fetch_daily(self, symbol: str, market: str, date_from: dt.date, date_to: dt.date) -> list[NormalizedBar]:
        items = await self._bars(
            symbol,
            {
                "timeframe": "1Day",
                "start": date_from.isoformat(),
                "end": date_to.isoformat(),
                "adjustment": ADJUSTMENT_PARAM,
            },
            cursor=f"daily_bar:{market}:{symbol}:{date_from.isoformat()}",
        )
        return self._normalize(items, symbol, market)

    async def fetch_minute(
        self, symbol: str, market: str, ts_from: dt.datetime, ts_to: dt.datetime, interval_min: int
    ) -> list[NormalizedBar]:
        timeframe = _TIMEFRAME_BY_INTERVAL.get(interval_min)
        if timeframe is None:
            raise ProviderResponseInvalid(f"지원하지 않는 분봉 주기입니다: {interval_min}분")
        items = await self._bars(
            symbol,
            {
                "timeframe": timeframe,
                "start": ts_from.isoformat(),
                "end": ts_to.isoformat(),
                "adjustment": ADJUSTMENT_PARAM,
            },
            cursor=f"minute_bar:{market}:{symbol}:{ts_from.isoformat()}",
        )
        return self._normalize(items, symbol, market)

    async def fetch_quotes(self, symbols: list[tuple[str, str]]) -> list[NormalizedQuote]:
        if not symbols:
            return []
        market_by_symbol = {symbol.upper(): market.upper() for market, symbol in symbols}
        try:
            latest = await self._client().latest_bars(sorted(market_by_symbol))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RateLimitExhausted(cursor="quote:" + ",".join(sorted(market_by_symbol))) from exc
            raise ProviderResponseInvalid(
                f"Alpaca 응답 상태 {exc.response.status_code}", http_status=exc.response.status_code
            ) from exc
        except httpx.DecodingError as exc:
            # 원문(영문)을 사유로 싣지 않는다 — 이 문자열은 화면까지 간다.
            raise ProviderResponseInvalid("Alpaca 응답을 해석하지 못했습니다 (형식이 바뀌었을 수 있습니다)") from exc

        quotes: list[NormalizedQuote] = []
        skipped: list[str] = []
        for symbol, item in latest.items():
            market = market_by_symbol.get(symbol.upper())
            if market is None or not isinstance(item, dict):
                continue
            try:
                quotes.append(to_quote(item, symbol, market))
            except SkippedRow as exc:
                skipped.append(exc.reason)
        self.last_skipped = skipped
        return quotes


register_provider(SOURCE, AlpacaProvider)
