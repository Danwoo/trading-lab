import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# 1. Base 클래스
class Base(DeclarativeBase):
    pass


# 2. Board 모델
class Board(Base):
    # PostgreSQL 은 따옴표 없는 식별자를 소문자로 폴딩한다 — 혼합 케이스로 정의하면 raw SQL 의
    # 따옴표 없는 참조(FROM tn_board)가 relation not found 로 깨진다. 테이블명은 소문자 snake_case.
    __tablename__ = "tn_board"
    __table_args__ = (Index("idx_board_reg_dt", "reg_dt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bbs_ty: Mapped[str | None] = mapped_column(String(5), nullable=True)
    sj: Mapped[str] = mapped_column(String(200), nullable=False)
    cn: Mapped[str | None] = mapped_column(Text, nullable=True)
    atch_file_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rdcnt: Mapped[int | None] = mapped_column(Integer, default=0)
    use_at: Mapped[str | None] = mapped_column(String(5), default="Y", server_default="Y")

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


# 3. MessageQueue (Kafka 대체 DB 메시지 큐 — producer publish → consumer 소비/적재; 시세/체결 틱 인제스트)
class MessageQueue(Base):
    # 소문자 폴딩만으로는 tn_messagequeue 가 되어 읽기 어렵다 — snake_case 로 끊어 tn_message_queue 로 둔다.
    __tablename__ = "tn_message_queue"
    __table_args__ = (Index("idx_message_queue_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


# 4. Watchlist (관심종목) 모델
class Watchlist(Base):
    __tablename__ = "tn_watchlist"

    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    issuer_nm: Mapped[str | None] = mapped_column(String(200), nullable=True)
    market: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(5), nullable=True)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    alert_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(5), nullable=True)
    use_at: Mapped[str | None] = mapped_column(String(1), default="Y", server_default="Y")
    memo: Mapped[str | None] = mapped_column(String(1300), nullable=True)
    atch_file_id: Mapped[str | None] = mapped_column(String(20), nullable=True)

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


# 4-1. ResearchDocument (리서치 문서 업로드→인덱싱 잡 스토어 — file 모듈 저장 + doc-search 인제스트 오케스트레이션 상태)
class ResearchDocument(Base):
    # 소문자 폴딩만으로는 tn_researchdocument 가 되어 읽기 어렵다 — snake_case 로 끊어 tn_research_document 로 둔다.
    __tablename__ = "tn_research_document"
    __table_args__ = (
        Index("idx_research_document_workspace", "workspace_id"),
        Index("idx_research_document_atch_file", "atch_file_id"),
    )

    research_doc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    atch_file_id: Mapped[str] = mapped_column(String(20), nullable=False)
    file_sn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doc_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # uploaded|indexed|mock-indexed|empty|failed
    status: Mapped[str] = mapped_column(String(20), default="uploaded", server_default="uploaded")
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


# 5. Portfolio → Holding (2-level master-detail 예시 — 포트폴리오 마스터 / 보유종목 디테일)
class Portfolio(Base):
    __tablename__ = "tn_portfolio"

    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    portfolio_nm: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_ordr: Mapped[int | None] = mapped_column(Integer, default=1)
    use_at: Mapped[str] = mapped_column(String(1), default="Y", server_default="Y")
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Holding(Base):
    __tablename__ = "tn_holding"

    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    portfolio_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    holding_nm: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int | None] = mapped_column(Integer, default=0)
    avg_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), default=0)
    # 종목 시장(KOSPI·KOSDAQ·NASDAQ·NYSE 등) — Watchlist.market 과 대칭(#328). 기존 행은 백필하지
    # 않는다(추정 금지) — nullable 로 두고, 비어 있으면 프론트가 "시장 정보가 비어 있다"고 있는
    # 그대로 말한다(alembic/versions/0010_holding_market.py).
    market: Mapped[str | None] = mapped_column(String(20), nullable=True)
    use_at: Mapped[str] = mapped_column(String(1), default="Y", server_default="Y")
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


