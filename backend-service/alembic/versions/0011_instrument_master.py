"""instrument_master — 종목 마스터와 소스 표기 별칭 (오더 3 T1)

Revision ID: 0011_instrument_master
Revises: 0010_holding_market
Create Date: 2026-08-03

## 재배치 — 0008 이 아니라 0011 인 이유 (#378, 머지 시점 2026-08-04)

이 리비전은 애초 `0008_instrument_master` 로 작성됐다. 그런데 main 에는 그 사이
`0010_holding_market`(#328, down_revision=`0007_kst_write_shift_correction`)이 먼저 머지됐다 —
`0008`·`0010` 이 둘 다 `0007` 에 체이닝되어 있어 그대로 두면 `alembic heads` 가 갈라진다
(`0010_holding_market.py` docstring 이 이 시나리오와 처리 절차를 미리 적어 두었다). fix-303-timezone
이 `0006` 충돌을 `0007` 로 재배치한 선례(커밋 dbc1a47)와 동일하게, **파일명·리비전 ID 를 `0011` 로
옮기고 `down_revision` 을 `0010_holding_market` 으로 재지정**했다 — 뒤이은 `0009_market_bars` 도
`0012` 로 함께 밀렸다(그 파일 docstring 참조).

이 리비전이 만드는 두 테이블은 이 서비스(alembic)가 소유하며 `frontend`(Prisma) 스키마의 어떤
테이블도 참조하지 않는다 — #333 이 고친 "대상 테이블 부재 시 fail-closed" 가드(0005·0006 이 실례)는
`frontend`(Prisma) 소유 테이블에 대한 db-migrate 실행 순서 의존이 있을 때 필요한 것이다(현재
`process-compose.yaml` 은 prisma db push 를 alembic 보다 먼저 돌린다). 여기는 이 서비스가 처음부터
끝까지 소유하는 새 `public` 테이블을 `CREATE TABLE` 하는 것뿐이라 그 가드가 적용될 대상(참조할
남의 스키마 테이블)이 없다.

시세는 워크스페이스 스코프가 아니다(AD-10) — 두 테이블 모두 `workspace_id` 를 두지 않는다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_instrument_master"
# #378 재배치 — 위 리비전 번호 설명 참조. 0010_holding_market(#328) 뒤에 온다.
down_revision: str | Sequence[str] | None = "0010_holding_market"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tn_instrument",
        sa.Column("instrument_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("market", sa.String(20), nullable=False),
        # 국내 6자리 코드의 선행 0 이 죽지 않게 symbol 은 반드시 문자열이다 (AD-13).
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("issuer_nm", sa.String(200), nullable=False),
        sa.Column("currency", sa.String(5), nullable=False),
        sa.Column("sector_code", sa.String(20), nullable=True),
        sa.Column("listed_dt", sa.Date(), nullable=True),
        sa.Column("delisted_dt", sa.Date(), nullable=True),
        sa.Column("is_active", sa.String(1), nullable=False, server_default="Y"),
        sa.Column("reg_dt", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reg_id", sa.String(100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(100), nullable=True),
        sa.UniqueConstraint("market", "symbol", name="ux_instrument_market_symbol"),
    )
    op.create_index("idx_instrument_country_active", "tn_instrument", ["country", "is_active"])

    op.create_table(
        "tn_symbol_alias",
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("tn_instrument.instrument_id"), primary_key=True),
        # isin · cik · cusip · figi · source:<소스명> — 이 문자열은 providers/ 안에서만 만든다.
        sa.Column("alias_kind", sa.String(30), primary_key=True),
        sa.Column("valid_from", sa.Date(), primary_key=True),
        sa.Column("alias_value", sa.String(50), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("reg_dt", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reg_id", sa.String(100), nullable=True),
        sa.Column("mod_dt", sa.DateTime(), nullable=True),
        sa.Column("mod_id", sa.String(100), nullable=True),
    )
    # "지금 유효한" 매핑만(valid_to IS NULL) 전역 유일성을 강제한다 (AD-25). 과거(닫힌) 구간끼리의
    # 겹침은 이 인덱스로 막히지 않는다 — 애플리케이션 계층(적재·별칭 등록 경로)이 삽입 전 검사한다.
    op.create_index(
        "ux_symbol_alias_current",
        "tn_symbol_alias",
        ["alias_kind", "alias_value"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tn_symbol_alias")
    op.drop_table("tn_instrument")
