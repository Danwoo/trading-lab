import json

from sqlalchemy import text
from utils.common.devextreme_utils import build_filter_params, parse_sort


class BotRepository:
    """봇과 봇에 실린 전략 — 마스터·디테일 한 쌍을 한 트랜잭션으로 다룬다.

    전략은 파일이라 DB 에 없다. `strategy_key` 는 파일이 선언한 key 를 FK 없이 가리킨다
    (`.docs/specs/2026-08-15-strategy-contract.md` §6).
    """

    def __init__(self, sql_client):
        self.sql_client = sql_client

    def query_select_bot(self) -> str:
        return """
            SELECT *
              FROM (
                SELECT bot_id
                     , bot_nm
                     , bot_desc
                     , combine_rule
                     , universe_kind
                     , universe_ref
                     , CAST(alloc_per_symbol AS float)   AS alloc_per_symbol
                     , max_positions
                     , CAST(stop_loss_pct AS float)      AS stop_loss_pct
                     , CAST(take_profit_pct AS float)    AS take_profit_pct
                     , max_trades_per_day
                     , bot_role
                     , use_at
                     , param_sources
                     , to_char(reg_dt, 'YYYY-MM-DD HH24:MI:SS') AS reg_dt
                     , reg_id
                     , to_char(mod_dt, 'YYYY-MM-DD HH24:MI:SS') AS mod_dt
                     , mod_id
                FROM tn_bot
                WHERE workspace_id = :workspace_id
                ) A
            WHERE 1 = 1
        """

    def select_bot_list(self, args: dict) -> tuple[list[dict], int]:
        base_sql = self.query_select_bot()

        sql_where, sql_params = build_filter_params(args)
        sql_params["workspace_id"] = args["workspace_id"]
        order_by = parse_sort(args.get("sort")) or "bot_nm ASC"

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
        else:
            final_sql = f"""
                SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS rn
                     , TB.*
                  FROM ({base_sql} {sql_where}) TB
            """
        count_sql = f"SELECT COUNT(*) AS cnt FROM ({base_sql} {sql_where}) TB"

        with self.sql_client.connect() as conn:
            rows = conn.execute(text(final_sql), sql_params).mappings().all()
            count = conn.execute(text(count_sql), sql_params).scalar()
            return [dict(row) for row in rows], count

    def select_bot(self, args: dict) -> dict | None:
        sql = f"{self.query_select_bot()} AND bot_id = :bot_id"
        with self.sql_client.connect() as conn:
            row = conn.execute(text(sql), args).mappings().first()
            return dict(row) if row else None

    def select_bot_strategy_list(self, args: dict) -> list[dict]:
        sql = """
            SELECT bot_strategy_id
                 , bot_id
                 , strategy_key
                 , params
                 , param_sources
                 , CAST(weight AS float) AS weight
                 , sort_order
              FROM tn_bot_strategy
             WHERE bot_id = :bot_id
             ORDER BY sort_order, bot_strategy_id
        """
        with self.sql_client.connect() as conn:
            rows = conn.execute(text(sql), args).mappings().all()
            return [dict(row) for row in rows]

    def insert_bot(self, args: dict, strategies: list[dict]) -> tuple:
        """봇과 실린 전략을 한 트랜잭션으로 넣는다 — 전략 없는 봇이 남지 않게."""
        with self.sql_client.connect() as conn:
            with conn.begin():
                bot_id = conn.execute(text(_INSERT_BOT), _bot_params(args)).scalar_one()
                self._replace_strategies(conn, bot_id, strategies, args["reg_id"])
                return (bot_id,)

    def update_bot(self, args: dict, strategies: list[dict] | None) -> None:
        """전략 목록이 오면 통째로 갈아 끼운다 — 부분 갱신은 어느 것이 남았는지 모호해진다."""
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(_UPDATE_BOT), _bot_params(args))
                if strategies is not None:
                    self._replace_strategies(conn, args["bot_id"], strategies, args["mod_id"])

    def delete_bot(self, args: dict) -> None:
        # tn_bot_strategy 는 ON DELETE CASCADE 로 함께 지워진다.
        sql = "DELETE FROM tn_bot WHERE workspace_id = :workspace_id AND bot_id = :bot_id"
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def _replace_strategies(self, conn, bot_id: int, strategies: list[dict], actor: str | None) -> None:
        conn.execute(text("DELETE FROM tn_bot_strategy WHERE bot_id = :bot_id"), {"bot_id": bot_id})
        for order, strategy in enumerate(strategies):
            conn.execute(
                text(_INSERT_BOT_STRATEGY),
                {
                    "bot_id": bot_id,
                    "strategy_key": strategy["strategy_key"],
                    "params": json.dumps(strategy.get("params") or {}, ensure_ascii=False),
                    "param_sources": json.dumps(strategy.get("param_sources") or {}, ensure_ascii=False),
                    "weight": strategy.get("weight"),
                    "sort_order": order,
                    "reg_id": actor,
                },
            )


