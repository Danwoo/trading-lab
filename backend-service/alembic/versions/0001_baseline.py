"""baseline — backend-service 전체 스키마 (PostgreSQL)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-26 00:28:14.600218

빈 DB 에서 backend-service 스키마를 통째로 세우는 베이스라인이다. 이전의 기능별 리비전
4장(company_id 테넌트 격리 / nav 멱등키 / watchlist 첨부 / research_document 잡 스토어)은
이 한 장으로 스쿼시했다 — 4장은 테이블을 만드는 베이스라인 없이 `add_column` 부터 시작해
빈 DB 에서는 적용 자체가 불가능했고(#166 S3), 내용은 전부 현재 모델에 반영돼 있다.

식별자는 전부 소문자 snake_case — PostgreSQL 은 따옴표 없는 식별자를 소문자로 폴딩하므로
혼합 케이스 테이블명은 raw SQL 참조를 깨뜨린다. PK 제약 이름은 지정하지 않는다(모델에
naming convention 이 없어 DB 기본명 `<table>_pkey` 를 그대로 쓴다 — 모델과 무드리프트 유지).

이 리비전은 `alembic upgrade head` 로 적용한다. db_push.py 는 이 서비스에서 쓰지 않는다
(리비전이 있으면 스스로 중단한다).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tn_board",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bbs_ty", sa.String(length=5), nullable=True),
        sa.Column("sj", sa.String(length=200), nullable=False),
        sa.Column("cn", sa.Text(), nullable=True),
        sa.Column("atch_file_id", sa.String(length=20), nullable=True),
        sa.Column("rdcnt", sa.Integer(), nullable=True),
        sa.Column("use_at", sa.String(length=5), server_default="Y", nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_id", sa.String(length=100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_board_reg_dt", "tn_board", ["reg_dt"], unique=False)

    op.create_table(
        "tn_message_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_id", sa.String(length=100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_message_queue_status", "tn_message_queue", ["status"], unique=False)

    # 테넌트 격리: company_id 가 복합 PK 선두 (watchlist / portfolio / holding)
    op.create_table(
        "tn_watchlist",
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("issuer_nm", sa.String(length=200), nullable=True),
        sa.Column("market", sa.String(length=20), nullable=True),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("currency", sa.String(length=5), nullable=True),
        sa.Column("target_price", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("alert_price", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("priority", sa.String(length=5), nullable=True),
        sa.Column("use_at", sa.String(length=1), server_default="Y", nullable=True),
        sa.Column("memo", sa.String(length=1300), nullable=True),
        sa.Column("atch_file_id", sa.String(length=20), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_id", sa.String(length=100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("company_id", "ticker"),
    )

    op.create_table(
        "tn_portfolio",
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.String(length=20), nullable=False),
        sa.Column("portfolio_nm", sa.String(length=200), nullable=False),
        sa.Column("sort_ordr", sa.Integer(), nullable=True),
        sa.Column("use_at", sa.String(length=1), server_default="Y", nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_id", sa.String(length=100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("company_id", "portfolio_id"),
    )

    op.create_table(
        "tn_holding",
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("portfolio_id", sa.String(length=20), nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("holding_nm", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("avg_price", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("use_at", sa.String(length=1), server_default="Y", nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_id", sa.String(length=100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("company_id", "portfolio_id", "ticker"),
    )

    op.create_table(
        "tn_nav",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("source_message_id", sa.Integer(), nullable=True),
        sa.Column("nav_dt", sa.DateTime(), nullable=False),
        sa.Column("nav", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("benchmark", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("daily_return", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("drawdown", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_id", sa.String(length=100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_nav_company", "tn_nav", ["company_id"], unique=False)
    op.create_index("idx_nav_dt", "tn_nav", ["nav_dt"], unique=False)
    # 큐 at-least-once 재소비의 중복 적재 방지 멱등키 — NULL(수동/기존 적재행)은 제외하는 부분 유니크.
    # 방언별 where kwarg 를 둘 다 둔다: postgresql_where 가 현행 경로, mssql_where 는 롤백 여지 (#166).
    op.create_index(
        "ux_nav_source_message",
        "tn_nav",
        ["source_message_id"],
        unique=True,
        mssql_where=sa.text("source_message_id IS NOT NULL"),
        postgresql_where=sa.text("source_message_id IS NOT NULL"),
    )

    op.create_table(
        "tn_research_document",
        sa.Column("research_doc_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("atch_file_id", sa.String(length=20), nullable=False),
        sa.Column("file_sn", sa.Integer(), nullable=True),
        sa.Column("doc_title", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="uploaded", nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("error_msg", sa.String(length=1000), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_id", sa.String(length=100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("research_doc_id"),
    )
    op.create_index("idx_research_document_company", "tn_research_document", ["company_id"], unique=False)
    op.create_index("idx_research_document_atch_file", "tn_research_document", ["atch_file_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_research_document_atch_file", table_name="tn_research_document")
    op.drop_index("idx_research_document_company", table_name="tn_research_document")
    op.drop_table("tn_research_document")

    op.drop_index(
        "ux_nav_source_message",
        table_name="tn_nav",
        mssql_where=sa.text("source_message_id IS NOT NULL"),
        postgresql_where=sa.text("source_message_id IS NOT NULL"),
    )
    op.drop_index("idx_nav_dt", table_name="tn_nav")
    op.drop_index("idx_nav_company", table_name="tn_nav")
    op.drop_table("tn_nav")

    op.drop_table("tn_holding")
    op.drop_table("tn_portfolio")
    op.drop_table("tn_watchlist")

    op.drop_index("idx_message_queue_status", table_name="tn_message_queue")
    op.drop_table("tn_message_queue")

    op.drop_index("idx_board_reg_dt", table_name="tn_board")
    op.drop_table("tn_board")
