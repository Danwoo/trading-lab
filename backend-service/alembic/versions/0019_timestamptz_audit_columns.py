"""timestamptz_audit_columns — 감사·운영 시각 75컬럼을 timestamptz 로 옮긴다 (#359)

Revision ID: 0019_timestamptz_audit_columns
Revises: 0018_backtest_costless_summary
Create Date: 2026-08-25

## 무엇을 옮기나

`public` 40 + `frontend` 35 = **75 컬럼**. 감사(`reg_dt`·`mod_dt`·`createdAt`·`updatedAt`)와
운영(`ingested_at`·`started_dt`·`finished_dt`·`*expiresAt`) 컬럼이다. **업무 시각 컬럼은 안
옮긴다** — `tn_minute_bar.ts`·`tn_backtest_trade.entry_ts`/`exit_ts`·`tn_nav.nav_dt` 는
2026-07-30 결정으로 「시장 현지 벽시계」라는 뜻이 이미 붙어 있고, tz 를 붙이면 그 계약이 깨진다.

`frontend` 스키마는 Prisma 소유인데도 이 리비전이 옮긴다(0007 선례). Prisma `db push` 는 이
타입 변경을 SafeCast 로 분류해 **`USING` 절 없이** `SET DATA TYPE TIMESTAMPTZ(3)` 을 조용히
실행하고, 그러면 naive 자릿수를 push 커넥션의 세션 tz 로 **일괄** 해석한다. 한 컬럼에 두 기원이
섞인 `frontend` 11개 테이블에서는 어느 세션 tz 로 돌려도 절반이 틀린다.

## 기존 값의 뜻 — 행 기원으로 가른다

naive 자릿수 자체에는 tz 표식이 없으므로, 그 자릿수를 **무엇이 썼는가**로 뜻을 정한다:

- `CURRENT_TIMESTAMP`·`now()`·seed.sql·DDL `DEFAULT now()` 가 쓴 값 → **DB 서버 tz 벽시계**
  (`src_tz`). `public` 전부와 `frontend.ai_chat_history` 가 여기다.
- Prisma·Better Auth 가 `new Date()` 로 쓴 값 → **UTC 자릿수**. 어댑터가 UTC getter 로 만든
  오프셋 없는 문자열을 naive 컬럼에 넣기 때문에 세션 tz 와 무관하게 UTC 다.
- `frontend` 11개 테이블은 **한 컬럼 안에 둘이 섞여 있다** — seed(`MGR`)·백필(`migration`) 행은
  서버 tz, 나머지는 UTC. 판정은 0007 과 같은 술어를 쓴다: `reg_id`/`mod_id` 가 `MGR`·`migration`
  이면 서버 tz, 그 밖(NULL 포함)이면 UTC. 컬럼 단위 판정이라 같은 행이라도 `reg_dt` 는 seed 값,
  `mod_dt` 는 앱 값일 수 있다.

`0007_kst_write_shift_correction` 의 docstring 은 「시드 = 참값」을 전제로 썼는데, 그 전제는
**세션 tz 가 UTC 인 배포에서만** 참이었다. 서버 tz 가 KST 인 로컬 스택에서는 시드 행이 KST
벽시계로 들어가 있다 — 그래서 이 리비전은 「시드 = UTC」가 아니라 「시드 = 서버 tz」로 읽는다.

## `src_tz` 를 어디서 받나

1. 기본: `SELECT reset_val FROM pg_settings WHERE name='TimeZone'` — alembic 커넥션은 세션 tz
   옵션을 박지 않으므로(`alembic/env.py` 를 일부러 안 건드린다) 서버·DB 기본값이 그대로 온다.
   로컬 pgserver 는 initdb 가 적은 `Asia/Seoul`, 도커·CI 는 `UTC` 라 **지금 존재하는 모든
   DB 에서 맞는 값**이다.
2. 덮어쓰기: env `ALEMBIC_NAIVE_SOURCE_TZ`. 서버 tz 를 DB 수명 중 바꾼 적이 있으면 코드가 알
   수 없으므로 사람이 준다. 둘 다 로그에 남기고, 값이 다르면 경고를 찍는다.

`src_tz` 를 실제보다 **동쪽**으로 잘못 주면(KST DB 에 `UTC`) 감사 시각이 미래로 간다 — 아래
사후 검사가 같은 트랜잭션에서 잡아 통째로 롤백한다. **서쪽** 오류(UTC DB 에 `Asia/Seoul`)는
9시간 과거로 가 이 검사에 안 걸리므로 `scripts/timestamptz_migration_check.py` 의 snapshot/diff
로 대조한다.

## 되돌리기

`downgrade()` 는 **같은 술어·같은 `src_tz`** 로 `TYPE timestamp USING (c AT TIME ZONE <기원별 tz>)`
을 돌려 원래 자릿수를 복원한다 — 판정에 쓰는 `reg_id`/`mod_id` 를 이 리비전이 건드리지 않으므로
up/down 이 같은 행 집합을 가리킨다. 세션 tz 와 무관하다. 다운 뒤에는 코드도 함께 되돌려야 한다
(`schema.prisma`·세션 tz 옵션) — 되돌리기 = PR 리버트 + `downgrade -1` 한 쌍이다.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_timestamptz_audit_columns"
down_revision: str | Sequence[str] | None = "0018_backtest_costless_summary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLOW_MISSING_ENV = "ALEMBIC_ALLOW_MISSING_FRONTEND_SCHEMA"
SRC_TZ_ENV = "ALEMBIC_NAIVE_SOURCE_TZ"

# seed.sql·0005 백필이 남긴 표식 — 0007 과 같은 값을 쓴다. 갈리면 두 리비전이 다른 행 집합을 본다.
NON_APP_ACTORS = ("MGR", "migration")

# 기원 — naive 자릿수를 어느 벽시계로 읽을지
SERVER_TZ = "server_tz"  # CURRENT_TIMESTAMP·now()·seed.sql·DDL DEFAULT now() → DB 서버 tz
UTC = "utc"  # Prisma·Better Auth 의 new Date() → UTC 자릿수
ACTOR = "actor"  # 한 컬럼에 둘이 섞였다 — reg_id/mod_id 로 가른다

# 만료 시각은 미래가 정상이다 — 사후 검사(미래 시각 = 동쪽 tz 오류)에서 뺀다.
FUTURE_ALLOWED_COLUMNS = frozenset({"expiresAt", "accessTokenExpiresAt", "refreshTokenExpiresAt"})

# 정밀도 — public 은 sa.DateTime() 이 만든 기본(6), frontend 는 Prisma @db.Timestamp(3) 이라 3.
# frontend 에 3 을 명시해야 뒤따르는 `prisma db push` 가 @db.Timestamptz(3) 과 같은 타입으로 보고
# 아무것도 안 한다.
PUBLIC_PRECISION: int | None = None
FRONTEND_PRECISION: int | None = 3

# (테이블, ((컬럼, 기원), ...))
PUBLIC_COLUMNS: list[tuple[str, tuple[tuple[str, str], ...]]] = [
    (
        "tn_backtest_run",
        (("started_dt", SERVER_TZ), ("finished_dt", SERVER_TZ), ("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ)),
    ),
    ("tn_board", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_bot", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_bot_strategy", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_daily_bar", (("ingested_at", SERVER_TZ),)),
    ("tn_file", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_file_detail", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_holding", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    (
        "tn_ingest_run",
        (("started_dt", SERVER_TZ), ("finished_dt", SERVER_TZ), ("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ)),
    ),
    ("tn_instrument", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_message_queue", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    # 월 파티션 12개는 부모에 ALTER 하면 자식으로 전파된다 — 자식을 따로 적지 않는다.
    ("tn_minute_bar", (("ingested_at", SERVER_TZ),)),
    # nav_dt 는 시장 벽시계라 뺀다 (2026-07-30 결정) — reg_dt·mod_dt 만 옮긴다.
    ("tn_nav", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_portfolio", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_research_document", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_scheduler", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_scheduler_member", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_symbol_alias", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    ("tn_watchlist", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
]

# reg_id/mod_id 로 기원이 갈리는 테이블 — 0007 의 목록과 같다(th_email_log 제외: 배우 컬럼이 없다).
_MIXED_ORIGIN_TABLES = (
    "tn_user",
    "tn_workspace",
    "tn_workspace_member",
    "tn_workspace_menu",
    "tn_workspace_domain",
    "tn_author",
    "tn_author_member",
    "tn_author_menu",
    "tn_menu",
    "tc_group_code",
    "tc_code",
)

FRONTEND_COLUMNS: list[tuple[str, tuple[tuple[str, str], ...]]] = [
    *((table, (("reg_dt", ACTOR), ("mod_dt", ACTOR))) for table in _MIXED_ORIGIN_TABLES),
    # multi-agent 가 SQL now() 로 쓴다 — 서버 tz 벽시계.
    ("ai_chat_history", (("reg_dt", SERVER_TZ), ("mod_dt", SERVER_TZ))),
    # 쓰는 경로가 JS new Date() 뿐이라 조건 없이 UTC (0007 과 같은 판정).
    ("th_email_log", (("reg_dt", UTC),)),
    # Better Auth — 라이브러리가 스스로 만들 때도 Postgres 에서는 timestamptz 다.
    ("ba_session", (("expiresAt", UTC), ("createdAt", UTC), ("updatedAt", UTC))),
    (
        "ba_account",
        (("accessTokenExpiresAt", UTC), ("refreshTokenExpiresAt", UTC), ("createdAt", UTC), ("updatedAt", UTC)),
    ),
    ("ba_verification", (("expiresAt", UTC), ("createdAt", UTC), ("updatedAt", UTC))),
]

# IANA tz 이름 꼴 — SQL 문자열 리터럴에 넣기 전 1차 검증. 실존 여부는 pg_timezone_names 로 본다.
_TZ_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_+/-]{0,63}$")


class TimestamptzMigrationError(RuntimeError):
    """이 리비전이 안전하게 옮길 수 없는 상태를 만났다."""


def _quote(identifier: str) -> str:
    """식별자를 큰따옴표로 감싼다 — ba_* 의 camelCase 컬럼은 인용 없이는 소문자로 접힌다."""
    if '"' in identifier:
        raise TimestamptzMigrationError(f"식별자에 큰따옴표가 있다: {identifier!r}")
    return f'"{identifier}"'


def _actor_column(column: str) -> str:
    """감사 컬럼의 기원을 말해 주는 배우 컬럼 — reg_dt 는 reg_id, mod_dt 는 mod_id."""
    if column == "reg_dt":
        return "reg_id"
    if column == "mod_dt":
        return "mod_id"
    raise TimestamptzMigrationError(f"배우 컬럼을 알 수 없다: {column!r}")


def origin_tz_expression(column: str, origin: str, src_tz: str) -> str:
    """naive 컬럼을 인스턴트로 읽는 식 — `AT TIME ZONE` 의 오른쪽이 「이 자릿수의 뜻」이다."""
    col = _quote(column)
    if origin == UTC:
        return f"{col} AT TIME ZONE 'UTC'"
    if origin == SERVER_TZ:
        return f"{col} AT TIME ZONE '{src_tz}'"
    if origin == ACTOR:
        actors = ", ".join(f"'{actor}'" for actor in NON_APP_ACTORS)
        actor_col = _actor_column(column)
        # NULL 배우는 IN 이 NULL 을 내므로 ELSE 로 떨어진다 — 0007 의 `IS NULL OR NOT IN` 과 같은 편.
        return (
            f"CASE WHEN {actor_col} IN ({actors}) THEN {col} AT TIME ZONE '{src_tz}' ELSE {col} AT TIME ZONE 'UTC' END"
        )
    raise TimestamptzMigrationError(f"모르는 기원: {origin!r}")


def to_timestamptz_sql(schema: str, table: str, column: str, origin: str, src_tz: str, precision: int | None) -> str:
    """naive → timestamptz. `USING` 이 세션 tz 를 무의미하게 만든다."""
    kind = "timestamptz" if precision is None else f"timestamptz({precision})"
    return (
        f"ALTER TABLE {_quote(schema)}.{_quote(table)} "
        f"ALTER COLUMN {_quote(column)} TYPE {kind} "
        f"USING ({origin_tz_expression(column, origin, src_tz)})"
    )


def to_naive_sql(schema: str, table: str, column: str, origin: str, src_tz: str, precision: int | None) -> str:
    """timestamptz → naive. 같은 기원 판정을 그대로 되감아 원래 자릿수를 복원한다."""
    kind = "timestamp" if precision is None else f"timestamp({precision})"
    return (
        f"ALTER TABLE {_quote(schema)}.{_quote(table)} "
        f"ALTER COLUMN {_quote(column)} TYPE {kind} "
        f"USING ({origin_tz_expression(column, origin, src_tz)})"
    )


def _validate_tz(bind: sa.engine.Connection, tz: str, where: str) -> str:
    if not _TZ_NAME.match(tz):
        raise TimestamptzMigrationError(f"{where} 의 타임존 이름이 IANA 꼴이 아니다: {tz!r}")
    known = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name = :tz)"), {"tz": tz}
    ).scalar()
    if not known:
        raise TimestamptzMigrationError(f"{where} 의 타임존을 이 서버가 모른다: {tz!r}")
    return tz


def resolve_source_tz(bind: sa.engine.Connection) -> tuple[str, str]:
    """(쓸 값, 어떻게 정했는지) — 기본은 서버 기본값, env 가 있으면 그것이 이긴다."""
    server_tz = bind.execute(sa.text("SELECT reset_val FROM pg_settings WHERE name = 'TimeZone'")).scalar()
    if not server_tz:
        raise TimestamptzMigrationError("pg_settings 에서 서버 기본 TimeZone 을 읽지 못했다")
    server_tz = _validate_tz(bind, str(server_tz), "pg_settings.reset_val")

    override = os.environ.get(SRC_TZ_ENV)
    if not override:
        return server_tz, f"pg_settings.reset_val={server_tz}"
    override = _validate_tz(bind, override.strip(), SRC_TZ_ENV)
    if override != server_tz:
        print(
            f"[0019] 경고 — {SRC_TZ_ENV}={override} 가 서버 기본값 {server_tz} 과 다르다. "
            "env 값을 쓴다 (서버 tz 를 DB 수명 중 바꿨다면 이것이 맞다)."
        )
    return override, f"{SRC_TZ_ENV}={override} (서버 기본값 {server_tz})"


def _column_type(bind: sa.engine.Connection, schema: str, table: str, column: str) -> str | None:
    return bind.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t AND column_name = :c"
        ),
        {"s": schema, "t": table, "c": column},
    ).scalar()


def _row_count(bind: sa.engine.Connection, schema: str, table: str) -> int:
    return int(bind.execute(sa.text(f"SELECT count(*) FROM {_quote(schema)}.{_quote(table)}")).scalar() or 0)


_MISSING_FRONTEND_SQL = "SELECT " + " OR ".join(
    f"to_regclass('frontend.{table}') IS NULL" for table, _ in FRONTEND_COLUMNS
)


def _frontend_missing(bind: sa.engine.Connection) -> bool:
    return bool(bind.execute(sa.text(_MISSING_FRONTEND_SQL)).scalar())


def _skip_frontend(bind: sa.engine.Connection) -> bool:
    """frontend 스키마가 없으면 True(건너뜀 허용) 또는 예외 — 0007 과 같은 가드."""
    if not _frontend_missing(bind):
        return False
    if os.environ.get(ALLOW_MISSING_ENV) == "1":
        print("[0019] frontend 스키마 없음 — 격리 검증이므로 frontend 35컬럼을 건너뛴다")
        return True
    raise TimestamptzMigrationError(
        "frontend 스키마 테이블(tn_user·ba_session 등 16개)이 없습니다 — db-migrate 순서가 깨졌습니다"
        "(prisma db push 가 alembic 보다 먼저 돌아야 합니다, #333). "
        f"frontend 를 아예 배제한 격리 검증이라면 {ALLOW_MISSING_ENV}=1 을 명시하세요."
    )


def _apply(bind: sa.engine.Connection, *, to_tz: bool, src_tz: str) -> int:
    """전환/복원 공통 — 옮긴 컬럼 수를 돌려준다."""
    target_type = "timestamp with time zone" if to_tz else "timestamp without time zone"
    already_type = "timestamp without time zone" if to_tz else "timestamp with time zone"
    render = to_timestamptz_sql if to_tz else to_naive_sql

    plan: list[tuple[str, str, tuple[tuple[str, str], ...], int | None]] = [
        ("public", table, columns, PUBLIC_PRECISION) for table, columns in PUBLIC_COLUMNS
    ]
    if not _skip_frontend(bind):
        plan += [("frontend", table, columns, FRONTEND_PRECISION) for table, columns in FRONTEND_COLUMNS]

    moved = 0
    for schema, table, columns, precision in plan:
        rows = _row_count(bind, schema, table)
        table_moved = 0
        for column, origin in columns:
            current = _column_type(bind, schema, table, column)
            if current is None:
                raise TimestamptzMigrationError(f"{schema}.{table}.{column} 이 없다 — 대상 목록과 DB 가 어긋났다")
            if current == target_type:
                # 이미 옮겨져 있다. 빈 테이블이면 신규 DB 에서 prisma db push 가 먼저 만든 것이라 정상.
                if rows == 0:
                    continue
                raise TimestamptzMigrationError(
                    f"{schema}.{table}.{column} 이 이미 {target_type} 인데 행이 {rows}건 있다 — "
                    "`prisma db push` 가 이 리비전보다 먼저 돌아 USING 없이 타입을 바꿨을 수 있고, "
                    "그러면 기존 값의 뜻(기원별 tz)을 잃는다. 스냅샷에서 복원한 뒤 db-migrate 순서를 "
                    "`alembic upgrade head` → `prisma db push` → `alembic upgrade head` 로 맞추세요 "
                    "(process-compose.yaml 의 db-migrate 참조)."
                )
            if current != already_type:
                raise TimestamptzMigrationError(f"{schema}.{table}.{column} 의 타입이 예상 밖이다: {current}")
            op.execute(render(schema, table, column, origin, src_tz, precision))
            table_moved += 1
        if table_moved:
            moved += table_moved
            print(f"[0019] {schema}.{table} — {table_moved}컬럼 · {rows}행")
        else:
            print(f"[0019] {schema}.{table} — 건너뜀 (이미 {target_type}, 0행)")

    if moved == 0:
        raise TimestamptzMigrationError(
            "옮긴 컬럼이 0개다 — 대상 목록이 DB 와 어긋났거나 이미 전부 전환돼 있다. "
            "「검사할 게 없어 통과」를 통과로 치지 않는다(fail-closed)."
        )
    return moved


def _assert_no_future_audit_times(bind: sa.engine.Connection) -> None:
    """감사 시각이 미래면 src_tz 를 실제보다 동쪽으로 잡은 것이다 — 트랜잭션째 롤백한다."""
    checked = 0
    offenders: list[str] = []
    plan = [("public", table, columns) for table, columns in PUBLIC_COLUMNS]
    if not _frontend_missing(bind):
        plan += [("frontend", table, columns) for table, columns in FRONTEND_COLUMNS]
    for schema, table, columns in plan:
        for column, _origin in columns:
            if column in FUTURE_ALLOWED_COLUMNS:
                continue
            checked += 1
            latest = bind.execute(
                sa.text(f"SELECT max({_quote(column)}) FROM {_quote(schema)}.{_quote(table)}")
            ).scalar()
            if latest is None:
                continue
            future = bind.execute(
                sa.text(
                    f"SELECT max({_quote(column)}) > now() + interval '5 minutes' FROM {_quote(schema)}.{_quote(table)}"
                )
            ).scalar()
            if future:
                offenders.append(f"{schema}.{table}.{column} (max={latest})")
    if checked == 0:
        raise TimestamptzMigrationError("미래 시각 검사 대상이 0건이다 — 검사가 아무것도 안 봤다(fail-closed)")
    print(f"[0019] 미래 시각 검사 — 감사·운영 컬럼 {checked}개 (만료 컬럼 {len(FUTURE_ALLOWED_COLUMNS)}종은 제외)")
    if offenders:
        raise TimestamptzMigrationError(
            "전환 뒤 감사 시각이 미래다 — src_tz 를 실제 서버 tz 보다 동쪽으로 잡았을 때 나는 모양이다: "
            + ", ".join(offenders)
            + f". {SRC_TZ_ENV} 로 올바른 값을 주고 다시 실행하세요."
        )


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    src_tz, source = resolve_source_tz(bind)
    print(f"[0019] src_tz={src_tz} (출처 {source})")
    moved = _apply(bind, to_tz=True, src_tz=src_tz)
    print(f"[0019] timestamptz 로 옮긴 컬럼 {moved}개")
    _assert_no_future_audit_times(bind)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    src_tz, source = resolve_source_tz(bind)
    print(f"[0019] src_tz={src_tz} (출처 {source})")
    moved = _apply(bind, to_tz=False, src_tz=src_tz)
    print(f"[0019] naive 로 되돌린 컬럼 {moved}개")