def _bot_params(args: dict) -> dict:
    """JSONB 컬럼은 문자열로 바인딩한다 — psycopg 가 dict 를 그대로 못 넣는다."""
    params = dict(args)
    for column in ("universe_ref", "param_sources"):
        value = params.get(column)
        params[column] = None if value is None else json.dumps(value, ensure_ascii=False)
    return params


_INSERT_BOT = """
    INSERT INTO tn_bot (
         workspace_id
       , bot_nm
       , bot_desc
       , combine_rule
       , universe_kind
       , universe_ref
       , alloc_per_symbol
       , max_positions
       , stop_loss_pct
       , take_profit_pct
       , max_trades_per_day
       , bot_role
       , use_at
       , param_sources
       , reg_id
       , reg_dt
       , mod_id
       , mod_dt
    )
    VALUES (
         :workspace_id
       , :bot_nm
       , :bot_desc
       , :combine_rule
       , :universe_kind
       , CAST(:universe_ref AS jsonb)
       , :alloc_per_symbol
       , :max_positions
       , :stop_loss_pct
       , :take_profit_pct
       , :max_trades_per_day
       , :bot_role
       , :use_at
       , CAST(:param_sources AS jsonb)
       , :reg_id
       , CURRENT_TIMESTAMP
       , :reg_id
       , CURRENT_TIMESTAMP
    )
    RETURNING bot_id
"""

_UPDATE_BOT = """
    UPDATE tn_bot
       SET bot_nm             = :bot_nm
         , bot_desc           = :bot_desc
         , combine_rule       = :combine_rule
         , universe_kind      = :universe_kind
         , universe_ref       = CAST(:universe_ref AS jsonb)
         , alloc_per_symbol   = :alloc_per_symbol
         , max_positions      = :max_positions
         , stop_loss_pct      = :stop_loss_pct
         , take_profit_pct    = :take_profit_pct
         , max_trades_per_day = :max_trades_per_day
         , bot_role           = :bot_role
         , use_at             = :use_at
         , param_sources      = CAST(:param_sources AS jsonb)
         , mod_id             = :mod_id
         , mod_dt             = CURRENT_TIMESTAMP
     WHERE workspace_id = :workspace_id
       AND bot_id = :bot_id
"""

_INSERT_BOT_STRATEGY = """
    INSERT INTO tn_bot_strategy (
         bot_id
       , strategy_key
       , params
       , param_sources
       , weight
       , sort_order
       , reg_id
       , reg_dt
       , mod_id
       , mod_dt
    )
    VALUES (
         :bot_id
       , :strategy_key
       , CAST(:params AS jsonb)
       , CAST(:param_sources AS jsonb)
       , :weight
       , :sort_order
       , :reg_id
       , CURRENT_TIMESTAMP
       , :reg_id
       , CURRENT_TIMESTAMP
    )
"""
