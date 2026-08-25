"""샘플 어댑터 — 키 없이 종목 마스터·일봉을 낸다 (#217).

## 왜 있나

일봉을 주는 소스 셋(`alpaca`·`data_go_kr`·`sec`)이 **전부 키를 요구**해서, 키가 없으면
백테스트를 한 번도 못 돌린다 — 엔진·지표·격자·맥락이 다 들어왔는데 아무도 눈으로 본
적이 없는 상태였다. 이 어댑터가 그 첫 완주를 연다.

## 실데이터인 척하지 않는다

값은 **합성**이고 티커도 샘플(`SAMPLE001`…)이다. `capabilities()` 의 사유에 그 사실이
실려 화면까지 간다 — 코드 분기가 아니라 **데이터로** 흐르게 하는 것이 그 표의 존재 이유다
(sec 어댑터와 같은 규율).

## 무엇을 안 주나

호가·현재가는 안 준다. 백테스트는 **일봉만** 있으면 돌고, 없는 것을 있는 척하면
「없는 계산을 한 척하는 값」과 같은 부류가 된다.
"""

from datetime import date, datetime, time
from decimal import Decimal

from providers import register_provider
from providers.base import ProviderResponseInvalid
from providers.models import Capability, NormalizedBar, NormalizedInstrument, NormalizedQuote
from providers.sample import SOURCE
from providers.sample.generator import SAMPLE_INSTRUMENTS, daily_bars

_NO_QUOTE_REASON = "샘플 소스는 현재가·호가를 내지 않습니다 — 백테스트에 필요한 일봉만 제공합니다"
_NO_MINUTE_REASON = "샘플 소스는 분봉을 내지 않습니다 — 일봉만 제공합니다"
_SAMPLE_NOTE = "합성 샘플 데이터입니다 (실제 시세가 아닙니다) — 키 없이 백테스트를 돌려보는 용도"

_CURRENCY = {"KR": "KRW", "US": "USD"}
_COUNTRY = {"KR": "KR", "US": "US"}

#: 이 어댑터가 `capabilities()` 에 싣는 시장 — **값을 가진 시장에서 뽑는다.** 손으로 적으면
#: 종목이 하나도 없는 시장이 표에 남는다(#351 이 그 부류다).
MARKETS = tuple(SAMPLE_INSTRUMENTS)


class SampleProvider:
    """`MarketDataProvider` 구현체. 인증이 없다 — 값을 만들어 내므로 외부 호출도 없다."""

    def __init__(self, *_args, **_kwargs) -> None:
        # 레지스트리가 다른 어댑터와 같은 형태로 부른다(키·연락처를 위치 인자로 넘긴다) —
        # 샘플은 인증이 없으므로 받되 쓰지 않는다. 시그니처를 좁히면 그 자리에서 터진다.
        # 다른 어댑터와 같은 자리를 둔다 (적재 워커가 `skipped_rows` 로 올린다).
        self.last_skipped: list[str] = []

    def capabilities(self) -> list[Capability]:
        out: list[Capability] = []
        for market in MARKETS:
            out.append(Capability(market=market, data_kind="instrument_master", available=True, reason=_SAMPLE_NOTE))
            out.append(Capability(market=market, data_kind="daily_bar", available=True, reason=_SAMPLE_NOTE))
            out.append(Capability(market=market, data_kind="minute_bar", available=False, reason=_NO_MINUTE_REASON))
            out.append(Capability(market=market, data_kind="quote", available=False, reason=_NO_QUOTE_REASON))
        return out

    async def list_instruments(self, market: str) -> list[NormalizedInstrument]:
        self.last_skipped = []
        market = market.upper()
        if market not in SAMPLE_INSTRUMENTS:
            # 이 소스가 다루지 않는 시장 — 빈 목록이 아니라 capability 표가 답할 문제다
            # (sec·data_go_kr 관례). 빈 목록은 「0건 적재 성공」으로 기록돼 이유를 지운다.
            raise ProviderResponseInvalid(f"{SOURCE} 는 {market} 시장을 다루지 않습니다")
        rows = SAMPLE_INSTRUMENTS[market]
        return [
            NormalizedInstrument(
                country=_COUNTRY.get(market.upper(), market.upper()),
                market=market.upper(),
                symbol=symbol,
                issuer_nm=name,
                currency=_CURRENCY.get(market.upper(), "USD"),
                aliases={},
            )
            for symbol, name in rows
        ]

    async def fetch_daily(self, symbol: str, market: str, date_from: date, date_to: date) -> list[NormalizedBar]:
        known = {s for s, _ in SAMPLE_INSTRUMENTS.get(market.upper(), [])}
        if symbol.upper() not in known:
            # 모르는 종목에 값을 지어내지 않는다 — 빈 목록이 「없다」를 정직하게 말한다.
            return []
        return [
            NormalizedBar(
                symbol=symbol.upper(),
                market=market.upper(),
                ts=datetime.combine(row["dt"], time.min),
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=int(row["volume"]),
                adj_policy="raw",  # 샘플은 수정 전 원가 — 배당·분할 이벤트 자체가 없다
            )
            for row in daily_bars(symbol.upper(), date_from, date_to)
        ]

    async def fetch_minute(self, *args, **kwargs) -> list[NormalizedBar]:
        return []

    async def fetch_quotes(self, symbols: list[tuple[str, str]]) -> list[NormalizedQuote]:
        return []


register_provider(SOURCE, SampleProvider)
