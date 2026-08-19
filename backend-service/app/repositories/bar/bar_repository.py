"""캔들 적재본 읽기 — 이 리포지토리는 provider 를 모른다 (MD-AD-19 갈래 1).

`tn_daily_bar`·`tn_minute_bar` 에는 `workspace_id` 가 없다 — 시세는 전역 공용이고 워크스페이스
스코프는 API 키뿐이다(M2-AD-10). 그래서 다른 리포지토리와 달리 테넌트 조건이 붙지 않는다.
"""

import datetime as dt

from sqlalchemy import text


class BarRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    def select_instrument(self, args: dict) -> dict | None:
        """`(market, symbol)` → 종목 마스터 한 행. 대리키 해석의 유일한 경로(MD-AD-13)."""
        sql = """
            SELECT instrument_id
                 , country
                 , market
                 , symbol
                 , issuer_nm
                 , currency
                 , listed_dt
                 , delisted_dt
                 , is_active
              FROM tn_instrument
             WHERE market = :market
               AND symbol = :symbol
        """
        with self.sql_client.connect() as conn:
            row = conn.execute(text(sql), {"market": args["market"], "symbol": args["symbol"]}).mappings().fetchone()
            return dict(row) if row else None

    def has_any_instrument(self, market: str) -> bool:
        """그 시장의 종목 마스터를 한 번이라도 받았는가.

        「없는 종목」과 「아직 안 받은 종목」을 가르는 유일한 근거다 — 마스터가 통째로 비어
        있으면 그 종목이 없는 것인지 아직 안 받은 것인지 **알 수 없고**, 모르는 것을 아는 척
        답하면 사용자가 자기 입력을 의심한다.
        """
        sql = "SELECT EXISTS (SELECT 1 FROM tn_instrument WHERE market = :market) AS present"
        with self.sql_client.connect() as conn:
            return bool(conn.execute(text(sql), {"market": market}).scalar_one())

    def select_daily_bar_list(self, args: dict) -> tuple[list[dict], int]:
        """기간 지정 일봉. 차트는 페이지가 아니라 **기간 윈도**로 자르므로 `skip/take` 대신
        기간 + 상한(`limit`)이 페이지네이션 역할을 한다 — anti-patterns 룰 6 의 해석은 라우터
        docstring 에 적었다. 상한을 넘는 요청은 서비스가 400 으로 거절하므로 여기서 조용히
        잘리는 일은 없다.

        정렬은 **오름차순**이다. 차트가 시간축 왼쪽부터 그리므로, 최신순으로 주면 소비자마다
        뒤집는 코드가 생긴다 (MCP `market_ohlc` 의 최신순 계약과 의도적으로 다르다 — 그쪽은 LLM
        컨텍스트 보호가 목적이라 "최근 N개"가 자연스럽다).
        """
        params = {
            "instrument_id": args["instrument_id"],
            "date_from": args["date_from"],
            "date_to": args["date_to"],
            "take": args["limit"],
        }
        rows_sql = """
            SELECT to_char(trade_date, 'YYYY-MM-DD')  AS time
                 , CAST(open AS float)                AS open
                 , CAST(high AS float)                AS high
                 , CAST(low AS float)                 AS low
                 , CAST(close AS float)               AS close
                 , volume
                 , CAST(trade_value AS float)         AS trade_value
                 , source
                 , adj_policy
                 , ingested_at
              FROM tn_daily_bar
             WHERE instrument_id = :instrument_id
               AND trade_date BETWEEN :date_from AND :date_to
             ORDER BY trade_date ASC
             LIMIT :take
        """
        count_sql = """
            SELECT COUNT(*) AS cnt
              FROM tn_daily_bar
             WHERE instrument_id = :instrument_id
               AND trade_date BETWEEN :date_from AND :date_to
        """
        with self.sql_client.connect() as conn:
            rows = conn.execute(text(rows_sql), params).mappings().all()
            total = conn.execute(text(count_sql), params).scalar()
            return [dict(row) for row in rows], int(total or 0)

    def select_minute_bar_list(self, args: dict) -> tuple[list[dict], int]:
        """기간 지정 1분봉. 다른 주기는 저장하지 않는다(MD-AD-26) — 합성은 서비스의 몫이다."""
        params = {
            "instrument_id": args["instrument_id"],
            "ts_from": args["ts_from"],
            "ts_to": args["ts_to"],
            "take": args["limit"],
        }
        rows_sql = """
            SELECT to_char(ts, 'YYYY-MM-DD"T"HH24:MI') AS time
                 , CAST(open AS float)                 AS open
                 , CAST(high AS float)                 AS high
                 , CAST(low AS float)                  AS low
                 , CAST(close AS float)                AS close
                 , volume
                 , source
                 , adj_policy
                 , ingested_at
              FROM tn_minute_bar
             WHERE instrument_id = :instrument_id
               AND ts >= :ts_from
               AND ts <= :ts_to
             ORDER BY ts ASC
             LIMIT :take
        """
        count_sql = """
            SELECT COUNT(*) AS cnt
              FROM tn_minute_bar
             WHERE instrument_id = :instrument_id
               AND ts >= :ts_from
               AND ts <= :ts_to
        """
        with self.sql_client.connect() as conn:
            rows = conn.execute(text(rows_sql), params).mappings().all()
            total = conn.execute(text(count_sql), params).scalar()
            return [dict(row) for row in rows], int(total or 0)

    def select_traded_dates(self, args: dict) -> list[dt.date]:
        """구간 안에서 실제로 적재된 거래일 목록 — 캘린더 세션과의 차집합이 갭이다(MD-AD-23)."""
        sql = """
            SELECT trade_date
              FROM tn_daily_bar
             WHERE instrument_id = :instrument_id
               AND trade_date BETWEEN :date_from AND :date_to
             ORDER BY trade_date ASC
        """
        with self.sql_client.connect() as conn:
            rows = conn.execute(text(sql), args).mappings().all()
            return [row["trade_date"] for row in rows]
