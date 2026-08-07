"""적재 잡·적재본 쓰기. `tn_ingest_run` 하나가 요청·실행·이력 셋을 겸한다 (M2-AD-12).

중복 방지는 애플리케이션 사전 조회가 아니라 **유니크 제약 + upsert** 다(MD-AD-16) — 같은 구간을
다시 적재하면 중복 행이 아니라 갱신이고, 그 불변식이 스키마 수준에서 성립한다.

`tn_daily_bar`·`tn_minute_bar` 에는 감사 컬럼 4종이 없다 — 대용량 시계열의 의도된 예외이며
(anti-patterns 룰 5 예외), `source`·`ingest_run_id`·`ingested_at` 가 행 단위 provenance 를 진다.
`tn_instrument`·`tn_symbol_alias`·`tn_ingest_run` 은 일반 테이블이라 4종을 그대로 채운다.
"""

import datetime as dt

from sqlalchemy import text
from utils.common.devextreme_utils import build_filter_params, parse_sort

# 잡 폴링·실행 중복을 막는 advisory lock 키. `--workers=1` 이라 사실상 단일이지만, 개발 중
# 재시작이 겹치는 창(옛 프로세스가 아직 안 죽었는데 새 프로세스가 뜬 상태)을 닫는다.
INGEST_ADVISORY_LOCK_KEY = 2430001


class IngestRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    # ── 잡 레코드 ────────────────────────────────────────────────────────────
    def query_select_ingest_run(self) -> str:
        return """
            SELECT *
              FROM (
                SELECT run_id
                     , source
                     , job_kind
                     , scope
                     , to_char(period_from, 'YYYY-MM-DD') AS period_from
                     , to_char(period_to, 'YYYY-MM-DD')   AS period_to
                     , status
                     , cursor
                     , written_rows
                     , skipped_rows
                     , failed_reason
                     , workspace_id
                     , to_char(started_dt, 'YYYY-MM-DD HH24:MI:SS')  AS started_dt
                     , to_char(finished_dt, 'YYYY-MM-DD HH24:MI:SS') AS finished_dt
                     , to_char(reg_dt, 'YYYY-MM-DD HH24:MI:SS')      AS reg_dt
                     , reg_id
                     , to_char(mod_dt, 'YYYY-MM-DD HH24:MI:SS')      AS mod_dt
                     , mod_id
                  FROM tn_ingest_run
                ) A
             WHERE 1 = 1
        """

    def select_ingest_run_list(self, args: dict) -> tuple[list[dict], int]:
        base_sql = self.query_select_ingest_run()
        sql_where, sql_params = build_filter_params(args)
        order_by = parse_sort(args.get("sort")) or "run_id DESC"
        skip = int(args.get("skip", 0))
        take = args.get("take")

        count_sql = f"SELECT COUNT(*) AS cnt FROM ({base_sql} {sql_where}) TB"
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
                SELECT *
                  FROM (
                        SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS rn
                             , TB.*
                          FROM ({base_sql} {sql_where}) TB
                       ) TB
            """
        with self.sql_client.connect() as conn:
            rows = conn.execute(text(final_sql), sql_params).mappings().all()
            total = conn.execute(text(count_sql), sql_params).scalar()
            return [dict(row) for row in rows], int(total or 0)

    def select_ingest_run(self, args: dict) -> dict | None:
        sql = self.query_select_ingest_run() + " AND run_id = :run_id"
        with self.sql_client.connect() as conn:
            row = conn.execute(text(sql), {"run_id": args["run_id"]}).mappings().fetchone()
            return dict(row) if row else None

    def insert_ingest_run(self, args: dict) -> int:
        sql = """
            INSERT INTO tn_ingest_run (
                 source, job_kind, scope, period_from, period_to, status
               , written_rows, skipped_rows, workspace_id
               , reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (
                 :source, :job_kind, :scope, :period_from, :period_to, 'queued'
               , 0, 0, :workspace_id
               , :reg_id, CURRENT_TIMESTAMP, :reg_id, CURRENT_TIMESTAMP
            )
            RETURNING run_id
        """
        with self.sql_client.connect() as conn:
            run_id = conn.execute(text(sql), args).scalar()
            conn.commit()
            return int(run_id)

    def update_ingest_run_status(self, args: dict) -> None:
        """잡 상태 전이. 백그라운드 워커가 유일한 호출자라 `mod_id` 는 'system' 이다
        (anti-patterns 룰 5 의 Background-only update 예외)."""
        sql = """
            UPDATE tn_ingest_run
               SET status        = :status
                 , cursor        = COALESCE(:cursor, cursor)
                 , written_rows  = COALESCE(:written_rows, written_rows)
                 , skipped_rows  = COALESCE(:skipped_rows, skipped_rows)
                 , failed_reason = :failed_reason
                 , started_dt    = COALESCE(started_dt, :started_dt)
                 , finished_dt   = :finished_dt
                 , mod_id        = 'system'
                 , mod_dt        = CURRENT_TIMESTAMP
             WHERE run_id = :run_id
        """
        params = {
            "cursor": None,
            "written_rows": None,
            "skipped_rows": None,
            "failed_reason": None,
            "started_dt": None,
            "finished_dt": None,
            **args,
        }
        with self.sql_client.connect() as conn:
            conn.execute(text(sql), params)
            conn.commit()

    def claim_next_queued_run(self) -> dict | None:
        """가장 오래된 `queued` 잡 하나를 `running` 으로 바꿔 가져온다.

        `FOR UPDATE SKIP LOCKED` 로 집는 이유: 같은 행을 두 프로세스가 동시에 집어 두 번 실행하는
        창을 DB 가 닫는다. 워커가 하나뿐인 지금도 재시작이 겹치는 순간에는 둘이 된다.
        """
        select_sql = """
            SELECT run_id
              FROM tn_ingest_run
             WHERE status = 'queued'
             ORDER BY run_id ASC
             LIMIT 1
               FOR UPDATE SKIP LOCKED
        """
        update_sql = """
            UPDATE tn_ingest_run
               SET status = 'running', started_dt = CURRENT_TIMESTAMP
                 , mod_id = 'system', mod_dt = CURRENT_TIMESTAMP
             WHERE run_id = :run_id
        """
        with self.sql_client.connect() as conn:
            run_id = conn.execute(text(select_sql)).scalar()
            if run_id is None:
                conn.commit()
                return None
            conn.execute(text(update_sql), {"run_id": run_id})
            conn.commit()
        return self.select_ingest_run({"run_id": run_id})

    def try_advisory_lock(self) -> bool:
        """세션 수준 advisory lock — 잡 폴링 루프의 중복 실행을 막는다."""
        with self.sql_client.connect() as conn:
            acquired = conn.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": INGEST_ADVISORY_LOCK_KEY}
            ).scalar()
            # 세션(=커넥션)이 풀로 돌아가면 잠금이 남으므로, 소유 여부만 확인하고 바로 푼다.
            # 우리가 막으려는 것은 "동시에 두 실행이 겹치는 것"이지 프로세스 수명 전체가 아니다.
            if acquired:
                conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": INGEST_ADVISORY_LOCK_KEY})
            conn.commit()
            return bool(acquired)

    # ── 종목 마스터 ──────────────────────────────────────────────────────────
    def upsert_instruments(self, rows: list[dict], reg_id: str) -> int:
        """`(market, symbol)` 유니크로 upsert. 이미 있으면 종목명·통화·업종만 갱신한다 —
        `instrument_id` 는 캔들이 참조하는 대리키라 절대 바뀌지 않는다(MD-AD-13)."""
        if not rows:
            return 0
        sql = """
            INSERT INTO tn_instrument (
                 country, market, symbol, issuer_nm, currency, sector_code, is_active
               , reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (
                 :country, :market, :symbol, :issuer_nm, :currency, :sector_code, 'Y'
               , :reg_id, CURRENT_TIMESTAMP, :reg_id, CURRENT_TIMESTAMP
            )
            ON CONFLICT (market, symbol) DO UPDATE
               SET issuer_nm   = EXCLUDED.issuer_nm
                 , currency    = EXCLUDED.currency
                 , sector_code = COALESCE(EXCLUDED.sector_code, tn_instrument.sector_code)
                 , is_active   = 'Y'
                 , mod_id      = EXCLUDED.mod_id
                 , mod_dt      = CURRENT_TIMESTAMP
        """
        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), [{**row, "reg_id": reg_id} for row in rows])
            conn.commit()
            return result.rowcount if result.rowcount and result.rowcount > 0 else len(rows)

    def upsert_symbol_aliases(self, rows: list[dict], reg_id: str) -> int:
        """별칭 upsert. PK 가 `(instrument_id, alias_kind, valid_from)` 이라 같은 날 다시 적재하면
        갱신이고, 유효기간이 다르면 새 행이다(MD-AD-25).

        **과거(닫힌) 구간끼리의 겹침은 DB 가 막지 않는다** — `EXCLUDE USING gist` 가 `btree_gist`
        확장을 요구해 배포 환경에 달렸기 때문이다(구현설계 §1.2 미결). 지금 이 경로는 언제나
        `valid_to IS NULL` 인 현재값만 쓰므로 겹침이 생기지 않는다. 과거 구간을 닫는 경로를
        추가할 때 삽입 전 겹침 검사를 함께 넣어야 한다.
        """
        if not rows:
            return 0
        sql = """
            INSERT INTO tn_symbol_alias (
                 instrument_id, alias_kind, alias_value, valid_from, valid_to
               , reg_id, reg_dt, mod_id, mod_dt
            ) VALUES (
                 :instrument_id, :alias_kind, :alias_value, :valid_from, NULL
               , :reg_id, CURRENT_TIMESTAMP, :reg_id, CURRENT_TIMESTAMP
            )
            ON CONFLICT (instrument_id, alias_kind, valid_from) DO UPDATE
               SET alias_value = EXCLUDED.alias_value
                 , mod_id      = EXCLUDED.mod_id
                 , mod_dt      = CURRENT_TIMESTAMP
        """
        with self.sql_client.connect() as conn:
            conn.execute(text(sql), [{**row, "reg_id": reg_id} for row in rows])
            conn.commit()
            return len(rows)

    def select_current_alias_owners(self, pairs: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
        """지금 유효한(`valid_to IS NULL`) `(alias_kind, alias_value)` → `instrument_id`.

        부분 유니크 인덱스(`ux_symbol_alias_current`, MD-AD-25)는 "이 값은 지금 한 종목의 것"을
        강제한다. 그래서 **삽입 전에** 누가 이미 쥐고 있는지 물어봐야 한다 — 안 물어보면
        `IntegrityError` 가 배치 전체를 되돌리고, 정상 별칭까지 함께 사라진다(실측: SEC 의 CIK 는
        회사 단위라 GOOGL·GOOG 처럼 한 회사의 두 클래스가 같은 값을 갖는다).
        """
        if not pairs:
            return {}
        sql = """
            SELECT alias_kind, alias_value, instrument_id
              FROM tn_symbol_alias
             WHERE valid_to IS NULL
               AND alias_kind = ANY(:kinds)
               AND alias_value = ANY(:values)
        """
        params = {"kinds": sorted({kind for kind, _ in pairs}), "values": sorted({value for _, value in pairs})}
        with self.sql_client.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
            return {(row["alias_kind"], row["alias_value"]): row["instrument_id"] for row in rows}

    def select_instrument_id_map(self, market: str, symbols: list[str]) -> dict[str, int]:
        """`(market, symbol)` → `instrument_id`. 심볼 해석의 입력이며, 여기 없는 심볼이 곧
        `skipped_rows` 다 — 버리지 않고 센다."""
        if not symbols:
            return {}
        sql = """
            SELECT symbol, instrument_id
              FROM tn_instrument
             WHERE market = :market
               AND symbol = ANY(:symbols)
        """
        with self.sql_client.connect() as conn:
            rows = conn.execute(text(sql), {"market": market, "symbols": list(symbols)}).mappings().all()
            return {row["symbol"]: row["instrument_id"] for row in rows}

    def select_last_trade_date(self, instrument_id: int) -> dt.date | None:
        """이 종목의 마지막 저장 거래일 — 적재 시작점이다(MD-AD-22: 그 하루를 항상 다시 받는다)."""
        sql = "SELECT MAX(trade_date) FROM tn_daily_bar WHERE instrument_id = :instrument_id"
        with self.sql_client.connect() as conn:
            return conn.execute(text(sql), {"instrument_id": instrument_id}).scalar()

    # ── 캔들 ─────────────────────────────────────────────────────────────────
    def upsert_daily_bars(self, rows: list[dict]) -> int:
        """일봉 벌크 upsert (MD-AD-16). 감사 컬럼 대신 `source`·`ingest_run_id`·`ingested_at`."""
        if not rows:
            return 0
        sql = """
            INSERT INTO tn_daily_bar (
                 instrument_id, trade_date, open, high, low, close, volume, trade_value
               , source, adj_policy, ingest_run_id, ingested_at
            ) VALUES (
                 :instrument_id, :trade_date, :open, :high, :low, :close, :volume, :trade_value
               , :source, :adj_policy, :ingest_run_id, CURRENT_TIMESTAMP
            )
            ON CONFLICT (instrument_id, trade_date) DO UPDATE
               SET open          = EXCLUDED.open
                 , high          = EXCLUDED.high
                 , low           = EXCLUDED.low
                 , close         = EXCLUDED.close
                 , volume        = EXCLUDED.volume
                 , trade_value   = EXCLUDED.trade_value
                 , source        = EXCLUDED.source
                 , adj_policy    = EXCLUDED.adj_policy
                 , ingest_run_id = EXCLUDED.ingest_run_id
                 , ingested_at   = CURRENT_TIMESTAMP
        """
        with self.sql_client.connect() as conn:
            conn.execute(text(sql), rows)
            conn.commit()
            return len(rows)

    def upsert_minute_bars(self, rows: list[dict]) -> int:
        """1분봉 벌크 upsert. `interval_min` 은 언제나 1 이다 — 스키마 CHECK 가 그것을 강제하며,
        다른 값을 넣으려는 시도는 조용한 키 충돌이 아니라 제약 위반으로 터진다(MD-AD-26)."""
        if not rows:
            return 0
        sql = """
            INSERT INTO tn_minute_bar (
                 instrument_id, ts, interval_min, open, high, low, close, volume
               , source, adj_policy, ingest_run_id, ingested_at
            ) VALUES (
                 :instrument_id, :ts, 1, :open, :high, :low, :close, :volume
               , :source, :adj_policy, :ingest_run_id, CURRENT_TIMESTAMP
            )
            ON CONFLICT (instrument_id, ts) DO UPDATE
               SET open          = EXCLUDED.open
                 , high          = EXCLUDED.high
                 , low           = EXCLUDED.low
                 , close         = EXCLUDED.close
                 , volume        = EXCLUDED.volume
                 , source        = EXCLUDED.source
                 , adj_policy    = EXCLUDED.adj_policy
                 , ingest_run_id = EXCLUDED.ingest_run_id
                 , ingested_at   = CURRENT_TIMESTAMP
        """
        with self.sql_client.connect() as conn:
            conn.execute(text(sql), rows)
            conn.commit()
            return len(rows)
