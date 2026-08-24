"""토스증권 어댑터 — 국내(KRX) 일봉·분봉·마스터의 소스.

실호출로 대조했다 (2026-08-19, IP 허용 후): 캔들 `timestamp` 에 `+09:00` 이 붙고 가격·거래량은
문자열이며, `stocks/all` 은 KOSPI 2,476 · KOSDAQ 1,824 행을 `symbol·name·securityType·
isCommonShare·isinCode` 로 준다(market·currency 없음 — 요청 컨텍스트에서 채운다).

시세(quote)는 선언하지 않는다 — `/api/v1/prices` 응답이 `symbol·timestamp·lastPrice·currency`
뿐이라 `NormalizedQuote` 가 요구하는 등락·등락률·거래량을 채울 수 없다(실측 확인). 없는 값을
0 으로 채워 파는 것보다 「못 준다」가 낫다(FR-021).

**국내 마스터의 정본은 토스다** — 제품 정의 §7(리드 확정 2026-08-19) 이 "브로커·시세는 토스증권
Open API 단일" 이라고 못박는다. data_go_kr 은 빈 구간을 채우는 쪽이다(MD-AD-17). 미국 마스터는
NASDAQ·NYSE 를 SEC 가 가져가고 **AMEX 만 이 소스가 정본이다** — 어느 시장이 그런지는 여기가
아니라 `providers/base.py` 의 `CANONICAL_MASTER_SOURCE` 가 정한다.
"""

from __future__ import annotations

import datetime as dt

from core.calendar import get_market_calendar
from core.logger import logger

from providers import register_provider
from providers.base import (
    CANONICAL_MASTER_SOURCE,
    CREDENTIAL_MISSING_HINT,
    ProviderKeyMissing,
    ProviderResponseInvalid,
    not_canonical_reason,
)
from providers.models import Capability, NormalizedBar, NormalizedInstrument, NormalizedQuote
from providers.toss import SOURCE
from providers.toss.client import PAGE_LIMIT, TossClient
from providers.toss.mapper import SkippedRow, to_bar, to_instrument

#: 소스가 **받아 주는** 시장. 실측 2026-08-23: `stocks/all` 이 그 밖의 값을 HTTP 400 으로
#: 거절하며 허용 목록을 직접 말한다 — "유효하지 않은 market 입니다. KOSPI, KOSDAQ, NYSE,
#: NASDAQ, AMEX 만 허용됩니다".
KR_MARKETS = ("KOSPI", "KOSDAQ")
US_MARKETS = ("NASDAQ", "NYSE", "AMEX")

#: 소스가 다루지 않지만 **우리 시장 집합에는 있는** 시장 — 못 한다는 사실을 사유와 함께
#: 표에 실어야 화면이 「없다」와 「이 소스는 안 준다」를 가른다(FR-021). 빼 버리면 KONEX 를
#: 고른 사람은 토스가 왜 안 나오는지 물을 자리가 없다.
UNSERVED_MARKETS = ("KONEX",)

#: 이 어댑터가 `capabilities()` 에 싣는 시장 전부.
MARKETS = KR_MARKETS + US_MARKETS + UNSERVED_MARKETS

# 어댑터는 자격의 **모양**만 말한다 — 변수 이름은 로더(`services/data_key/`)가 안내한다.
# 여기 이름을 적으면 그 값이 가림 등록을 안 거친 채 읽히는 길이 생긴다 (경계 스캐너가 잡는다).
ENV_HINT = (
    "토스증권 앱의 Client ID 와 Client Secret 을 'ID:SECRET' 형식으로 — developers.tossinvest.com 앱 등록에서 발급"
)

#: 페이지네이션 안전 상한. **분봉 소급이 기준이다** — KRX 정규장 390분×245일 ≈ 9.6만 봉이라
#: 1년치가 약 478페이지다. 일봉으로 잡으면(60페이지=48년) 분봉 1년이 상한에 막힌다.
#: 200봉×2000페이지 = 40만 봉 ≈ 분봉 4년치. 커서가 안 도는 경우는 상한이 아니라 아래에서 직접 잡는다.
MAX_PAGES = 2000

# 아래 두 사유는 화면에 그대로 나간다 — `providers/models.py` 의 `Capability.reason` 규칙을 따른다.
# 상류 엔드포인트 이름(`/api/v1/prices`)과 구현 단위 이름은 위 모듈 주석에만 둔다.
_NO_QUOTE_REASON = "토스증권이 주는 현재가에는 등락·등락률·거래량이 없어 시세를 채울 수 없습니다"
_NO_ORDERBOOK_REASON = "토스증권 호가는 아직 받아오지 않습니다 — 소스에는 있지만 연결하지 않았습니다"
_UNSERVED_REASON = "토스증권이 다루는 시장에 없습니다 — 소스가 KOSPI·KOSDAQ·NYSE·NASDAQ·AMEX 만 받습니다"


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
        for market in MARKETS:
            if market in UNSERVED_MARKETS:
                for kind in ("instrument_master", "daily_bar", "minute_bar", "quote", "orderbook"):
                    rows.append(Capability(market=market, data_kind=kind, available=False, reason=_UNSERVED_REASON))
                continue
            canonical = CANONICAL_MASTER_SOURCE[market]
            if canonical == SOURCE:
                # 국내는 토스가 정본이다 — 제품 정의 §7(리드 확정 2026-08-19): "브로커·시세는
                # 토스증권 Open API 단일". data_go_kr 은 빈 구간을 채우는 쪽이다 (MD-AD-17).
                # **AMEX 만 미국에서 예외다** — 정본이던 SEC 가 AMEX 를 식별하지 못한다(그 소스는
                # `Nasdaq`·`NYSE`·`OTC`·`CBOE` 만 내보낸다). 정본이 못 주는 시장까지 양보하면
                # 아무도 안 주는 시장이 「받을 수 있는 것」에 남는다(#351). 어느 시장이 그런지는
                # 여기서 판단하지 않는다 — 정본 표가 정하고 이 줄은 그것을 읽는다.
                master = (key_reason is None, key_reason)
            else:
                master = (False, not_canonical_reason(f"{market} 종목 마스터", canonical))
            for kind, (ok, reason) in {
                "instrument_master": master,
                "daily_bar": (key_reason is None, key_reason),
                "minute_bar": (key_reason is None, key_reason),
                "quote": (False, _NO_QUOTE_REASON),
                "orderbook": (False, _NO_ORDERBOOK_REASON),
            }.items():
                rows.append(Capability(market=market, data_kind=kind, available=ok, reason=reason))
        return rows

    def _require_key(self) -> None:
        if not self.client.credentials_well_formed:
            raise ProviderKeyMissing(SOURCE, ENV_HINT)

    async def list_instruments(self, market: str) -> list[NormalizedInstrument]:
        market = market.upper()
        if market not in KR_MARKETS + US_MARKETS:
            # 소스가 400 으로 거절할 값을 굳이 보내지 않는다 — capability 표가 답할 문제다
            # (sec·data_go_kr 관례). 보내면 「소스가 요청을 거절했습니다」로 기록돼, 우리가
            # 애초에 못 묻는 시장을 소스 장애처럼 읽게 만든다.
            raise ProviderResponseInvalid(f"{SOURCE} 는 {market} 시장을 다루지 않습니다")
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
        raise ProviderResponseInvalid(_NO_QUOTE_REASON)


register_provider(SOURCE, TossProvider)
