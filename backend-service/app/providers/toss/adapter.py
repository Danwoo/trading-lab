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

from core.calendar import get_market_calendar
from core.logger import logger

from providers import register_provider
from providers.base import (
    CREDENTIAL_MISSING_HINT,
    ProviderKeyMissing,
    ProviderResponseInvalid,
    not_canonical_reason,
)
from providers.models import Capability, NormalizedBar, NormalizedInstrument, NormalizedQuote
from providers.toss import SOURCE
from providers.toss.client import PAGE_LIMIT, TossClient
from providers.toss.mapper import SkippedRow, to_bar, to_instrument

KR_MARKETS = ("KOSPI", "KOSDAQ", "KONEX")
US_MARKETS = ("NASDAQ", "NYSE", "AMEX")

# 어댑터는 자격의 **모양**만 말한다 — 변수 이름은 로더(`services/data_key/`)가 안내한다.
# 여기 이름을 적으면 그 값이 가림 등록을 안 거친 채 읽히는 길이 생긴다 (경계 스캐너가 잡는다).
ENV_HINT = (
    "토스증권 앱의 Client ID 와 Client Secret 을 'ID:SECRET' 형식으로 — developers.tossinvest.com 앱 등록에서 발급"
)

#: 페이지네이션 안전 상한. **분봉 소급이 기준이다** — KRX 정규장 390분×245일 ≈ 9.6만 봉이라
#: 1년치가 약 478페이지다. 일봉으로 잡으면(60페이지=48년) 분봉 1년이 상한에 막힌다.
#: 200봉×2000페이지 = 40만 봉 ≈ 분봉 4년치. 커서가 안 도는 경우는 상한이 아니라 아래에서 직접 잡는다.
MAX_PAGES = 2000


def _market_tz(market: str) -> dt.tzinfo:
    """소스에 보낼 **커서**용 tz. 저장 시각은 매퍼가 `market_local_naive` 로 고정한다."""
    return get_market_calendar(market).tz


class TossProvider:
    def __init__(self, api_key: str | None = None, *_args, **_kwargs):
        self.api_key = (api_key or "").strip() or None
        self.client = TossClient(api_key or "")
        #: 마지막 호출에서 건너뛴 행 — 적재 실행 기록의 `skipped_rows` 가 여기서 온다.
        #: 없으면 「버렸는데 0건으로 기록」이 된다 (alpaca 관례).
        self.last_skipped: list[str] = []

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
                master = (False, not_canonical_reason("국내 종목 마스터", "data_go_kr"))
            else:
                master = (False, not_canonical_reason("미국 종목 마스터", "SEC"))
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
        skipped: list[str] = []
        for row in rows:
            try:
                out.append(to_instrument(row, market))
            except SkippedRow as exc:
                skipped.append(str(exc))
        self.last_skipped = skipped
        if skipped:
            logger.warning(f"toss 마스터 행 건너뜀 — market={market} skipped={len(skipped)}/{len(rows)}")
        return out

    async def _paged_bars(
        self, symbol: str, market: str, interval: str, *, keep_from: dt.datetime, keep_to: dt.datetime
    ) -> list[NormalizedBar]:
        """`before` 커서로 최신→과거로 걷어, 구간 밖으로 나가면 멈춘다."""
        bars: list[NormalizedBar] = []
        # 커서는 소스 쪽 시각이라 offset 을 붙여 보낸다 (경계는 naive, 커서는 aware).
        before = keep_to.replace(tzinfo=_market_tz(market)).isoformat()
        skipped: list[str] = []
        for _ in range(MAX_PAGES):
            result = await self.client.candles(symbol, interval, count=PAGE_LIMIT, before=before)
            rows = result.get("candles") or []
            if not rows:
                break
            oldest: dt.datetime | None = None
            for row in rows:
                try:
                    bar = to_bar(row, symbol, market)
                except SkippedRow as exc:
                    skipped.append(str(exc))
                    continue
                oldest = bar.ts if oldest is None or bar.ts < oldest else oldest
                if keep_from <= bar.ts <= keep_to:
                    bars.append(bar)
            next_before = result.get("nextBefore")
            if not next_before or (oldest is not None and oldest < keep_from):
                break
            if next_before == before:
                # 상한과 구분해서 잡는다 — 둘을 뭉치면 「구간이 길다」를 「소스가 고장」으로 오진한다.
                raise ProviderResponseInvalid(
                    f"커서가 전진하지 않습니다 — nextBefore 가 그대로입니다 (symbol={symbol})"
                )
            before = next_before
        else:
            raise ProviderResponseInvalid(
                f"페이지 상한 {MAX_PAGES}에 닿았습니다 — 구간을 나눠 요청하세요 (symbol={symbol} interval={interval})"
            )
        self.last_skipped = skipped
        if skipped:
            logger.warning(f"toss 캔들 행 건너뜀 — symbol={symbol} skipped={len(skipped)}")
        bars.sort(key=lambda b: b.ts)
        return bars

    async def fetch_daily(self, symbol: str, market: str, date_from: dt.date, date_to: dt.date) -> list[NormalizedBar]:
        self._require_key()
        # 매퍼가 시장 벽시계 naive 를 돌려주므로 경계도 naive 다 — 섞으면 비교가 TypeError 다.
        # (분봉 경로의 `ts_from`/`ts_to` 도 적재 서비스가 naive 로 만들어 넘긴다)
        keep_from = dt.datetime.combine(date_from, dt.time.min)
        keep_to = dt.datetime.combine(date_to, dt.time.max)
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
