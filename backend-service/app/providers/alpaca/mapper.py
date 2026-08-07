"""Alpaca 응답 → 정규화 모델.

`adjustment=raw` 로 요청하므로 저장되는 값은 무수정 원본이고 `adj_policy` 는 `raw` 다 —
소스가 나중에 수정계수를 재계산해도 우리 정본이 흔들리지 않는다(MD-AD-18·NFR-006). 이 한 줄이
어댑터에 붙는 이유는, 요청 파라미터와 행에 적히는 정책이 **같은 자리에서** 정해져야 둘이
어긋나지 않기 때문이다.
"""

import datetime as dt
from decimal import Decimal, InvalidOperation

from core.calendar import market_local_naive
from pydantic import ValidationError

from providers.models import NormalizedBar, NormalizedQuote

# Alpaca 는 시장(거래소) 축을 캔들 응답에 담지 않는다 — 종목 마스터(SEC)가 이미 아는 값을
# 호출부가 넘겨 주고, 어댑터는 그것을 그대로 붙인다.
ADJ_POLICY = "raw"
ADJUSTMENT_PARAM = "raw"


class SkippedRow(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _decimal(item: dict, field: str) -> Decimal:
    try:
        return Decimal(str(item[field]))
    except (KeyError, InvalidOperation) as exc:
        raise SkippedRow(f"{field} 가 수치가 아닙니다") from exc


def _timestamp(item: dict, market: str) -> dt.datetime:
    raw = item.get("t")
    if not isinstance(raw, str):
        raise SkippedRow("타임스탬프가 없는 캔들")
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SkippedRow(f"타임스탬프 파싱 실패: {raw!r}") from exc
    # 저장은 **시장 현지 벽시계**의 naive 시각이다 — 차트 시간축이 시장 시각 고정이라는 결정
    # (2026-07-30)을 표시 계층이 아니라 저장 시점에 지킨다. 근거는 `core.calendar` 의 그 함수.
    return market_local_naive(market, parsed)


def to_bar(item: dict, symbol: str, market: str) -> NormalizedBar:
    try:
        return NormalizedBar(
            symbol=symbol.upper(),
            market=market.upper(),
            ts=_timestamp(item, market),
            open=_decimal(item, "o"),
            high=_decimal(item, "h"),
            low=_decimal(item, "l"),
            close=_decimal(item, "c"),
            volume=int(_decimal(item, "v")),
            trade_value=None,  # Alpaca 캔들에는 거래대금 축이 없다 (vw 는 거래량가중평균가다)
            adj_policy=ADJ_POLICY,
        )
    except ValidationError as exc:
        raise SkippedRow(f"정규화 모델 파싱 실패: {exc.error_count()}건") from exc


def to_quote(item: dict, symbol: str, market: str) -> NormalizedQuote:
    """최신 캔들을 스냅샷 시세로 환산한다 — 전일 대비는 이 응답에 없어 0 이 아니라 종가-시가로
    둔다. "없는 값을 0 으로 뭉개지 않는다"는 원칙(FR-021)상 등락은 계산 근거를 밝힐 수 있는
    값이어야 하고, 캔들 하나로 말할 수 있는 등락은 그 캔들 안의 변화뿐이다."""
    close = _decimal(item, "c")
    open_price = _decimal(item, "o")
    change = close - open_price
    try:
        return NormalizedQuote(
            symbol=symbol.upper(),
            market=market.upper(),
            price=close,
            change=change,
            change_rate=(change / open_price * 100) if open_price else Decimal(0),
            volume=int(_decimal(item, "v")),
            asof=_timestamp(item, market),
        )
    except ValidationError as exc:
        raise SkippedRow(f"정규화 모델 파싱 실패: {exc.error_count()}건") from exc
