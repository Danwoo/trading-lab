#!/usr/bin/env python3
"""격자 칸이 **「거래가 없었다」와 「낙폭이 0 이었다」를 가르는가** (#349).

## 왜 이 그물이 있나

한 번도 사지 않은 조합의 자산곡선은 시작 자금 그대로 평평하다. 그 곡선에서 나오는
「미회복 0봉 · 낙폭 0% · 수익률 +0.0%」를 숫자로 실어 보내면, 격자는 그 칸을 척도의
**가장 좋은 끝**으로 칠한다 — 조합을 고르러 온 사람이 격자만 보고 **아무것도 하지 않는
봇**을 고른다. 실측(#349): 5×5 격자 25칸 중 16칸이 그랬다.

「없는 값을 0 으로 뭉개지 않는다」(FR-021 · #268 · #285 · #291 · #314)가 성과 화면
한복판에서 깨진 자리다. 그래서 이 검사는 **서비스가 만드는 칸 지표**를 직접 태운다 —
응답 모델도 화면도 여기서 나온 dict 를 받아 쓴다.

DB 는 쓰지 않는다. 저장소·캔들 조회는 대역으로 세우고, 이 검사가 보는 것은
`BacktestService.run_grid` 가 칸마다 무엇을 실어 보내는가다.

    cd backend-service && APP_ENV=development uv run python tests/test_backtest_grid_cell_metrics.py
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from schemas.backtest.backtest_schema import GridCellMetricsOut, GridOut  # noqa: E402
from services.backtest.backtest_service import BacktestService  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0

#: 이 그물이 죽지 않았음을 보증하는 하한 — 단언이 이보다 적으면 실패로 끝낸다.
MIN_CHECKS = 30


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def fake_repository() -> SimpleNamespace:
    """저장소 대역 — run_id 를 세어 주고 쓰기는 건수만 돌려준다."""
    state = {"next_id": 0}

    def insert_run(_args) -> int:
        state["next_id"] += 1
        return state["next_id"]

    return SimpleNamespace(
        insert_run=insert_run,
        next_attempt_no=lambda *_a: 1,
        finish_run=lambda _args: None,
        insert_equity=lambda rows: len(rows),
        insert_trades=lambda rows: len(rows),
        insert_signals=lambda rows: len(rows),
        insert_cash_events=lambda rows: len(rows),
    )


def fake_bar_service(closes: list[float]) -> SimpleNamespace:
    """캔들 조회 대역. 항목 계약은 `time` 이다 (#217)."""
    start = dt.date(2026, 1, 1)
    items = [
        {
            "time": (start + dt.timedelta(days=i)).isoformat(),
            "open": c,
            "high": c,
            "low": c,
            "close": c,
            "volume": 1000,
        }
        for i, c in enumerate(closes)
    ]
    return SimpleNamespace(select_daily_bar_list=lambda _args: {"items": items, "total_count": len(items)})


def fake_strategy():
    """`threshold` 축으로 **거래 유무를 가르는** 전략.

    - `threshold == 0` → 한 번도 사지 않는다 (거래 0건 · 곡선이 평평하다)
    - `threshold == 1` → 사고 판다 (청산된 거래 1건)
    - `threshold == 2` → 사고 **안 판다** (구간 끝에 열린 자리 1건)

    셋을 한 격자에 담아야 「거래 없음」·「청산 안 함」·「정상」이 서로 다른 칸으로 나오는지
    한 번에 볼 수 있다 (#314 가 가른 두 상태를 여기서도 가른다).
    """
    return SimpleNamespace(
        STRATEGY={
            "key": "fixture",
            "name": "고정",
            "timeframe": "1d",
            "params": [{"name": "threshold"}],
            "version": "1",
        },
        indicators=lambda bars, params: {},
        entry=lambda ctx: ctx["params"]["threshold"] > 0 and ctx["index"] == 1,
        exit=lambda ctx: ctx["params"]["threshold"] == 1 and ctx["index"] == 4,
    )


def run_grid_cells() -> list[dict]:
    service = BacktestService(
        backtest_repository=fake_repository(),
        # 값이 오르내려야 낙폭·미회복이 0 이 아닌 값으로 나온다.
        bar_service=fake_bar_service([100, 110, 90, 95, 130, 120]),
        strategy_loader=lambda key: fake_strategy(),
    )
    out = service.run_grid(
        {
            "workspace_id": 4242,
            "strategy_key": "fixture",
            "market": "KR",
            "symbol": "TEST",
            "period_from": "2026-01-01",
            "period_to": "2026-01-06",
            "initial_cash": 1_000_000,
            "sweep": {"threshold": [0, 1, 2]},
            "costs": {"fee_rate": 0.0, "slippage_rate": 0.0, "sell_tax_rate": 0.0},
        }
    )
    # 응답 모델을 실제로 태운다 — 서비스가 만들어도 모델이 선언 안 하면 FastAPI 가 버린다 (#268).
    validated = GridOut(**out)
    check("격자가 3칸", len(validated.cells), 3)
    return out["cells"]


def test_no_trade_cell_reports_absence_not_zero() -> None:
    """거래 0건 칸은 지표 자리를 **비우고 사유를 싣는다** — 0 은 성적이 아니다."""
    cells = {c["params"]["threshold"]: c for c in run_grid_cells()}

    idle = cells[0]["metrics"]
    check("거래 0건 칸에도 지표 객체는 온다", idle is not None, True)
    check("청산된 거래 0건", idle["closed_trades"], 0)
    check("열린 자리도 0건", idle["open_positions"], 0)
    check("사유가 실린다", bool(idle["absent_reason"]), True)
    check("사유가 「거래」를 말한다", "거래" in (idle["absent_reason"] or ""), True)
    # **여기가 이 이슈의 핵심이다** — 네 값 전부가 0 이 아니라 None 이어야 한다.
    for key in ("longest_underwater", "still_underwater", "mdd_pct", "total_return_pct"):
        check(f"거래 0건 칸의 {key} 는 값이 없다", idle[key], None)
        check(f"거래 0건 칸의 {key} 가 0 으로 뭉개지지 않았다", idle[key] == 0, False)


def test_traded_cells_keep_their_numbers() -> None:
    """거래가 있는 칸의 값은 그대로다 — 그물이 멀쩡한 칸까지 비우면 안 된다."""
    cells = {c["params"]["threshold"]: c for c in run_grid_cells()}

    closed = cells[1]["metrics"]
    check("청산된 거래가 1건", closed["closed_trades"], 1)
    check("열린 자리는 없다", closed["open_positions"], 0)
    check("사유가 없다", closed["absent_reason"], None)
    check("미회복 기간이 숫자다", isinstance(closed["longest_underwater"], float), True)
    check("낙폭이 숫자다", isinstance(closed["mdd_pct"], float), True)
    check("실제로 낙폭이 있었다", closed["mdd_pct"] < 0, True)
    check("아직 회복 중인지 참거짓으로 온다", isinstance(closed["still_underwater"], bool), True)


def test_open_position_is_not_no_trade() -> None:
    """**「청산 안 함」은 「거래 없음」이 아니다** (#314).

    자리를 잡았으면 곡선이 실제로 움직였으므로 지표는 진짜 값이다 — 척도에 올린다.
    """
    cells = {c["params"]["threshold"]: c for c in run_grid_cells()}

    held = cells[2]["metrics"]
    check("청산된 거래는 0건", held["closed_trades"], 0)
    check("열린 자리가 1건", held["open_positions"], 1)
    check("사유 없이 값이 온다", held["absent_reason"], None)
    check("미회복 기간이 숫자다", isinstance(held["longest_underwater"], float), True)
    check("낙폭이 숫자다", isinstance(held["mdd_pct"], float), True)


def test_response_model_declares_every_key_the_service_makes() -> None:
    """서비스가 만드는 키를 응답 모델이 **하나도 안 버리는가** (#268 의 클래스).

    선언하지 않은 키는 FastAPI 가 조용히 버리고 화면은 그것을 `null` 로 본다 — 그때
    격자는 다시 「값 없음」을 알 방법을 잃는다.
    """
    declared = set(GridCellMetricsOut.model_fields)
    made: set[str] = set()
    for cell in run_grid_cells():
        if cell["metrics"] is not None:
            made |= set(cell["metrics"])

    check("서비스가 만드는 칸 지표 키가 있다", len(made) > 0, True)
    check("응답 모델이 안 버린다", sorted(made - declared), [])
    check("모델이 선언한 것을 서비스가 다 채운다", sorted(declared - made), [])


def main() -> int:
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        fn()
    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < MIN_CHECKS:
        print(f"::error::단언이 {CHECKED}건뿐이다 (하한 {MIN_CHECKS}) — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
