from sqlalchemy import Engine
from utils.common.database_utils import create_sql_engine_from_settings


def get_backend_sql_client(config) -> Engine:
    return create_sql_engine_from_settings(
        db_name_log="BACKEND",
        driver=config.BACKEND_SQL_DB_DRIVER,
        odbc_driver=config.BACKEND_SQL_DB_ODBC_DRIVER,
        host=config.BACKEND_SQL_DB_HOST,
        port=config.BACKEND_SQL_DB_PORT,
        dbname=config.BACKEND_SQL_DB_NAME,
        user=config.BACKEND_SQL_DB_USER,
        password=config.BACKEND_SQL_DB_PASSWORD,
    )
