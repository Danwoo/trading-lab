from repositories.common.sql_format import DT_ISO_TZ
from sqlalchemy import text
from utils.common.devextreme_utils import build_filter_params, parse_sort


class ResearchDocumentRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    def query_select_research_document(self) -> str:
        return f"""
            SELECT *
              FROM (
                SELECT research_doc_id
                     , workspace_id
                     , user_id
                     , atch_file_id
                     , file_sn
                     , doc_title
                     , status
                     , chunk_count
                     , error_msg
                     , to_char(reg_dt, '{DT_ISO_TZ}') AS reg_dt
                     , reg_id
                     , to_char(mod_dt, '{DT_ISO_TZ}') AS mod_dt
                     , mod_id
                FROM tn_research_document
                WHERE workspace_id = :workspace_id
                ) A
            WHERE 1 = 1
        """

    def select_research_document_list(self, args: dict) -> tuple[list[dict], int]:
        base_sql = self.query_select_research_document()

        sql_where, sql_params = build_filter_params(args)
        sql_params["workspace_id"] = args["workspace_id"]
        order_by = parse_sort(args.get("sort")) or "research_doc_id DESC"

        skip = int(args.get("skip", 0))
        take = args.get("take")

        if take is not None:
            take = int(take)
            final_sql = f"""
                SELECT *
                  FROM (
                            SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS rn
                                 , TB.*
                              FROM ({base_sql} {sql_where}) TB
                       ) TB
                 WHERE rn BETWEEN {skip + 1} AND {skip + take}
            """
            count_sql = f"SELECT COUNT(*) AS cnt FROM ({base_sql} {sql_where}) TB"

            with self.sql_client.connect() as conn:
                result = conn.execute(text(final_sql), sql_params).mappings().all()
                count = conn.execute(text(count_sql), sql_params).scalar()
                return [dict(row) for row in result], count
        else:
            final_sql = f"""
                SELECT *
                  FROM (
                            SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS rn
                                 , TB.*
                              FROM ({base_sql} {sql_where}) TB
                       ) TB
            """

            with self.sql_client.connect() as conn:
                result = conn.execute(text(final_sql), sql_params).mappings().all()
                return [dict(row) for row in result], len(result)

    def select_research_document(self, args: dict) -> dict | None:
        sql = self.query_select_research_document() + " AND research_doc_id = :research_doc_id"
        # workspace_id 는 inner WHERE 에 이미 바인딩됨 (args 에 포함)
        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), args).mappings().fetchone()
            return dict(result) if result else None

    def insert_research_document(self, args: dict) -> tuple:
        sql = """
            INSERT INTO tn_research_document (
                 workspace_id
               , user_id
               , atch_file_id
               , file_sn
               , doc_title
               , status
               , reg_id
               , reg_dt
            )
            VALUES (
                 :workspace_id
               , :user_id
               , :atch_file_id
               , :file_sn
               , :doc_title
               , :status
               , :reg_id
               , CURRENT_TIMESTAMP
            )
            RETURNING research_doc_id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                result = conn.execute(text(sql), args)
                return result.fetchone()

    def update_research_document_status(self, args: dict) -> None:
        sql = """
            UPDATE tn_research_document
               SET status      = :status
                 , chunk_count = :chunk_count
                 , error_msg   = :error_msg
                 , mod_id      = :mod_id
                 , mod_dt      = CURRENT_TIMESTAMP
             WHERE research_doc_id = :research_doc_id
               AND workspace_id      = :workspace_id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def delete_research_document(self, args: dict) -> None:
        sql = """
            DELETE
              FROM tn_research_document
             WHERE research_doc_id = :research_doc_id
               AND workspace_id      = :workspace_id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)
