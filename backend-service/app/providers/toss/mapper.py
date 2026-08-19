"""토스 응답 → 정규화 모델. 필드명은 openapi.json 사양 그대로 (2026-08-19 확인).

`adjusted=false` 로 받아 `adj_policy="raw"` 를 적는다 — 무수정 원본이 정본(AD-18)이고,
`adjusted=true` 가 분할만 반영하는지 배당락까지 반영하는지 사양에 없어 라벨을 확신할 수 없다.
확신 없는 라벨은 백테스트를 조용히 틀리게 한다.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal, InvalidOperation

from core.calendar import market_local_naive

from providers.models import NormalizedBar, NormalizedInstrument


class SkippedRow(Exception):
    """필드가 모자란 행 — 조용히 0 으로 채우지 않고 행 단위로 건너뛴 사실을 남긴다."""


def to_ts(raw: str, market: str) -> dt.datetime:
    """소스 시각 → **시장 현지 벽시계 naive** (2026-07-30 결정, `core/calendar.market_local_naive`).

    토스는 offset 을 붙여 준다(`2026-03-25T09:00:00+09:00`). 그대로 두면 aware 값이
    `timestamp without time zone` 컬럼에 들어가고, 구간 비교도 aware/naive 가 섞인다.
    offset 이 없는 응답도 같은 함수가 UTC 로 읽어 시장 tz 로 옮기므로 한 갈래로 끝난다.
    """
    return market_local_naive(market, dt.datetime.fromisoformat(raw))


def to_bar(row: dict, symbol: str, market: str) -> NormalizedBar:
    try:
        return NormalizedBar(
            symbol=symbol,
            market=market,
            ts=to_ts(row["timestamp"], market),
            open=Decimal(str(row["openPrice"])),
            high=Decimal(str(row["highPrice"])),
            low=Decimal(str(row["lowPrice"])),
            close=Decimal(str(row["closePrice"])),
            volume=int(row["volume"]),
            adj_policy="raw",
        )
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        # `Decimal("None")`·`Decimal("1,234")` 는 InvalidOperation 이다 — ValueError 가 아니다.
        # 이것을 안 잡으면 이상 행 하나가 그 종목의 적재를 통째로 죽인다 (alpaca·data_go_kr 관례).
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
    except (KeyError, TypeError, ValueError) as exc:
        raise SkippedRow(f"마스터 행 필드 결손: {type(exc).__name__}") from exc
