# utils/portfolio/portfolio_utils.py
"""portfolio_service 의 순수 헬퍼 — since/until 정규화·보유/거래/주문/활동 라인 변환(계좌번호 마스킹 포함).

IO/DB 없는 순수 함수만 모은다(서비스에서 분리 → 단위 테스트 용이). 외부 시각(now)은 인자로 받는다.
자유텍스트(detail 등)는 redact_secrets() 로 계좌번호/카드번호를 마스킹한 뒤 노출한다 (그 외 PII 는 게이트웨이 PiiMaskGuard 담당).
"""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from utils.common.time_utils import parse_iso_to_kst
from utils.redaction.redactor import redact_secrets

_DEFAULT_QUERY_DAYS = 30  # since 미지정 시 최근 30일
_MIN_AWARE_DATETIME = datetime.min.replace(tzinfo=UTC)
_ZERO = Decimal("0")


def _dec(value) -> Decimal:
    """float/int/str → Decimal. 금액 계산은 이진 float 오차·중간 반올림 드리프트를 피해 Decimal 로 한다."""
    return Decimal(str(value or 0))


def _round2(value: Decimal) -> float:
    """계산 경계에서 2자리로 한 번만 반올림해 float 로 반환한다 (스키마·tool 계약은 float 유지)."""
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def market_value_dec(quantity, last_price) -> Decimal:
    """평가금액(수량×현재가)을 full precision Decimal 로. 표시·합산이 모두 이 값에서 파생(중간 반올림 없음)."""
    return _dec(quantity) * _dec(last_price)


def sum_by_currency(lines: list[dict], value_key: str) -> dict[str, float]:
    """lines 의 value_key 를 통화별로 합산. 환율 없이 통화를 섞어 더하면 무의미하므로 통화별로 분리한다.

    누적은 Decimal 로 하고 통화별 버킷마다 한 번만 반올림한다 (중간 float 누적 드리프트 방지).
    """
    totals: dict[str, Decimal] = {}
    for line in lines:
        ccy = line.get("currency") or "KRW"
        totals[ccy] = totals.get(ccy, _ZERO) + _dec(line.get(value_key))
    return {ccy: _round2(v) for ccy, v in totals.items()}


def sum_market_value_by_currency(lines: list[dict]) -> dict[str, float]:
    """보유 라인의 평가금액을 통화별로 합산한다. 표시용으로 반올림된 line["market_value"] 가 아니라
    수량×현재가 full precision 을 통화별로 누적한 뒤 한 번만 반올림한다 (라인별 반올림 드리프트 방지)."""
    totals: dict[str, Decimal] = {}
    for line in lines:
        ccy = line.get("currency") or "KRW"
        totals[ccy] = totals.get(ccy, _ZERO) + market_value_dec(line.get("quantity"), line.get("last_price"))
    return {ccy: _round2(v) for ccy, v in totals.items()}


def assign_weights(lines: list[dict]) -> None:
    """각 라인의 weight(%) = 평가금액 / 계좌 평가자산 × 100 을 채운다 (in-place).

    계좌 평가자산·분자 모두 full precision 평가금액에서 계산한다. 평가자산 0(빈/전액현금)은 0 으로 안전 처리.
    """
    acc_total = sum((market_value_dec(line.get("quantity"), line.get("last_price")) for line in lines), _ZERO)
    for line in lines:
        mv = market_value_dec(line.get("quantity"), line.get("last_price"))
        line["weight"] = _round2(mv / acc_total * 100) if acc_total else 0.0


def nav_by_currency(base_currency: str, cash: float, holdings: list[dict]) -> dict[str, float]:
    """통화별 순자산가치(환율 환산 없음). 예수금은 기준통화 버킷, 보유분은 종목통화 버킷에 full precision 누적."""
    totals: dict[str, Decimal] = {base_currency: _dec(cash)}
    for h in holdings:
        ccy = h.get("currency") or base_currency
        totals[ccy] = totals.get(ccy, _ZERO) + market_value_dec(h.get("quantity"), h.get("last_price"))
    return {ccy: _round2(v) for ccy, v in totals.items()}


def fx_pairs_for(currencies, base_currency: str) -> set[str]:
    """기준통화로 환산하려면 필요한 통화쌍 집합 ('{통화}/{기준통화}'). 기준통화 자신은 제외(환율 불필요)."""
    return {f"{c}/{base_currency}" for c in currencies if c and c != base_currency}


def select_rates(fetched: dict[str, dict], currencies, base_currency: str) -> tuple[dict[str, float], dict[str, dict]]:
    """조회된 환율맵에서 필요한 통화의 환율만 골라 (rates, fx_rates_used) 로 정리한다.

    rates[통화] = 1 단위 통화의 기준통화 값. fx_rates_used[pair] = {rate, asof} (근거 노출용).
    없는 통화쌍은 지어내지 않고 그냥 빠진다 (호출측이 unconverted 로 표기).
    """
    rates: dict[str, float] = {}
    used: dict[str, dict] = {}
    for ccy in currencies:
        if not ccy or ccy == base_currency:
            continue
        pair = f"{ccy}/{base_currency}"
        row = fetched.get(pair)
        if row and row.get("rate") is not None:
            rates[ccy] = float(row["rate"])
            used[pair] = {"rate": float(row["rate"]), "asof": row.get("asof") or ""}
    return rates, used


