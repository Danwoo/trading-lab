"""backtest — 실행·자산곡선·거래·신호·현금 원장 (#200 M3 덩어리 1)

Revision ID: 0015_backtest
Revises: 0014_bot
Create Date: 2026-08-18

컬럼 구성은 실험대 스펙 §6 「엔진이 남겨야 할 것」의 표를 그대로 옮긴 것이다 —
화면 요구에서 역산한 목록이라 여기서 다시 설계하지 않는다.

`parent_run_id` 와 `attempt_no` 두 컬럼이 세 요구를 동시에 떠받친다: 「무엇이 달라졌나」·
「몇 번째 시도인가」·「이력 복원」. 이게 없으면 셋 다 계산할 수 없다.

**현금 원장이 따로 있는 이유** — 초기자금과 입출금 이벤트를 기록해야 현금 비중이 닫힌다.
자산곡선의 `cash` 만으로는 「돈이 들어와서 늘었는지 벌어서 늘었는지」를 가를 수 없다.

`workspace_id` 는 기존 `tn_watchlist`·`tn_bot` 과 같은 관례로 FK 를 걸지 않는다 —
`frontend`(Prisma) 스키마 테이블을 `public` 이 참조하면 `prisma db push` 와 충돌한다.

`strategy_key` 도 FK 가 없다. 전략은 **파일**이고 DB 에 없다(결정 로그 2026-07-28) —
`tn_bot_strategy` 와 같은 규약이다.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015_backtest"
down_revision: str | Sequence[str] | None = "0014_bot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit() -> list[sa.Column]:
    """공통 감사 컬럼 — 이 레포의 모든 업무 테이블이 같은 넷을 단다."""
    return [
        sa.Column("reg_dt", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("reg_id", sa.String(100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(100), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "tn_backtest_run",
        sa.Column("run_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        # 계보 — 같은 부모에서 갈라진 실행끼리 「무엇이 달라졌나」를 계산한다.
        sa.Column("parent_run_id", sa.BigInteger(), nullable=True),
        # 시도 순번 — 사용자가 **처음 평가하는 조합마다** 오른다. 격자를 훑는 것도 시도다
        # (스펙 §8.5.2). 이게 없으면 다중검정 경고가 자기모순에 빠진다.
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("bot_id", sa.BigInteger(), nullable=True),
        sa.Column("strategy_key", sa.String(100), nullable=False),
        sa.Column("strategy_version", sa.String(50), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        # 유니버스는 **정의와 as-of 를 함께** 남긴다. 「그때 그 종목 목록」을 복원할 수 없으면
        # 같은 실행을 다시 돌려도 다른 답이 나온다 (생존 편향).
        sa.Column("universe_def", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("universe_as_of", sa.Date(), nullable=True),
        # 데이터 스냅샷 — 적재본이 갱신돼도 이 실행이 무엇을 봤는지 남는다.
        sa.Column("data_snapshot_id", sa.String(100), nullable=True),
        sa.Column("adj_policy", sa.String(30), nullable=False, server_default="unadjusted"),
        # 비용 가정. 스펙 §8.5.1 — 위탁수수료 0.15% 는 10배 오차였다. 왕복 0.015% 수준 +
        # 증권거래세(매도만)가 맞다. 기본값을 여기 박지 않고 실행마다 남긴다.
        sa.Column("cost_assumptions", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("period_from", sa.Date(), nullable=False),
        sa.Column("period_to", sa.Date(), nullable=False),
        sa.Column("initial_cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("failed_reason", sa.Text(), nullable=True),
        sa.Column("started_dt", sa.DateTime(), nullable=True),
        sa.Column("finished_dt", sa.DateTime(), nullable=True),
        *_audit(),
    )
    op.create_index("ix_backtest_run_workspace", "tn_backtest_run", ["workspace_id", "run_id"])
    op.create_index("ix_backtest_run_parent", "tn_backtest_run", ["parent_run_id"])

    op.create_table(
        "tn_backtest_equity",
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("dt", sa.Date(), nullable=False),
        sa.Column("equity", sa.Numeric(20, 4), nullable=False),
        sa.Column("cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("position_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gross_exposure", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("run_id", "dt"),
        sa.ForeignKeyConstraint(["run_id"], ["tn_backtest_run.run_id"], ondelete="CASCADE"),
    )

    op.create_table(
        "tn_backtest_trade",
        sa.Column("trade_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("entry_ts", sa.DateTime(), nullable=False),
        sa.Column("exit_ts", sa.DateTime(), nullable=True),
        sa.Column("qty", sa.Numeric(20, 6), nullable=False),
        sa.Column("fill_price", sa.Numeric(20, 6), nullable=False),
        sa.Column("exit_price", sa.Numeric(20, 6), nullable=True),
        sa.Column("fee", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("slippage", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("realized_pnl", sa.Numeric(20, 6), nullable=True),
        # MAE/MFE — 「얼마나 물렸다 살아났나」. 평균만 보면 견딜 수 있는 전략인지 모른다.
        sa.Column("mae", sa.Numeric(20, 6), nullable=True),
        sa.Column("mfe", sa.Numeric(20, 6), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["tn_backtest_run.run_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_backtest_trade_run", "tn_backtest_trade", ["run_id", "entry_ts"])

    op.create_table(
        "tn_backtest_signal",
        sa.Column("signal_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("dt", sa.Date(), nullable=False),
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        # 조건별 통과 여부와 팩터 값 — 「왜 샀나」를 되짚는 유일한 근거다. 이게 없으면
        # 사후에 신호를 재구성해야 하고, 재구성은 그때의 코드가 아니라 지금의 코드로 한다.
        sa.Column("conditions", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("factors", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["run_id"], ["tn_backtest_run.run_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_backtest_signal_run", "tn_backtest_signal", ["run_id", "dt"])

    op.create_table(
        "tn_backtest_cash",
        sa.Column("cash_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("dt", sa.Date(), nullable=False),
        # initial · deposit · withdraw · fee · trade — 현금이 왜 움직였는지.
        sa.Column("event_kind", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["tn_backtest_run.run_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_backtest_cash_run", "tn_backtest_cash", ["run_id", "dt"])


def downgrade() -> None:
    op.drop_table("tn_backtest_cash")
    op.drop_table("tn_backtest_signal")
    op.drop_table("tn_backtest_trade")
    op.drop_table("tn_backtest_equity")
    op.drop_table("tn_backtest_run")
