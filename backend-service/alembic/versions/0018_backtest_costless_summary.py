"""tn_backtest_run.costless_summary — 같은 조합을 비용 0으로 다시 돌린 결과 요약.

SC-007 이 요구하는 것은 「비용 미반영 vs 반영을 **나란히**」다. 치른 비용 한 값만으로는
그 격차를 못 말한다 — 비용은 현금을 깎아 **체결 수량 자체를 바꾸므로**, 나눗셈으로 흉내내면
거래 수가 다른 세계를 같은 세계인 척하게 된다. 그래서 대조군을 실제로 돌려 그 요약을 남긴다.

`NULL` 은 「격차가 0」이 아니라 **「이 마이그레이션 이전에 돌린 실행이라 대조군이 없다」**다.
화면은 그 둘을 갈라 말해야 한다.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0018_backtest_costless_summary"
down_revision = "0017_backtest_trade_tax"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tn_backtest_run",
        sa.Column("costless_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema=None,
    )


def downgrade() -> None:
    op.drop_column("tn_backtest_run", "costless_summary", schema=None)