def convert_to_base(
    by_currency: dict[str, float], base_currency: str, rates: dict[str, float]
) -> tuple[float, list[str]]:
    """통화별 합계를 기준통화로 환산 합산한다. rates[통화]=1 단위 통화의 기준통화 값(같은 통화는 자동 1.0).

    환율 없는 통화는 지어내지 않고 unconverted 로 반환하며 합산에서 제외한다 (역수·삼각환산 안 함).
    반환된 합계는 환산 가능한 통화만의 합이므로 unconverted 가 비어야 전체를 포괄한다.
    """
    total = _ZERO
    unconverted: list[str] = []
    for ccy, amount in by_currency.items():
        if ccy == base_currency:
            total += _dec(amount)
        elif ccy in rates:
            total += _dec(amount) * _dec(rates[ccy])
        else:
            unconverted.append(ccy)
    return _round2(total), sorted(unconverted)


def norm_since(s: str | None, now) -> str:
    """since 정규화: 미지정=최근 30일, bare 'YYYY-MM-DD'=그날 00:00 KST."""
    if not s:
        return (now - timedelta(days=_DEFAULT_QUERY_DAYS)).strftime("%Y-%m-%dT00:00:00+09:00")
    return f"{s}T00:00:00+09:00" if len(s) == 10 else s


def norm_until(s: str | None, now) -> str:
    """until 정규화: 미지정=현재, bare 'YYYY-MM-DD'=그날 23:59:59 KST (그날치 거래 누락 방지)."""
    if not s:
        return now.strftime("%Y-%m-%dT23:59:59+09:00")
    return f"{s}T23:59:59+09:00" if len(s) == 10 else s


def timestamp_sort_key(s: str | None) -> datetime:
    """ISO-8601 문자열을 시간순 비교용 aware datetime 으로 변환한다."""
    return parse_iso_to_kst(s) or _MIN_AWARE_DATETIME


def timestamp_in_range(value: str | None, since: str, until: str) -> bool:
    """ISO-8601 타임스탬프가 [since, until] 범위에 포함되는지 확인한다."""
    dt = parse_iso_to_kst(value)
    start = parse_iso_to_kst(since)
    end = parse_iso_to_kst(until)
    return dt is not None and start is not None and end is not None and start <= dt <= end


def holding_line(account_id: str, h: dict) -> dict:
    """원시 보유 dict → 평가금액·평가손익·비중 계산된 구조화 라인."""
    qty = float(h.get("quantity") or 0)
    avg = float(h.get("avg_price") or 0)
    last = float(h.get("last_price") or 0)
    mv = market_value_dec(qty, last)
    market_value = _round2(mv)
    unrealized = _round2(mv - _dec(avg) * _dec(qty))
    return {
        "account_id": account_id,
        "ticker": h.get("ticker") or "",
        "name": h.get("name") or "",
        "asset_class": h.get("asset_class") or "equity",
        "quantity": qty,
        "avg_price": avg,
        "last_price": last,
        "market_value": market_value,
        "unrealized_pnl": unrealized,
        "weight": 0.0,  # 계좌 평가자산 합산 후 service 가 채움
        "currency": h.get("currency") or "KRW",
    }


def tx_line(account_id: str, t: dict) -> dict:
    """원시 거래 dict → 구조화 라인 (금액 부호 그대로)."""
    return {
        "account_id": account_id,
        "trade_date": (t.get("trade_date") or "")[:10],
        "tx_type": t.get("tx_type") or "",
        "ticker": t.get("ticker") or "",
        "name": t.get("name") or "",
        "quantity": float(t.get("quantity") or 0),
        "price": float(t.get("price") or 0),
        "amount": float(t.get("amount") or 0),
        "currency": t.get("currency") or "KRW",
    }


def order_line(account_id: str, o: dict) -> dict:
    """원시 주문 dict → 구조화 라인."""
    return {
        "account_id": account_id,
        "order_id": o.get("order_id") or "",
        "ticker": o.get("ticker") or "",
        "name": o.get("name") or "",
        "side": o.get("side") or "",
        "order_type": o.get("order_type") or "limit",
        "status": o.get("status") or "",
        "quantity": float(o.get("quantity") or 0),
        "filled_quantity": float(o.get("filled_quantity") or 0),
        "price": float(o.get("price") or 0),
        "avg_fill_price": float(o.get("avg_fill_price") or 0),
        "placed_at": (o.get("placed_at") or "")[:10],
        "currency": o.get("currency") or "KRW",
    }


def event_line(e: dict) -> dict:
    """원시 활동 dict → 구조화 라인. detail 은 계좌번호/카드번호 마스킹."""
    return {
        "date": (e.get("date") or "")[:10],
        "action": e.get("action") or "",
        "detail": redact_secrets(e.get("detail") or ""),
        "amount": float(e.get("amount") or 0),
    }
