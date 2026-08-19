"""토스증권 어댑터 — 국내(KRX) 일봉·분봉·마스터의 소스 (운영 규약 0.0.3).

**실호출 미검증** — 자격증명 한쪽이 아직 없다. 사양(openapi.json) 기준 구현이며 실측 대조는
자격 완성 뒤의 일이다. `capabilities()` 가 그 상태를 credential_missing 으로 정직하게 낸다.

시세(quote)는 선언하지 않는다 — `/api/v1/prices` 응답이 `symbol·timestamp·lastPrice·currency`
뿐이라(사양) `NormalizedQuote` 가 요구하는 등락·등락률·거래량을 채울 수 없다. 없는 값을 0 으로
채워 파는 것보다 「못 준다」가 낫다(FR-021).

국내 종목 마스터를 available 로 선언한다 — MD-AD-17(시장마다 정본 하나)의 현 정본은
data_go_kr 이지만 그 키가 없는 설치에서 토스 키만으로 마스터를 채울 수 있어야 한다.
두 소스가 함께 키를 갖는 설치에서의 정본 판정은 결정 대기(Cycle 0 결정 묶음).
"""

from __future__ import annotations

import datetime as dt

from core.logger import logger

from providers import register_provider
from providers.base import CREDENTIAL_MISSING_HINT, ProviderKeyMissing, ProviderResponseInvalid
from providers.models import Capability, NormalizedBar, NormalizedInstrument, NormalizedQuote
from providers.toss import SOURCE
from providers.toss.client import PAGE_LIMIT, TossClient
from providers.toss.mapper import SkippedRow, to_bar, to_instrument

KR_MARKETS = ("KOSPI", "KOSDAQ", "KONEX")
US_MARKETS = ("NASDAQ", "NYSE", "AMEX")

ENV_HINT = "TOSS_CLIENT_ID 와 TOSS_CLIENT_SECRET 두 값 — developers.tossinvest.com 앱 등록에서 발급"

#: 페이지네이션 안전 상한 — 200봉×60페이지 = 12,000봉(일봉 약 48년). 이보다 길면 잘못된 루프다.
MAX_PAGES = 60

KST = dt.timezone(dt.timedelta(hours=9))


class TossProvider:
    def __init__(self, api_key: str | None = None, *_args, **_kwargs):
        self.client = TossClient(api_key or "")

    def _key_reason(self) -> str | None:
        if self.client.credentials_well_formed:
            return None
        return f"토스증권 자격증명이 완성되지 않았습니다 — {CREDENTIAL_MISSING_HINT} ({ENV_HINT})"

    def capabilities(self) -> list[Capability]:
        key_reason = self._key_reason()
        rows: list[Capability] = []
        for market in KR_MARKETS + US_MARKETS:
            is_kr = market in KR_MARKETS
            if is_kr:
                master = (key_reason is None, key_reason)
            else:
                master = (False, "미국 종목 마스터의 정본 소스는 SEC 입니다 (MD-AD-17 — 시장마다 정본 소스 하나)")
            for kind, (ok, reason) in {
                "instrument_master": master,
                "daily_bar": (key_reason is None, key_reason),
                "minute_bar": (key_reason is None, key_reason),
                "quote": (False, "prices 응답에 등락·등락률·거래량이 없어(사양) 시세 계약을 채울 수 없습니다"),
                "orderbook": (False, "호가 어댑터를 아직 붙이지 않았습니다"),
            }.items():
                rows.append(Capability(market=market, data_kind=kind, available=ok, reason=reason))
        return rows

    def _require_key(self) -> None:
        if not self.client.credentials_well_formed:
            raise ProviderKeyMissing(SOURCE, ENV_HINT)

    async def list_instruments(self, market: str) -> list[NormalizedInstrument]:
        self._require_key()
        rows = await self.client.stocks_all(market)
        out: list[NormalizedInstrument] = []
        skipped = 0
        for row in rows:
            try:
                out.append(to_instrument(row, market))
            except SkippedRow:
                skipped += 1
        if skipped:
            logger.warning(f"toss 마스터 행 건너뜀 — market={market} skipped={skipped}/{len(rows)}")
        return out

    async def _paged_bars(
        self, symbol: str, market: str, interval: str, *, keep_from: dt.datetime, keep_to: dt.datetime
    ) -> list[NormalizedBar]:
        """`before` 커서로 최신→과거로 걷어, 구간 밖으로 나가면 멈춘다."""
        bars: list[NormalizedBar] = []
        before = keep_to.isoformat()
        skipped = 0
        for _ in range(MAX_PAGES):
            result = await self.client.candles(symbol, interval, count=PAGE_LIMIT, before=before)
            rows = result.get("candles") or []
            if not rows:
                break
            oldest: dt.datetime | None = None
            for row in rows:
                try:
                    bar = to_bar(row, symbol, market)
                except SkippedRow:
                    skipped += 1
                    continue
                oldest = bar.ts if oldest is None or bar.ts < oldest else oldest
                if keep_from <= bar.ts <= keep_to:
                    bars.append(bar)
            next_before = result.get("nextBefore")
            if not next_before or (oldest is not None and oldest < keep_from):
                break
            before = next_before
        else:
            raise ProviderResponseInvalid(f"페이지가 {MAX_PAGES}를 넘었습니다 — 커서가 전진하지 않는 것으로 보입니다")
        if skipped:
            logger.warning(f"toss 캔들 행 건너뜀 — symbol={symbol} skipped={skipped}")
        bars.sort(key=lambda b: b.ts)
        return bars

    async def fetch_daily(self, symbol: str, market: str, date_from: dt.date, date_to: dt.date) -> list[NormalizedBar]:
        self._require_key()
        tz = KST if market in KR_MARKETS else dt.UTC
        keep_from = dt.datetime.combine(date_from, dt.time.min, tz)
        keep_to = dt.datetime.combine(date_to, dt.time.max, tz)
        return await self._paged_bars(symbol, market, "1d", keep_from=keep_from, keep_to=keep_to)

    async def fetch_minute(
        self, symbol: str, market: str, ts_from: dt.datetime, ts_to: dt.datetime, interval_min: int
    ) -> list[NormalizedBar]:
        # 소스 세분화는 1분뿐이다(사양 enum "1m"/"1d") — 저장은 언제나 1분(AD-26), 합성은 서비스 몫.
        self._require_key()
        return await self._paged_bars(symbol, market, "1m", keep_from=ts_from, keep_to=ts_to)

    async def fetch_quotes(self, symbols: list[tuple[str, str]]) -> list[NormalizedQuote]:
        raise ProviderResponseInvalid("toss 는 시세 계약을 채울 수 없습니다 — capabilities 의 quote 사유 참조")


register_provider(SOURCE, TossProvider)
