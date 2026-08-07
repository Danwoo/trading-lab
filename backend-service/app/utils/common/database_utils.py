import urllib.parse

from core.logger import logger
from sqlalchemy import Engine, create_engine, event, text
from utils.common.retry_utils import retry


def get_sql_db_url(
    driver: str,
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
    odbc_driver: str = "",
    extra_params: dict = None,
) -> str:
    """
    SQLAlchemy 기반 SQL 데이터베이스 접속 URL 생성

    지원 DB:
        - MSSQL: mssql+pyodbc
        - PostgreSQL: postgresql+psycopg2
        - MySQL: mysql+pymysql
        - Oracle: oracle+cx_oracle
        - SQLite: sqlite

    Args:
        driver: DB 드라이버 (예: mssql+pyodbc, postgresql+psycopg2)
        host: 호스트 주소
        port: 포트 번호
        dbname: 데이터베이스명 (SQLite의 경우 파일 경로)
        user: 사용자명
        password: 비밀번호
        odbc_driver: ODBC 드라이버명 (pyodbc 사용 시 필수)
        extra_params: 추가 연결 파라미터

    Returns:
        SQLAlchemy 연결 URL
    """

    if "pyodbc" in driver.lower():
        if not odbc_driver:
            raise ValueError("odbc_driver is required for pyodbc connections")

        odbc_str = f"DRIVER={odbc_driver};SERVER={host},{port};DATABASE={dbname};UID={user};PWD={password};"

        default_params = {"Encrypt": "no", "TrustServerCertificate": "yes"}
        params = {**default_params, **(extra_params or {})}
        odbc_str += "".join(f"{k}={v};" for k, v in params.items())

        encoded_conn_str = urllib.parse.quote_plus(odbc_str)
        return f"{driver}:///?odbc_connect={encoded_conn_str}"

    if "oracle" in driver.lower():
        if extra_params and "sid" in extra_params:
            return f"{driver}://{user}:{password}@{host}:{port}/{extra_params['sid']}"
        return f"{driver}://{user}:{password}@{host}:{port}/?service_name={dbname}"

    if "sqlite" in driver.lower():
        return f"{driver}:///{dbname}"

    url = f"{driver}://{user}:{password}@{host}:{port}/{dbname}"
    if extra_params:
        query_string = urllib.parse.urlencode(extra_params)
        url += f"?{query_string}"

    return url


def create_sql_engine_from_settings(
    db_name_log: str,
    driver: str,
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
    odbc_driver: str = "",
    extra_params: dict = None,
    pool_size: int = 10,
    max_overflow: int = 20,
) -> Engine:
    """
    SQLAlchemy Engine 생성 및 연결 테스트

    Args:
        db_name_log: 로그에 표시될 DB 이름
        driver: DB 드라이버
        host: 호스트 주소
        port: 포트 번호
        dbname: 데이터베이스명
        user: 사용자명
        password: 비밀번호
        odbc_driver: ODBC 드라이버명 (선택)
        extra_params: 추가 연결 파라미터 (선택)
        pool_size: 커넥션 풀 크기
        max_overflow: 최대 오버플로우 연결 수

    Returns:
        SQLAlchemy Engine 객체

    Raises:
        Exception: 데이터베이스 연결 실패 시
    """
    engine_url = get_sql_db_url(
        driver=driver,
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        odbc_driver=odbc_driver,
        extra_params=extra_params,
    )

    # hide_parameters=True — SQLAlchemy 예외 문자열·echo 로그에서 바인딩 파라미터를 지운다 (#234).
    # 예외를 exc_info=True 로 찍는 핸들러(core/exception_handler.py)의 트레이스백 마지막 줄이
    # StatementError.__str__ 이라 `[parameters: {...}]` 로 행 값이 통째로 실렸다. 진단은 드라이버
    # 메시지·SQLSTATE·제약/테이블/컬럼명(#216 allowlist)·`[SQL: ...]` 문장으로 충분히 남는다.
    #
    # SQLite는 파일/인메모리 기반 → 풀 옵션(pool_size·overflow·recycle) 무의미,
    # check_same_thread=False 로 멀티스레드(스레드풀) 접근 허용
    if "sqlite" in driver.lower():
        engine = create_engine(
            engine_url,
            echo=False,
            hide_parameters=True,
            connect_args={"check_same_thread": False},
        )
    else:
        engine = create_engine(
            engine_url,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=30,
            pool_recycle=1800,
            echo=False,
            hide_parameters=True,
        )

        # 연결 수립(신규·풀 재연결) 시 일시적 오류 유한 재시도 — pool_pre_ping 과 합쳐 끊김→재연결 복구 (무한 아님)
        @event.listens_for(engine, "do_connect")
        def _retry_connect(dialect, conn_rec, cargs, cparams):
            return retry(
                lambda: dialect.connect(*cargs, **cparams),
                max_retries=2,
                base_delay=0.5,
                label=f"DB connect ({db_name_log})",
            )

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    logger.info(f"SQL Database connect successful ({db_name_log})")
    return engine
