#!/usr/bin/env python3
"""분봉 파티션 커버리지 SQL 을 **진짜 Postgres 에 태운다**.

## 왜 이 그물이 따로 필요한가

`IngestRepository.select_minute_partition_range()` 는 `pg_get_expr` 이 렌더링한 파티션 경계
문자열을 정규식으로 파싱한다. 그 문자열의 **정확한 모양은 Postgres 가 정한다** — 파이썬 쪽
단위 테스트는 레포지토리를 대역으로 갈아 끼우므로 이 SQL 이 DB 앞에 한 번도 서지 않는다.

실제로 그렇게 새어 나갔다: `ts` 가 `timestamp` 라 경계가 `FROM ('2026-08-01 00:00:00')` 로
렌더링되는데 정규식이 날짜 뒤에 닫는 인용부호를 기대해 **매치가 통째로 실패**했다. 그러면
`MIN`/`MAX` 가 NULL 이 되고, 호출부는 「파티션이 없다」로 읽어 **정상 구간 요청까지 전부
거절**했다 — 고치려던 것보다 나빠진 상태였다(PR #182 독립 리뷰가 실제 DB 로 잡았다).

## 무엇을 하나

임시 스키마에 같은 구조(`PARTITION BY RANGE (ts timestamp)`)를 만들고 SQL 원문을 돌려,
경계가 **날짜로 파싱되는지** 확인한 뒤 되돌린다. 운영 테이블은 건드리지 않는다.

    cd backend-service && uv run python scripts/verify_minute_partition_query.py
    (DB URL 은 MINUTE_PARTITION_TEST_DB_URL 또는 BACKEND_TEST_DB_URL)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# 이 스크립트는 `backend-service/scripts/` 에 산다 — 그 CI 잡의 `working-directory` 가
# `backend-service` 이고 옆 검증들이 다 여기 있다. 루트에 두면 CI 가 파일을 못 찾는다(실측).
BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND / "app" / "repositories" / "ingest" / "ingest_repository.py"
SCHEMA = "minute_partition_probe"


def extract_sql() -> str:
    """레포지토리에서 SQL 원문을 **그대로** 떼어 온다 — 여기 복제하면 두 벌이 되어 갈린다.

    파싱이 아니라 **AST 로 읽는다.** 문자열 접두(raw 등)나 포맷터의 줄바꿈에 흔들리지 않게 —
    첫 판은 대입문을 문자열로 찾다가 ruff 가 raw 문자열로 바꾸자 바로 깨졌다.
    """
    import ast

    tree = ast.parse(REPOSITORY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "select_minute_partition_range":
            continue
        for stmt in ast.walk(node):
            if (
                isinstance(stmt, ast.Assign)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
                and "pg_inherits" in stmt.value.value
            ):
                return stmt.value.value
    raise SystemExit("::error::SQL 을 못 떼어 왔다 — 레포지토리 구조가 바뀌었는지 보라")


def main() -> int:
    url = os.environ.get("MINUTE_PARTITION_TEST_DB_URL") or os.environ.get("BACKEND_TEST_DB_URL")
    if not url:
        # **DB 없이는 건너뛴다** — 이 파일은 `test: backend` 스위트(DB 없음)와 `test: backend`
        # 잡(DB 있음)에 **둘 다** 걸린다. 옆 DB 스크립트들의 관례가 그것이다.
        #
        # 그래서 「조용히 초록」이 될 수 있다 — 그 위험을 CI 쪽에서 막는다: backend-db 잡이
        # URL 을 주고 부르므로, 그 잡에서 이 검사가 실제로 돌지 않으면 아래 REQUIRE 표식이
        # 없는 출력이 남는다. 여기서 exit 1 로 두면 DB 없는 스위트가 통째로 빨개진다.
        print(
            "MINUTE_PARTITION_TEST_DB_URL 이 없어 건너뜁니다 — "
            "이 검사는 실제 Postgres 가 있어야 의미가 있습니다 (test: backend 잡이 돌립니다).",
        )
        return 0

    try:
        import psycopg
    except ImportError:
        print("::error::psycopg 가 없다", file=sys.stderr)
        return 1

    sql = extract_sql().replace("tn_minute_bar", f"{SCHEMA}_bar")
    print(f"레포지토리에서 떼어 온 SQL {len(sql.strip().splitlines())}줄을 실제 DB 에 태운다")

    with psycopg.connect(url, autocommit=False) as conn, conn.cursor() as cur:
        try:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
            cur.execute(f"SET search_path TO {SCHEMA}, public")
            # 운영과 같은 축: RANGE (ts) · ts 는 timestamp
            cur.execute(f"CREATE TABLE {SCHEMA}_bar (instrument_id int, ts timestamp) PARTITION BY RANGE (ts)")
            for year, month, nxt_y, nxt_m in [(2026, 8, 2026, 9), (2026, 9, 2026, 10)]:
                cur.execute(
                    f"CREATE TABLE {SCHEMA}_bar_{year}_{month:02d} PARTITION OF {SCHEMA}_bar "
                    f"FOR VALUES FROM ('{year}-{month:02d}-01') TO ('{nxt_y}-{nxt_m:02d}-01')"
                )
            rendered = cur.execute(
                "SELECT pg_get_expr(c.relpartbound, c.oid) FROM pg_class c "
                "JOIN pg_inherits i ON i.inhrelid=c.oid JOIN pg_class p ON p.oid=i.inhparent "
                f"WHERE p.relname='{SCHEMA}_bar' LIMIT 1"
            ).fetchone()[0]
            print(f"  Postgres 가 렌더링한 경계: {rendered}")

            low, high = cur.execute(sql).fetchone()
            print(f"  SQL 이 뽑은 구간: {low} ~ {high}")
        finally:
            conn.rollback()
            with conn.cursor() as clean:
                clean.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
            conn.commit()

    date = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if low is None or high is None:
        print(
            f"::error::경계가 NULL 이다 — 정규식이 실제 렌더링 형식과 안 맞는다. 렌더링: {rendered}",
            file=sys.stderr,
        )
        return 1
    if not (date.match(low) and date.match(high)):
        print(f"::error::경계가 날짜가 아니다: {low!r} ~ {high!r}", file=sys.stderr)
        return 1
    if (low, high) != ("2026-08-01", "2026-10-01"):
        print(
            f"::error::경계가 기대와 다르다: {low} ~ {high} (기대 2026-08-01 ~ 2026-10-01)",
            file=sys.stderr,
        )
        return 1

    print("판정: 파티션 경계가 날짜로 정확히 파싱된다 (REQUIRE=db 실행됨)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
