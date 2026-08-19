#!/usr/bin/env python3
"""백테스트 마이그레이션이 **실제 Postgres 에 적용되고** 스펙의 컬럼을 만드는지 확인한다.

## 왜 실제 DB 인가

마이그레이션은 돌려 보지 않으면 검증이 아니다. 구문이 맞아도 `server_default` 표현식·
`ondelete`·복합 PK·JSONB 는 실제 서버가 거부할 수 있고, 그때 알게 되는 자리는 배포다.

## 무엇을 대조하나

실험대 스펙 §6 「엔진이 남겨야 할 것」의 표. **그 표가 정본이고 이 목록은 사본이라**,
표를 고치면 여기도 고쳐야 한다 — 어긋나면 이 검사가 빨개진다.

`parent_run_id`·`attempt_no` 를 따로 단언하는 이유: 그 둘이 「무엇이 달라졌나」·
「몇 번째 시도인가」·「이력 복원」 셋을 동시에 떠받치는데, 없어도 나머지 컬럼만으로
테이블이 만들어져 **조용히 통과**하기 때문이다.

## 쓰는 법

    BACKTEST_TEST_DB_URL=postgresql+psycopg://u:p@host:port/db \
      uv run python scripts/verify_backtest_schema.py

URL 이 없으면 **건너뛴다(exit 0)** — `test: backend` 스위트는 DB 없이 돌기 때문이다.
건너뛴 것이 조용한 초록이 되지 않도록, 실제로 돌면 `REQUIRE=db 실행됨` 을 찍고
DB 잡의 CI 가 그 문구를 grep 한다.

**사람의 개발 DB 를 쓰지 마라.** 이 스크립트는 대상 DB 에 테이블을 만든다.
일회용 인스턴스를 띄워 가리켜라.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "app"))

#: 태울 마이그레이션 — **backtest 테이블을 건드리는 것 전부**를 소스에서 찾는다.
#: 한 파일을 핀으로 박아 두면 뒤에 붙는 것이 영원히 이 그물 밖으로 남는다 — 실제로 0016 의
#: `tax` 컬럼이 그렇게 빠졌고, 아래 `EXPECTED` 도 함께 낡았다.
MIGRATION_MARKER = "tn_backtest"

# 스펙 §6 표의 사본. 표를 고치면 여기도 고친다.
EXPECTED: dict[str, set[str]] = {
    "tn_backtest_run": {
        "run_id",
        "workspace_id",
        "parent_run_id",
        "attempt_no",
        "strategy_key",
        "strategy_version",
        "params",
        "universe_def",
        "universe_as_of",
        "data_snapshot_id",
        "adj_policy",
        "cost_assumptions",
        "period_from",
        "period_to",
        "initial_cash",
        "status",
    },
    "tn_backtest_equity": {"run_id", "dt", "equity", "cash", "position_count", "gross_exposure"},
    "tn_backtest_trade": {
        "run_id",
        "instrument_id",
        "side",
        "entry_ts",
        "exit_ts",
        "qty",
        "fill_price",
        "fee",
        "slippage",
        # 증권거래세 — 국내 명시 비용 중 가장 크다(0.15%). 이것이 없으면 「치른 비용」이
        # 가장 큰 항목을 빼고 답한다 (#271).
        "tax",
        "realized_pnl",
        "mae",
        "mfe",
    },
    "tn_backtest_signal": {"run_id", "dt", "instrument_id", "conditions", "factors", "passed"},
    "tn_backtest_cash": {"run_id", "dt", "event_kind", "amount"},
}

# 이 둘이 빠져도 테이블은 만들어진다 — 그래서 따로 단언한다.
LINEAGE = {"parent_run_id", "attempt_no"}

# 인덱스는 **마이그레이션과 ORM 모델 양쪽에** 있어야 한다.
#
# 한쪽에만 있으면 `alembic check` 가 「지워야 할 인덱스」로 읽어 드리프트로 잡는다 —
# 실제로 그렇게 CI 가 빨개졌다. 컬럼만 대조하면 그 자리가 안 보이므로 여기서도 센다.
EXPECTED_INDEXES: dict[str, set[str]] = {
    "tn_backtest_run": {"ix_backtest_run_workspace", "ix_backtest_run_parent"},
    "tn_backtest_trade": {"ix_backtest_trade_run"},
    "tn_backtest_signal": {"ix_backtest_signal_run"},
    "tn_backtest_cash": {"ix_backtest_cash_run"},
}


def load_migration():
    """backtest 테이블을 건드리는 마이그레이션들 — **체인 순서대로**. 없으면 `None`."""
    import importlib.util

    versions = BACKEND / "alembic" / "versions"
    modules, parents = {}, {}
    for path in sorted(versions.glob("[0-9]*.py")):
        if MIGRATION_MARKER not in path.read_text(encoding="utf-8"):
            continue
        spec = importlib.util.spec_from_file_location(f"_bt_schema_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[module.revision] = module
        parents[module.revision] = getattr(module, "down_revision", None)
    if not modules:
        print(f"::error::backtest 테이블을 다루는 마이그레이션을 0건 찾았다: {versions}", file=sys.stderr)
        return None

    order, remaining = [], dict(modules)
    while remaining:
        ready = [rev for rev in remaining if parents[rev] not in remaining]
        if not ready:
            print(f"::error::마이그레이션 순서를 정할 수 없다 (순환?): {sorted(remaining)}", file=sys.stderr)
            return None
        for rev in sorted(ready):
            order.append(rev)
            del remaining[rev]
    return [modules[rev] for rev in order]


def main() -> int:
    url = os.environ.get("BACKTEST_TEST_DB_URL")
    if not url:
        print("건너뜀: BACKTEST_TEST_DB_URL 없음 (DB 필요 검사)")
        return 0

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text

    migrations = load_migration()
    if migrations is None:
        return 1

    # 이 레포는 SQL 예외 로그에 파라미터 값이 새는 것을 막는다 — `test_sql_parameter_hiding` 이 강제.
    engine = create_engine(url, hide_parameters=True)
    schema = "bt_verify"

    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {schema}"))
        conn.execute(text(f"SET search_path TO {schema}"))

        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        ops._install_proxy()
        try:
            for migration in migrations:
                migration.upgrade()
        finally:
            ops._remove_proxy()

    problems: list[str] = []
    checked = 0
    with engine.connect() as conn:
        conn.execute(text(f"SET search_path TO {schema}"))
        insp = inspect(conn)
        present = set(insp.get_table_names(schema=schema))
        for table, columns in EXPECTED.items():
            if table not in present:
                problems.append(f"{table} 가 만들어지지 않았다")
                continue
            actual = {c["name"] for c in insp.get_columns(table, schema=schema)}
            for col in sorted(columns):
                checked += 1
                if col not in actual:
                    problems.append(f"{table}.{col} 가 없다 (스펙 §6 표)")

        for table, names in EXPECTED_INDEXES.items():
            if table not in present:
                continue
            actual = {i["name"] for i in insp.get_indexes(table, schema=schema)}
            for name in sorted(names):
                checked += 1
                if name not in actual:
                    problems.append(
                        f"{table} 에 인덱스 {name} 가 없다 — 마이그레이션과 ORM 모델 양쪽에 있어야 "
                        "alembic check 가 드리프트로 잡지 않는다"
                    )

        run_cols = (
            {c["name"] for c in insp.get_columns("tn_backtest_run", schema=schema)}
            if "tn_backtest_run" in present
            else set()
        )
        for col in sorted(LINEAGE):
            checked += 1
            if col not in run_cols:
                problems.append(
                    f"tn_backtest_run.{col} 가 없다 — 계보·시도 순번이 없으면 "
                    "「무엇이 달라졌나」·「몇 번째 시도인가」·「이력 복원」 셋이 계산 불가"
                )

    # downgrade 가 되돌리는지 — 되돌릴 수 없는 마이그레이션은 되돌리기 쉽지 않다.
    with engine.begin() as conn:
        conn.execute(text(f"SET search_path TO {schema}"))
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        ops._install_proxy()
        try:
            # 역순으로 내린다 — 뒤에 붙인 것부터 걷어야 의존이 안 깨진다.
            for migration in reversed(migrations):
                migration.downgrade()
        except Exception as exc:  # noqa: BLE001
            problems.append(f"downgrade 가 실패했다: {exc}")
        finally:
            ops._remove_proxy()

    with engine.connect() as conn:
        insp = inspect(conn)
        left = {t for t in insp.get_table_names(schema=schema) if t.startswith("tn_backtest")}
        checked += 1
        if left:
            problems.append(f"downgrade 후에도 남은 테이블: {sorted(left)}")

    with engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))

    print(f"테이블 {len(EXPECTED)}종 · 컬럼 단언 {checked}건 검사 (REQUIRE=db 실행됨)")

    if checked < 40:
        print(f"::error::단언이 {checked}건뿐이다 — 목록이 비었을 수 있다", file=sys.stderr)
        return 1

    if problems:
        for line in problems:
            print(f"::error::{line}", file=sys.stderr)
        return 1

    print("판정: 마이그레이션이 적용되고 스펙 §6 의 컬럼이 전부 있다 · downgrade 가 되돌린다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
