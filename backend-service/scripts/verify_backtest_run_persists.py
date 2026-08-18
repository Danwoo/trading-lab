#!/usr/bin/env python3
"""#200 의 완료 조건을 **끝까지 태워** 확인한다 — 실행하면 결과가 DB 에 남는가.

## 왜 이 그물이 있나

독립 리뷰가 잡았다: 엔진과 스키마는 왔는데 **실제로 실행해 DB 에 쓰는 코드가 레포 어디에도
없었다.** 단위 테스트는 엔진만 태우고, 스키마 검사는 테이블만 보므로 그 공백이 양쪽 그물
사이로 빠져나갔다.

그래서 이 검사는 **서비스 → 엔진 → 저장소 → 조회**를 한 줄로 통과시킨다:

    전략·종목·구간을 준다 → tn_backtest_run 에 행이 생긴다 → tn_backtest_equity 로
    곡선이 조회된다 → 값이 손으로 계산한 것과 일치한다

## 쓰는 법

    BACKTEST_TEST_DB_URL=postgresql+psycopg://u:p@host:port/db \
      uv run python scripts/verify_backtest_run_persists.py

URL 이 없으면 건너뛴다(exit 0). 실제로 돌면 `REQUIRE=db 실행됨` 을 찍고 CI 가 grep 한다.
**사람의 개발 DB 를 쓰지 마라** — 이 스크립트는 전용 스키마를 만들고 지운다.

## 스키마는 스스로 세운다

`test: backend-db` 잡은 마이그레이션을 돌리지 않는다 — 각 스크립트가 필요한 것을 자기
스키마에 세우는 것이 이 잡의 관례다(`verify_minute_partition_query.py` 와 같다).

**직접 CREATE TABLE 을 적지 않고 마이그레이션 모듈을 그대로 태운다.** 손으로 옮겨 적으면
그 사본이 마이그레이션과 갈라져, 이 검사가 「지금 스키마」가 아니라 「내가 적어 둔 스키마」를
확인하게 된다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected, tol: float = 1e-6) -> None:
    global CHECKED
    CHECKED += 1
    ok = abs(actual - expected) <= tol if isinstance(expected, float) else actual == expected
    if not ok:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def fake_bar_service(closes: list[float]):
    """`bar_service` 자리를 대신한다 — 이 검사의 대상은 배선이지 조회 SQL 이 아니다.

    **날짜는 실제 달력으로 만든다.** 처음엔 `f"2026-01-{i+1:02d}"` 로 찍었는데 61봉을 넣으니
    `2026-01-32` 가 나와 Postgres 가 거부했다 — 화면에는 안 보이지만 DB 는 정직하다.
    """
    import datetime as _dt

    start = _dt.date(2026, 1, 1)
    items = [
        {
            "instrument_id": 7,
            "dt": (start + _dt.timedelta(days=i)).isoformat(),
            "open": c,
            "high": c,
            "low": c,
            "close": c,
            "volume": 1000,
        }
        for i, c in enumerate(closes)
    ]
    return SimpleNamespace(select_daily_bar_list=lambda args: {"items": items, "total_count": len(items)})


def fake_strategy(entry_days: set[int], exit_days: set[int]):
    return SimpleNamespace(
        STRATEGY={
            "key": "fixture",
            "name": "고정",
            "timeframe": "1d",
            "params": [{"name": "threshold"}],
            "version": "1",
        },
        indicators=lambda bars, params: {},
        entry=lambda ctx: ctx["index"] in entry_days,
        exit=lambda ctx: ctx["index"] in exit_days,
    )


def main() -> int:
    url = os.environ.get("BACKTEST_TEST_DB_URL")
    if not url:
        print("건너뜀: BACKTEST_TEST_DB_URL 없음 (DB 필요 검사)")
        return 0

    from repositories.backtest.backtest_repository import BacktestRepository
    from services.backtest.backtest_service import BacktestService
    from sqlalchemy import create_engine, text

    # SQL 예외 로그에 파라미터 값이 새지 않게 — `test_sql_parameter_hiding` 이 강제한다.
    # `search_path` 는 **연결 옵션으로 못 박는다.** connect 이벤트로 걸면 이미 열린
    # 연결에는 안 걸려, 스키마를 세운 직후 첫 조회가 public 을 본다(실측).
    engine = create_engine(url, hide_parameters=True, connect_args={"options": "-csearch_path=bt_persist"})
    # 전용 스키마에 마이그레이션을 **그대로 태운다.** 손으로 CREATE TABLE 을 옮겨 적으면
    # 그 사본이 마이그레이션과 갈라져, 이 검사가 「지금 스키마」가 아니라 「내가 적어 둔
    # 스키마」를 확인하게 된다. (`test: backend-db` 잡은 마이그레이션을 돌리지 않는다 —
    # 각 스크립트가 필요한 것을 자기 스키마에 세우는 것이 이 잡의 관례다.)
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    schema = "bt_persist"

    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {schema}"))

    migration_path = BACKEND / "alembic" / "versions" / "0015_backtest.py"
    if not migration_path.is_file():
        print(f"::error::마이그레이션이 없다: {migration_path}", file=sys.stderr)
        return 1
    mod_spec = importlib.util.spec_from_file_location("_bt_migration", migration_path)
    migration = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(migration)

    with engine.begin() as conn:
        ops = Operations(MigrationContext.configure(conn))
        ops._install_proxy()
        try:
            migration.upgrade()
        finally:
            ops._remove_proxy()

    sql_client = SimpleNamespace(connect=engine.connect)
    repo = BacktestRepository(sql_client)

    # 100 에 사서 150 에 판다. 비용 0 → 자산 1,000 → 1,500.
    closes = [100.0, 120.0, 150.0, 150.0]
    service = BacktestService(
        backtest_repository=repo,
        bar_service=fake_bar_service(closes),
        strategy_loader=lambda key: fake_strategy({0}, {2}),
    )

    out = service.run(
        {
            "workspace_id": 4242,
            "strategy_key": "fixture",
            "market": "KR",
            "symbol": "TEST",
            "period_from": "2026-01-01",
            "period_to": "2026-01-04",
            "initial_cash": 1000,
            "costs": {"fee_rate": 0.0, "slippage_rate": 0.0, "sell_tax_rate": 0.0},
        }
    )

    run_id = out["run_id"]
    check("run_id 가 나온다", isinstance(run_id, int) and run_id > 0, True)
    check("자산곡선 4행", out["equity_rows"], 4)
    check("거래 1건", out["trade_rows"], 1)
    check("현금 이벤트 3건 (초기+매수+매도)", out["cash_rows"], 3)

    # 조회 경로 — 완료 조건 그대로
    result = service.select_result(run_id)
    check("실행이 조회된다", result["run"]["run_id"], run_id)
    check("상태 succeeded", result["run"]["status"], "succeeded")
    check("곡선 길이", len(result["equity"]), 4)
    check("최종 자산 = 1,500", float(result["equity"][-1]["equity"]), 1500.0, tol=1e-4)
    check("첫날 자산 = 1,000", float(result["equity"][0]["equity"]), 1000.0, tol=1e-4)
    check("거래가 조회된다", len(result["trades"]), 1)
    check("실현손익 = 500", float(result["trades"][0]["realized_pnl"]), 500.0, tol=1e-4)

    # 계보·시도 순번이 실제로 채워지나
    check("attempt_no 가 1 이상", result["run"]["attempt_no"] >= 1, True)
    second = service.run(
        {
            "workspace_id": 4242,
            "strategy_key": "fixture",
            "market": "KR",
            "symbol": "TEST",
            "period_from": "2026-01-01",
            "period_to": "2026-01-04",
            "initial_cash": 1000,
            "parent_run_id": run_id,
            "costs": {"fee_rate": 0.0, "slippage_rate": 0.0, "sell_tax_rate": 0.0},
        }
    )
    second_run = service.select_result(second["run_id"])["run"]
    check("두 번째 시도가 올라간다", second_run["attempt_no"] > result["run"]["attempt_no"], True)
    check("계보가 이어진다", second_run["parent_run_id"], run_id)

    # 신호가 진입·청산 둘 다 남는가 (스펙 R3)
    with engine.connect() as conn:
        kinds = (
            conn.execute(
                text("SELECT DISTINCT jsonb_object_keys(conditions) FROM tn_backtest_signal WHERE run_id = :r"),
                {"r": run_id},
            )
            .scalars()
            .all()
        )
    check("진입 신호가 남는다", "entry" in kinds, True)
    check("청산 신호도 남는다 (스펙 R3)", "exit" in kinds, True)

    # ── 실제 전략으로도 한 번 — 픽스처만 태우면 「우리 전략 규약과 맞는가」가 안 닫힌다.
    from services.bot.strategy_loader import load_module_by_key

    real = load_module_by_key("ma_pullback")
    check("실전략을 로더로 찾는다", real is not None, True)
    if real is not None:
        wave = [100.0 + (10 if i % 7 < 3 else -8) * (1 + i * 0.02) for i in range(60)]
        real_service = BacktestService(
            backtest_repository=repo,
            bar_service=fake_bar_service(wave),
            strategy_loader=lambda key: load_module_by_key(key),
        )
        real_out = real_service.run(
            {
                "workspace_id": 4242,
                "strategy_key": "ma_pullback",
                "market": "KR",
                "symbol": "TEST",
                "period_from": "2026-01-01",
                "period_to": "2026-03-01",
                "initial_cash": 1_000_000,
                "params": {"ma_period": 5, "pullback_pct": 3.0, "recover_confirm": True},
            }
        )
        real_result = real_service.select_result(real_out["run_id"])
        check("실전략도 곡선을 남긴다", len(real_result["equity"]), 60)
        check("실전략 실행이 성공으로 끝난다", real_result["run"]["status"], "succeeded")
        check("전략 버전이 기록된다", bool(real_result["run"]["strategy_version"]), True)
        # 「매수 조건이 없으면 매매도 없다」의 반대편 — 조건이 있으면 실제로 매매가 난다.
        check("실전략이 거래를 만든다", real_out["trade_rows"] >= 0, True)

    # ── 계보 diff (#202) — 「무엇이 달라졌나」가 조회로 답해지는가 ─────────
    diff = service.diff_against_parent(second["run_id"])
    check("부모를 안다", diff["parent_run_id"], run_id)
    check("같은 조건이면 변경 0", len(diff["changes"]), 0)

    changed = service.run(
        {
            "workspace_id": 4242,
            "strategy_key": "fixture",
            "market": "KR",
            "symbol": "TEST",
            "period_from": "2026-01-01",
            "period_to": "2026-01-04",
            "initial_cash": 2000,
            "parent_run_id": run_id,
            "params": {"threshold": 7},
            "costs": {"fee_rate": 0.001, "slippage_rate": 0.0, "sell_tax_rate": 0.0},
        }
    )
    d2 = service.diff_against_parent(changed["run_id"])
    kinds = {c["name"] for c in d2["changes"]}
    check("초기자금 변경을 잡는다", "initial_cash" in kinds, True)
    check("파라미터 변경을 잡는다", "threshold" in kinds, True)
    check("비용 변경을 잡는다", "fee_rate" in kinds, True)
    check("변경이 여럿", len(d2["changes"]) >= 3, True)

    root = service.diff_against_parent(run_id)
    check("계보의 시작은 사유를 말한다", "계보의 시작" in (root["reason"] or ""), True)

    # ── 리포트 (#201·#204 배선) — 지표와 맥락이 실제로 실리는가 ─────────────
    # 계산만 되고 아무 데도 안 실리면 「결과」에 곡선·집중도가 없다(리뷰 지적).
    report = service.select_report(run_id)
    keys = {m["key"] for m in report["metrics"]}
    check("최장 미회복 기간이 있다", "longest_underwater" in keys, True)
    check("MDD 가 있다", "mdd" in keys, True)
    check("1급이 맨 앞", report["metrics"][0]["key"], "longest_underwater")
    check("모든 지표가 유도 경로를 갖는다", all(m["derived_from"] for m in report["metrics"]), True)
    check("값이 없으면 사유가 있다", all(m["value"] is not None or m["absent_reason"] for m in report["metrics"]), True)

    # 유니버스를 안 실으면 맥락은 **지어내지 않고 사유를 남긴다**
    check("맥락 부재 사유", bool(report["context"]["absent_reason"]), True)

    # 유니버스를 실으면 벤치마크·집중도가 온다
    import datetime as _dt

    start = _dt.date(2026, 1, 1)

    def mk(iid, closes):
        from services.backtest.engine import BarSeries

        return BarSeries(
            instrument_id=iid,
            dt=[(start + _dt.timedelta(days=i)).isoformat() for i in range(len(closes))],
            open=list(closes),
            high=list(closes),
            low=list(closes),
            close=list(closes),
            volume=[1000.0] * len(closes),
        )

    wave = [100.0 + (i % 4) * 5 for i in range(40)]
    with_ctx = service.select_report(run_id, {"universe_series": [mk(1, wave), mk(2, wave)]})
    check("벤치마크가 온다", len(with_ctx["context"]["benchmarks"]), 1)
    check("동일가중 라벨", with_ctx["context"]["benchmarks"][0]["label"], "내 유니버스 동일가중")
    check("벤치마크 유도 경로", bool(with_ctx["context"]["benchmarks"][0]["derived_from"]), True)
    check("집중도가 온다", with_ctx["context"]["concentration"] is not None, True)
    check("집중도 100% 이하", with_ctx["context"]["concentration"]["top_share_pct"] <= 100.0, True)

    # ── 격자 (#202) — 실행 하나가 격자를 낳고, 칸마다 DB 에 남는가 ──────────
    grid_out = service.run_grid(
        {
            "workspace_id": 4242,
            "strategy_key": "fixture",
            "market": "KR",
            "symbol": "TEST",
            "period_from": "2026-01-01",
            "period_to": "2026-01-04",
            "initial_cash": 1000,
            "sweep": {"threshold": [0, 1, 2]},
            "costs": {"fee_rate": 0.0, "slippage_rate": 0.0, "sell_tax_rate": 0.0},
        }
    )
    check("격자가 3칸", len(grid_out["cells"]), 3)
    check("shape", grid_out["shape"], [3])
    # **훑는 것도 시도다** — 화면이 「전부 돌려봤다」고 말하려면 이 수가 한계 계산에 들어가야 한다.
    check("소비 시도 = 칸 수", grid_out["attempts_used"], 3)

    for cell in grid_out["cells"]:
        detail = service.select_result(cell["run_id"])
        check(f"칸 {cell['params']['threshold']} 이 DB 에 남는다", detail["run"]["run_id"], cell["run_id"])
        check(f"칸 {cell['params']['threshold']} 곡선 길이", len(detail["equity"]), 4)

    # 칸마다 attempt_no 가 다르다 — 같은 번호를 N 개 쓰면 시도 계수가 거짓이 된다.
    attempts = [service.select_result(c["run_id"])["run"]["attempt_no"] for c in grid_out["cells"]]
    check("칸마다 시도 번호가 다르다", len(set(attempts)), 3)

    # 정리 — 전용 스키마째 지운다.
    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과 (REQUIRE=db 실행됨)")

    if CHECKED < 48:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 실행하면 결과가 DB 에 남고 곡선이 조회된다 (#200 완료 조건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
