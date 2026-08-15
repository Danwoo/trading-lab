"""bot — 봇과 봇에 실린 전략 (#150 B0)

Revision ID: 0014_bot
Revises: 0013_anonymize_withdrawn_audit
Create Date: 2026-08-15

전략은 **파일**이고 봇은 **그 조합**이다(결정 로그 2026-07-28). 그래서 전략 자체는 DB 에
없고, `tn_bot_strategy.strategy_key` 가 파일이 선언한 `key` 를 **FK 없이** 가리킨다 —
규약과 대가는 `.docs/specs/2026-08-15-strategy-contract.md` §6.

`workspace_id` 는 기존 `tn_watchlist` 등과 같은 관례로 FK 를 걸지 않는다 —
`frontend`(Prisma) 스키마 테이블을 `public` 이 참조하면 `prisma db push` 와 충돌한다(#333).

`param_sources` 가 지금 있는 이유: 실험대 스펙 §8.6.3 의 안전장치 「출처가 남는다」가 B3 의
완료 조건이라, 저장할 자리를 여기서 내 두지 않으면 B3 이 마이그레이션부터 시작하게 된다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_bot"
down_revision: str | Sequence[str] | None = "0013_anonymize_withdrawn_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COMBINE_RULES = ("AND", "OR", "SCORE")
UNIVERSE_KINDS = ("POOL", "WATCHLIST", "LIST")
BOT_ROLES = ("READONLY", "PROPOSE", "EXECUTE")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tn_bot",
        sa.Column("bot_id", sa.Integer(), sa.Identity(), primary_key=True),
        # 다른 테이블(`tn_ingest_run` 등)과 같은 정수형. `require_workspace_id()` 가 int 를 준다.
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("bot_nm", sa.String(100), nullable=False),
        sa.Column("bot_desc", sa.String(500), nullable=True),
        # 결합 — 전략들을 어떻게 섞는가
        sa.Column("combine_rule", sa.String(10), nullable=False, server_default="AND"),
        # 유니버스 — 어느 종목군을 도는가
        sa.Column("universe_kind", sa.String(20), nullable=False, server_default="WATCHLIST"),
        sa.Column("universe_ref", postgresql.JSONB(), nullable=True),
        # 자금 배분
        sa.Column("alloc_per_symbol", sa.Numeric(18, 2), nullable=True),
        sa.Column("max_positions", sa.Integer(), nullable=True),
        # 리스크
        sa.Column("stop_loss_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("take_profit_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("max_trades_per_day", sa.Integer(), nullable=True),
        # 봇의 신원 — 조회만 / 제안 / 승인 후 실행 (결정 로그 2026-07-28)
        sa.Column("bot_role", sa.String(20), nullable=False, server_default="READONLY"),
        sa.Column("use_at", sa.String(1), nullable=False, server_default="Y"),
        # 설정별 출처 — {"stop_loss_pct": "AI_SUGGESTED"} (실험대 스펙 §8.6.3)
        sa.Column("param_sources", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reg_dt", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reg_id", sa.String(100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(100), nullable=True),
        sa.CheckConstraint(_in_list("combine_rule", COMBINE_RULES), name="ck_tn_bot_combine_rule"),
        sa.CheckConstraint(_in_list("universe_kind", UNIVERSE_KINDS), name="ck_tn_bot_universe_kind"),
        sa.CheckConstraint(_in_list("bot_role", BOT_ROLES), name="ck_tn_bot_bot_role"),
        sa.CheckConstraint("max_positions IS NULL OR max_positions > 0", name="ck_tn_bot_max_positions"),
    )
    # 워크스페이스 안에서 봇 이름은 유일하다 — 목록에서 같은 이름 둘을 구분할 수 없다.
    op.create_unique_constraint("uq_tn_bot_workspace_nm", "tn_bot", ["workspace_id", "bot_nm"])
    op.create_index("ix_tn_bot_workspace", "tn_bot", ["workspace_id"])

    op.create_table(
        "tn_bot_strategy",
        sa.Column("bot_strategy_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "bot_id",
            sa.Integer(),
            sa.ForeignKey("tn_bot.bot_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 전략 파일이 선언한 key — 전략은 파일이라 DB 에 없어서 FK 가 아니다
        sa.Column("strategy_key", sa.String(40), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("param_sources", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("weight", sa.Numeric(6, 2), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reg_dt", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reg_id", sa.String(100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(100), nullable=True),
    )
    # 한 봇에 같은 전략을 두 번 실으면 어느 쪽 파라미터가 도는지 모호해진다.
    op.create_unique_constraint("uq_tn_bot_strategy_bot_key", "tn_bot_strategy", ["bot_id", "strategy_key"])
    op.create_index("ix_tn_bot_strategy_bot", "tn_bot_strategy", ["bot_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_tn_bot_strategy_bot", table_name="tn_bot_strategy")
    op.drop_constraint("uq_tn_bot_strategy_bot_key", "tn_bot_strategy", type_="unique")
    op.drop_table("tn_bot_strategy")
    op.drop_index("ix_tn_bot_workspace", table_name="tn_bot")
    op.drop_constraint("uq_tn_bot_workspace_nm", "tn_bot", type_="unique")
    op.drop_table("tn_bot")


def _in_list(column: str, allowed: tuple[str, ...]) -> str:
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"
