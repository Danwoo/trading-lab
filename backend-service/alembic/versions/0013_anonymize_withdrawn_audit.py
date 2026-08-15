"""anonymize_withdrawn_audit — 이미 탈퇴한 사용자가 감사 컬럼·인증 토큰에 남긴 이메일을 정리한다 (#3)

Revision ID: 0013_anonymize_withdrawn_audit
Revises: 0012_market_bars
Create Date: 2026-08-12

`deleteUserCascade`(frontend/lib/auth/authUtils.ts)가 이 리비전 이후의 탈퇴는 같은 트랜잭션에서
처리하지만, **그 코드가 생기기 전에 탈퇴한 사용자**의 값은 남아 있을 수 있다. 이 리비전이 그
잔존분을 2026-08-12 리드 결정(#3)과 같은 방침으로 정리한다:

- **감사 컬럼 `reg_id`·`mod_id` (26개 테이블) → 익명화.** 이메일 모양(`@` 포함)인데
  `frontend.tn_user` 에 (대소문자 무관으로) 없는 값을 「탈퇴자 잔존값」으로 판정해
  `deleted-user-<uuid>` 로 치환한다. 탈퇴자의 `tn_user.id` 는 행이 지워져 알 수 없으므로
  **고아 이메일별로 무작위 uuid 를 새로 뽑는다** — 매핑을 저장하지 않아 복원 불가, 같은
  이메일(대소문자 무관)은 같은 uuid 를 받아 「같은 사람이 한 일」은 묶이고, uuid 라 충돌이
  없다. 런타임 치환값(`deleted-user-<tn_user.id>`)과 형식이 같다.
  `MGR`·`migration`(alembic 0007 전수 조사)·`system`(backend 백그라운드) 같은 비이메일 액터
  값은 `@` 필터에 안 걸려 보존된다. NULL 로 만들지 않는다 — 「누가 했는지 모른다」와
  「탈퇴한 사람이 했다」는 다르다.
- **`frontend.ba_verification` 잔존 행 → 삭제.** 두 종류다 (frontend/lib/auth/verificationIdentifier.ts):
  - 가입 OTP 행 (`identifier = 'email-verification-otp-<이메일>'`) — 그 이메일이 `tn_user` 에
    없고 **만료된** 행만 지운다. 만료 조건을 거는 이유: 가입 진행 중인 사용자는 아직
    `tn_user` 행이 없어, 만료 전 행까지 지우면 진행 중인 가입이 깨진다.
  - 비밀번호 재설정 행 (`identifier` 는 SHA-256 해시, `value` 가 `tn_user.id` 원문) —
    `value` 가 uuid 모양인데 `tn_user` 에 없는 행을 지운다. 계정이 사라진 재설정 토큰은
    만료 여부와 무관하게 쓸 곳이 없다. OTP 접두어 행은 이 판정에서 제외해 두 갈래가 겹치지
    않게 한다.

## 안전장치

- **처리 전에 대상을 세고 stdout 에 남긴다** — 고아 이메일 수, 테이블별 갱신 행 수, 토큰 삭제
  행 수. 0건이어도 유효하다(앞으로의 탈퇴는 런타임이 막는다) — 0건이면 0건이라고 찍힌다.
- **대상 테이블 부재 시 fail-closed** — 0007 과 같은 함정: db-migrate 는 `prisma db push` 를
  alembic 보다 먼저 돌리므로, frontend 테이블이 없으면 순서가 깨진 것이다. 조용히 건너뛰지
  않고 예외로 죽는다. frontend 스키마를 아예 만들지 않는 격리 검증(CI `alembic-drift`)만
  `ALEMBIC_ALLOW_MISSING_FRONTEND_SCHEMA=1` 로 명시 예외 (0007 과 같은 env).
- **downgrade 는 없다** — 익명화는 되돌릴 수 없어야 익명화다. 매핑을 저장하지 않으므로
  downgrade 는 예외로 죽는다.
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_anonymize_withdrawn_audit"
down_revision: str | Sequence[str] | None = "0012_market_bars"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLOW_MISSING_ENV = "ALEMBIC_ALLOW_MISSING_FRONTEND_SCHEMA"

# frontend/lib/auth/authUtils.ts 의 AUDIT_ANONYMIZED_TABLES 와 같은 목록 — 이 리비전은 작성
# 시점의 스냅샷이다 (0007 과 같은 방식). 앞으로 감사 컬럼 테이블이 늘어도 이 리비전은 안
# 고친다: 새 테이블에는 탈퇴 잔존값이 생길 수 없다 (런타임 익명화가 이미 탈퇴마다 돈다).
# TS 상수 쪽은 dbtest 그물이 information_schema 와 양방향 완전 일치로 대조한다.
_AUDIT_TABLES: list[str] = [
    "frontend.ai_chat_history",
    "frontend.tc_code",
    "frontend.tc_group_code",
    "frontend.tn_author",
    "frontend.tn_author_member",
    "frontend.tn_author_menu",
    "frontend.tn_menu",
    "frontend.tn_user",
    "frontend.tn_workspace",
    "frontend.tn_workspace_domain",
    "frontend.tn_workspace_member",
    "frontend.tn_workspace_menu",
    "public.tn_board",
    "public.tn_file",
    "public.tn_file_detail",
    "public.tn_holding",
    "public.tn_ingest_run",
    "public.tn_instrument",
    "public.tn_message_queue",
    "public.tn_nav",
    "public.tn_portfolio",
    "public.tn_research_document",
    "public.tn_scheduler",
    "public.tn_scheduler_member",
    "public.tn_symbol_alias",
    "public.tn_watchlist",
]

_UUID_PATTERN = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

# 'email-verification-otp-' 는 23자 — 이메일은 24번째 문자부터다 (verificationIdentifier.ts).
_OTP_PREFIX = "email-verification-otp-"

_FRONTEND_TABLES_FOR_GUARD = [t for t in _AUDIT_TABLES if t.startswith("frontend.")] + [
    "frontend.ba_verification",
]

_MISSING_TABLE_SQL = "SELECT " + " OR ".join(f"to_regclass('{table}') IS NULL" for table in _FRONTEND_TABLES_FOR_GUARD)


def _guard_or_raise(bind: sa.engine.Connection) -> bool:
    """frontend 테이블이 없으면 True(건너뜀 허용) 를 돌려주거나 예외로 죽는다 (0007 과 동일 규약)."""
    if not bool(bind.execute(sa.text(_MISSING_TABLE_SQL)).scalar()):
        return False
    if os.environ.get(ALLOW_MISSING_ENV) == "1":
        return True
    raise RuntimeError(
        "frontend 스키마 테이블이 없습니다 — db-migrate 순서가 깨졌습니다"
        "(prisma db push 가 alembic 보다 먼저 돌아야 합니다, #333). "
        f"frontend 를 아예 배제한 격리 검증이라면 {ALLOW_MISSING_ENV}=1 을 명시하세요."
    )


def _orphan_source_sql() -> str:
    """26개 테이블 × 2컬럼의 모든 액터 값 — 고아 이메일 후보의 원천."""
    selects = []
    for table in _AUDIT_TABLES:
        selects.append(f"SELECT reg_id AS actor FROM {table}")
        selects.append(f"SELECT mod_id AS actor FROM {table}")
    return " UNION ALL ".join(selects)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if _guard_or_raise(bind):
        return

    # 고아 이메일 → 익명화 값 매핑 (세션 임시 테이블 — 커밋과 무관하게 마지막에 명시적으로 지운다).
    op.execute(sa.text("DROP TABLE IF EXISTS tmp_orphan_audit_map"))
    op.execute(
        sa.text(
            f"""
            CREATE TEMP TABLE tmp_orphan_audit_map AS
            SELECT o.email_lower, 'deleted-user-' || gen_random_uuid() AS anon
            FROM (
              SELECT DISTINCT lower(actor) AS email_lower
              FROM ({_orphan_source_sql()}) AS a
              WHERE actor LIKE '%@%'
            ) AS o
            WHERE NOT EXISTS (
              SELECT 1 FROM frontend.tn_user u WHERE lower(u.email) = o.email_lower
            )
            """
        )
    )
    orphan_count = bind.execute(sa.text("SELECT count(*) FROM tmp_orphan_audit_map")).scalar()
    print(f"[0013] 고아 이메일(탈퇴자 잔존 식별자): {orphan_count}건")

    total_rows = 0
    for table in _AUDIT_TABLES:
        result = bind.execute(
            sa.text(
                f"""
                UPDATE {table} t
                SET reg_id = COALESCE(
                      (SELECT m.anon FROM tmp_orphan_audit_map m WHERE m.email_lower = lower(t.reg_id)),
                      t.reg_id),
                    mod_id = COALESCE(
                      (SELECT m.anon FROM tmp_orphan_audit_map m WHERE m.email_lower = lower(t.mod_id)),
                      t.mod_id)
                WHERE lower(t.reg_id) IN (SELECT email_lower FROM tmp_orphan_audit_map)
                   OR lower(t.mod_id) IN (SELECT email_lower FROM tmp_orphan_audit_map)
                """
            )
        )
        total_rows += result.rowcount
        print(f"[0013] {table}: {result.rowcount}행 익명화")
    print(f"[0013] 감사 컬럼 익명화 합계: 테이블 {len(_AUDIT_TABLES)}개 검사, {total_rows}행")

    otp = bind.execute(
        sa.text(
            """
            DELETE FROM frontend.ba_verification v
            WHERE v.identifier LIKE :otp_like
              AND v."expiresAt" < now()
              AND NOT EXISTS (
                SELECT 1 FROM frontend.tn_user u
                WHERE lower(u.email) = lower(substring(v.identifier FROM :email_start))
              )
            """
        ),
        {"otp_like": f"{_OTP_PREFIX}%", "email_start": len(_OTP_PREFIX) + 1},
    )
    print(f"[0013] ba_verification 고아 OTP(만료분): {otp.rowcount}행 삭제")

    reset = bind.execute(
        sa.text(
            """
            DELETE FROM frontend.ba_verification v
            WHERE v.identifier NOT LIKE :otp_like
              AND v.value ~ :uuid_pattern
              AND NOT EXISTS (SELECT 1 FROM frontend.tn_user u WHERE u.id = v.value)
            """
        ),
        {"otp_like": f"{_OTP_PREFIX}%", "uuid_pattern": _UUID_PATTERN},
    )
    print(f"[0013] ba_verification 고아 재설정 토큰: {reset.rowcount}행 삭제")

    op.execute(sa.text("DROP TABLE IF EXISTS tmp_orphan_audit_map"))


def downgrade() -> None:
    """Downgrade schema."""
    raise RuntimeError(
        "0013 은 되돌릴 수 없다 — 익명화 매핑(고아 이메일 → uuid)을 저장하지 않는 것이 "
        "복원 불가 성질의 근거다 (#3). 되돌릴 수 있으면 익명화가 아니다."
    )
