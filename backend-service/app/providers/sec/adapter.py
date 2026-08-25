"""SEC EDGAR 어댑터 — 미국 종목 마스터만 제공한다.

**SEC 는 시세를 주지 않는다.** 공시·재무 공개기관이라 캔들·호가·현재가가 애초에 없다. 이 사실이
`capabilities()` 에 사유와 함께 그대로 실려 화면까지 간다(FR-021) — 코드 분기가 아니라 데이터로
"미국 일봉이 왜 비어 있는지"가 흐르게 하는 것이 이 표의 존재 이유다.
"""

from datetime import date, datetime

import httpx
from core.logger import logger

from providers import register_provider
from providers.base import ProviderKeyMissing, ProviderResponseInvalid, RateLimitExhausted
from providers.models import Capability, NormalizedBar, NormalizedInstrument, NormalizedQuote
from providers.sec import SOURCE
from providers.sec.client import SecClient, contact_is_usable
from providers.sec.mapper import MARKET_BY_SEC_EXCHANGE, SkippedRow, to_instrument

#: 이 소스가 말하는 시장 — **매핑표에서 뽑는다.** 손으로 적으면 매핑이 못 만드는 시장이 표에
#: 남고, 그 줄이 화면의 「지금 받을 수 있는 것」에 올라 눌러도 영영 0행이 된다(#351: AMEX 가
#: 그랬다 — SEC 는 `NYSE American`·`NYSE MKT`·`NYSE Arca` 를 한 건도 내보내지 않는다).
MARKETS = tuple(sorted(set(MARKET_BY_SEC_EXCHANGE.values())))
_NO_PRICE_REASON = "SEC 는 공시·재무 공개기관으로 가격 데이터를 제공하지 않습니다"
_NO_CONTACT_REASON = (
    "SEC 는 연락처(이메일)가 담긴 User-Agent 를 요구합니다 — MARKET_DATA_CONTACT 에 연락처가 필요합니다 "
    "(API 키가 아니라 우리를 밝히는 문자열입니다)"
)


class SecProvider:
    """`MarketDataProvider` 구현체. 키가 아니라 연락처 문자열을 받는다 (client docstring 참조)."""

    def __init__(self, contact: str | None):
        self.contact = contact
        # 직전 `list_instruments` 에서 버린 행 수·사유. 적재 워커가 `skipped_rows` 로 올린다.
        self.last_skipped: list[str] = []

    def capabilities(self) -> list[Capability]:
        usable = contact_is_usable(self.contact)
        caps: list[Capability] = []
        for market in MARKETS:
            caps.append(
                Capability(
                    market=market,
                    data_kind="instrument_master",
                    available=usable,
                    reason=None if usable else _NO_CONTACT_REASON,
                )
            )
            for kind in ("daily_bar", "minute_bar", "quote", "orderbook"):
                caps.append(Capability(market=market, data_kind=kind, available=False, reason=_NO_PRICE_REASON))
        return caps

    async def list_instruments(self, market: str) -> list[NormalizedInstrument]:
        """전 종목 스냅샷을 한 번 받아 요청한 시장만 걸러 낸다.

        시장별로 따로 호출하지 않는 이유: 소스가 파일 하나로 전 종목을 주므로 시장을 나눠
        호출해도 트래픽만 늘고 얻는 것이 없다(#Dev Notes "국내는 전 종목이 오히려 싸다"와 같은
        성질이다).
        """
        market = market.upper()
        if market not in MARKETS:
            # 이 소스가 다루지 않는 시장 — 빈 목록이 아니라 capability 표가 답할 문제다.
            raise ProviderResponseInvalid(f"{SOURCE} 는 {market} 시장을 다루지 않습니다")

        if not contact_is_usable(self.contact):
            raise ProviderKeyMissing(SOURCE, "MARKET_DATA_CONTACT (연락처 문자열 — 비밀값 아님)")

        try:
            payload = await SecClient(self.contact).company_tickers_exchange()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RateLimitExhausted(cursor=f"instrument_master:{market}") from exc
            raise ProviderResponseInvalid(
                f"SEC 응답 상태 {exc.response.status_code}", http_status=exc.response.status_code
            ) from exc

        if not isinstance(payload, dict):
            raise ProviderResponseInvalid("최상위가 객체가 아닙니다")
        fields, rows = payload.get("fields"), payload.get("data")
        if not isinstance(fields, list) or not isinstance(rows, list):
            raise ProviderResponseInvalid("fields/data 배열이 없습니다")

        instruments: list[NormalizedInstrument] = []
        skipped: list[str] = []
        for row in rows:
            try:
                instrument = to_instrument(row, fields)
            except SkippedRow as exc:
                skipped.append(exc.reason)
                continue
            if instrument.market == market:
                instruments.append(instrument)

        self.last_skipped = skipped
        logger.info(f"[{SOURCE}] {market} 종목 {len(instruments)}건 정규화, 계약 밖 {len(skipped)}건 제외")
        return instruments

    async def fetch_daily(self, symbol: str, market: str, date_from: date, date_to: date) -> list[NormalizedBar]:
        raise ProviderResponseInvalid(_NO_PRICE_REASON)

    async def fetch_minute(
        self, symbol: str, market: str, ts_from: datetime, ts_to: datetime, interval_min: int
    ) -> list[NormalizedBar]:
        raise ProviderResponseInvalid(_NO_PRICE_REASON)

    async def fetch_quotes(self, symbols: list[tuple[str, str]]) -> list[NormalizedQuote]:
        raise ProviderResponseInvalid(_NO_PRICE_REASON)


register_provider(SOURCE, SecProvider)
