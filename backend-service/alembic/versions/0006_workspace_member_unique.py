"""workspace_member_unique — is_default 유일성을 DB 제약으로 강제한다

Revision ID: 0006_workspace_member_unique
Revises: 0005_backfill_workspace_member
Create Date: 2026-08-02

`tn_workspace_member.is_default` 는 사용자당 정확히 하나여야 하는데(로그인 시 기본 워크스페이스
선택 근거), 이 불변식이 애플리케이션 코드에만 있고 DB 제약이 없었다(#253). 부분 유니크 인덱스
(`WHERE is_default`)로 "사용자당 is_default=true 는 최대 1건"을 DB 가 직접 보장한다 — "최소 1건"은
이 인덱스로 강제되지 않고 여전히 애플리케이션·백필(0005) 책임이다.

대상 테이블은 Prisma 소유인 `frontend` 스키마다(0005 와 같은 경계 — CLAUDE.md "DB" 절 참조).
Prisma 스키마 문법으로 부분 유니크 인덱스를 표현할 수 없어 raw SQL 로 넣는다 — 스키마 소유가
이중화되는 대가를 감수한다(대안: 애플리케이션 규약만 유지 + 검증 스크립트 주기 확인, 또는
`tn_user.workspace_id` 를 정본으로 삼는 모델 변경 — 설계 문서 m2-전환설계.md §7.5 참조).

db-migrate 는 prisma db push 를 alembic 보다 먼저 돌린다(#333) — 0005 와 동일하게, 이 리비전이
돌 때 대상 테이블이 없으면 순서가 다시 깨진 것이므로 조용히 넘어가지 않고 예외로 죽는다
(fail-closed). 유일한 예외는 frontend 스키마를 아예 만들지 않는 격리된 alembic 전용 검증(예: CI
`alembic-drift` 잡)이며, 그 경우는 `ALEMBIC_ALLOW_MISSING_FRONTEND_SCHEMA=1` 로 명시적으로 건너뛴다.

#253 최초 도입(PR #334 커밋 9708e78)은 순서 결함(#333)이 발견돼 반쪽 제약이 될 뻔해 되돌렸다가,
#333 이 풀린 뒤 여기서 되살렸다 — 인덱스 SQL 자체는 원본과 동일하고, 가드만 0005 와 같은 방식
(Python 사전 체크 + 명시적 예외 플래그)으로 다시 작성했다.
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_workspace_member_unique"
down_revision: str | Sequence[str] | None = "0005_backfill_workspace_member"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLOW_MISSING_ENV = "ALEMBIC_ALLOW_MISSING_FRONTEND_SCHEMA"

_FRONTEND_TABLE_MISSING_SQL = "SELECT to_regclass('frontend.tn_workspace_member') IS NULL"


def _frontend_table_missing(bind: sa.engine.Connection) -> bool:
    return bool(bind.execute(sa.text(_FRONTEND_TABLE_MISSING_SQL)).scalar())


INDEX_NAME = "ux_tn_workspace_member_default_per_user"

UPGRADE_SQL = f"""
CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME}
    ON frontend.tn_workspace_member (user_id) WHERE is_default;
"""

DOWNGRADE_SQL = f"""
DROP INDEX IF EXISTS frontend.{INDEX_NAME};
"""


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if _frontend_table_missing(bind):
        if os.environ.get(ALLOW_MISSING_ENV) == "1":
            return  # 격리된 alembic 전용 검증 — frontend 스키마 자체를 만들지 않는 경로(CI alembic-drift)
        raise RuntimeError(
            "frontend.tn_workspace_member 테이블이 없습니다 — db-migrate 순서가 깨졌습니다"
            "(prisma db push 가 alembic 보다 먼저 돌아야 합니다, #333). "
            f"frontend 를 아예 배제한 격리 검증이라면 {ALLOW_MISSING_ENV}=1 을 명시하세요."
        )
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(DOWNGRADE_SQL)
