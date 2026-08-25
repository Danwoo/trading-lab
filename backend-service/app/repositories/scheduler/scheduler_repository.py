from repositories.common.sql_format import DT_ISO_TZ
from sqlalchemy import text
from utils.common.devextreme_utils import build_filter_params, parse_sort


class SchedulerRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    # ── Scheduler (master) ──────────────────────────────────────────────
    def query_select_scheduler(self) -> str:
        return f"""
            SELECT *
              FROM (
                SELECT scheduler_id
                     , workspace_id
                     , scheduler_nm
                     , day_of_week
                     , hour
                     , minute
                     , period_weeks
                     , use_at
                     , description
                     , to_char(reg_dt, '{DT_ISO_TZ}') AS reg_dt
                     , reg_id
                     , to_char(mod_dt, '{DT_ISO_TZ}') AS mod_dt
                     , mod_id
                FROM tn_scheduler
                WHERE workspace_id = :workspace_id
                ) A
            WHERE 1 = 1
        """

    def select_scheduler_list(self, args: dict) -> tuple[list[dict], int]:
        base_sql = self.query_select_scheduler()
        sql_where, sql_params = build_filter_params(args)
        sql_params["workspace_id"] = args["workspace_id"]
        order_by = parse_sort(args.get("sort")) or "scheduler_id ASC"
        skip = int(args.get("skip", 0))
        take = args.get("take")

        if take is not None:
            take = int(take)
            final_sql = f"""
                SELECT *
                  FROM (SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS rn, TB.*
                          FROM ({base_sql} {sql_where}) TB) TB
                 WHERE rn BETWEEN {skip + 1} AND {skip + take}
            """
            count_sql = f"SELECT COUNT(*) AS cnt FROM ({base_sql} {sql_where}) TB"
            with self.sql_client.connect() as conn:
                rows = conn.execute(text(final_sql), sql_params).mappings().all()
                count = conn.execute(text(count_sql), sql_params).scalar()
                return [dict(r) for r in rows], count
        final_sql = f"""
            SELECT *
              FROM (SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS rn, TB.*
                      FROM ({base_sql} {sql_where}) TB) TB
        """
        with self.sql_client.connect() as conn:
            rows = conn.execute(text(final_sql), sql_params).mappings().all()
            return [dict(r) for r in rows], len(rows)

    def select_scheduler(self, args: dict) -> dict | None:
        # workspace_id 는 inner WHERE 에 이미 바인딩됨 (args 에 포함)
        sql = self.query_select_scheduler() + " AND scheduler_id = :scheduler_id"
        with self.sql_client.connect() as conn:
            row = conn.execute(text(sql), args).mappings().fetchone()
            return dict(row) if row else None

    def select_active_schedulers(self) -> list[dict]:
        """잡 등록 대상 — use_at='Y'. 부팅 시 전 테넌트 대상 (요청 밖 시스템 경로)."""
        sql = """
            SELECT scheduler_id, scheduler_nm, day_of_week, hour, minute, period_weeks
              FROM tn_scheduler WHERE use_at = 'Y'
        """
        with self.sql_client.connect() as conn:
            return [dict(r) for r in conn.execute(text(sql)).mappings().all()]

    def select_scheduler_for_job(self, scheduler_id: str) -> dict | None:
        """cron 실행 시점 — 집계기간·소속 테넌트(workspace_id) 산정용. scheduler_id 전역 유일이라 조회는 테넌트 무관.

        workspace_id 는 요청 밖 cron 경로가 하류 MCP 를 스케줄러 소속 워크스페이스로 스코핑(on-behalf 토큰)하기 위해 싣는다.
        """
        sql = "SELECT scheduler_id, workspace_id, period_weeks FROM tn_scheduler WHERE scheduler_id = :scheduler_id"
        with self.sql_client.connect() as conn:
            row = conn.execute(text(sql), {"scheduler_id": scheduler_id}).mappings().fetchone()
            return dict(row) if row else None

    def insert_scheduler(self, args: dict) -> tuple:
        sql = """
            INSERT INTO tn_scheduler (
                 scheduler_id, workspace_id, scheduler_nm, day_of_week, hour, minute, period_weeks, use_at, description,
                 reg_id, reg_dt, mod_id, mod_dt
            )
            VALUES (
                 :scheduler_id, :workspace_id, :scheduler_nm, :day_of_week, :hour, :minute, :period_weeks, :use_at, :description,
                 :reg_id, CURRENT_TIMESTAMP, :reg_id, CURRENT_TIMESTAMP
            )
            RETURNING scheduler_id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                return conn.execute(text(sql), args).fetchone()

    def update_scheduler(self, args: dict) -> None:
        sql = """
            UPDATE tn_scheduler
               SET scheduler_nm  = :scheduler_nm
                 , day_of_week  = :day_of_week
                 , hour         = :hour
                 , minute       = :minute
                 , period_weeks = :period_weeks
                 , use_at       = :use_at
                 , description  = :description
                 , mod_id       = :mod_id
                 , mod_dt       = CURRENT_TIMESTAMP
             WHERE scheduler_id = :scheduler_id
               AND workspace_id   = :workspace_id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def delete_scheduler(self, args: dict) -> None:
        sql_members = (
            "DELETE FROM tn_scheduler_member WHERE scheduler_id = :scheduler_id AND workspace_id = :workspace_id"
        )
        sql_scheduler = "DELETE FROM tn_scheduler WHERE scheduler_id = :scheduler_id AND workspace_id = :workspace_id"
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql_members), args)
                conn.execute(text(sql_scheduler), args)

    # ── SchedulerMember (detail) ────────────────────────────────────────
    def select_member_list(self, args: dict) -> tuple[list[dict], int]:
        base_sql = f"""
            SELECT scheduler_id
                 , account_id
                 , email
                 , name
                 , to_char(reg_dt, '{DT_ISO_TZ}') AS reg_dt
                 , reg_id
                 , to_char(mod_dt, '{DT_ISO_TZ}') AS mod_dt
                 , mod_id
              FROM tn_scheduler_member
             WHERE scheduler_id = :scheduler_id
               AND workspace_id   = :workspace_id
        """
        order_by = parse_sort(args.get("sort")) or "account_id ASC"
        params = {"scheduler_id": args["scheduler_id"], "workspace_id": args["workspace_id"]}
        with self.sql_client.connect() as conn:
            rows = conn.execute(text(f"{base_sql} ORDER BY {order_by}"), params).mappings().all()
            return [dict(r) for r in rows], len(rows)

    def select_member(self, args: dict) -> dict | None:
        sql = (
            "SELECT scheduler_id, account_id FROM tn_scheduler_member "
            "WHERE scheduler_id = :scheduler_id AND account_id = :account_id AND workspace_id = :workspace_id"
        )
        with self.sql_client.connect() as conn:
            row = conn.execute(text(sql), args).mappings().fetchone()
            return dict(row) if row else None

    def select_members_for_job(self, scheduler_id: str) -> list[dict]:
        """잡 실행 시점 — 발송 대상 (account_id/email/name). scheduler_id 전역 유일이라 테넌트 무관."""
        sql = "SELECT account_id, email, name FROM tn_scheduler_member WHERE scheduler_id = :scheduler_id ORDER BY account_id"
        with self.sql_client.connect() as conn:
            return [dict(r) for r in conn.execute(text(sql), {"scheduler_id": scheduler_id}).mappings().all()]

    def insert_member(self, args: dict) -> None:
        sql = """
            INSERT INTO tn_scheduler_member (scheduler_id, workspace_id, account_id, email, name, reg_id, reg_dt, mod_id, mod_dt)
            VALUES (:scheduler_id, :workspace_id, :account_id, :email, :name, :reg_id, CURRENT_TIMESTAMP, :reg_id, CURRENT_TIMESTAMP)
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def delete_member(self, args: dict) -> None:
        sql = "DELETE FROM tn_scheduler_member WHERE scheduler_id = :scheduler_id AND account_id = :account_id AND workspace_id = :workspace_id"
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)
