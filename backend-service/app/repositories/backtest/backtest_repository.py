"""백테스트 실행과 산출물 쓰기·조회.

`tn_backtest_run` 하나가 요청·실행·이력 셋을 겸한다 — `tn_ingest_run` 과 같은 규약이다.

자산곡선·거래·신호·현금원장은 **행이 많다.** 한 건씩 넣으면 왕복이 곧 병목이 되므로
`executemany` 로 한 번에 넣는다 — 엔진이 「로드 1회 + 인메모리 N회」인 이유와 같은 축이다.
"""

from sqlalchemy import text


class BacktestRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    # ── 실행 레코드 ──────────────────────────────────────────────────────────
    def insert_run(self, args: dict) -> int:
        sql = """
            INSERT INTO tn_backtest_run (
                 workspace_id, parent_run_id, attempt_no, bot_id
               , strategy_key, strategy_version, params
               , universe_def, universe_as_of, data_snapshot_id
               , adj_policy, cost_assumptions
               , period_from, period_to, initial_cash, status
               , reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (
                 :workspace_id, :parent_run_id, :attempt_no, :bot_id
               , :strategy_key, :strategy_version, CAST(:params AS jsonb)
               , CAST(:universe_def AS jsonb), :universe_as_of, :data_snapshot_id
               , :adj_policy, CAST(:cost_assumptions AS jsonb)
               , :period_from, :period_to, :initial_cash, 'running'
               , :reg_id, CURRENT_TIMESTAMP, :reg_id, CURRENT_TIMESTAMP
            )
            RETURNING run_id
        """
        with self.sql_client.connect() as conn:
            run_id = conn.execute(text(sql), args).scalar()
            conn.commit()
            return int(run_id)

    def finish_run(self, args: dict) -> None:
        """상태를 확정한다. 백그라운드 실행이 유일한 호출자라 `mod_id` 는 'system' 이다."""
        sql = """
            UPDATE tn_backtest_run
               SET status = :status
                 , failed_reason = :failed_reason
                 , finished_dt = CURRENT_TIMESTAMP
                 , mod_id = 'system'
                 , mod_dt = CURRENT_TIMESTAMP
             WHERE run_id = :run_id
        """
        with self.sql_client.connect() as conn:
            conn.execute(text(sql), args)
            conn.commit()

    # ── 산출물 (대량) ────────────────────────────────────────────────────────
    def insert_equity(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        sql = """
            INSERT INTO tn_backtest_equity (run_id, dt, equity, cash, position_count, gross_exposure)
            VALUES (:run_id, :dt, :equity, :cash, :position_count, :gross_exposure)
        """
        with self.sql_client.connect() as conn:
            conn.execute(text(sql), rows)
            conn.commit()
        return len(rows)

    def insert_trades(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        sql = """
            INSERT INTO tn_backtest_trade (
                 run_id, instrument_id, side, entry_ts, exit_ts, qty
               , fill_price, exit_price, fee, slippage, tax, realized_pnl, mae, mfe
            ) VALUES (
                 :run_id, :instrument_id, :side, :entry_ts, :exit_ts, :qty
               , :fill_price, :exit_price, :fee, :slippage, :tax, :realized_pnl, :mae, :mfe
            )
        """
        with self.sql_client.connect() as conn:
            conn.execute(text(sql), rows)
            conn.commit()
        return len(rows)

    def insert_signals(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        sql = """
            INSERT INTO tn_backtest_signal (run_id, dt, instrument_id, conditions, factors, passed)
            VALUES (:run_id, :dt, :instrument_id, CAST(:conditions AS jsonb), CAST(:factors AS jsonb), :passed)
        """
        with self.sql_client.connect() as conn:
            conn.execute(text(sql), rows)
            conn.commit()
        return len(rows)

    def insert_cash_events(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        sql = """
            INSERT INTO tn_backtest_cash (run_id, dt, event_kind, amount, note)
            VALUES (:run_id, :dt, :event_kind, :amount, :note)
        """
        with self.sql_client.connect() as conn:
            conn.execute(text(sql), rows)
            conn.commit()
        return len(rows)

    # ── 조회 ─────────────────────────────────────────────────────────────────
    def select_run(self, run_id: int) -> dict | None:
        sql = "SELECT * FROM tn_backtest_run WHERE run_id = :run_id"
        with self.sql_client.connect() as conn:
            row = conn.execute(text(sql), {"run_id": run_id}).mappings().first()
            return dict(row) if row else None

    def select_runs_by_bot(self, bot_id: int, workspace_id: int, limit: int) -> list[dict]:
        """한 봇의 실행 이력. 워크스페이스를 SQL 에서 함께 좁힌다 — 남의 봇 번호를 넣어도 빈 목록이다."""
        sql = """
            SELECT run_id, status, strategy_key, universe_def, period_from, period_to
                 , attempt_no, parent_run_id, finished_dt
              FROM tn_backtest_run
             WHERE bot_id = :bot_id
               AND workspace_id = :workspace_id
             ORDER BY run_id DESC
             LIMIT :limit
        """
        params = {"bot_id": bot_id, "workspace_id": workspace_id, "limit": limit}
        with self.sql_client.connect() as conn:
            return [dict(r) for r in conn.execute(text(sql), params).mappings()]

    def count_runs_by_bot(self, bot_id: int, workspace_id: int) -> int:
        """`LIMIT` 뒤 건수는 총수가 아니다 — 한 페이지만 보고 「이 봇은 3번 검증했다」고 말하면 거짓이 된다."""
        sql = """
            SELECT COUNT(*) AS total
              FROM tn_backtest_run
             WHERE bot_id = :bot_id
               AND workspace_id = :workspace_id
        """
        params = {"bot_id": bot_id, "workspace_id": workspace_id}
        with self.sql_client.connect() as conn:
            return int(conn.execute(text(sql), params).scalar_one())

    def select_equity_curve(self, run_id: int) -> list[dict]:
        sql = """
            SELECT dt, equity, cash, position_count, gross_exposure
              FROM tn_backtest_equity
             WHERE run_id = :run_id
             ORDER BY dt
        """
        with self.sql_client.connect() as conn:
            return [dict(r) for r in conn.execute(text(sql), {"run_id": run_id}).mappings()]

    def select_trades(self, run_id: int) -> list[dict]:
        sql = """
            SELECT trade_id, instrument_id, side, entry_ts, exit_ts, qty
                 , fill_price, exit_price, fee, slippage, tax, realized_pnl, mae, mfe
              FROM tn_backtest_trade
             WHERE run_id = :run_id
             ORDER BY entry_ts, trade_id
        """
        with self.sql_client.connect() as conn:
            return [dict(r) for r in conn.execute(text(sql), {"run_id": run_id}).mappings()]

    def next_attempt_no(self, workspace_id: int, strategy_key: str) -> int:
        """이 전략에서 **처음 평가하는 조합마다** 오르는 번호 (스펙 §8.5.2).

        격자를 훑는 것도 시도다 — 그 계수는 격자(#202)가 맡고, 여기서는 다음 값을 낸다.
        """
        sql = """
            SELECT COALESCE(MAX(attempt_no), 0) + 1
              FROM tn_backtest_run
             WHERE workspace_id = :workspace_id AND strategy_key = :strategy_key
        """
        with self.sql_client.connect() as conn:
            return int(conn.execute(text(sql), {"workspace_id": workspace_id, "strategy_key": strategy_key}).scalar())
