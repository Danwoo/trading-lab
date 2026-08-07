"""금융위 응답 → 정규화 모델.

**미검증**: 필드명·값 형식은 공개 문서 기준이며 실호출로 대조하지 않았다(client docstring).
특히 `adj_policy` 는 이 소스가 무수정 원본을 주는지 확인하고 정해야 하는 값인데(오더 3 T5 위험),
확인 수단이 키뿐이라 지금은 `raw` 로 두고 그 사실을 여기 적어 둔다 — 키가 들어오면 가장 먼저
대조해야 할 자리다.
"""

import datetime as dt
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from providers.models import NormalizedBar, NormalizedInstrument

# 금융위 `mrktCtg` → 우리 `market`.
MARKET_BY_MRKT_CTG: dict[str, str] = {
    "KOSPI": "KOSPI",
    "KOSDAQ": "KOSDAQ",
    "KONEX": "KONEX",
}

_COUNTRY = "KR"
_CURRENCY = "KRW"

# 확인 전 잠정값 — 위 docstring 참조.
ADJ_POLICY = "raw"


class SkippedRow(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _market(item: dict) -> str:
    market = MARKET_BY_MRKT_CTG.get(str(item.get("mrktCtg") or "").strip().upper())
    if market is None:
        raise SkippedRow(f"우리 시장 집합에 없는 시장 구분: {item.get('mrktCtg')!r}")
    return market


def _symbol(item: dict) -> str:
    """단축코드는 6자리 문자열이다. 소스가 숫자로 주더라도 선행 0 이 죽지 않게 문자열로 되살린다."""
    raw = item.get("srtnCd")
    if raw is None:
        raise SkippedRow("단축코드가 없는 행")
    text = str(raw).strip()
    if not text.isdigit() or len(text) > 6:
        raise SkippedRow(f"단축코드 형식이 아닙니다: {text!r}")
    return text.zfill(6)


def _decimal(item: dict, field: str) -> Decimal:
    try:
        return Decimal(str(item[field]).strip().replace(",", ""))
    except (KeyError, InvalidOperation, AttributeError) as exc:
        raise SkippedRow(f"{field} 가 수치가 아닙니다") from exc


def _optional_decimal(item: dict, field: str) -> Decimal | None:
    try:
        return _decimal(item, field)
    except SkippedRow:
        return None


def to_instrument(item: dict) -> NormalizedInstrument:
    name = str(item.get("itmsNm") or "").strip()
    if not name:
        raise SkippedRow("종목명이 없는 행")
    aliases: dict[str, str] = {}
    isin = str(item.get("isinCd") or "").strip()
    if isin:
        aliases["isin"] = isin
    try:
        return NormalizedInstrument(
            country=_COUNTRY,
            market=_market(item),
            symbol=_symbol(item),
            issuer_nm=name,
            currency=_CURRENCY,
            sector_code=None,
            aliases=aliases,
        )
    except ValidationError as exc:
        raise SkippedRow(f"정규화 모델 파싱 실패: {exc.error_count()}건") from exc


def to_bar(item: dict) -> NormalizedBar:
    basis = str(item.get("basDt") or "").strip()
    if len(basis) != 8 or not basis.isdigit():
        raise SkippedRow(f"기준일자 형식이 아닙니다: {basis!r}")
    try:
        ts = dt.datetime.strptime(basis, "%Y%m%d")
    except ValueError as exc:
        raise SkippedRow(f"기준일자 파싱 실패: {basis!r}") from exc

    try:
        return NormalizedBar(
            symbol=_symbol(item),
            market=_market(item),
            ts=ts,
            open=_decimal(item, "mkp"),
            high=_decimal(item, "hipr"),
            low=_decimal(item, "lopr"),
            close=_decimal(item, "clpr"),
            volume=int(_decimal(item, "trqu")),
            trade_value=_optional_decimal(item, "trPrc"),
            adj_policy=ADJ_POLICY,
        )
    except ValidationError as exc:
        raise SkippedRow(f"정규화 모델 파싱 실패: {exc.error_count()}건") from exc
