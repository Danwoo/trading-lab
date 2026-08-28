"""
Alembic Migration Environment Configuration

이 모듈은 Alembic의 마이그레이션 환경을 설정합니다.
`alembic upgrade head`(스키마 적용 경로) 와 `alembic revision --autogenerate`(모델 대비 diff)
모두 이 파일을 거칩니다.
"""

import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import Table, engine_from_config, event, pool

from alembic import context

# ==============================================================================
# Path Configuration
# ==============================================================================

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(os.path.dirname(current_dir), "app")

if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from models.schema import Base

# ==============================================================================
# Alembic Configuration
# ==============================================================================

config = context.config

# alembic.ini 파일에서 로깅 설정 로드
if config.config_file_name:
    fileConfig(config.config_file_name)

# SQLAlchemy 모델의 메타데이터 (테이블 정의)
target_metadata = Base.metadata


# 어느 DB 를 향하고 있는지 + 그 좌표가 어디서 왔는지. 연결이 실패했을 때 이것을 함께 낸다 (#399).
db_target: dict[str, str] = {}


def get_db_url() -> str:
    """마이그레이션 대상 DB URL 을 해석한다.

    두 진입점을 모두 지원한다:
      - `alembic` CLI 직접 실행 — 서비스 설정(app/.env.{APP_ENV} → core.config.settings)에서 조립한다.
      - ALEMBIC_DB_URL 환경변수 — CI 처럼 서비스 설정 없이 대상을 직접 주는 경로.

    URL 은 configparser 보간을 거치므로 `%` 는 `%%` 로 이스케이프해야 한다.
    """
    if db_url := os.getenv("ALEMBIC_DB_URL"):
        db_target.update(where="(URL 은 찍지 않는다 — 비밀번호가 들어 있다)", origin="ALEMBIC_DB_URL 환경변수")
        return db_url

    app_env = os.getenv("APP_ENV", "development")
    env_file = os.path.join(app_dir, f".env.{app_env}")
    load_dotenv(env_file)

    from core.config import settings
    from utils.common.database_utils import get_sql_db_url

    db_target.update(
        where=f"{settings.BACKEND_SQL_DB_HOST}:{settings.BACKEND_SQL_DB_PORT}/{settings.BACKEND_SQL_DB_NAME}",
        origin=(
            f"{os.path.relpath(env_file, os.path.dirname(current_dir))} 의 "
            "BACKEND_SQL_DB_HOST·BACKEND_SQL_DB_PORT (프로세스 환경변수가 있으면 그쪽이 이긴다)"
        ),
    )
    url = get_sql_db_url(
        driver=settings.BACKEND_SQL_DB_DRIVER,
        odbc_driver=settings.BACKEND_SQL_DB_ODBC_DRIVER,
        host=settings.BACKEND_SQL_DB_HOST,
        port=settings.BACKEND_SQL_DB_PORT,
        dbname=settings.BACKEND_SQL_DB_NAME,
        user=settings.BACKEND_SQL_DB_USER,
        password=settings.BACKEND_SQL_DB_PASSWORD,
    )
    return url.replace("%", "%%")


def unreachable_message(exc: Exception) -> str:
    """연결 실패를 「어디로 갔고, 그 좌표는 누가 정했나」로 바꿔 준다 (#399).

    드라이버가 내는 것은 `connection to server at "127.0.1.1", port 5432 failed` 뿐이라,
    그 5432 가 어느 파일에서 왔는지는 읽는 사람이 스스로 찾아야 했다 — 낡은
    `.env.development` 를 그대로 들고 있으면 그 추적이 매번 반복된다(리드 실측).
    """
    return (
        f"마이그레이션 대상 DB 에 연결하지 못했다 — {db_target.get('where', '(좌표 미상)')}\n"
        f"  · 이 좌표의 출처: {db_target.get('origin', '(미상)')}\n"
        "  · 로컬 기본값은 process-compose 의 postgres 포트 5442 다. 그 파일이 낡았는지는 "
        "`python3 scripts/bootstrap_local_env.py` 를 다시 돌리면 알려 준다(덮어쓰지 않는다).\n"
        "  · 다른 DB 로 한 번만 보내려면 좌표를 명령에 직접 준다: "
        "`BACKEND_SQL_DB_HOST=… BACKEND_SQL_DB_PORT=… uv run python -m alembic upgrade head`\n"
        f"  · 드라이버 원문: {exc}"
    )


