from sqlalchemy import Engine
from utils.common.database_utils import create_sql_engine_from_settings


def get_multi_agent_sql_client(config) -> Engine:
    # 공통 DB(frontend.ai_chat_history) — frontend Prisma 가 write, 여기선 멀티턴 히스토리 read-only 조회.
    # search_path 는 기본값(public)이고 스키마 수식은 쿼리 쪽에 있다 (chat_history_repository).
    return create_sql_engine_from_settings(
        db_name_log="MULTI_AGENT",
        driver=config.MULTI_AGENT_SQL_DB_DRIVER,
        odbc_driver=config.MULTI_AGENT_SQL_DB_ODBC_DRIVER,
        host=config.MULTI_AGENT_SQL_DB_HOST,
        port=config.MULTI_AGENT_SQL_DB_PORT,
        dbname=config.MULTI_AGENT_SQL_DB_NAME,
        user=config.MULTI_AGENT_SQL_DB_USER,
        password=config.MULTI_AGENT_SQL_DB_PASSWORD,
    )
