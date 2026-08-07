"""absorb_devactivity — devactivity 스키마(tn_scheduler·tn_scheduler_member)를 통합 이력으로 편입

Revision ID: 0003_absorb_devactivity
Revises: 0002_absorb_file
Create Date: 2026-07-29

0002_absorb_file 과 같은 이유로 멱등하다 — devactivity 도 이력 없는 push 로 이 두 테이블을
만들어 왔으므로, 빈 DB 와 이미 적재된 DB 양쪽에서 통과해야 한다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_absorb_devactivity"
down_revision: str | Sequence[str] | None = "0002_absorb_file"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tn_scheduler",
        sa.Column("scheduler_id", sa.String(length=20), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("scheduler_nm", sa.String(length=200), nullable=False),
        sa.Column("day_of_week", sa.String(length=20), server_default="mon", nullable=False),
        sa.Column("hour", sa.Integer(), server_default="9", nullable=False),
        sa.Column("minute", sa.Integer(), server_default="0", nullable=False),
        sa.Column("period_weeks", sa.Integer(), server_default="1", nullable=False),
        sa.Column("use_at", sa.String(length=5), server_default="N", nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_id", sa.String(length=100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("scheduler_id"),
        if_not_exists=True,
    )
    op.create_table(
        "tn_scheduler_member",
        sa.Column("scheduler_id", sa.String(length=20), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_id", sa.String(length=100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("scheduler_id", "account_id"),
        if_not_exists=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tn_scheduler_member", if_exists=True)
    op.drop_table("tn_scheduler", if_exists=True)
