"""backtest_trade — 증권거래세를 거래에 기록한다 (#271)

Revision ID: 0016_backtest_trade_tax
Revises: 0015_backtest
Create Date: 2026-08-20

증권거래세는 국내 명시 비용 중 **가장 크다**(0.15% vs 수수료 0.015%). 엔진은 `sell_cost` 안에서
차감만 하고 거래에 남기지 않아, 「이 성과가 무엇을 치르고 남은 것인가」를 물으면 가장 큰 항목을
빼고 답하게 된다.

제품 정의 §5 W4 가 「미반영 대비 격차가 함께 표시」를 완료 조건으로 세운 그 숫자다.
"""

import sqlalchemy as sa

from alembic import op

revision = "0016_backtest_trade_tax"
down_revision = "0015_backtest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tn_backtest_trade",
        sa.Column("tax", sa.Numeric(20, 6), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("tn_backtest_trade", "tax")
