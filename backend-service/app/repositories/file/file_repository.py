from sqlalchemy import text
from utils.common.devextreme_utils import build_filter_params, parse_sort


class FileRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    def query_select_file(self) -> str:
        """파일 기본 정보 조회 쿼리"""
        return """
            SELECT *
              FROM (
                SELECT atch_file_id
                     , to_char(reg_dt, 'YYYY-MM-DD HH24:MI:SS') AS reg_dt
                     , reg_id
                     , to_char(mod_dt, 'YYYY-MM-DD HH24:MI:SS') AS mod_dt
                     , mod_id
                  FROM tn_file
              ) A
            WHERE 1 = 1
        """

    def select_file_list(self, args: dict) -> tuple[list[dict], int]:
        """파일 목록 조회 (DevExtreme 필터/정렬/페이지네이션)"""
        base_sql = self.query_select_file()

        sql_where, sql_params = build_filter_params(args)
        order_by = parse_sort(args.get("sort")) or "reg_dt ASC NULLS LAST"

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

    def select_file(self, args: dict) -> dict | None:
        """파일 기본 정보 조회"""
        sql = self.query_select_file() + " AND atch_file_id = :atch_file_id"

        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), args).mappings().fetchone()
            return dict(result) if result else None

    def get_next_file_sn(self, atch_file_id: str) -> int:
        """다음 파일 순번 조회"""
        sql = """
            SELECT COALESCE(MAX(file_sn), -1) + 1 AS next_sn
              FROM tn_file_detail
             WHERE atch_file_id = :atch_file_id
        """
        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), {"atch_file_id": atch_file_id}).scalar()
            return result

    def get_last_file_sn(self, atch_file_id: str) -> int:
        """마지막 파일 순번 조회 (파일이 없으면 0)"""
        sql = """
            SELECT COALESCE(MAX(file_sn), 0) AS last_sn
              FROM tn_file_detail
             WHERE atch_file_id = :atch_file_id
        """
        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), {"atch_file_id": atch_file_id}).scalar()
            return result

    def insert_file(self, args: dict) -> None:
        """파일 기본 정보 저장"""
        sql = """
            INSERT INTO tn_file (
                 atch_file_id
               , reg_id
               , reg_dt
               , mod_id
               , mod_dt
            )
            VALUES (
                 :atch_file_id
               , :reg_id
               , CURRENT_TIMESTAMP
               , :mod_id
               , CURRENT_TIMESTAMP
            )
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def delete_file(self, args: dict) -> None:
        """파일과 관련 상세 정보를 연쇄 삭제"""
        sql_delete_file_details = """
            DELETE FROM tn_file_detail WHERE atch_file_id = :atch_file_id
        """
        sql_delete_file = """
            DELETE FROM tn_file WHERE atch_file_id = :atch_file_id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql_delete_file_details), args)
                conn.execute(text(sql_delete_file), args)

    def query_select_file_detail(self) -> str:
        """파일 상세 정보 조회 쿼리"""
        return """
            SELECT *
            FROM (
                SELECT atch_file_id
                    , file_sn
                    , file_stre_cours
                    , stre_file_nm
                    , orignl_file_nm
                    , file_extsn
                    , file_mg
                    , file_ty
                    , to_char(reg_dt, 'YYYY-MM-DD HH24:MI:SS') AS reg_dt
                    , reg_id
                    , to_char(mod_dt, 'YYYY-MM-DD HH24:MI:SS') AS mod_dt
                    , mod_id
                FROM tn_file_detail
            ) A
            WHERE 1 = 1
              AND atch_file_id = :atch_file_id
        """

    def select_file_detail_list(self, args: dict) -> tuple[list[dict], int]:
        """파일 상세 목록 조회 (순번 포함)"""
        base_sql = self.query_select_file_detail()
        order_by = "file_sn ASC"

        sql = f"""
            SELECT *
            FROM (
                SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS rn
                     , TB.*
                FROM ({base_sql}) TB
            ) TB
        """

        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), args).mappings().all()
            return [dict(row) for row in result], len(result)

    def select_file_detail(self, args: dict) -> dict | None:
        """개별 파일 상세 정보 조회"""
        sql = self.query_select_file_detail() + " AND file_sn = :file_sn"

        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), args).mappings().fetchone()
            return dict(result) if result else None

    def insert_file_detail(self, args: dict) -> None:
        """파일 상세 정보 저장"""
        sql = """
            INSERT INTO tn_file_detail (
                 atch_file_id
               , file_sn
               , file_stre_cours
               , stre_file_nm
               , orignl_file_nm
               , file_extsn
               , file_mg
               , file_ty
               , reg_id
               , reg_dt
               , mod_id
               , mod_dt
            )
            VALUES (
                 :atch_file_id
               , :file_sn
               , :file_stre_cours
               , :stre_file_nm
               , :orignl_file_nm
               , :file_extsn
               , :file_mg
               , :file_ty
               , :reg_id
               , CURRENT_TIMESTAMP
               , :mod_id
               , CURRENT_TIMESTAMP
            )
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def delete_file_detail(self, args: dict) -> None:
        """개별 파일 상세 정보 삭제"""
        sql = """
            DELETE FROM tn_file_detail
             WHERE atch_file_id = :atch_file_id
               AND file_sn      = :file_sn
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)
