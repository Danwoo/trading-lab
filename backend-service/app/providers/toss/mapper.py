"""토스 응답 → 정규화 모델. 필드명은 openapi.json 사양 그대로 (2026-08-19 확인).

`adjusted=false` 로 받아 `adj_policy="raw"` 를 적는다 — 무수정 원본이 정본(AD-18)이고,
`adjusted=true` 가 분할만 반영하는지 배당락까지 반영하는지 사양에 없어 라벨을 확신할 수 없다.
확신 없는 라벨은 백테스트를 조용히 틀리게 한다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from providers.models import NormalizedBar, NormalizedInstrument


class SkippedRow(Exception):
    """필드가 모자란 행 — 조용히 0 으로 채우지 않고 행 단위로 건너뛴 사실을 남긴다."""


def to_bar(row: dict, symbol: str, market: str) -> NormalizedBar:
    try:
        return NormalizedBar(
            symbol=symbol,
            market=market,
            ts=dt.datetime.fromisoformat(row["timestamp"]),
            open=Decimal(str(row["openPrice"])),
            high=Decimal(str(row["highPrice"])),
            low=Decimal(str(row["lowPrice"])),
            close=Decimal(str(row["closePrice"])),
            volume=int(row["volume"]),
            adj_policy="raw",
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SkippedRow(f"캔들 행 필드 결손: {type(exc).__name__}") from exc


def to_instrument(row: dict, market: str) -> NormalizedInstrument:
    """stocks/all 행 → 마스터. 응답에 market·currency 가 없어(사양) 요청 컨텍스트에서 채운다."""
    try:
        aliases = {"isin": row["isinCode"]} if row.get("isinCode") else {}
        return NormalizedInstrument(
            country="KR" if market in ("KOSPI", "KOSDAQ", "KONEX") else "US",
            market=market,
            symbol=str(row["symbol"]),
            issuer_nm=str(row["name"]),
            currency="KRW" if market in ("KOSPI", "KOSDAQ", "KONEX") else "USD",
            aliases=aliases,
        )
    except (KeyError, TypeError) as exc:
        raise SkippedRow(f"마스터 행 필드 결손: {type(exc).__name__}") from exc
