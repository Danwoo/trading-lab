"""판정 지표 — 최장 미회복 기간이 1급이고, 모든 숫자가 유도 경로를 갖는다 (#201).

## 순서가 뒤집혀 있다 — 의도한 것이다 (스펙 D-Q2)

**트레이더가 계좌를 닫는 이유는 샤프가 낮아서가 아니라 낙폭을 못 견뎌서다.**

    1  최장 미회복 기간   몇 달을 물려 있어야 하나
    2  MDD + Calmar       내가 견딜 수 있는 크기인가
    3  거래당 평균 vs 비용 비용 먹고도 남나
    4  연환산 수익률       얼마 버나
    5  샤프                참고용

**MDD 와 최장 미회복 기간은 다른 정보다.** MDD −22% 는 견딜 만해 보이지만 그것이 14개월
지속됐다면 대부분 중간에 끊는다. 조사한 도구 대다수가 MDD 만 크게 보여주고 지속 기간은
표 안에 묻어 둔다 — 우리는 반대로 놓는다.

## 계산 정의는 검산으로 잡은 실제 버그다 (스펙 §8.5.1)

추측이 아니라 프로토타입을 떼어 실행해 찾은 것이다:

| 항목 | 잘못된 구현 | 올바른 정의 |
|---|---|---|
| 낙폭 금액 | `원금 × MDD` | **`그때의 고점 평가액 × MDD`** — 원금에 곱하면 체계적 과소(실측 36%) |
| 언더워터 기간 | 「원금 회복까지」 | **「전 고점 아래에 머문 최장」.** 원금과 무관 |
| CAGR | 구간과 무관하게 환산 | **표본이 짧으면 환산하지 않는다** — 26일을 환산하면 57.8%가 나온다 |
| 구간 낙폭 | 브러시 시작을 고점으로 리셋 | **구간 밖의 직전 고점을 이어받는다** |

## 유도 경로 없는 숫자 금지 (스펙 §8.5.3)

프로토타입의 `수수료 여유 3.4배`·`3종목 48%` 는 **전부 격자 품질값의 1차식**이었다.
거래도 곡선도 계산에 안 들어갔다.

> *"근거 없이 정밀한 숫자는 근거 없이 뭉뚱그린 숫자보다 나쁩니다."*

그래서 이 모듈은 **값만 반환하지 않는다.** 모든 지표가 `derived_from`(무엇에서 나왔나)을
달고 나오고, 계산할 수 없으면 `0` 을 지어내는 대신 `absent_reason` 을 단다.

거래가 0건이면 승률은 `0%` 가 아니라 **「거래 없음」**이다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# 이보다 짧은 구간은 연환산하지 않는다.
#
# 스펙이 "26일 구간을 연환산하면 57.8%" 를 문제로 지목했다. 경계를 어디 둘지는 스펙에
# 없으므로 **1년**으로 잡는다 — 1년 미만을 연환산하는 것은 관측하지 않은 기간을 외삽하는
# 것이고, 그 외삽분이 관측분보다 크면 그 숫자는 측정이 아니라 추측이다.
MIN_ANNUALIZE_DAYS = 365

TRADING_DAYS_PER_YEAR = 252

# 스펙 D-Q2 3급 지표의 이름. 값은 **엔진이 이미 비용을 뺀 실현손익**의 평균이라, 이름이
# 「− 왕복 비용」이면 화면이 한 번 더 뺀 값으로 읽힌다.
AVG_TRADE_LABEL = "거래당 평균 실현수익 (비용 차감 후)"


@dataclass(frozen=True)
class Metric:
    """지표 하나. **값과 유도 경로가 항상 함께 간다.**

    `value` 가 `None` 이면 계산하지 못한 것이고 `absent_reason` 이 왜인지 말한다 —
    화면은 그 문구를 그대로 쓴다. 0 으로 채우지 마라.
    """

    key: str
    label: str
    value: float | None
    unit: str
    derived_from: str
    absent_reason: str | None = None
    note: str | None = None

    @property
    def is_absent(self) -> bool:
        return self.value is None


@dataclass(frozen=True)
class OpenPosition:
    """구간 끝에 청산되지 않고 남은 자리 (#314).

    엔진은 이 자리를 **청산한 척하지 않는다** — 그래서 실현손익도, 승률도, 거래당 평균도
    없다. 그런데 자산곡선의 마지막 점은 이 자리의 **평가액**을 그대로 담는다. 두 사실을
    같이 말하지 않으면 화면에 「거래 0건」과 「+268%」가 나란히 서고, 어느 쪽이 거짓인지
    사용자가 화면 안에서 가릴 방법이 없다.

    `entry_cost` 가 `None` 이면 진입 기록이 없는 옛 실행이다 — 0 원이 아니라 **모르는 것**이다.
    """

    count: int
    #: 구간 끝 평가액 — 자산곡선 마지막 점의 `gross_exposure`.
    value: float
    entry_ts: str | None
    #: 진입에서 **이미 치른** 수수료 + 슬리피지. 매도 비용은 아직 안 물렸다.
    entry_cost: float | None
    unrealized_pnl: float | None
    #: 이 실행의 손익 중 미실현이 차지하는 비중. 100% 면 성과 전부가 아직 안 판 자리다.
    unrealized_share_pct: float | None
    derived_from: str
    absent_reason: str | None = None


def summarize_open_position(
    *,
    position_count: int,
    gross_exposure: float,
    trades: list,
    initial_cash: float,
    final_equity: float,
) -> OpenPosition | None:
    """자산곡선 마지막 점과 거래 기록에서 「구간 끝에 열린 자리」를 세운다.

    `position_count` 는 자산곡선 마지막 점의 것이고, 열린 자리의 진입 기록은 `trades` 안의
    **실현손익 없는 행**이다. 곡선은 자리가 있다는데 그 행이 없으면 이 변경 이전에 저장된
    실행이다 — 지어내지 않고 사유를 남긴다.
    """
    if position_count <= 0:
        return None

    recorded = [t for t in trades if getattr(t, "realized_pnl", None) is None]
    if not recorded:
        return OpenPosition(
            count=position_count,
            value=gross_exposure,
            entry_ts=None,
            entry_cost=None,
            unrealized_pnl=None,
            unrealized_share_pct=None,
            derived_from=f"자산곡선 마지막 점 — 보유 {position_count}자리 · 평가액 {gross_exposure:,.0f}원",
            absent_reason=(
                "열린 자리의 진입 기록이 없는 옛 실행입니다 — 언제 얼마에 들어갔는지 말할 수 없습니다. "
                "다시 실행하면 채워집니다"
            ),
        )

    entry_cost = sum(
        (getattr(t, "fee", 0.0) or 0.0) + (getattr(t, "slippage", 0.0) or 0.0) + (getattr(t, "tax", 0.0) or 0.0)
        for t in recorded
    )
    entry_notional = sum(float(t.entry_price) * float(t.qty) for t in recorded)
    unrealized = gross_exposure - (entry_notional + entry_cost)
    total_pnl = final_equity - initial_cash
    entry_ts = min(str(t.entry_ts) for t in recorded)
    return OpenPosition(
        count=position_count,
        value=gross_exposure,
        entry_ts=entry_ts,
        entry_cost=entry_cost,
        unrealized_pnl=unrealized,
        # 손익이 0 이면 비중이라는 값 자체가 없다 — 0% 로 답하면 「미실현이 없다」로 읽힌다.
        unrealized_share_pct=(unrealized / total_pnl * 100) if total_pnl else None,
        derived_from=(
            f"{entry_ts} 진입 · 자산곡선 마지막 점의 평가액 {gross_exposure:,.0f}원 "
            f"− 진입 원금 {entry_notional + entry_cost:,.0f}원 (매도 비용은 아직 안 물렸다)"
        ),
    )


def _peak_series(equity: list[float]) -> list[float]:
    """각 시점까지의 누적 고점."""
    peaks: list[float] = []
    running = float("-inf")
    for value in equity:
        running = max(running, value)
        peaks.append(running)
    return peaks


def max_drawdown(equity: list[float]) -> tuple[float, int, int]:
    """MDD 비율과 (고점 index, 저점 index).

    비율은 **그때의 고점 대비**다 — 원금 대비가 아니다.
    """
    if not equity:
        return 0.0, 0, 0
    peaks = _peak_series(equity)
    worst, peak_i, trough_i = 0.0, 0, 0
    current_peak_i = 0
    for i, (value, peak) in enumerate(zip(equity, peaks, strict=True)):
        if value >= peak:
            current_peak_i = i
        if peak > 0:
            dd = (value - peak) / peak
            if dd < worst:
                worst, peak_i, trough_i = dd, current_peak_i, i
    return worst, peak_i, trough_i


def drawdown_amount(equity: list[float]) -> float:
    """낙폭 **금액**.

    **`원금 × MDD` 가 아니다.** 그때의 고점 평가액에 곱해야 한다 — 원금에 곱하면 자산이
    불어난 뒤의 낙폭을 원금 기준으로 축소해 재고, 실측에서 36% 과소로 나왔다.
    """
    if not equity:
        return 0.0
    ratio, peak_i, _ = max_drawdown(equity)
    return equity[peak_i] * ratio


def longest_underwater(equity: list[float]) -> tuple[int, bool]:
    """전 고점 아래에 머문 **최장** 구간 길이와, 끝에서 미회복인지.

    **「원금 회복까지」가 아니다** — 원금과 무관하다. 자산이 원금의 3배가 된 뒤 30% 빠졌으면
    원금은 한참 위지만 그 트레이더는 물려 있는 것이다.
    """
    if not equity:
        return 0, False
    peak = equity[0]
    longest = 0
    current = 0
    for value in equity:
        if value >= peak:
            peak = value
            longest = max(longest, current)
            current = 0
        else:
            current += 1
    longest = max(longest, current)
    still_under = current > 0
    return longest, still_under


def _span_days(first: str, last: str) -> int:
    return (date.fromisoformat(last) - date.fromisoformat(first)).days


def compute(
    *,
    equity_dt: list[str],
    equity: list[float],
    trades: list,
    round_trip_cost_rate: float,
    initial_cash: float,
    sell_tax_rate: float,
    costless_summary: dict | None,
    open_position: OpenPosition | None,
) -> list[Metric]:
    """스펙 D-Q2 의 순서대로 지표를 낸다.

    `trades` 는 `engine.Trade` 목록 — **청산된 것과 구간 끝에 열린 것이 섞여 온다**(열린 것은
    `realized_pnl` 이 없다). `round_trip_cost_rate` 는 왕복 비용률(수수료 왕복 + 슬리피지 +
    증권거래세)로, **값에서 빼지 않고** 거래당 평균 실현수익 옆에 가정으로 적는다 —
    실현손익은 이미 순액이라 다시 빼면 비용을 두 번 문다.
    `initial_cash`·`sell_tax_rate` 는 비용 지표가 무엇으로 나누고 무엇을 기록으로 인정할지를
    가른다 — 기본값을 두지 않는 것은 안 넘기면 조용히 틀린 값이 나오기 때문이다.
    `costless_summary` 는 같은 조합을 비용 0으로 다시 돌린 결과다(없으면 `None`).
    `open_position` 은 `summarize_open_position` 이 세운 「구간 끝에 열린 자리」다 — 이것이
    `None` 이면 수익률·치른 비용이 **전부 실현된 것**이라고 말하게 되므로 기본값을 두지 않는다.
    """
    out: list[Metric] = []

    if not equity:
        reason = "자산곡선이 없습니다 — 아직 돌리지 않았습니다"
        for key, label, unit in (
            ("longest_underwater", "최장 미회복 기간", "일"),
            ("mdd", "최대 낙폭", "%"),
            ("calmar", "Calmar", "배"),
            ("avg_trade_vs_cost", AVG_TRADE_LABEL, "%"),
            ("cagr", "연환산 수익률", "%"),
            ("sharpe", "샤프", ""),
        ):
            out.append(
                Metric(key=key, label=label, value=None, unit=unit, derived_from="자산곡선", absent_reason=reason)
            )
        return out

    span = _span_days(equity_dt[0], equity_dt[-1]) if len(equity_dt) > 1 else 0

    # ── 1급: 최장 미회복 기간 ──────────────────────────────────────────
    underwater, still_under = longest_underwater(equity)
    out.append(
        Metric(
            key="longest_underwater",
            label="최장 미회복 기간",
            value=float(underwater),
            unit="봉",
            derived_from="자산곡선 — 전 고점 아래에 머문 최장 구간",
            note="아직 회복 중" if still_under else None,
        )
    )

    # ── 2급: MDD + 낙폭 금액 + Calmar ─────────────────────────────────
    mdd, _, _ = max_drawdown(equity)
    out.append(
        Metric(
            key="mdd",
            label="최대 낙폭",
            value=mdd * 100,
            unit="%",
            derived_from="자산곡선 — 그때의 고점 대비 하락률",
        )
    )
    out.append(
        Metric(
            key="drawdown_amount",
            label="최대 낙폭 금액",
            value=drawdown_amount(equity),
            unit="원",
            derived_from="그때의 고점 평가액 × 최대 낙폭률 (원금 × MDD 가 아니다)",
        )
    )

    total_return = (equity[-1] - equity[0]) / equity[0] if equity[0] else 0.0

    # **수익률이 무엇 위에 서 있는지 유도 문구가 말한다** (#314). 자산곡선의 마지막 점은 청산하지
    # 않은 자리의 평가액을 담는데, 그 자리는 `trades` 에 없어 거래 목록·승률이 「없음」이라 답한다.
    # 두 사실을 한 화면에 놓고 아무 말도 안 하면 어느 쪽이 거짓인지 가릴 방법이 없다.
    unrealized_note = (
        f" · 마지막 점은 청산하지 않은 자리 {open_position.count}건의 평가액 {open_position.value:,.0f}원을 포함한다"
        if open_position
        else ""
    )

    # CAGR — 표본이 짧으면 환산하지 않는다.
    if span >= MIN_ANNUALIZE_DAYS and equity[0] > 0 and equity[-1] > 0:
        years = span / 365.0
        cagr = ((equity[-1] / equity[0]) ** (1 / years) - 1) * 100
        cagr_metric = Metric(
            key="cagr",
            label="연환산 수익률",
            value=cagr,
            unit="%",
            derived_from=f"자산곡선 시작·끝과 구간 {span}일{unrealized_note}",
        )
    else:
        cagr = None
        cagr_metric = Metric(
            key="cagr",
            label="연환산 수익률",
            value=None,
            unit="%",
            derived_from=f"자산곡선 — 구간 {span}일",
            absent_reason=(
                f"구간이 {span}일이라 연환산하지 않습니다 "
                f"({MIN_ANNUALIZE_DAYS}일 미만은 외삽입니다). 구간 총수익률로 봅니다"
            ),
        )
        out.append(
            Metric(
                key="total_return",
                label="구간 총수익률",
                value=total_return * 100,
                unit="%",
                derived_from=f"자산곡선 시작·끝{unrealized_note}",
            )
        )

    if cagr is not None and mdd < 0:
        out.append(
            Metric(
                key="calmar",
                label="Calmar",
                value=cagr / abs(mdd * 100),
                unit="배",
                derived_from="연환산 수익률 ÷ 최대 낙폭",
            )
        )
    else:
        out.append(
            Metric(
                key="calmar",
                label="Calmar",
                value=None,
                unit="배",
                derived_from="연환산 수익률 ÷ 최대 낙폭",
                absent_reason=(
                    "연환산 수익률이 없어 계산할 수 없습니다" if cagr is None else "낙폭이 0이라 나눌 수 없습니다"
                ),
            )
        )

    # ── 3급: 거래당 평균 실현수익 — **비용은 엔진이 이미 뺐다** ──────────
    #
    # `engine.Trade.realized_pnl` 은 매수측 수수료·슬리피지와 매도측 수수료·슬리피지·
    # 증권거래세를 **체결금액에 실제로 물린 뒤**의 순액이다. 그래서 이 평균 자체가 스펙
    # D-Q2 3급의 질문(「비용 먹고도 남나」)에 대한 답이고, 여기서 왕복 비용률을 다시 빼면
    # 같은 비용을 두 번 문다.
    #
    # 가정 비율로 빼는 쪽을 택하지 않은 이유가 하나 더 있다 — 증권거래세와 매도측
    # 수수료·슬리피지는 **청산금액**에 붙는데 이 평균의 분모는 **진입금액**이라, 진입금액에
    # 비율을 곱해 빼면 실제로 치른 비용과도 어긋난다. 가정 비율은 값에서 빼지 않고 `note` 로
    # 나란히 세워, 쿠션이 얼마짜리 비용을 견딘 것인지 읽는 사람이 직접 견주게 한다.
    closed = [t for t in trades if getattr(t, "realized_pnl", None) is not None]
    if closed:
        avg_pnl = sum(t.realized_pnl for t in closed) / len(closed)
        avg_notional = sum(t.entry_price * t.qty for t in closed) / len(closed)
        avg_pct = (avg_pnl / avg_notional * 100) if avg_notional else 0.0
        out.append(
            Metric(
                key="avg_trade_vs_cost",
                label=AVG_TRADE_LABEL,
                value=avg_pct,
                unit="%",
                derived_from=(
                    f"청산된 거래 {len(closed)}건의 실현손익(수수료·슬리피지·증권거래세 차감 후) 평균 ÷ 평균 진입금액"
                ),
                note=f"왕복 비용률 가정 {round_trip_cost_rate * 100:.3f}%",
            )
        )
        wins = sum(1 for t in closed if t.realized_pnl > 0)
        out.append(
            Metric(
                key="win_rate",
                label="승률",
                value=wins / len(closed) * 100,
                unit="%",
                derived_from=f"청산된 거래 {len(closed)}건",
            )
        )
    else:
        # **0% 가 아니다.** 거래가 없으면 승률이라는 값 자체가 존재하지 않는다.
        #
        # 그리고 **「청산 안 함」과 「거래 없음」은 다른 상태다** (#314). 열린 자리를 안고 끝난
        # 실행에 「거래 없음」이라 답하면, 그 옆의 +268% 가 어디서 났는지 화면 안에서 못 가린다.
        no_trade_reason = (
            f"청산된 거래 없음 — 구간 끝에 열린 자리 {open_position.count}건이 있습니다. 청산해야 실현손익이 생깁니다"
            if open_position
            else "거래 없음 — 청산된 거래가 0건입니다"
        )
        for key, label in (("avg_trade_vs_cost", AVG_TRADE_LABEL), ("win_rate", "승률")):
            out.append(
                Metric(
                    key=key,
                    label=label,
                    value=None,
                    unit="%",
                    derived_from="청산된 거래",
                    absent_reason=no_trade_reason,
                )
            )

    out.append(cagr_metric)

    # ── 구간 끝에 열린 자리 — **성과의 얼마가 아직 안 판 것인가** (#314) ────────
    if open_position is not None:
        out.append(
            Metric(
                key="open_position_value",
                label="구간 끝에 열린 자리 평가액",
                value=open_position.value,
                unit="원",
                derived_from=open_position.derived_from,
                note=f"{open_position.count}건 미청산",
            )
        )
        share_absent = None
        if open_position.unrealized_share_pct is None:
            share_absent = open_position.absent_reason or "이 실행의 총손익이 0이라 비중을 낼 수 없습니다"
        out.append(
            Metric(
                key="unrealized_share_pct",
                label="성과 중 미실현 비중",
                value=open_position.unrealized_share_pct,
                unit="%",
                derived_from="열린 자리의 평가손익 ÷ 이 실행의 총손익(끝난 자산 − 시작 자금)",
                absent_reason=share_absent,
            )
        )

    # ── 비용 — **이 성과가 무엇을 치르고 남은 것인가** (#271) ────────────────
    #
    # 제품 정의 §5 W4 가 「현실 조건 반영 성과 … **미반영 대비 격차가 함께 표시**」를 완료
    # 조건으로 세웠다. 엔진은 이미 거래마다 비용을 치르고 기록한다 — 계산이 없는 게 아니라
    # 말을 안 했던 것이다.
    paid = sum(
        (getattr(t, "fee", 0.0) or 0.0) + (getattr(t, "slippage", 0.0) or 0.0) + (getattr(t, "tax", 0.0) or 0.0)
        for t in trades
    )
    # `tax` 축은 나중에 들어왔고 기존 행은 `server_default="0"` 으로 채워졌다. 그 0 은 「안 냈다」가
    # 아니라 **「기록이 없다」**다. **판정 대상은 청산된 거래뿐이다** — 매도세는 팔아야 붙으므로
    # 열린 자리의 세금 0 은 정상이고, 그것까지 세면 진입만 한 실행이 늘 「옛 실행」이 된다.
    tax_unrecorded = sell_tax_rate > 0 and bool(closed) and not any((getattr(t, "tax", 0.0) or 0.0) > 0 for t in closed)
    open_recorded = [t for t in trades if getattr(t, "realized_pnl", None) is None]
    # 「구간 끝에 열려 있는 자리」의 진입 비용도 **이미 치른 돈**이다 — 청산된 것만 세면 그 돈이
    # 합계에서 조용히 빠져, 진입만 한 실행이 「치른 비용 0원」이 된다 (#314).
    paid_derivation = f"청산된 거래 {len(closed)}건의 수수료 + 슬리피지 + 증권거래세 합"
    if open_recorded:
        paid_derivation += f" + 구간 끝에 열린 자리 {len(open_recorded)}건의 진입 비용 (매도 비용은 아직 안 물렸다)"
    # 곡선은 자리가 열려 있다는데 그 진입 기록이 없으면, 얼마를 냈는지 **모르는 것**이다.
    # 0 원이라 답하면 실제로 낸 돈을 안 낸 것으로 말하게 된다 — `tax_unrecorded` 와 같은 규약이다.
    open_cost_unrecorded = open_position is not None and open_position.entry_cost is None
    # 분모는 **시작 자금**이다. `equity[0]` 은 첫 봉 종료 시점 평가액이라 그 봉에서 진입했다면
    # 이미 매수 비용이 빠져 있어, 이름(「시작 자금」)과 값이 어긋난다.
    start_equity = initial_cash
    if tax_unrecorded or open_cost_unrecorded:
        absent = (
            "증권거래세 기록이 없는 옛 실행입니다 — 세금을 뺀 합계를 내면 적게 말하게 됩니다. 다시 실행하면 채워집니다"
            if tax_unrecorded
            else (
                f"구간 끝에 열린 자리 {open_position.count}건의 진입 비용이 기록되지 않은 옛 실행입니다 — "
                "이미 치른 돈을 0원이라 말하게 됩니다. 다시 실행하면 채워집니다"
            )
        )
        for key, label, unit in (("cost_paid", "치른 비용", "원"), ("cost_drag_pct", "비용이 먹은 수익률", "p")):
            out.append(
                Metric(
                    key=key,
                    label=label,
                    value=None,
                    unit=unit,
                    derived_from=paid_derivation,
                    absent_reason=absent,
                )
            )
    else:
        out.append(
            Metric(
                key="cost_paid",
                label="치른 비용",
                value=paid,
                unit="원",
                derived_from=paid_derivation,
            )
        )
        if start_equity > 0:
            out.append(
                Metric(
                    key="cost_drag_pct",
                    label="비용이 먹은 수익률",
                    value=paid / start_equity * 100,
                    unit="p",
                    # **재실행이 아니다.** 비용을 0 으로 두고 다시 돌리면 현금 제약이 달라져 체결
                    # 수량이 달라질 수 있다. 이 값은 「치른 비용」이지 「비용 없는 세계의 성과」가
                    # 아니다 — 그 경계를 여기 적어 화면이 그대로 읽게 한다.
                    derived_from="치른 비용 ÷ 시작 자금 (비용 0으로 다시 돌린 값이 아니다 — 체결 수량이 달라질 수 있다)",
                )
            )
        else:
            out.append(
                Metric(
                    key="cost_drag_pct",
                    label="비용이 먹은 수익률",
                    value=None,
                    unit="p",
                    derived_from="치른 비용 ÷ 시작 자금",
                    absent_reason="시작 자금이 0 이하라 나눌 수 없습니다",
                )
            )

    # ── 미반영 대비 격차 — **차별화 축 1** (SC-007) ─────────────────────
    #
    # 제품 정의 §6 SC-007: 「비용·제약 미반영 vs 반영 격차를 **수치로 나란히**」. 치른 비용 한 값은
    # 그 격차가 아니다 — 비용은 현금을 깎아 **체결 수량 자체를 바꾸므로**, 나눗셈으로 흉내내면
    # 거래 수가 다른 두 세계를 같은 세계인 척하게 된다. 그래서 대조군을 실제로 돌린 값을 쓴다.
    realized_return = (equity[-1] - initial_cash) / initial_cash * 100 if initial_cash > 0 else None
    costless_return = (costless_summary or {}).get("return_pct")
    # `NULL` 은 「안 돌린 옛 실행」이고, `absent_reason` 이 실린 요약은 「돌렸는데 못 구했다」다.
    # 둘을 뭉개면 터진 실행에 **소용없는 재실행**을 시킨다.
    twin_absent = (costless_summary or {}).get("absent_reason") if costless_summary else None
    if costless_summary is None or twin_absent:
        out.append(
            Metric(
                key="cost_gap_pct",
                label="비용을 안 냈다면 (격차)",
                value=None,
                unit="p",
                derived_from="비용 0으로 다시 돌린 실행의 수익률 − 이 실행의 수익률",
                absent_reason=twin_absent or "대조군을 돌리지 않은 옛 실행입니다 — 다시 실행하면 채워집니다",
            )
        )
    elif costless_return is None or realized_return is None:
        out.append(
            Metric(
                key="cost_gap_pct",
                label="비용을 안 냈다면 (격차)",
                value=None,
                unit="p",
                derived_from="비용 0으로 다시 돌린 실행의 수익률 − 이 실행의 수익률",
                absent_reason="시작 자금이 0 이하라 수익률을 낼 수 없습니다",
            )
        )
    else:
        # **판정 신호는 두 세계가 같다** — 전략은 현금을 보지 않는다(engine 의 ctx 에 현금·포지션이
        # 없다). 갈리는 것은 체결 **수량**이고, 그래서 끝난 자산이 다르다. 거래 **건수**로 갈림을
        # 말하는 분기는 지금 엔진에서 켜질 수 없어 두지 않는다 — 자금배분이 들어오는 날 다시 본다.
        out.append(
            Metric(
                key="cost_gap_pct",
                label="비용을 안 냈다면 (격차)",
                value=costless_return - realized_return,
                unit="p",
                derived_from=f"비용 0으로 다시 돌린 실행 {costless_return:.2f}% − 이 실행 {realized_return:.2f}%",
            )
        )

    # ── 5급: 샤프 (참고용) ────────────────────────────────────────────
    # 무위험수익률은 0 고정이고 화면이 그 사실을 밝힌다 (스펙 D-Q2).
    returns = [(equity[i] - equity[i - 1]) / equity[i - 1] for i in range(1, len(equity)) if equity[i - 1]]
    if len(returns) >= 2:
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std = var**0.5
        if std > 0:
            sharpe = mean / std * (TRADING_DAYS_PER_YEAR**0.5)
            out.append(
                Metric(
                    key="sharpe",
                    label="샤프",
                    value=sharpe,
                    unit="",
                    derived_from=f"일별 수익률 {len(returns)}개 · 무위험수익률 0 가정",
                )
            )
        else:
            out.append(
                Metric(
                    key="sharpe",
                    label="샤프",
                    value=None,
                    unit="",
                    derived_from="일별 수익률",
                    absent_reason="수익률 변동이 0이라 나눌 수 없습니다",
                )
            )
    else:
        out.append(
            Metric(
                key="sharpe",
                label="샤프",
                value=None,
                unit="",
                derived_from="일별 수익률",
                absent_reason=f"수익률 표본이 {len(returns)}개뿐입니다",
            )
        )

    return out


def window(equity_dt: list[str], equity: list[float], start: str, end: str) -> tuple[list[str], list[float], float]:
    """구간을 잘라 낸다 — **구간 밖의 직전 고점을 이어받는다.**

    브러시 시작을 고점으로 리셋하면 구간 낙폭이 실제보다 작게 나온다. 이미 물려 있는 상태로
    구간이 시작됐을 수 있고, 그 사실이 사라지면 「여기서부터는 괜찮았다」로 읽힌다.

    세 번째 반환값이 이어받은 고점이다.
    """
    inherited = float("-inf")
    dts: list[str] = []
    values: list[float] = []
    for dt, value in zip(equity_dt, equity, strict=True):
        if dt < start:
            inherited = max(inherited, value)
            continue
        if dt > end:
            break
        dts.append(dt)
        values.append(value)
    if inherited == float("-inf"):
        inherited = values[0] if values else 0.0
    return dts, values, inherited
