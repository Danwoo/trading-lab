# repositories/message_queue/message_queue_repository.py
from sqlalchemy import text


class MessageQueueRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    def insert_message(self, args: dict) -> tuple:
        sql = """
            INSERT INTO tn_message_queue (
                 topic
               , payload
               , status
               , retry_count
               , reg_id
               , reg_dt
               , mod_id
               , mod_dt
            )
            VALUES (
                 :topic
               , :payload
               , 'pending'
               , 0
               , :reg_id
               , CURRENT_TIMESTAMP
               , :reg_id
               , CURRENT_TIMESTAMP
            )
            RETURNING id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                result = conn.execute(text(sql), args)
                return result.fetchone()

    def select_pending(self, args: dict) -> list[dict]:
        sql = """
            SELECT id
                 , topic
                 , payload
                 , status
                 , retry_count
              FROM tn_message_queue
             WHERE status = 'pending'
             ORDER BY id ASC
             LIMIT :limit
        """
        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), args).mappings().all()
            return [dict(row) for row in result]

    def mark_done(self, args: dict) -> None:
        sql = """
            UPDATE tn_message_queue
               SET status = 'done'
                 , mod_id = :mod_id
                 , mod_dt = CURRENT_TIMESTAMP
             WHERE id = :id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def mark_failed(self, args: dict) -> None:
        # 비터미널 재시도 — 재시도 여력이 남으면 'pending' 으로 되돌려 재소비 대상 유지,
        # max_retries 소진 시에만 터미널 'failed'(데드레터). retry_count 가 실제 시도 횟수로 산다.
        sql = """
            UPDATE tn_message_queue
               SET retry_count = retry_count + 1
                 , status = CASE
                              WHEN retry_count + 1 >= :max_retries THEN 'failed'
                              ELSE 'pending'
                            END
                 , error = :error
                 , mod_id = :mod_id
                 , mod_dt = CURRENT_TIMESTAMP
             WHERE id = :id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)
