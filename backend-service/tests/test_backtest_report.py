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


def service(repo: FakeRepository) -> BacktestService:
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


def main() -> int:
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        fn()
    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < 10:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
