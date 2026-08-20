"""data.go.kr 금융위 어댑터 — 국내 종목 마스터·일봉. 키가 없으면 `available=False` + 사유.

키 없이도 **인스턴스는 만들어진다**(FR-013). 기동을 막지 않고 capability 표가 사유를 들고
화면까지 가는 것이 이 소스의 현재 상태다 — 「국내는 키 대기」가 코드 분기가 아니라 데이터다.
"""

import datetime as dt

import httpx
from core.logger import logger

from providers import register_provider
from providers.base import (
    CREDENTIAL_MISSING_HINT,
    ProviderKeyMissing,
    ProviderResponseInvalid,
    RateLimitExhausted,
)
from providers.data_go_kr import SOURCE
from providers.data_go_kr.client import DataGoKrClient
from providers.data_go_kr.mapper import SkippedRow, to_bar, to_instrument
from providers.merge import merge_duplicate_bars
from providers.models import Capability, NormalizedBar, NormalizedInstrument, NormalizedQuote

_MARKETS = ("KOSPI", "KOSDAQ", "KONEX")
_ENV_HINT = "data.go.kr 일반 인증키(Encoding)"
_NO_KEY_REASON = f"data.go.kr 인증키가 등록되지 않았습니다 — {CREDENTIAL_MISSING_HINT}"
_NO_MINUTE_REASON = "금융위 주식시세정보는 일봉까지만 제공합니다 — 분봉은 증권사 API 축입니다"
_NO_QUOTE_REASON = "금융위 주식시세정보는 장 마감 후 확정치라 실시간 시세·호가를 제공하지 않습니다"


class DataGoKrProvider:
    def __init__(self, api_key: str | None):
        self.api_key = (api_key or "").strip() or None
        self.last_skipped: list[str] = []

    def capabilities(self) -> list[Capability]:
        caps: list[Capability] = []
        for market in _MARKETS:
            for kind in ("instrument_master", "daily_bar"):
                caps.append(
                    Capability(
                        market=market,
                        data_kind=kind,
                        available=self.api_key is not None,
                        reason=None if self.api_key else _NO_KEY_REASON,
                    )
                )
            caps.append(Capability(market=market, data_kind="minute_bar", available=False, reason=_NO_MINUTE_REASON))
            for kind in ("quote", "orderbook"):
                caps.append(Capability(market=market, data_kind=kind, available=False, reason=_NO_QUOTE_REASON))
        return caps

    def _client(self) -> DataGoKrClient:
        if self.api_key is None:
            raise ProviderKeyMissing(SOURCE, _ENV_HINT)
        return DataGoKrClient(self.api_key)

    async def _pages(self, params: dict, cursor: str) -> list[dict]:
        try:
            return await self._client().stock_price_pages(params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RateLimitExhausted(cursor=cursor) from exc
            raise ProviderResponseInvalid(
                f"금융위 응답 상태 {exc.response.status_code}", http_status=exc.response.status_code
            ) from exc
        except httpx.DecodingError as exc:
            # 원문(영문)을 사유로 싣지 않는다 — 이 문자열은 화면까지 간다.
            raise ProviderResponseInvalid("금융위 응답을 해석하지 못했습니다 (형식이 바뀌었을 수 있습니다)") from exc

    async def list_instruments(self, market: str) -> list[NormalizedInstrument]:
        """최신 거래일 스냅샷 한 장에서 종목 마스터를 뽑는다 — 국내는 날짜별 전종목이라
        종목 수가 늘어도 호출 수가 늘지 않는다."""
        market = market.upper()
        if market not in _MARKETS:
            raise ProviderResponseInvalid(f"{SOURCE} 는 {market} 시장을 다루지 않습니다")

        items = await self._pages({"mrktCls": market}, cursor=f"instrument_master:{market}")
        instruments: list[NormalizedInstrument] = []
        skipped: list[str] = []
        seen: set[str] = set()
        for item in items:
            try:
                instrument = to_instrument(item)
            except SkippedRow as exc:
                skipped.append(exc.reason)
                continue
            if instrument.market != market or instrument.symbol in seen:
                continue
            seen.add(instrument.symbol)
            instruments.append(instrument)

        self.last_skipped = skipped
        logger.info(f"[{SOURCE}] {market} 종목 {len(instruments)}건, 계약 밖 {len(skipped)}건 제외")
        return instruments

    async def fetch_daily(self, symbol: str, market: str, date_from: dt.date, date_to: dt.date) -> list[NormalizedBar]:
        cursor = f"daily_bar:{market}:{symbol}:{date_from.isoformat()}"
        items = await self._pages(
            {
                "likeSrtnCd": symbol,
                "beginBasDt": date_from.strftime("%Y%m%d"),
                "endBasDt": date_to.strftime("%Y%m%d"),
            },
            cursor=cursor,
        )
        bars: list[NormalizedBar] = []
        skipped: list[str] = []
        for item in items:
            try:
                bar = to_bar(item)
            except SkippedRow as exc:
                skipped.append(exc.reason)
                continue
            # `likeSrtnCd` 는 접두 일치라 다른 종목이 섞여 온다 — 정확 일치만 남긴다.
            if bar.symbol == symbol.zfill(6):
                bars.append(bar)

        self.last_skipped = skipped
        return merge_duplicate_bars(bars, source=SOURCE)

    async def fetch_minute(
        self, symbol: str, market: str, ts_from: dt.datetime, ts_to: dt.datetime, interval_min: int
    ) -> list[NormalizedBar]:
        raise ProviderResponseInvalid(_NO_MINUTE_REASON)

    async def fetch_quotes(self, symbols: list[tuple[str, str]]) -> list[NormalizedQuote]:
        raise ProviderResponseInvalid(_NO_QUOTE_REASON)


register_provider(SOURCE, DataGoKrProvider)
