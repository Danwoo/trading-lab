"""리비전 `0019` 의 `USING` 술어가 기원별로 옳은 인스턴트를 내는지 진짜 Postgres 에 태운다 (#359).

## 왜 별도 검사인가

드리프트 검사는 **빈 DB** 에 마이그레이션을 올린다 — 그래서 `USING` 절이 값을 어떻게
해석하는지는 한 번도 실행되지 않는다. 이 리비전의 위험은 DDL 구문이 아니라 **기존 값의 뜻**에
있으므로, 그 자리를 따로 봐야 한다.

## 무엇을 하나

스크래치 테이블에 **두 기원의 픽스처**를 같은 인스턴트로 넣는다 — seed·`CURRENT_TIMESTAMP` 가
쓴 것처럼 서버 tz 벽시계 자릿수인 행 하나, Prisma·Better Auth 가 쓴 것처럼 UTC 자릿수인 행
하나. 그 위에 **리비전과 같은 함수**(`to_timestamptz_sql`·`to_naive_sql`·`origin_tz_expression`)
로 만든 SQL 을 그대로 적용해:

  (1) 두 행이 **같은 인스턴트**가 되는지 — 이것이 이슈 #359 가 없애려는 9시간 간극이다.
  (2) 되돌리면 **원래 자릿수**가 복원되는지 — `downgrade()` 가 값을 잃지 않는다는 계약.
  (3) 판정이 **세션 tz 와 무관**한지 — 일부러 다른 세션 tz 로 붙여도 결과가 같아야 한다.

리비전의 함수를 import 해서 쓰는 이유는 두 벌이 갈리지 않게 하기 위해서다 — 검사가 자기
버전의 SQL 을 들고 있으면 리비전이 바뀌어도 초록으로 남는다(`0007`·`kst_timestamp_correction.py`
와 같은 규약).

**단언 건수가 기대치에 못 미치면 실패한다**(fail-closed).

    TIMESTAMPTZ_USING_TEST_DB_URL=postgresql://ci:ci@localhost:5432/ci \\
      uv run python scripts/verify_timestamptz_using.py --i-know-this-drops-tables   (cwd=backend-service)

`--i-know-this-drops-tables` 는 이 스크립트가 자기 스크래치 테이블을 DROP 하기 때문이다 —
`vt_0019_*` 접두사만 건드리고 앱 테이블은 손대지 않는다.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REVISION = BACKEND / "alembic" / "versions" / "0019_timestamptz_audit_columns.py"

SCRATCH_SCHEMA = "public"
SCRATCH_TABLE = "vt_0019_origin_probe"

# 기준 인스턴트와 두 기원의 자릿수. 서버 tz 는 아래에서 Asia/Seoul 로 고정해 재현 가능하게 한다.
FIXTURE_SRC_TZ = "Asia/Seoul"
INSTANT_UTC = "2026-08-23 02:23:47.504"
SEED_WALL_CLOCK = "2026-08-23 11:23:47.504"  # 같은 순간을 Asia/Seoul 벽시계로 적은 것

EXPECTED_ASSERTIONS = 8


def _load_revision():
    spec = importlib.util.spec_from_file_location("rev0019", REVISION)
    if spec is None or spec.loader is None:
        raise SystemExit(f"::error::리비전을 읽지 못했다: {REVISION}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_sql(rev) -> str:
    actors = ", ".join(f"'{actor}'" for actor in rev.NON_APP_ACTORS)
    return f"""
        DROP TABLE IF EXISTS {SCRATCH_SCHEMA}.{SCRATCH_TABLE};
        CREATE TABLE {SCRATCH_SCHEMA}.{SCRATCH_TABLE} (
            id      integer PRIMARY KEY,
            reg_id  varchar(100),
            reg_dt  timestamp
        );
        INSERT INTO {SCRATCH_SCHEMA}.{SCRATCH_TABLE} VALUES
            (1, {actors.split(",")[0].strip()}, TIMESTAMP '{SEED_WALL_CLOCK}'),
            (2, 'user@example.com',              TIMESTAMP '{INSTANT_UTC}');
    """


def _run(conn, session_tz: str, rev) -> tuple[int, list[str]]:
    """한 세션 tz 에서 전환 → 대조 → 복원 → 대조. (단언 수, 실패 목록)"""
    checked = 0
    failures: list[str] = []
    label = f"세션 tz={session_tz}"

    conn.execute(f"SET TIME ZONE '{session_tz}'")
    conn.execute(_fixture_sql(rev))

    conn.execute(rev.to_timestamptz_sql(SCRATCH_SCHEMA, SCRATCH_TABLE, "reg_dt", rev.ACTOR, FIXTURE_SRC_TZ, None))

    rows = dict(conn.execute(f"SELECT id, reg_dt AT TIME ZONE 'UTC' FROM {SCRATCH_SCHEMA}.{SCRATCH_TABLE}").fetchall())
    # 값으로 비교한다 — 문자열로 대조하면 마이크로초 표기(.504 vs .504000)만으로 빨개진다.
    expected_instant = datetime.fromisoformat(INSTANT_UTC)
    for row_id, origin in ((1, "seed(서버 tz 벽시계)"), (2, "앱(UTC 자릿수)")):
        checked += 1
        if rows[row_id] != expected_instant:
            failures.append(f"{label}: {origin} 행이 {expected_instant} 가 아니라 {rows[row_id]}")
    checked += 1
    if rows[1] != rows[2]:
        failures.append(f"{label}: 두 기원이 같은 인스턴트가 아니다 — {rows[1]} vs {rows[2]}")

    conn.execute(rev.to_naive_sql(SCRATCH_SCHEMA, SCRATCH_TABLE, "reg_dt", rev.ACTOR, FIXTURE_SRC_TZ, None))
    restored = dict(conn.execute(f"SELECT id, reg_dt FROM {SCRATCH_SCHEMA}.{SCRATCH_TABLE}").fetchall())
    for row_id, expected in ((1, SEED_WALL_CLOCK), (2, INSTANT_UTC)):
        checked += 1
        expected_naive = datetime.fromisoformat(expected)
        if restored[row_id] != expected_naive:
            failures.append(f"{label}: 되돌린 뒤 id={row_id} 자릿수가 {expected_naive} 가 아니라 {restored[row_id]}")

    conn.execute(f"DROP TABLE {SCRATCH_SCHEMA}.{SCRATCH_TABLE}")
    return checked, failures


def main() -> int:
    import os

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--i-know-this-drops-tables", action="store_true", dest="consent")
    args = parser.parse_args()

    url = os.environ.get("TIMESTAMPTZ_USING_TEST_DB_URL") or os.environ.get("BACKEND_TEST_DB_URL")
    if not url:
        print(
            "TIMESTAMPTZ_USING_TEST_DB_URL 이 없어 건너뜁니다 — "
            "이 검사는 실제 Postgres 가 있어야 의미가 있습니다 (test: backend-db 잡이 돌립니다).",
        )
        return 0
    if not args.consent:
        print(f"::error::--i-know-this-drops-tables 가 필요하다 ({SCRATCH_TABLE} 을 DROP 한다)", file=sys.stderr)
        return 1

    import psycopg

    rev = _load_revision()
    print("0019 USING 술어 검증 (기원별 해석 · 되돌리기 · 세션 tz 무관)")

    checked = 0
    failures: list[str] = []
    with psycopg.connect(url, autocommit=True) as conn:
        # 세션 tz 를 셋으로 바꿔 가며 같은 판정을 돌린다 — USING 이 세션 tz 를 안 탄다는 것이 계약.
        for session_tz in ("Asia/Seoul", "UTC", "America/New_York"):
            n, f = _run(conn, session_tz, rev)
            checked += n
            failures += f
            if not f:
                print(f"  ✓ 세션 tz={session_tz}: 두 기원이 {INSTANT_UTC}Z 로 모이고, 되돌리면 원 자릿수 복원")

    print(f"검사한 단언 {checked}건 (하한 {EXPECTED_ASSERTIONS}건)")
    if checked < EXPECTED_ASSERTIONS:
        print(f"::error::단언이 {checked}건뿐이다 — 검사가 대상을 다 못 봤다(fail-closed)", file=sys.stderr)
        return 1
    for line in failures:
        print(f"  ✗ {line}")
    if failures:
        print("::error::USING 술어가 기원별로 옳은 인스턴트를 내지 않는다", file=sys.stderr)
        return 1

    print("판정: 자릿수의 뜻은 행 기원이 정하고, 세션 tz 는 결과를 바꾸지 못한다 (REQUIRE=db 실행됨)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
