"""rename_company_to_workspace — public 스키마의 company_id 컬럼을 workspace_id 로

Revision ID: 0004_rename_company_to_workspace
Revises: 0003_absorb_devactivity
Create Date: 2026-07-29

ALTER TABLE ... RENAME COLUMN 은 메타데이터만 바꾼다 — 데이터 복사가 없고, PK 를 구성하는
컬럼(tn_watchlist·tn_portfolio·tn_holding)도 인덱스·제약이 따라오므로 그대로 가능하다.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_rename_company_to_workspace"
down_revision: str | Sequence[str] | None = "0003_absorb_devactivity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "tn_watchlist",
    "tn_portfolio",
    "tn_holding",
    "tn_nav",
    "tn_research_document",
    "tn_scheduler",
    "tn_scheduler_member",
)

INDEX_RENAMES = (
    ("idx_research_document_company", "idx_research_document_workspace"),
    ("idx_nav_company", "idx_nav_workspace"),
)


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        op.alter_column(table, "company_id", new_column_name="workspace_id")
    for old, new in INDEX_RENAMES:
        op.execute(f'ALTER INDEX IF EXISTS "{old}" RENAME TO "{new}"')


def downgrade() -> None:
    """Downgrade schema."""
    for old, new in INDEX_RENAMES:
        op.execute(f'ALTER INDEX IF EXISTS "{new}" RENAME TO "{old}"')
    for table in TABLES:
        op.alter_column(table, "workspace_id", new_column_name="company_id")
