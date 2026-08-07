"""holding_market — tn_holding 에 시장(market) 컬럼 추가 (#328)

Revision ID: 0010_holding_market
Revises: 0007_kst_write_shift_correction
Create Date: 2026-08-03

리드 결정(#328, 2026-08-02) — 「㉠ 백엔드 스키마에 market 추가」. `tn_watchlist.market` 과
대칭을 맞춘다. 보유 종목 클릭 시 터미널 패널이 안 열리는 근본 원인(`Holding` 에 시장 정보가
없어 `resolveRegion` 이 UNKNOWN 으로 판정)을 스키마 레벨에서 해소한다.

**백필 방침 — 추정하지 않는다.** 기존 행은 `market` 을 NULL 로 둔다. 어느 시장인지 확정할 근거
(종목마스터 조인 등)가 이 리비전 시점에 없으므로 지어내지 않는다. 프론트(#326 O11)는 이미 빈
시장 문자열을 "이 종목에 등록된 시장 값이 비어 있습니다" 로 정직하게 보여주도록 되어 있다
(frontend/components/features/Terminal/PanelSlot.tsx 의 MARKET_MISSING_VERDICT) — 새 행은
등록·수정 시 값을 채우면 그때부터 패널이 열린다.

## 번호 메모

`0008`·`0009` 는 영구 결번이다 — 그 번호를 예약하던 브랜치가 머지되면서
`0011_instrument_master`·`0012_market_bars` 로 재배치됐다(#378). 체인은
`0007 → 0010 → 0011 → 0012` 단일 head 이고, 결번은 나중에도 채우지 않는다 — 순서를 정하는
것은 파일명이 아니라 `down_revision` 이다.

## fail-closed 가드

`tn_holding` 은 이 서비스(alembic) 소유 테이블이라 #333 이 고친 "frontend(Prisma) 스키마
db-migrate 순서" 가드와는 다른 위험이다 — 그래도 대상 테이블이 없는 상태로 조용히 넘어가지
않고 예외로 죽는다(0005·0006 이 세운 관례를 이 서비스 소유 테이블에도 동일하게 적용).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_holding_market"
down_revision: str | Sequence[str] | None = "0007_kst_write_shift_correction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_MISSING_SQL = "SELECT to_regclass('tn_holding') IS NULL"


def _table_missing(bind: sa.engine.Connection) -> bool:
    return bool(bind.execute(sa.text(_TABLE_MISSING_SQL)).scalar())


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if _table_missing(bind):
        raise RuntimeError(
            "tn_holding 테이블이 없습니다 — 이 리비전은 0001_baseline 이후에 돌아야 합니다. "
            "alembic 리비전 체인이 깨졌거나 잘못된 DB 를 겨눈 것인지 확인하세요."
        )
    op.add_column("tn_holding", sa.Column("market", sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tn_holding", "market")