# 6. Nav (producer → message queue → consumer 파이프라인이 적재하는 포트폴리오 NAV/가격 시계열, 대시보드 차트 소스)
class Nav(Base):
    __tablename__ = "tn_nav"
    __table_args__ = (
        Index("idx_nav_dt", "nav_dt"),
        Index("idx_nav_workspace", "workspace_id"),
        # 큐 at-least-once 재소비의 중복 적재 방지 멱등키. 수동/기존 적재행은 NULL 허용해야 하므로
        # 필터드(부분) 유니크 — NULL 행을 인덱스 대상에서 제외한다.
        # 방언별 kwarg 를 둘 다 둔다: postgresql_where 가 현행 경로, mssql_where 는 롤백 여지 (#166).
        # (MSSQL 은 유니크 인덱스에 NULL 을 1개만 허용해 필터가 필수였고, PostgreSQL 은 NULL 다중을
        #  허용하지만 부분 인덱스가 의도를 그대로 표현하고 인덱스도 작다.)
        Index(
            "ux_nav_source_message",
            "source_message_id",
            unique=True,
            mssql_where=text("source_message_id IS NOT NULL"),
            postgresql_where=text("source_message_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nav_dt: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    nav: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    benchmark: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    daily_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    drawdown: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


# 7. File → FileDetail (첨부파일 마스터 / 상세 — SFTP 실물 저장, DB 는 메타)
class File(Base):
    # PostgreSQL 은 따옴표 없는 식별자를 소문자로 폴딩한다 — 혼합 케이스로 정의하면 raw SQL 의
    # 따옴표 없는 참조(FROM tn_file)가 relation not found 로 깨진다. 테이블명은 소문자 snake_case.
    __tablename__ = "tn_file"
    __table_args__ = {"comment": "첨부파일"}

    # Primary Key
    atch_file_id: Mapped[str] = mapped_column(String(20), primary_key=True, comment="첨부파일 ID")

    # Audit
    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now(), comment="생성일시")
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="생성자 ID")
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), comment="수정일시")
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="수정자 ID")

    # Relationships
    details: Mapped[list["FileDetail"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class FileDetail(Base):
    __tablename__ = "tn_file_detail"
    __table_args__ = {"comment": "첨부파일 상세"}

    # Composite Primary Key
    atch_file_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("tn_file.atch_file_id", ondelete="CASCADE"), primary_key=True, comment="첨부파일 ID"
    )
    file_sn: Mapped[int] = mapped_column(Integer, primary_key=True, comment="파일 순번")

    # File Info
    file_stre_cours: Mapped[str | None] = mapped_column(String(1300), nullable=True, comment="파일 저장 경로")
    stre_file_nm: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="저장 파일명")
    orignl_file_nm: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="원본 파일명")
    file_extsn: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="파일 확장자")
    file_mg: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="파일 크기")
    file_ty: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="파일 타입")

    # Audit
    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now(), comment="생성일시")
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="생성자 ID")
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), comment="수정일시")
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="수정자 ID")

    # Relationships
    file: Mapped["File"] = relationship(back_populates="details")


