#!/usr/bin/env python3
"""리포트 조회가 지표를 붙여 내고, 남의 워크스페이스 run 을 숨기는지 확인한다 (#203).

cd backend-service && APP_ENV=development uv run python tests/test_backtest_report.py
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from core.exceptions import NotFoundError  # noqa: E402
from services.backtest.backtest_service import BacktestService  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


class FakeRepository:
    """DB 행을 흉내 낸다 — 숫자는 psycopg 가 주는 대로 Decimal 이다."""

    def __init__(self, run: dict | None, equity: list[dict], trades: list[dict]):
        self.run = run
        self.equity = equity
        self.trades = trades

    def select_run(self, run_id: int):
        return self.run

    def select_equity_curve(self, run_id: int):
        return self.equity

    def select_trades(self, run_id: int):
        return self.trades


def run_row(**overrides) -> dict:
    row = {
        "run_id": 7,
        "workspace_id": 1,
        "bot_id": None,
        "parent_run_id": None,
        "attempt_no": 3,
        "strategy_key": "ma_pullback",
        "strategy_version": "1",
        "params": {"ma_period": 20},
        "universe_def": {"market": "KOSPI", "symbols": ["005930"]},
        "adj_policy": "unadjusted",
        "cost_assumptions": {"fee_rate": 0.00015, "slippage_rate": 0.0005, "sell_tax_rate": 0.0018},
        "period_from": date(2026, 1, 2),
        "period_to": date(2026, 3, 31),
        "initial_cash": Decimal("1000000"),
        "status": "succeeded",
        "failed_reason": None,
        "finished_dt": None,
    }
    row.update(overrides)
    return row


def equity_rows(values: list[float]) -> list[dict]:
    return [
        {
            "dt": date(2026, 1, 2 + i),
            "equity": Decimal(str(v)),
            "cash": Decimal(str(v)),
            "position_count": 0,
            "gross_exposure": Decimal("0"),
        }
        for i, v in enumerate(values)
    ]


class CapturingRepository:
    """`_persist` 가 각 테이블에 **무엇을 넣는지** 붙잡는다 — DB 없이 저장 계약을 본다."""

    def __init__(self) -> None:
        self.trades: list[dict] = []
        self.equity: list[dict] = []

    def insert_equity(self, rows):
        self.equity = rows
        return len(rows)

    def insert_trades(self, rows):
        self.trades = rows
        return len(rows)

    def insert_signals(self, rows):
        return len(rows)

    def insert_cash_events(self, rows):
        return len(rows)


def service(repo) -> BacktestService:
    return BacktestService(backtest_repository=repo, bar_service=None, strategy_loader=lambda key: None)


def test_metrics_ride_along_and_longest_underwater_is_first() -> None:
    repo = FakeRepository(run_row(), equity_rows([100.0, 90.0, 95.0, 101.0]), [])
    report = service(repo).select_report({"run_id": 7, "workspace_id": 1})

    check("지표가 함께 온다", bool(report["metrics"]), True)
    check("최장 미회복 기간이 맨 위다 (D-Q2)", report["metrics"][0]["key"], "longest_underwater")
    keys = [m["key"] for m in report["metrics"]]
    check("샤프는 맨 뒤다", keys[-1], "sharpe")

    # **이 성과가 무엇을 치르고 남은 것인지** 말한다 (#271 — 제품 정의 §5 W4 완료 조건).
    check("치른 비용이 있다", "cost_paid" in keys, True)
    check("비용이 먹은 수익률이 있다", "cost_drag_pct" in keys, True)
    by_key = {m["key"]: m for m in report["metrics"]}
    # 재실행이 아니라는 것을 **유도 문구가** 밝힌다 — 비용 0 으로 다시 돌리면 체결 수량이 달라진다
    check(
        "재실행이 아님을 밝힌다",
        "다시 돌린 값이 아니다" in (by_key["cost_drag_pct"]["derived_from"] or ""),
        True,
    )
    check("치른 비용의 유도가 세 항목을 말한다", "증권거래세" in (by_key["cost_paid"]["derived_from"] or ""), True)


def test_zero_trades_is_absent_not_zero() -> None:
    repo = FakeRepository(run_row(), equity_rows([100.0, 101.0, 102.0]), [])
    report = service(repo).select_report({"run_id": 7, "workspace_id": 1})

    win = next(m for m in report["metrics"] if m["key"] == "win_rate")
    check("거래 0건 승률은 값이 없다", win["value"], None)
    check("사유가 「거래 없음」이다", "거래 없음" in (win["absent_reason"] or ""), True)


def test_decimal_rows_become_floats() -> None:
    trades = [
        {
            "trade_id": 1,
            "instrument_id": 10,
            "side": "BUY",
            "entry_ts": date(2026, 1, 2),
            "exit_ts": date(2026, 1, 5),
            "qty": Decimal("3"),
            "fill_price": Decimal("100"),
            "exit_price": Decimal("110"),
            "fee": Decimal("0.1"),
            "slippage": Decimal("0.1"),
            "tax": Decimal("0.6"),
            "realized_pnl": Decimal("30"),
            "mae": None,
            "mfe": None,
        }
    ]
    repo = FakeRepository(run_row(), equity_rows([100.0, 105.0, 110.0]), trades)
    report = service(repo).select_report({"run_id": 7, "workspace_id": 1})

    check("equity 가 float 이다", isinstance(report["equity"][0]["equity"], float), True)
    check("qty 가 float 이다", isinstance(report["trades"][0]["qty"], float), True)
    check("run.initial_cash 가 float 이다", isinstance(report["run"]["initial_cash"], float), True)
    win = next(m for m in report["metrics"] if m["key"] == "win_rate")
    check("청산 거래 1건이 승률 계산에 들어간다", win["value"], 100.0)
    check("거래 목록이 세금을 싣고 나온다", report["trades"][0]["tax"], 0.6)
    # **비용 3종이 다 실려야 값이 맞는다.** `backtest_service` 에서 `fee=`·`slippage=`·`tax=`
    # 중 하나만 빠져도 이 합이 조용히 작아진다 — 실측으로 25거래에 0원이 나왔던 자리다.
    paid = next(m for m in report["metrics"] if m["key"] == "cost_paid")
    check("치른 비용 = 수수료+슬리피지+세금", paid["value"], 0.8)
    # 분모는 run 의 시작 자금(1,000,000)이지 `equity[0]`(=100) 이 아니다.
    drag = next(m for m in report["metrics"] if m["key"] == "cost_drag_pct")
    check("비용이 먹은 수익률의 분모는 시작 자금", drag["value"], 0.8 / 1_000_000 * 100)


def trade_row(qty: str) -> dict:
    return {
        "trade_id": 1,
        "instrument_id": 10,
        "side": "BUY",
        "entry_ts": date(2026, 1, 2),
        "exit_ts": date(2026, 1, 5),
        "qty": Decimal(qty),
        "fill_price": Decimal("189700"),
        "exit_price": Decimal("184000"),
        "fee": Decimal("0"),
        "slippage": Decimal("0"),
        "tax": Decimal("0"),
        "realized_pnl": Decimal("-1"),
        "mae": None,
        "mfe": None,
    }


def test_report_states_how_it_filled() -> None:
    """리포트가 **체결 가정**을 싣는다 — 비용 3종 옆에 설 자리 (#313).

    문구는 엔진(`FILL_ASSUMPTIONS`)이 정본이라 여기서 다시 적지 않고, 「1주」와 「종가」가
    실려 나오는지만 본다.
    """
    repo = FakeRepository(run_row(), equity_rows([100.0, 101.0]), [trade_row("3")])
    report = service(repo).select_report({"run_id": 7, "workspace_id": 1})

    fills = report["execution_assumptions"]
    check("주문 단위가 1주라고 말한다", "1주" in fills["order_unit"], True)
    check("체결가가 그 봉의 종가라고 말한다", "종가" in fills["fill_price"], True)
    check("유동성 상한이 없다고 말한다", "없음" in fills["liquidity_cap"], True)
    # 선언값을 사실인 척하지 않는다 — 캔들의 조정 정책과 대조하는 것은 아직 안 한다.
    check("조정 정책이 선언값임을 밝힌다", "선언값" in fills["adj_policy"], True)
    check("정수 수량 실행은 옛 모형 경고가 없다", fills["stale_reason"], None)


def test_fractional_qty_run_is_marked_stale() -> None:
    """소수점 수량이 남은 **옛 실행**은 그 사실이 결과에 실린다 (#313).

    체결 모형은 실행 행이 아니라 엔진 코드에 있어 옛 실행에 표식이 없다. 그래서 저장된
    수량에서 되읽는다 — 0.526806주는 지금 엔진이 만들 수 없는 수량이다.
    """
    repo = FakeRepository(run_row(), equity_rows([100.0, 99.0]), [trade_row("0.526806")])
    report = service(repo).select_report({"run_id": 7, "workspace_id": 1})

    stale = report["execution_assumptions"]["stale_reason"]
    check("옛 실행임을 말한다", stale is not None and "소수점 체결" in stale, True)
    check("다시 돌리면 달라진다고 말한다", stale is not None and "달라집니다" in stale, True)


def test_other_workspace_run_is_hidden() -> None:
    repo = FakeRepository(run_row(workspace_id=99), equity_rows([100.0]), [])
    global CHECKED
    CHECKED += 1
    try:
        service(repo).select_report({"run_id": 7, "workspace_id": 1})
        FAILURES.append("남의 워크스페이스: NotFoundError 가 나지 않았다")
    except NotFoundError:
        pass


def test_round_trip_cost_feeds_metric() -> None:
    trades = [
        {
            "trade_id": 1,
            "instrument_id": 10,
            "side": "BUY",
            "entry_ts": date(2026, 1, 2),
            "exit_ts": date(2026, 1, 5),
            "qty": Decimal("1"),
            "fill_price": Decimal("100"),
            "exit_price": Decimal("101"),
            "fee": Decimal("0"),
            "slippage": Decimal("0"),
            # 세율이 걸린 run 인데 세금이 0 — `0017` 이전에 남은 행이 이 모양이다.
            "tax": Decimal("0"),
            "realized_pnl": Decimal("1"),
            "mae": None,
            "mfe": None,
        }
    ]
    # 왕복 비용률 = 2*0.00015 + 2*0.0005 + 0.0018 = 0.0031 → 「0.310%」 로 지표 옆에 선다.
    # **값에서 빼지 않는다** — `realized_pnl` 은 이미 비용을 치른 순액이라 다시 빼면 두 번 문다 (#312).
    repo = FakeRepository(run_row(), equity_rows([100.0, 100.5, 101.0]), trades)
    report = service(repo).select_report({"run_id": 7, "workspace_id": 1})

    avg = next(m for m in report["metrics"] if m["key"] == "avg_trade_vs_cost")
    # 실현손익 1 ÷ 진입금액 100 = 1.00%. 이중 차감이면 0.69% 가 나온다.
    check("거래당 평균 = 실현손익 ÷ 진입금액", round(avg["value"], 4), 1.0)
    check("이중 차감값이 아니다", round(avg["value"], 4) != round(1.0 - 0.31, 4), True)
    check("왕복 비용률이 가정으로 실린다", avg["note"], "왕복 비용률 가정 0.310%")
    # 세금 기록이 없는 옛 실행은 합계를 지어내지 않는다 — 세금은 명시 비용의 절반을 넘는다.
    paid = next(m for m in report["metrics"] if m["key"] == "cost_paid")
    check("옛 실행의 치른 비용은 값이 없다", paid["value"], None)
    check("사유가 옛 실행임을 말한다", "옛 실행" in (paid["absent_reason"] or ""), True)


def test_grid_cell_twin_failure_is_recorded_not_swallowed() -> None:
    """격자 칸의 대조군이 터지면 **그 사유가 저장된다** — `NULL` 로 두면 「옛 실행」으로 읽힌다."""
    svc = service(FakeRepository(run_row(), [], []))
    cell = SimpleNamespace(
        costless=None, costless_absent="대조군을 구하지 못했습니다 — 실행이 KeyError 으로 멈췄습니다"
    )
    saved = svc._cell_costless_json(cell, None, 1_000_000.0)
    check("사유가 실린다", saved is not None and "구하지 못했습니다" in saved, True)

    # 실패한 칸은 대조군 이야기를 하지 않는다 — 그 칸은 애초에 결과가 없다.
    check("실패한 칸은 NULL", svc._cell_costless_json(cell, "전략이 터졌습니다", 1_000_000.0), None)

    # 안 돌린 칸(사유도 없음)은 「옛 실행」과 같은 NULL 이 맞다.
    check(
        "안 돌린 칸은 NULL",
        svc._cell_costless_json(SimpleNamespace(costless=None, costless_absent=None), None, 1_000_000.0),
        None,
    )


# ── 구간 끝에 열린 자리 (#314) ───────────────────────────────────────────────


def open_equity_rows(values: list[float], *, gross_exposure: float) -> list[dict]:
    """마지막 점에 자리가 **열려 있는** 자산곡선. 그 평가액이 곧 마지막 점의 노출액이다."""
    rows = equity_rows(values)
    rows[-1]["position_count"] = 1
    rows[-1]["gross_exposure"] = Decimal(str(gross_exposure))
    return rows


def open_trade_row() -> dict:
    """진입만 하고 청산되지 않은 자리 — `exit_ts`·`exit_price`·`realized_pnl` 이 전부 NULL 이다."""
    return {
        "trade_id": 1,
        "instrument_id": 10,
        "side": "long",
        "entry_ts": date(2026, 1, 3),
        "exit_ts": None,
        "qty": Decimal("9"),
        "fill_price": Decimal("100"),
        "exit_price": None,
        "fee": Decimal("0.9"),
        "slippage": Decimal("3.0"),
        "tax": Decimal("0"),
        "realized_pnl": None,
        "mae": None,
        "mfe": None,
    }


def test_open_position_is_persisted_as_an_unclosed_row() -> None:
    """엔진의 열린 자리가 **거래 원장에 남는다** — 청산한 척하지 않되 버리지도 않는다.

    남기지 않으면 그 자리의 진입 비용이 어느 합계에도 안 잡혀 「치른 비용 0원」이 된다.
    """
    from services.backtest.engine import BarSeries, CostModel, Strategy, run_single

    closes = [100.0, 120.0, 150.0]
    series = BarSeries(
        instrument_id=1,
        dt=["2026-01-02", "2026-01-03", "2026-01-04"],
        open=list(closes),
        high=list(closes),
        low=list(closes),
        close=list(closes),
        volume=[1000.0] * 3,
    )
    strategy = Strategy(
        SimpleNamespace(
            STRATEGY={"key": "fixture", "name": "고정", "timeframe": "1d", "params": []},
            indicators=lambda bars, params: {},
            entry=lambda ctx: ctx["index"] == 0,
            exit=lambda ctx: False,
        )
    )
    result = run_single(
        strategy=strategy,
        params={},
        series=series,
        rows=series.rows(),
        initial_cash=1000.0,
        costs=CostModel(fee_rate=0.01, slippage_rate=0.0, sell_tax_rate=0.0),
    )

    repo = CapturingRepository()
    written = service(repo)._persist(7, result)
    check("거래 행이 1건 저장된다", written["trade_rows"], 1)
    if not repo.trades:
        FAILURES.append("열린 자리가 거래 원장에 안 남았다 — 진입 비용이 어느 합계에도 안 잡힌다")
        return
    check("청산 시각이 비어 있다", repo.trades[0]["exit_ts"], None)
    check("실현손익이 비어 있다", repo.trades[0]["realized_pnl"], None)
    check("진입 비용이 남는다", float(repo.trades[0]["fee"]) > 0, True)


def test_open_position_rides_the_report() -> None:
    """리포트가 열린 자리를 **1급 정보로** 싣고, 지표가 그 사실을 반영한다.

    진입 원금 100 × 9 = 900 · 진입 비용 0.9 + 3.0 = 3.9 · 끝 평가액 1,400
      → 미실현 = 1,400 − 903.9 = 496.1
    """
    repo = FakeRepository(
        run_row(), open_equity_rows([1000.0, 900.0, 1400.0], gross_exposure=1400.0), [open_trade_row()]
    )
    report = service(repo).select_report({"run_id": 7, "workspace_id": 1})

    op = report["open_position"]
    check("열린 자리가 응답에 있다", op is not None, True)
    check("자리 수", op["count"], 1)
    check("평가액", op["value"], 1400.0)
    check("진입일", op["entry_ts"], "2026-01-03")
    # 진입 원금 = 100 × 9 + (0.9 + 3.0) = 903.9 → 미실현 = 1,400 − 903.9 = 496.1
    check("미실현 손익", round(op["unrealized_pnl"], 6), 496.1)

    # 「치른 비용」이 열린 자리의 진입 비용을 센다 — 이슈의 「0원」이 여기서 갈린다.
    paid = next(m for m in report["metrics"] if m["key"] == "cost_paid")
    check("치른 비용이 0원이 아니다", round(paid["value"], 6), 3.9)
    check("유도가 열린 자리를 밝힌다", "열린 자리 1건의 진입 비용" in (paid["derived_from"] or ""), True)

    # 「거래 없음」과 「청산 안 함」을 가른다.
    win = next(m for m in report["metrics"] if m["key"] == "win_rate")
    check("청산된 거래 없음이라 말한다", "청산된 거래 없음" in (win["absent_reason"] or ""), True)

    # 거래 목록에도 그 자리가 한 줄로 선다 — 세 곳이 같은 사실을 말한다.
    check("거래 목록에 열린 자리가 있다", len(report["trades"]), 1)
    check("청산 시각이 없다", report["trades"][0]["exit_ts"], None)


def test_old_run_with_open_position_does_not_claim_zero_cost() -> None:
    """진입 기록 없이 자리만 열린 옛 실행은 「치른 비용 0원」이라 답하지 않는다."""
    repo = FakeRepository(run_row(), open_equity_rows([1000.0, 1400.0], gross_exposure=1400.0), [])
    report = service(repo).select_report({"run_id": 7, "workspace_id": 1})

    op = report["open_position"]
    check("자리는 안다", op["count"], 1)
    check("진입 비용은 모른다", op["entry_cost"], None)
    paid = next(m for m in report["metrics"] if m["key"] == "cost_paid")
    check("치른 비용은 값이 없다", paid["value"], None)
    check("사유가 열린 자리를 말한다", "열린 자리" in (paid["absent_reason"] or ""), True)


def test_closed_run_has_no_open_position_field() -> None:
    """자리가 안 열린 실행은 `open_position` 이 `None` — 없는 자리를 만들지 않는다."""
    repo = FakeRepository(run_row(), equity_rows([100.0, 101.0, 102.0]), [])
    report = service(repo).select_report({"run_id": 7, "workspace_id": 1})
    check("열린 자리 없음", report["open_position"], None)


def main() -> int:
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        fn()
    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < 25:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
