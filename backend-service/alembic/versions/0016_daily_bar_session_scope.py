"""daily_bar — 이 봉이 덮는 구간을 기록한다 (#255)

Revision ID: 0016_daily_bar_session_scope
Revises: 0015_backtest
Create Date: 2026-08-20

실측(2026-08-19, 토스 실적재)에서 **같은 컬럼이 종목마다 다른 것을 뜻한다**가 드러났다.
토스 일봉은 시간외까지 포함하는 종목이 있고(보통주 표본 25종목 중 9종목), 그 종목의
일봉 종가는 정규장 종가(15:31 봉)와 −1.86%·+4.04% 어긋났다.

백테스트가 「종가에 판다」를 계산하면 **정규장에서 낼 수 없는 가격에 체결**한 것이 된다.
그 차이는 이 레포가 이미 잰 명시 비용 3종(수수료·슬리피지·거래세)의 총합과 같은 자릿수다.

`unknown` 이 기본값인 이유 — **소스가 준 그대로일 때 그것을 「정규장」이라고 부르면 거짓말**이
된다. 이미 들어와 있는 행도 무엇인지 모르므로 `unknown` 이다 (FR-021).
"""

import sqlalchemy as sa

from alembic import op

revision = "0016_daily_bar_session_scope"
down_revision = "0015_backtest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tn_daily_bar",
        sa.Column("session_scope", sa.String(length=20), nullable=False, server_default="unknown"),
    )


def downgrade() -> None:
    op.drop_column("tn_daily_bar", "session_scope")
