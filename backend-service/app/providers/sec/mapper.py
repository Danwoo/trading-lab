"""SEC 응답 → 정규화 모델. 소스 표기가 도메인 표기로 바뀌는 유일한 지점.

서드파티 응답은 무조건 untrusted 다(구현설계 §5.2 #3) — 행 단위로 검증하고, 계약 밖 행은
조용히 통과시키지 않고 사유와 함께 버린다. 버린 건수는 호출부가 `tn_ingest_run.skipped_rows`
로 올린다.
"""

from pydantic import ValidationError

from providers.models import NormalizedInstrument

# SEC 의 `exchange` 표기 → 우리 `market` 표기. 우리 시장 집합(구현설계 §1.1)에 없는 표기는
# 매핑하지 않는다 — `OTC`·`CBOE`·null 이 그것이다. 억지로 어디에 붙이면 시장 단위 판정(휴장·
# 정규장 시간·패널 가용성)이 통째로 틀어지므로, 매핑 없음은 "버린 행"으로 셈한다.
#
# **키는 소스가 실제로 내보내는 표기만 적는다.** 소스에 없는 표기를 적으면 그 값(value)이
# 「우리가 SEC 로 채울 수 있는 시장」인 척하게 되고, 어댑터가 그 시장을 `capabilities()` 에
# 실어 화면까지 보낸다 — 눌러도 영영 0행인 시장이 그렇게 생겼다(#351). 소스 어휘 대조는
# `scripts/verify_capability_market_reachability.py` 가 잡는다.
MARKET_BY_SEC_EXCHANGE: dict[str, str] = {
    "nasdaq": "NASDAQ",
    "nyse": "NYSE",
}

_COUNTRY = "US"
_CURRENCY = "USD"


class SkippedRow(Exception):
    """이 행은 계약 밖이라 버린다 — 사유를 담아 호출부가 집계할 수 있게 한다."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def market_of(sec_exchange: object) -> str:
    """SEC 거래소 표기를 우리 `market` 으로. 모르는 표기는 `SkippedRow`."""
    if not isinstance(sec_exchange, str) or not sec_exchange.strip():
        raise SkippedRow("거래소 표기가 없는 종목")
    market = MARKET_BY_SEC_EXCHANGE.get(sec_exchange.strip().lower())
    if market is None:
        raise SkippedRow(f"우리 시장 집합에 없는 거래소: {sec_exchange}")
    return market


def to_instrument(row: list, fields: list[str]) -> NormalizedInstrument:
    """`company_tickers_exchange.json` 의 한 행(`[cik, name, ticker, exchange]`)을 정규화한다.

    `fields` 를 받아 위치가 아니라 **이름으로** 읽는다 — SEC 가 컬럼 순서를 바꾸면 위치 기반
    파싱은 조용히 엉뚱한 값을 넣는다(티커 자리에 회사명이 들어가도 문자열이라 통과한다).
    """
    if not isinstance(row, list) or len(row) != len(fields):
        raise SkippedRow(f"컬럼 수가 헤더와 다른 행: {len(row) if isinstance(row, list) else type(row).__name__}")
    record = dict(zip(fields, row, strict=True))

    ticker = record.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        raise SkippedRow("티커가 없는 종목")
    name = record.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SkippedRow(f"회사명이 없는 종목: {ticker}")

    aliases: dict[str, str] = {}
    cik = record.get("cik")
    if isinstance(cik, int):
        # CIK 는 10자리 zero-padded 가 SEC 의 정본 표기다 — 정수로 두면 다른 SEC 엔드포인트
        # (`CIK##########.json`)와 조인할 때마다 포맷을 다시 맞춰야 한다.
        aliases["cik"] = f"{cik:010d}"

    try:
        return NormalizedInstrument(
            country=_COUNTRY,
            market=market_of(record.get("exchange")),
            symbol=ticker.strip().upper(),
            issuer_nm=name.strip(),
            currency=_CURRENCY,
            sector_code=None,  # SEC 스냅샷에는 업종 축이 없다 — SIC 코드는 종목당 조회가 필요하다
            aliases=aliases,
        )
    except ValidationError as exc:
        raise SkippedRow(f"정규화 모델 파싱 실패: {exc.error_count()}건") from exc
