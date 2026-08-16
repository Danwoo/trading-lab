"""캔들 조회 스키마 (갈래 1 — 적재본 읽기).

`BarsOut` 이 `source`·`adj_policy`·`asof` 를 함께 싣는 이유는 FR-019 다 — 화면이 "이 값이 어디서
왔고 언제 기준인지"를 표시할 수 있어야 임시 데이터와 실데이터가 눈으로 구분된다.

`unavailable_reason` 은 **빈 배열과 짝을 이루는 필드**다. 종목마다 시장이 다르게 열리고 소스마다
가진 것이 다르므로, 0건이 "그 기간에 거래가 없었다"인지 "이 시장은 아직 채워지지 않았다"인지
응답 자체가 말해야 한다(FR-021). 값이 있는 응답에서는 언제나 `null` 이다.
"""

from pydantic import BaseModel


class BarOut(BaseModel):
    # 차트 시간축은 시장 시각 고정이다 (2026-07-30 결정) — 문자열로 내보내 프론트의 사용자
    # 타임존 포매터가 이 값을 건드리지 못하게 한다. 일봉은 `YYYY-MM-DD`, 분봉은 `YYYY-MM-DDTHH:MM`.
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    trade_value: float | None = None


class BarsOut(BaseModel):
    items: list[BarOut]
    total_count: int
    market: str
    symbol: str
    interval: str
    source: str | None = None
    adj_policy: str | None = None
    asof: str | None = None
    unavailable_reason: str | None = None
    # 사유의 **기계가 읽는 갈래**. `credential_missing` 은 「키가 아직 없다」 하나뿐일 때만 온다 —
    # 화면은 이때만 임시 데이터로 골조를 보여준다(결정 로그 2026-07-28). 다른 사유가 섞이면
    # `null` 이고, 화면은 이유를 그대로 보여준다(진짜 결손을 덮지 않는다).
    unavailable_code: str | None = None


class GapsOut(BaseModel):
    """캘린더상 거래일인데 적재본에 없는 날짜 (MD-AD-23). 저장하지 않고 조회 시 계산한다."""

    items: list[str]
    total_count: int
    market: str
    symbol: str
    date_from: str
    date_to: str
