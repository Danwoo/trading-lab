# repositories/nav/nav_repository.py
from sqlalchemy import text


class NavRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    def insert_nav(self, args: dict) -> None:
        # source_message_id 로 멱등 — 같은 메시지의 재소비는 WHERE NOT EXISTS 로 스킵.
        # 하드 보장은 ux_nav_source_message(필터드 유니크); 이 SELECT 는 정상경로 no-op 삽입 회피.
        sql = """
            INSERT INTO tn_nav (
                 workspace_id
               , source_message_id
               , nav_dt
               , nav
               , benchmark
               , daily_return
               , drawdown
               , reg_id
               , reg_dt
               , mod_id
               , mod_dt
            )
            SELECT
                 :workspace_id
               , :source_message_id
               , CURRENT_TIMESTAMP
               , :nav
               , :benchmark
               , :daily_return
               , :drawdown
               , :reg_id
               , CURRENT_TIMESTAMP
               , :reg_id
               , CURRENT_TIMESTAMP
             WHERE NOT EXISTS (
                   SELECT 1 FROM tn_nav WHERE source_message_id = :source_message_id
             )
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def select_history(self, args: dict) -> list[dict]:
        sql = """
            SELECT to_char(nav_dt, 'YYYY-MM-DD"T"HH24:MI:SS') AS timestamp
                 , CAST(nav AS float)          AS nav
                 , CAST(benchmark AS float)    AS benchmark
                 , CAST(daily_return AS float) AS daily_return
                 , CAST(drawdown AS float)     AS drawdown
              FROM tn_nav
             WHERE nav_dt >= CURRENT_TIMESTAMP - (:minutes * INTERVAL '1 minute')
               AND workspace_id = :workspace_id
             ORDER BY nav_dt ASC
        """
        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), args).mappings().all()
            return [dict(row) for row in result]