# 8. Scheduler → SchedulerMember (주기 리포트 발송 스케줄 / 수신 멤버)
class Scheduler(Base):
    """스케줄러 (마스터) — 리포트 발송 잡. day_of_week/hour/minute 로 APScheduler cron 구성, period_weeks 로 주기·집계기간."""

    # PostgreSQL 은 따옴표 없는 식별자를 소문자로 폴딩한다 — 혼합 케이스로 정의하면 raw SQL 의
    # 따옴표 없는 참조(FROM tn_scheduler)가 relation not found 로 깨진다. 테이블명은 소문자 snake_case.
    __tablename__ = "tn_scheduler"

    scheduler_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduler_nm: Mapped[str] = mapped_column(String(200), nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(20), default="mon", server_default="mon")
    hour: Mapped[int] = mapped_column(Integer, default=9, server_default="9")
    minute: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    period_weeks: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )  # 1=주간 2=격주 4=월간 (집계기간·주기)
    use_at: Mapped[str] = mapped_column(String(5), default="N", server_default="N")
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class SchedulerMember(Base):
    """스케줄러 참여 멤버 (디테일) — 해당 스케줄러 발송 대상 계좌·포트폴리오."""

    # 소문자 폴딩만으로는 tn_schedulermember 가 되어 읽기 어렵다 — snake_case 로 끊어 tn_scheduler_member 로 둔다.
    __tablename__ = "tn_scheduler_member"

    scheduler_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


# 9. Instrument → SymbolAlias (시세 종목 마스터 · 소스 표기 별칭 — 오더 3 T1, AD-13 · AD-25)
class Instrument(Base):
    """종목 마스터. 통합 키는 대리키 `instrument_id`(IDENTITY, AD-13) — 화면·API 표면은 market+symbol 을 쓰고,
    대리키는 내부 조인 전용이다. 시세는 워크스페이스 스코프가 아니다(AD-10) — 이 테이블에 workspace_id 를
    두지 않는다."""

    __tablename__ = "tn_instrument"
    __table_args__ = (
        UniqueConstraint("market", "symbol", name="ux_instrument_market_symbol"),
        Index("idx_instrument_country_active", "country", "is_active"),
    )

    instrument_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # KR · US
    market: Mapped[str] = mapped_column(String(20), nullable=False)  # KOSPI·KOSDAQ·KONEX·NASDAQ·NYSE·AMEX
    # 국내 6자리 코드의 선행 0 이 죽지 않게 symbol 은 반드시 문자열이다.
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    issuer_nm: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(5), nullable=False)
    sector_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    listed_dt: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    delisted_dt: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[str] = mapped_column(String(1), default="Y", server_default="Y")

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class SymbolAlias(Base):
    """소스·표준 식별자 별칭 — 유효기간 포함(AD-25). zipline `equity_symbol_mappings` 가 선례 —
    티커 재사용 시 과거 캔들이 엉뚱한 종목에 붙는 것을 막는다. "지금 유효한" 매핑만
    (`valid_to IS NULL`) 전역 유일성을 부분 유니크 인덱스로 강제한다 — 과거(닫힌) 구간끼리의
    겹침은 DB 가 막지 않는다(애플리케이션 계층 삽입 전 검사가 필요, 구현설계 §1.2 미결 항목).

    alias_kind 는 isin·cik·cusip·figi·source:<소스명> 이다 — `source:` 합성 문자열은 소스 표기
    매핑이 이 표의 존재 이유라 의도된 것이지만, 애플리케이션 코드가 이 문자열을 파싱하게 두면
    안 된다. 상수는 `providers/` 안에서만 정의한다.
    """

    __tablename__ = "tn_symbol_alias"
    __table_args__ = (
        Index(
            "ux_symbol_alias_current",
            "alias_kind",
            "alias_value",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("tn_instrument.instrument_id"), primary_key=True)
    alias_kind: Mapped[str] = mapped_column(String(30), primary_key=True)
    valid_from: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    alias_value: Mapped[str] = mapped_column(String(50), nullable=False)
    valid_to: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


# 10. IngestRun → DailyBar · MinuteBar (시세 캔들 · 적재 이력 — 오더 3 T2, AD-12 · AD-14 · AD-15 · AD-18 · AD-26)
class IngestRun(Base):
    """적재 이력 겸 잡 레코드(AD-12) — 요청·실행·이력 셋을 겸한다. 새 큐 테이블을 만들지 않는다.
    `workspace_id` 는 "누가 요청했나"(키의 출처)일 뿐, 적재된 캔들 자체는 워크스페이스 스코프가
    아니다(AD-10) — `tn_daily_bar`·`tn_minute_bar` 에는 이 컬럼을 두지 않는다."""

    __tablename__ = "tn_ingest_run"
    __table_args__ = (
        Index("idx_ingest_run_source_status", "source", "status"),
        Index("idx_ingest_run_started", "started_dt"),
    )

    run_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    job_kind: Mapped[str] = mapped_column(String(30), nullable=False)  # instrument_master·daily_bar·minute_bar
    scope: Mapped[str | None] = mapped_column(String(200), nullable=True)
    period_from: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # queued → running → succeeded · failed · rate_limited
    status: Mapped[str] = mapped_column(String(20), default="queued", server_default="queued")
    cursor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    written_rows: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    skipped_rows: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    failed_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    workspace_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    reg_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class DailyBar(Base):
    """일봉 OHLCV — 단일 테이블(AD-14, 700만 행·1GB 는 파티셔닝 없이 다루는 통상 규모).
    anti-patterns 룰 5(감사 컬럼 4종)의 "스키마 양쪽 모두 컬럼 정의 안 됨" 예외를 명시적으로
    택한다 — `source`·`ingest_run_id`·`ingested_at` 가 행 단위 provenance 로 감사 컬럼보다
    정확하다(구현설계 §2.2). 무수정 원본이 정본이고 `adj_policy` 에 적용 정책을 기록한다(AD-18)."""

    __tablename__ = "tn_daily_bar"
    __table_args__ = (
        Index("idx_daily_bar_date", "trade_date"),
        Index("idx_daily_bar_run", "ingest_run_id"),
    )

    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("tn_instrument.instrument_id"), primary_key=True)
    trade_date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    trade_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    adj_policy: Mapped[str] = mapped_column(String(20), nullable=False)  # raw·adj_split·adj_split_div
    #: 이 봉이 **어느 구간**을 덮는가 — `regular`(정규장만) · `unknown`(소스가 준 그대로).
    #:
    #: 소스마다, 심지어 **같은 소스의 종목마다** 다르다: 토스 일봉은 시간외를 포함하는 종목이
    #: 있고(보통주 표본 25종목 중 9종목) 그 종목의 종가는 정규장 종가와 최대 4% 어긋났다.
    #: 같은 컬럼이 종목마다 다른 것을 뜻하면 백테스트가 정규장에서 낼 수 없는 가격에 체결한다.
    #: 그래서 **무엇인지 모르면 모른다고 적는다** (FR-021 — 없는 값을 0 으로 뭉개지 않는다).
    session_scope: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown", server_default="unknown")
    ingest_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tn_ingest_run.run_id"), nullable=True)
    ingested_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())


