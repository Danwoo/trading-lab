"""absorb_file — file-service 스키마(tn_file·tn_file_detail)를 통합 이력으로 편입

Revision ID: 0002_absorb_file
Revises: 0001_baseline
Create Date: 2026-07-29

file-service 는 이력 없는 push(db_push.py)로 이 두 테이블을 만들어 왔다. 흡수 후에는 통합 앱의
alembic 이력 하나가 스키마를 소유한다 — 그래서 이 리비전은 두 곳 모두에서 통과해야 한다:
빈 DB(테이블을 실제로 만든다)와 이미 push 로 적재된 DB(건너뛴다).

`IF NOT EXISTS` 로 멱등하게 둔 대가: 이미 있는 테이블의 모양은 검사하지 않는다. 두 테이블은
같은 모델(models/schema.py)에서 나왔으므로 push 로 만들어진 것과 모양이 같다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_absorb_file"
down_revision: str | Sequence[str] | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tn_file",
        sa.Column("atch_file_id", sa.String(length=20), nullable=False, comment="첨부파일 ID"),
        sa.Column("reg_dt", sa.DateTime(), nullable=True, comment="생성일시"),
        sa.Column("reg_id", sa.String(length=100), nullable=True, comment="생성자 ID"),
        sa.Column("mod_dt", sa.DateTime(), nullable=True, comment="수정일시"),
        sa.Column("mod_id", sa.String(length=100), nullable=True, comment="수정자 ID"),
        sa.PrimaryKeyConstraint("atch_file_id"),
        comment="첨부파일",
        if_not_exists=True,
    )
    op.create_table(
        "tn_file_detail",
        sa.Column("atch_file_id", sa.String(length=20), nullable=False, comment="첨부파일 ID"),
        sa.Column("file_sn", sa.Integer(), nullable=False, comment="파일 순번"),
        sa.Column("file_stre_cours", sa.String(length=1300), nullable=True, comment="파일 저장 경로"),
        sa.Column("stre_file_nm", sa.String(length=500), nullable=True, comment="저장 파일명"),
        sa.Column("orignl_file_nm", sa.String(length=500), nullable=True, comment="원본 파일명"),
        sa.Column("file_extsn", sa.String(length=50), nullable=True, comment="파일 확장자"),
        sa.Column("file_mg", sa.Integer(), nullable=True, comment="파일 크기"),
        sa.Column("file_ty", sa.String(length=20), nullable=True, comment="파일 타입"),
        sa.Column("reg_dt", sa.DateTime(), nullable=True, comment="생성일시"),
        sa.Column("reg_id", sa.String(length=100), nullable=True, comment="생성자 ID"),
        sa.Column("mod_dt", sa.DateTime(), nullable=True, comment="수정일시"),
        sa.Column("mod_id", sa.String(length=100), nullable=True, comment="수정자 ID"),
        sa.ForeignKeyConstraint(["atch_file_id"], ["tn_file.atch_file_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("atch_file_id", "file_sn"),
        comment="첨부파일 상세",
        if_not_exists=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tn_file_detail", if_exists=True)
    op.drop_table("tn_file", if_exists=True)