config.set_main_option("sqlalchemy.url", get_db_url())


# 이 서비스의 버전 테이블 이름 (SoT 는 alembic.ini). 파이썬 세 서비스가 한 DB(fintech)의 public
# 스키마를 공유하므로, 공용 이름 하나를 함께 쓰면 서로의 이력을 덮어쓴다 (#166).
version_table = config.get_main_option("version_table", "alembic_version")


# ==============================================================================
# Database-Specific Event Handlers
# ==============================================================================


@event.listens_for(Table, "column_reflect")
def receive_column_reflect(inspector, table, column_info):
    """
    MSSQL column comment 무시
    MSSQL은 컬럼 주석을 지원하지 않으므로 reflection 시 제거
    """
    column_info["comment"] = None


# ==============================================================================
# Migration Filters
# ==============================================================================


def include_object(object, name, type_, reflected, compare_to):
    """
    마이그레이션에 포함할 객체 필터링

    - 이 서비스 모델에 없는 DB 테이블 제외 (남의 서비스 것 — 아래 주석)
    - 테이블/컬럼의 comment 비교 무시 (MSSQL 호환성)
    """
    if type_ in ("table", "column") and compare_to is not None:
        object.comment = compare_to.comment = None

    # backend·devactivity·file 은 한 DB(fintech)의 public 스키마를 공유한다(#166). autogenerate 의
    # reflection 에는 남의 서비스 테이블과 남의 alembic 버전 테이블까지 잡히고, "내 모델에 없다"는
    # 이유로 drop_table 이 만들어진다 — 흡수 전 devactivity 의 이력 없는 push 가 backend 7 테이블
    # 삭제를 감지해 중단한 실측이 있다. 그래서 내 모델에 대응이 없는 DB 테이블은 남의 것으로 보고
    # 비교에서 뺀다
    # (`alembic_version*` 도 이 규칙에 흡수된다).
    # 대가: 모델에서 테이블을 지워도 DB 테이블은 남는다 — 정리는 직접 한다.
    if type_ == "table" and reflected and compare_to is None:
        return False

    return True


def include_name(name, type_, parent_names):
    """
    익명 제약조건 필터링

    SQLAlchemy가 자동 생성한 이름 없는 FK/Unique 제약조건 무시
    """
    return not (type_ in ("foreign_key_constraint", "unique_constraint") and name is None)


def process_revision_directives(context, revision, directives):
    """
    빈 마이그레이션 파일 생성 방지

    스키마 변경사항이 없을 경우 마이그레이션 파일을 생성하지 않음
    """
    if getattr(config.cmd_opts, "autogenerate", None):
        script = directives[0]
        if script.upgrade_ops.is_empty() or not script.upgrade_ops.ops:
            directives[:] = []
            print("ℹ️  No changes detected - skipping migration")


# ==============================================================================
# Migration Execution
# ==============================================================================


def run_migrations_offline():
    """
    오프라인 모드로 마이그레이션 실행

    DB 연결 없이 SQL 스크립트만 생성할 때 사용
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        include_name=include_name,
        compare_type=False,  # 컬럼 타입 변경 감지 비활성화 (MSSQL 호환성)
        compare_server_default=False,  # 서버 기본값 비교 비활성화
        version_table=version_table,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """
    온라인 모드로 마이그레이션 실행

    실제 DB 연결을 통해 스키마 변경을 적용
    """
    # hide_parameters=True — 앱 엔진(app/utils/common/database_utils.py)과 같은 처방 (#234).
    # DDL 중심이라 바인딩 값이 실릴 일이 드물지만, 데이터 마이그레이션(op.bulk_insert·op.execute 의
    # 파라미터 바인딩)이 실패하면 여기서도 StatementError 문자열에 행 값이 통째로 실린다.
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # 마이그레이션용 단일 연결
        hide_parameters=True,
    )

    try:
        connection_ctx = connectable.connect()
    except Exception as exc:
        raise ConnectionError(unreachable_message(exc)) from exc

    with connection_ctx as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=False,
            compare_server_default=False,
            include_object=include_object,
            include_name=include_name,
            process_revision_directives=process_revision_directives,
            version_table=version_table,
        )
        with context.begin_transaction():
            context.run_migrations()


# ==============================================================================
# Entry Point
# ==============================================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