class MinuteBar(Base):
    """분봉 OHLCV — `PARTITION BY RANGE (ts)` 월 단위(AD-15, 삭제가 목적 — `DROP PARTITION` 은 즉시·
    잠금 없음). **1분봉 전용**(AD-26) — `interval_min` 은 방어용 CHECK 이지 새 축이 아니다. PK 는
    바꾸지 않는다. 실제 파티션 자식 테이블 생성은 alembic autogenerate 가 다루지 못해 마이그레이션이
    손으로 12개월분을 선행 생성한다(구현설계 §3.2). 감사 컬럼 4종은 `DailyBar` 와 같은 이유로 생략."""

    __tablename__ = "tn_minute_bar"
    __table_args__ = (
        CheckConstraint("interval_min = 1", name="ck_minute_bar_interval_min"),
        {"postgresql_partition_by": "RANGE (ts)"},
    )

    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("tn_instrument.instrument_id"), primary_key=True)
    ts: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)
    interval_min: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1, server_default="1")
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    adj_policy: Mapped[str] = mapped_column(String(20), nullable=False)
    ingest_run_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("tn_ingest_run.run_id"), nullable=True)
    ingested_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())


# 12. Backtest (#200 M3 덩어리 1 — 스펙 §6 「엔진이 남겨야 할 것」)
#
# **이 모델들은 raw SQL 을 대신하지 않는다.** 런타임 조회는 종전대로 repository 의 raw SQL 이고,
# 여기 있는 이유는 `alembic check` 가 마이그레이션과 대조할 대상을 갖게 하기 위해서다 —
# 모델에 없는 테이블은 alembic 이 「남의 것」으로 보고 드리프트 비교에서 빼, 컬럼이 사라져도
# check 가 통과한다 (`verify_alembic_model_coverage.py` 가 그 구멍을 막는다).
class BacktestRun(Base):
    __tablename__ = "tn_backtest_run"
    # 인덱스는 마이그레이션과 **양쪽에** 있어야 한다 — 모델에 없으면 alembic check 가
    # 「지워야 할 인덱스」로 읽어 드리프트로 잡는다.
    __table_args__ = (
        Index("ix_backtest_run_workspace", "workspace_id", "run_id"),
        Index("ix_backtest_run_parent", "parent_run_id"),
    )

    run_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 계보와 시도 순번 — 「무엇이 달라졌나」·「몇 번째 시도인가」·「이력 복원」 셋을 떠받친다.
    parent_run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    bot_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    strategy_key: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    universe_def: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    universe_as_of: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    data_snapshot_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adj_policy: Mapped[str] = mapped_column(String(30), nullable=False, server_default="unadjusted")
    cost_assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    #: 같은 조합을 **비용 0으로 다시 돌린** 요약 (SC-007 「미반영 vs 반영을 나란히」).
    #: `NULL` 은 「격차가 0」이 아니라 **「대조군을 안 돌린 옛 실행」**이다 — 화면이 그 둘을 가른다.
    costless_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    period_from: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    period_to: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    failed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    finished_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    reg_dt: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    reg_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mod_dt: Mapped[datetime.datetime | None] = mapped_column(DateTime, onupdate=func.now(), nullable=True)
    mod_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class BacktestEquity(Base):
    __tablename__ = "tn_backtest_equity"

    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tn_backtest_run.run_id", ondelete="CASCADE"), primary_key=True
    )
    dt: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    equity: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    position_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    gross_exposure: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, server_default="0")


