"""market_bars — 일봉·분봉·적재 이력 (오더 3 T2)

Revision ID: 0012_market_bars
Revises: 0011_instrument_master
Create Date: 2026-08-03

번호 메모: 0008(`0011_instrument_master`, 작성 당시 파일명은 `0008_instrument_master`)과 동일한
사유로 오더 원본의 0007 대신 0009 를 썼다 — 0006 은 main 에 머지됐고(PR #340) 0007 은 미머지
PR #347 이 점유 중이다(확인 절차·근거는 0011 의 docstring).

## 재배치 — 0009 가 아니라 0012 인 이유 (#378, 머지 시점 2026-08-04)

`0010_holding_market`(#328)이 main 에 먼저 머지되어 `0008`(→`0011`)·`0010` 이 `0007` 에서
형제로 갈라졌다. `0011_instrument_master` 의 재배치와 함께 이 리비전도 그 뒤로 밀었다 — 자세한
사유는 `0011_instrument_master.py` docstring 참조.

`tn_minute_bar` 는 `PARTITION BY RANGE (ts)` 월 단위(AD-15)다. alembic autogenerate 는 선언적
파티션 부모/자식 구조를 다루지 못하므로(구현설계 §3.2 "대가" 표) 이 리비전은 손으로 작성한다.
파티션은 이 리비전의 Create Date(2026-08)를 기준으로 향후 12개월분(2026-08 ~ 2027-07)을
선행 생성한다 — 실행 시각의 `now()` 가 아니라 고정된 기준월을 쓴다(재실행·테스트마다 결과가
달라지지 않게, up/down 반복 검증이 결정적이게).

세 테이블 모두 `frontend`(Prisma) 스키마 테이블을 참조하지 않는다 — 0008 과 같은 이유로 #333
가드가 적용될 대상이 없다. `tn_ingest_run.workspace_id` 는 "누가 요청했나"(키의 출처)일 뿐
FK 가 아니다 — 시세는 워크스페이스 스코프가 아니다(AD-10, 기존 `Watchlist.workspace_id` 등과
같은 관례).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_market_bars"
# #378 재배치 — 위 리비전 번호 설명 참조. 0011_instrument_master 뒤에 온다.
down_revision: str | Sequence[str] | None = "0011_instrument_master"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PARTITION_START_YEAR = 2026
_PARTITION_START_MONTH = 8
_PARTITION_MONTHS = 12


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _partition_months() -> list[tuple[int, int]]:
    months = []
    year, month = _PARTITION_START_YEAR, _PARTITION_START_MONTH
    for _ in range(_PARTITION_MONTHS):
        months.append((year, month))
        year, month = _next_month(year, month)
    return months


def _partition_name(year: int, month: int) -> str:
    return f"tn_minute_bar_{year:04d}_{month:02d}"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tn_ingest_run",
        sa.Column("run_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("source", sa.String(30), nullable=False),
        # instrument_master · daily_bar · minute_bar
        sa.Column("job_kind", sa.String(30), nullable=False),
        sa.Column("scope", sa.String(200), nullable=True),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        # queued → running → succeeded · failed · rate_limited
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("cursor", sa.String(200), nullable=True),
        sa.Column("written_rows", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("skipped_rows", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("failed_reason", sa.String(1000), nullable=True),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("started_dt", sa.DateTime(), nullable=True),
        sa.Column("finished_dt", sa.DateTime(), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reg_id", sa.String(100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(100), nullable=True),
    )
    op.create_index("idx_ingest_run_source_status", "tn_ingest_run", ["source", "status"])
    op.create_index("idx_ingest_run_started", "tn_ingest_run", ["started_dt"])

    # 감사 컬럼 4종을 두지 않는다 — source · ingest_run_id · ingested_at 가 provenance(구현설계 §2.2,
    # anti-patterns 룰 5 "대용량 시계열" 예외).
    op.create_table(
        "tn_daily_bar",
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("tn_instrument.instrument_id"), primary_key=True),
        sa.Column("trade_date", sa.Date(), primary_key=True),
        sa.Column("open", sa.Numeric(18, 4), nullable=False),
        sa.Column("high", sa.Numeric(18, 4), nullable=False),
        sa.Column("low", sa.Numeric(18, 4), nullable=False),
        sa.Column("close", sa.Numeric(18, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("trade_value", sa.Numeric(20, 2), nullable=True),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("adj_policy", sa.String(20), nullable=False),  # raw · adj_split · adj_split_div (AD-18)
        sa.Column("ingest_run_id", sa.Integer(), sa.ForeignKey("tn_ingest_run.run_id"), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_daily_bar_date", "tn_daily_bar", ["trade_date"])
    op.create_index("idx_daily_bar_run", "tn_daily_bar", ["ingest_run_id"])

    # 파티션드 부모 테이블. FK·PK 는 파티션 키(ts)를 포함해야 하며, PK(instrument_id, ts)가 이미
    # 포함하므로 별도 처리가 필요 없다 (구현설계 §3.2 "대가" 표).
    op.create_table(
        "tn_minute_bar",
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("tn_instrument.instrument_id"), primary_key=True),
        sa.Column("ts", sa.DateTime(), primary_key=True),
        sa.Column("interval_min", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("open", sa.Numeric(18, 4), nullable=False),
        sa.Column("high", sa.Numeric(18, 4), nullable=False),
        sa.Column("low", sa.Numeric(18, 4), nullable=False),
        sa.Column("close", sa.Numeric(18, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("adj_policy", sa.String(20), nullable=False),
        sa.Column("ingest_run_id", sa.Integer(), sa.ForeignKey("tn_ingest_run.run_id"), nullable=True),
        sa.Column("ingested_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        # 1분봉 전용(AD-26) — 5·15·30·60분봉은 합성하지 저장하지 않는다는 PRD 가정을 스키마로 강제.
        # 방어용 CHECK 이지 새 축이 아니다 — PK 는 바꾸지 않는다.
        sa.CheckConstraint("interval_min = 1", name="ck_minute_bar_interval_min"),
        postgresql_partition_by="RANGE (ts)",
    )

    # 향후 12개월분 파티션 선행 생성 — 런타임 DDL 없이 적재 워커가 "파티션이 있는가"만 확인하게 한다.
    for year, month in _partition_months():
        next_year, next_month = _next_month(year, month)
        name = _partition_name(year, month)
        op.execute(
            f"CREATE TABLE {name} PARTITION OF tn_minute_bar "
            f"FOR VALUES FROM ('{year:04d}-{month:02d}-01') TO ('{next_year:04d}-{next_month:02d}-01')"
        )


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL 은 파티션드 부모를 DROP TABLE 하면 자식 파티션도 함께 지운다 — 개별 DROP 이 불필요하다.
    op.drop_table("tn_minute_bar")
    op.drop_table("tn_daily_bar")
    op.drop_table("tn_ingest_run")
