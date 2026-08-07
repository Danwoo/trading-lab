"""kst_write_shift_correction — 프론트엔드 관리 화면 쓰기 경로가 만든 +9h 시프트를 되돌린다

Revision ID: 0007_kst_write_shift_correction
Revises: 0006_workspace_member_unique
Create Date: 2026-08-02

## 리비전 번호 — 0006 이 아니라 0007 인 이유

이 리비전은 원래 `0005_backfill_workspace_member` 바로 뒤 `0006` 으로 작성됐다. 그런데 PR #340
(`fix-infra-migration-order`, #333 을 푸는 관문)이 **같은 자리**에 `0006_workspace_member_unique`
(#253 — `is_default` 유일성 인덱스)를 먼저 올렸고, 그쪽이 먼저 리뷰를 통과했다. 두 리비전이 모두
`down_revision = "0005_backfill_workspace_member"` 로 남으면 head 가 둘로 갈라져 `upgrade head` 가
깨진다 — 그래서 이 리비전을 `0007` 로 밀고 `down_revision` 을 `0006_workspace_member_unique` 로
재지정해 #340 뒤에 오도록 체인을 정리했다. **#340 이 머지되기 전까지 이 리비전은 로컬에서
`0006_workspace_member_unique.py` 없이는 `alembic upgrade head` 로 단독 적용할 수 없다** — 그
사실 자체가 올바른 순서 의존을 표시한다(둘 다 머지되면 자연히 이어진다).

frontend `getKSTTime()`(`addHours(d, 9)`)가 `reg_dt`/`mod_dt` 저장 직전에 쓰이던 결함(#303)으로,
그 경로를 거친 행은 실제보다 9시간 뒤인 인스턴트가 저장돼 있다. 같은 파일 안에서 읽기 쪽도
UTC 벽시계 문자열로 잘려 있어 두 왜곡이 상쇄됐고(#303 이 함께 고친다), 이 리비전은 **이미
저장된 행**을 보정한다 — 마이그레이션 없이 읽기만 고치면 화면이 9시간 미래로 튄다.

## 대상 판정 — reg_id/mod_id 로 쓰기 경로를 구분한다

`getKSTTime()` 을 거친 행은 전부 `frontend/app/api/common/**` 라우트 또는 better-auth 훅이
Prisma 로 직접 쓴 것이고, 이 행들의 `reg_id`/`mod_id` 는 항상 실사용자 이메일(`session.user.email`)
이다. 같은 컬럼에 **다른 경로로 들어온 행**이 이미 섞여 있다 — 전수 조사 결과 두 곳뿐이다:
  - `frontend/prisma/init/seed.sql` — 초기 시드, `reg_id`/`mod_id = 'MGR'`, `CURRENT_TIMESTAMP`(참값)
  - `0005_backfill_workspace_member.py` — 워크스페이스 백필, `reg_id`/`mod_id = 'migration'`, `now()`(참값)
(`backend-service`·`*-mcp-service` 등 다른 서비스가 이 12개 테이블에 쓰는 경로는 없다 — grep 전수
확인, 유일한 예외 `ai_chat_history` 는 이 12개 테이블 밖이고 `multi-agent-service` 소유라 무관.)

그래서 판정은 **컬럼 단위**(행 단위 아님)로 `reg_id NOT IN ('MGR','migration')` 이면 `reg_dt` 를,
`mod_id NOT IN ('MGR','migration')` 이면 `mod_dt` 를 보정 대상으로 삼는다 — 같은 행이라도 seed 로
생성된 뒤 앱에서 수정됐다면 `reg_dt` 는 참값, `mod_dt` 만 보정 대상이 되는 식이라 컬럼별 조건이
필요하다. `th_email_log` 는 `reg_id`/`mod_id` 컬럼 자체가 없다 — 이 테이블에 쓰는 경로는
`getKSTTime()` 뿐이라(전수 확인) 조건 없이 전체 행을 보정한다.

## 안전장치

- **역방향 포함** — 같은 판정 조건으로 +9h 되돌린다(판정에 쓰는 reg_id/mod_id 값은 이 리비전이
  건드리지 않으므로 up/down 모두 같은 행 집합을 가리킨다).
- **대상 테이블 부재 시 fail-closed** (#333 과 같은 함정) — db-migrate 는 `prisma db push` 를
  alembic 보다 먼저 돌린다. 이 리비전이 돌 때 대상 테이블이 없으면 순서가 깨진 것이므로 조용히
  건너뛰지 않고 예외로 죽는다. frontend 스키마를 아예 만들지 않는 격리 검증(CI `alembic-drift`)만
  `ALEMBIC_ALLOW_MISSING_FRONTEND_SCHEMA=1` 로 명시 예외.
- **되돌리기 어려운 작업이라 적용 전 `backend-service/scripts/kst_timestamp_correction.py snapshot`
  으로 대상 행의 현재값을 스냅샷하고, 적용 후 `diff` 로 실제 보정값이 스냅샷 기반 기대값과
  정확히 일치하는지 대조할 것을 권장한다** (스크립트 docstring 참조).
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_kst_write_shift_correction"
# PR #340(fix-infra-migration-order, #333)의 0006_workspace_member_unique 뒤에 온다 — 위 리비전
# 번호 설명 참조. #340 미머지 상태에서는 이 파일 하나만으로 `alembic upgrade head` 를 끝까지
# 돌릴 수 없다(down_revision 이 가리키는 리비전이 로컬에 없으므로).
down_revision: str | Sequence[str] | None = "0006_workspace_member_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLOW_MISSING_ENV = "ALEMBIC_ALLOW_MISSING_FRONTEND_SCHEMA"

# (테이블, reg_id/mod_id 컬럼 보유 여부) — reg_id/mod_id 가 없는 th_email_log 만 False.
_TABLES: list[tuple[str, bool]] = [
    ("tn_user", True),
    ("tn_workspace", True),
    ("tn_workspace_member", True),
    ("tn_workspace_menu", True),
    ("tn_workspace_domain", True),
    ("tn_author", True),
    ("tn_author_member", True),
    ("tn_author_menu", True),
    ("tn_menu", True),
    ("tc_group_code", True),
    ("tc_code", True),
    ("th_email_log", False),
]

# seed.sql·0005 backfill 이 남긴 "참값(unshifted)" 표식 — 이 두 값이 아니면 getKSTTime() 을 거친
# 앱 쓰기 경로로 본다.
_NON_APP_ACTORS = ("MGR", "migration")


def _actor_predicate(column: str) -> str:
    placeholders = ", ".join(f"'{actor}'" for actor in _NON_APP_ACTORS)
    return f"({column} IS NULL OR {column} NOT IN ({placeholders}))"


def _shift_sql(sign: str) -> str:
    statements: list[str] = []
    for table, has_actor_columns in _TABLES:
        if not has_actor_columns:
            # th_email_log — reg_id/mod_id 없음, 유일한 쓰기 경로가 getKSTTime() 이라 무조건 보정.
            statements.append(f"UPDATE frontend.{table} SET reg_dt = reg_dt {sign} INTERVAL '9 hours';")
            continue
        statements.append(
            f"UPDATE frontend.{table} SET reg_dt = reg_dt {sign} INTERVAL '9 hours' "
            f"WHERE reg_dt IS NOT NULL AND {_actor_predicate('reg_id')};"
        )
        statements.append(
            f"UPDATE frontend.{table} SET mod_dt = mod_dt {sign} INTERVAL '9 hours' "
            f"WHERE mod_dt IS NOT NULL AND {_actor_predicate('mod_id')};"
        )
    return "\n".join(statements)


UPGRADE_SQL = _shift_sql("-")
DOWNGRADE_SQL = _shift_sql("+")

_MISSING_TABLE_SQL = "SELECT " + " OR ".join(f"to_regclass('frontend.{table}') IS NULL" for table, _ in _TABLES)


def _frontend_tables_missing(bind: sa.engine.Connection) -> bool:
    return bool(bind.execute(sa.text(_MISSING_TABLE_SQL)).scalar())


def _guard_or_raise(bind: sa.engine.Connection) -> bool:
    """대상 테이블이 없으면 True(건너뜀 허용) 를 돌려주거나 예외로 죽는다."""
    if not _frontend_tables_missing(bind):
        return False
    if os.environ.get(ALLOW_MISSING_ENV) == "1":
        return True  # 격리된 alembic 전용 검증 — frontend 스키마 자체를 만들지 않는 경로(CI alembic-drift)
    raise RuntimeError(
        "frontend 스키마 테이블(tn_user 등 12개)이 없습니다 — db-migrate 순서가 깨졌습니다"
        "(prisma db push 가 alembic 보다 먼저 돌아야 합니다, #333). "
        f"frontend 를 아예 배제한 격리 검증이라면 {ALLOW_MISSING_ENV}=1 을 명시하세요."
    )


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if _guard_or_raise(bind):
        return
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if _guard_or_raise(bind):
        return
    op.execute(DOWNGRADE_SQL)
