"""정규화 모델 — 소스별 표기가 이 경계를 넘으면 공통 표현으로 바뀐다.

어댑터(`providers/<소스>/`)는 이 모델로만 밖에 응답한다. 소비자(적재 워커·서비스)는 이 모델만
알고 소스를 모른다 (시세-데이터-파이프라인.md §2). 서드파티 응답은 무조건 untrusted 이므로,
어댑터가 raw 응답을 이 모델로 변환하는 지점이 경계 검증이다 — pydantic 파싱 실패는 그 자체가
검증 실패 신호다.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# tn_daily_bar/tn_minute_bar.adj_policy 에 적을 수 있는 닫힌 집합(AD-18). DB 쪽은 varchar(20)
# NOT NULL 일 뿐 값 집합을 강제하는 CHECK 가 없으므로, 이 Literal 이 유일한 강제 지점이다 —
# 어댑터 경계에서 막지 않으면 계약 밖 값이 그대로 적재된다.
AdjPolicy = Literal["raw", "adj_split", "adj_split_div"]

# Capability.data_kind 의 닫힌 집합 — 오더 T3 Interfaces 에 명시된 다섯 가지.
DataKind = Literal["instrument_master", "daily_bar", "minute_bar", "quote", "orderbook"]


class NormalizedInstrument(BaseModel):
    """종목 마스터 정규화 모델. `aliases` 는 소스가 제공하는 식별자(단축코드·ISIN 등)를
    `{alias_kind: alias_value}` 로 담는다 — `tn_symbol_alias` 적재의 입력이 된다."""

    country: str
    market: str
    symbol: str
    issuer_nm: str
    currency: str
    sector_code: str | None = None
    aliases: dict[str, str] = Field(default_factory=dict)


class NormalizedBar(BaseModel):
    """일봉·분봉 공용 캔들 정규화 모델. `adj_policy` 는 무수정 원본이 정본이라는 원칙(AD-18)에
    따라 어댑터가 판정해 채운다 — 확인 없이 `raw` 로 박으면 백테스트가 조용히 틀어진다(오더 T5 위험)."""

    symbol: str
    market: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    trade_value: Decimal | None = None
    adj_policy: AdjPolicy


class NormalizedQuote(BaseModel):
    """실시간·일괄 시세 정규화 모델 (갈래 2·3, AD-19)."""

    symbol: str
    market: str
    price: Decimal
    change: Decimal
    change_rate: Decimal
    volume: int
    asof: datetime


class Capability(BaseModel):
    """ "이 소스가 이 시장에 무엇을 줄 수 있나"를 데이터로 노출한다 — 패널의 "해당 시장은 제공되지
    않음"(FR-021)이 화면 하드코딩이 아니라 이 조회 결과가 되게 한다. `available=False` 일 때는
    `reason` 을 채워 화면이 사유를 그대로 보여줄 수 있게 한다(예: "키 없음", "이 소스는 분봉 미제공")."""

    market: str
    data_kind: DataKind
    available: bool
    reason: str | None = None