class BacktestTrade(Base):
    __tablename__ = "tn_backtest_trade"
    __table_args__ = (Index("ix_backtest_trade_run", "run_id", "entry_ts"),)

    trade_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tn_backtest_run.run_id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_ts: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    exit_ts: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    fill_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, server_default="0")
    slippage: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, server_default="0")
    #: 증권거래세 — **매도에만** 붙고 국내 명시 비용 중 가장 크다(0.18% vs 수수료 0.015%).
    #: 이 컬럼이 없으면 「치른 비용」이 가장 큰 항목을 빼고 답한다 (#271).
    tax: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, server_default="0")
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    # 「얼마나 물렸다 살아났나」 — 평균만 보면 견딜 수 있는 전략인지 모른다.
    mae: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    mfe: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)


class BacktestSignal(Base):
    __tablename__ = "tn_backtest_signal"
    __table_args__ = (Index("ix_backtest_signal_run", "run_id", "dt"),)

    signal_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tn_backtest_run.run_id", ondelete="CASCADE"), nullable=False
    )
    dt: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    instrument_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 「왜 샀나」를 되짚는 유일한 근거. 없으면 사후에 신호를 재구성해야 하고,
    # 재구성은 그때의 코드가 아니라 지금의 코드로 하게 된다.
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    factors: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))


class BacktestCash(Base):
    __tablename__ = "tn_backtest_cash"
    __table_args__ = (Index("ix_backtest_cash_run", "run_id", "dt"),)

    cash_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tn_backtest_run.run_id", ondelete="CASCADE"), nullable=False
    )
    dt: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    # initial · deposit · withdraw · fee · trade — 현금이 왜 움직였는지.
    event_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
