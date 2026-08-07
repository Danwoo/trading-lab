"""backfill_workspace_member — 활성 사용자 전원에게 기본 워크스페이스 멤버십을 만든다

Revision ID: 0005_backfill_workspace_member
Revises: 0004_rename_company_to_workspace
Create Date: 2026-07-29

이행 후 불변식: **워크스페이스가 배정된 사용자는 승인·활성 여부와 무관하게** is_default=true 멤버십을
정확히 1개 갖는다. 승인대기·비활성 사용자를 빼면 안 된다 — 운영자 화면의 소속 판정이 멤버십을 보므로,
빠진 계정은 목록에는 뜨는데 승인·재활성화가 "사용자를 찾을 수 없습니다"로 막힌다(OEM 의 유일한
온보딩 경로가 기존 계정에 대해 닫힌다). 가입 경로도 승인대기 사용자에게 멤버십을 만든다.

워크스페이스가 없던 **활성** 계정(시스템관리자 등)에는 개인 워크스페이스를 만들어 배정한다 — 스코핑
우회 분기를 만들지 않고 관리자/운영자 비대칭만 없앤다. 미배정 비활성 계정까지 워크스페이스를 만들지는
않는다(쓰지 않을 행을 늘리지 않는다 — 그 계정은 어차피 시스템관리자만 다룬다).

대상 테이블은 Prisma 소유인 `frontend` 스키마다. db-migrate 는 prisma db push 를 alembic 보다
먼저 돌린다(#333) — 이 순서에서는 이 리비전이 돌 때 테이블이 이미 있어야 한다. 없다면 그 자체가
순서가 다시 깨졌다는 신호이므로 조용히 넘어가지 않고 예외로 죽는다(fail-closed). 유일한 예외는
frontend 스키마를 아예 만들지 않는 격리된 alembic 전용 검증(예: CI `alembic-drift` 잡)이며, 그
경우는 `ALEMBIC_ALLOW_MISSING_FRONTEND_SCHEMA=1` 로 명시적으로 건너뛴다.
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_backfill_workspace_member"
down_revision: str | Sequence[str] | None = "0004_rename_company_to_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLOW_MISSING_ENV = "ALEMBIC_ALLOW_MISSING_FRONTEND_SCHEMA"

_FRONTEND_TABLES_MISSING_SQL = """
SELECT to_regclass('frontend.tn_user') IS NULL
    OR to_regclass('frontend.tn_workspace') IS NULL
    OR to_regclass('frontend.tn_workspace_member') IS NULL
"""


def _frontend_tables_missing(bind: sa.engine.Connection) -> bool:
    return bool(bind.execute(sa.text(_FRONTEND_TABLES_MISSING_SQL)).scalar())


# 개인 워크스페이스 코드 — tn_workspace.workspace_code 가 VARCHAR(30) UNIQUE 라 uuid 를 그대로 못 쓴다.
PERSONAL_CODE = "'ws-' || substr(replace(u.id, '-', ''), 1, 27)"

UPGRADE_SQL = f"""
DO $$
BEGIN
  -- 개인 워크스페이스는 is_personal 로 표시한다 — 표시하지 않으면 OEM 의 "활성 공용 워크스페이스
  -- 정확히 1개" 카운트에 섞여 들어가 배포 전체의 가입이 막힌다 (frontend/lib/auth/authUtils.ts
  -- resolveOemSharedWorkspace 와 같은 규약).
  INSERT INTO frontend.tn_workspace
         (workspace_code, workspace_nm, use_at, is_personal, reg_dt, reg_id, mod_dt, mod_id)
  SELECT {PERSONAL_CODE},
         left(coalesce(nullif(u.name, ''), u.email) || '의 워크스페이스', 200),
         'Y', true, now(), 'migration', now(), 'migration'
  FROM frontend.tn_user u
  WHERE u.appr_at = 'Y' AND u.use_at = 'Y' AND u.workspace_id IS NULL
  ON CONFLICT (workspace_code) DO NOTHING;

  UPDATE frontend.tn_user u
  SET workspace_id = w.id, mod_dt = now(), mod_id = 'migration'
  FROM frontend.tn_workspace w
  WHERE w.workspace_code = {PERSONAL_CODE}
    AND u.appr_at = 'Y' AND u.use_at = 'Y' AND u.workspace_id IS NULL;

  -- 멤버십은 승인·활성 여부를 가리지 않는다 (docstring 참조 — 가리면 운영자가 승인대기 계정을 못 다룬다).
  -- 기본 멤버십이 없는 사용자만 대상으로 한다. "멤버십이 하나라도 있으면 건너뛴다"로 두면 개인
  -- 워크스페이스 멤버십(is_default=false)만 가진 계정이 기본 없이 남는다.
  INSERT INTO frontend.tn_workspace_member (workspace_id, user_id, role, is_default, reg_dt, reg_id, mod_dt, mod_id)
  SELECT u.workspace_id, u.id, 'owner', true, now(), 'migration', now(), 'migration'
  FROM frontend.tn_user u
  WHERE u.workspace_id IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM frontend.tn_workspace_member m WHERE m.user_id = u.id AND m.is_default
    )
  -- 같은 워크스페이스에 비기본 멤버십(개인 워크스페이스 owner 행 등)이 이미 있으면 승격시킨다.
  -- DO NOTHING 이면 그 계정만 기본 없이 남는다.
  ON CONFLICT (workspace_id, user_id)
  DO UPDATE SET is_default = true, mod_dt = now(), mod_id = 'migration';
END $$;
"""

DOWNGRADE_SQL = """
DO $$
BEGIN
  IF to_regclass('frontend.tn_workspace_member') IS NULL THEN
    RETURN;
  END IF;

  UPDATE frontend.tn_user u
  SET workspace_id = NULL
  FROM frontend.tn_workspace w
  WHERE w.id = u.workspace_id AND w.reg_id = 'migration';

  -- 백필이 만든 게 아니라 **승격**시킨 행(앱이 만든 비기본 멤버십)은 지우지 않고 되돌린다.
  -- upgrade 의 INSERT 는 기본 멤버십이 없는 사용자만 건드리므로, 여기 걸리는 행은 전부 그때 승격된 것이다.
  UPDATE frontend.tn_workspace_member
  SET is_default = false
  WHERE mod_id = 'migration' AND reg_id <> 'migration';

  DELETE FROM frontend.tn_workspace_member WHERE reg_id = 'migration';
  DELETE FROM frontend.tn_workspace WHERE reg_id = 'migration';
END $$;
"""


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if _frontend_tables_missing(bind):
        if os.environ.get(ALLOW_MISSING_ENV) == "1":
            return  # 격리된 alembic 전용 검증 — frontend 스키마 자체를 만들지 않는 경로(CI alembic-drift)
        raise RuntimeError(
            "frontend 스키마 테이블(tn_user/tn_workspace/tn_workspace_member)이 없습니다 — "
            "db-migrate 순서가 깨졌습니다(prisma db push 가 alembic 보다 먼저 돌아야 합니다, #333). "
            f"frontend 를 아예 배제한 격리 검증이라면 {ALLOW_MISSING_ENV}=1 을 명시하세요."
        )
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(DOWNGRADE_SQL)
