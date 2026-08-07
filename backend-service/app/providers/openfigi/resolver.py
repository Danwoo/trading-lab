"""OpenFIGI 식별자 리졸버 — `(market, symbol)` → `{figi, composite_figi, share_class_figi}`.

`MarketDataProvider` 가 아니라 `AliasResolver` 를 구현하는 이유는 `providers/base.py` 의 그
Protocol docstring 에 적었다 — 요약하면 "입력을 받아 매핑을 돌려주는" 모양이라 시장 전체 목록을
내놓는 계약을 만족할 수 없다.

국내 종목도 FIGI 를 갖지만(exchCode `KS`·`KQ`) 국내 종목 마스터 자체가 아직 없어(키 필요)
매핑할 대상이 없다 — 그래도 매핑 표는 지금 채워 둔다. 국내 어댑터가 붙는 순간 이 파일은
바뀌지 않는다.
"""

from core.logger import logger

from providers import register_alias_resolver
from providers.base import ProviderResponseInvalid
from providers.models import Capability
from providers.openfigi import SOURCE
from providers.openfigi.client import OpenFigiClient

# 우리 `market` → OpenFIGI `exchCode`. 미국은 복합(composite) 코드 `US` 하나로 세 시장을 덮는다 —
# 거래소별 코드(`UN`·`UW`·`UA`)로 물으면 상장 이전 종목이 매핑에서 빠진다.
EXCH_CODE_BY_MARKET: dict[str, str] = {
    "NASDAQ": "US",
    "NYSE": "US",
    "AMEX": "US",
    "KOSPI": "KS",
    "KOSDAQ": "KQ",
    "KONEX": "KQ",
}

# OpenFIGI 응답 필드 → `tn_symbol_alias.alias_kind`. 이 표가 alias_kind 문자열의 유일한 정의다.
ALIAS_KIND_BY_FIELD: dict[str, str] = {
    "figi": "figi",
    "compositeFIGI": "composite_figi",
    "shareClassFIGI": "share_class_figi",
}


class OpenFigiAliasResolver:
    def __init__(self, api_key: str | None):
        self.client = OpenFigiClient(api_key)

    def capabilities(self) -> list[Capability]:
        """키 유무와 무관하게 가용하다 — 키는 배치 크기만 키운다(client docstring)."""
        return [
            Capability(market=market, data_kind="instrument_master", available=True) for market in EXCH_CODE_BY_MARKET
        ]

    async def resolve_aliases(self, symbols: list[tuple[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
        wanted: list[tuple[str, str]] = []
        jobs: list[dict[str, str]] = []
        for market, symbol in symbols:
            exch_code = EXCH_CODE_BY_MARKET.get(market.upper())
            if exch_code is None:
                continue
            wanted.append((market.upper(), symbol.upper()))
            jobs.append({"idType": "TICKER", "idValue": symbol.upper(), "exchCode": exch_code})
        if not jobs:
            return {}

        results = await self.client.map_jobs(jobs)
        if len(results) != len(jobs):
            raise ProviderResponseInvalid(f"잡 {len(jobs)}건에 결과 {len(results)}건 — 순서 대응이 깨졌습니다")

        resolved: dict[tuple[str, str], dict[str, str]] = {}
        for key, result in zip(wanted, results, strict=True):
            if not isinstance(result, dict):
                continue
            # 매핑 실패는 `{"warning": ...}` 로 온다 — 예외가 아니라 "이 종목엔 매핑이 없다"다.
            data = result.get("data")
            if not isinstance(data, list) or not data:
                continue
            first = data[0]
            if not isinstance(first, dict):
                continue
            aliases = {
                alias_kind: value
                for field, alias_kind in ALIAS_KIND_BY_FIELD.items()
                if isinstance(value := first.get(field), str) and value
            }
            if aliases:
                resolved[key] = aliases

        logger.info(f"[{SOURCE}] 요청 {len(jobs)}건 중 {len(resolved)}건 매핑")
        return resolved


register_alias_resolver(SOURCE, OpenFigiAliasResolver)
