from repositories.common.sql_format import DT_ISO_TZ
from sqlalchemy import text
from utils.common.devextreme_utils import build_filter_params, parse_sort


class PortfolioRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    # ── Portfolio (master) ─────────────────────────────────────────────
    def query_select_portfolio(self) -> str:
        return f"""
            SELECT *
              FROM (
                SELECT portfolio_id
                     , portfolio_nm
                     , sort_ordr
                     , use_at
                     , description
                     , to_char(reg_dt, '{DT_ISO_TZ}') AS reg_dt
                     , reg_id
                     , to_char(mod_dt, '{DT_ISO_TZ}') AS mod_dt
                     , mod_id
                FROM tn_portfolio
                WHERE workspace_id = :workspace_id
                ) A
            WHERE 1 = 1
        """

    def select_portfolio_list(self, args: dict) -> tuple[list[dict], int]:
        base_sql = self.query_select_portfolio()
        sql_where, sql_params = build_filter_params(args)
        sql_params["workspace_id"] = args["workspace_id"]
        order_by = parse_sort(args.get("sort")) or "sort_ordr ASC, portfolio_id ASC"

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

    def select_portfolio(self, args: dict) -> dict | None:
        sql = self.query_select_portfolio() + " AND portfolio_id = :portfolio_id"
        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), args).mappings().fetchone()
            return dict(result) if result else None

    def insert_portfolio(self, args: dict) -> tuple:
        sql = """
            INSERT INTO tn_portfolio (
                 workspace_id
               , portfolio_id
               , portfolio_nm
               , sort_ordr
               , use_at
               , description
               , reg_id
               , reg_dt
               , mod_id
               , mod_dt
            )
            VALUES (
                 :workspace_id
               , :portfolio_id
               , :portfolio_nm
               , :sort_ordr
               , :use_at
               , :description
               , :reg_id
               , CURRENT_TIMESTAMP
               , :reg_id
               , CURRENT_TIMESTAMP
            )
            RETURNING portfolio_id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                result = conn.execute(text(sql), args)
                return result.fetchone()

    def update_portfolio(self, args: dict) -> None:
        sql = """
            UPDATE tn_portfolio
               SET portfolio_nm = :portfolio_nm
                 , sort_ordr    = :sort_ordr
                 , use_at       = :use_at
                 , description  = :description
                 , mod_id       = :mod_id
                 , mod_dt       = CURRENT_TIMESTAMP
             WHERE portfolio_id  = :portfolio_id
               AND workspace_id    = :workspace_id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def delete_portfolio(self, args: dict) -> None:
        sql_holdings = "DELETE FROM tn_holding WHERE portfolio_id = :portfolio_id AND workspace_id = :workspace_id"
        sql_portfolio = "DELETE FROM tn_portfolio WHERE portfolio_id = :portfolio_id AND workspace_id = :workspace_id"
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql_holdings), args)
                conn.execute(text(sql_portfolio), args)

    # ── Holding (detail) ───────────────────────────────────────────────
    def query_select_holding(self) -> str:
        return f"""
            SELECT *
              FROM (
                SELECT h.portfolio_id
                     , h.ticker
                     , h.holding_nm
                     , h.quantity
                     , CAST(h.avg_price AS float) AS avg_price
                     , h.market
                     , h.use_at
                     , h.description
                     , p.portfolio_nm
                     , to_char(h.reg_dt, '{DT_ISO_TZ}') AS reg_dt
                     , h.reg_id
                     , to_char(h.mod_dt, '{DT_ISO_TZ}') AS mod_dt
                     , h.mod_id
                FROM tn_holding h
                INNER JOIN tn_portfolio p
                        ON h.portfolio_id = p.portfolio_id
                       AND h.workspace_id = p.workspace_id
                WHERE h.workspace_id = :workspace_id
                ) A
            WHERE 1 = 1
              AND portfolio_id = :portfolio_id
        """

    def select_holding_list(self, args: dict) -> tuple[list[dict], int]:
        base_sql = self.query_select_holding()
        sql_where, sql_params = build_filter_params(args)
        order_by = parse_sort(args.get("sort")) or "ticker ASC"
        sql_params["portfolio_id"] = args["portfolio_id"]
        sql_params["workspace_id"] = args["workspace_id"]

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

    def select_holding(self, args: dict) -> dict | None:
        sql = self.query_select_holding() + " AND ticker = :ticker"
        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), args).mappings().fetchone()
            return dict(result) if result else None

    def insert_holding(self, args: dict) -> tuple:
        sql = """
            INSERT INTO tn_holding (
                 workspace_id
               , portfolio_id
               , ticker
               , holding_nm
               , quantity
               , avg_price
               , market
               , use_at
               , description
               , reg_id
               , reg_dt
               , mod_id
               , mod_dt
            )
            VALUES (
                 :workspace_id
               , :portfolio_id
               , :ticker
               , :holding_nm
               , :quantity
               , :avg_price
               , :market
               , :use_at
               , :description
               , :reg_id
               , CURRENT_TIMESTAMP
               , :reg_id
               , CURRENT_TIMESTAMP
            )
            RETURNING portfolio_id, ticker
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                result = conn.execute(text(sql), args)
                return result.fetchone()

    def update_holding(self, args: dict) -> None:
        sql = """
            UPDATE tn_holding
               SET holding_nm  = :holding_nm
                 , quantity    = :quantity
                 , avg_price   = :avg_price
                 , market      = :market
                 , use_at      = :use_at
                 , description = :description
                 , mod_id      = :mod_id
                 , mod_dt      = CURRENT_TIMESTAMP
             WHERE portfolio_id = :portfolio_id
               AND ticker        = :ticker
               AND workspace_id    = :workspace_id
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def delete_holding(self, args: dict) -> None:
        sql_holding = "DELETE FROM tn_holding WHERE portfolio_id = :portfolio_id AND ticker = :ticker AND workspace_id = :workspace_id"
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql_holding), args)
