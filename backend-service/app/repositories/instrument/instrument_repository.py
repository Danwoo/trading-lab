"""종목 마스터 검색 (`tn_instrument`) — 화면이 종목을 **찾아 고르는** 유일한 경로.

시세는 워크스페이스 스코프가 아니다(M2-AD-10) — 이 리포지토리의 어떤 쿼리에도 `workspace_id`
가 없다. `BarRepository` 와 같은 테이블을 읽지만 조회 단위가 다르다: 저쪽은 `(market, symbol)`
단건 해석이고 여기는 사람이 입력한 말로 훑는 목록이다.
"""

from sqlalchemy import text

#: LIKE 패턴에서 뜻을 가진 글자. 사용자가 친 `%`·`_` 는 와일드카드가 아니라 **글자**다 —
#: 안 막으면 `_` 한 글자가 4,303행을 통째로 훑는 패턴이 된다.
_LIKE_SPECIALS = str.maketrans({"\\": "\\\\", "%": "\\%", "_": "\\_"})


def _like_literal(value: str) -> str:
    return value.translate(_LIKE_SPECIALS)


class InstrumentRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    @staticmethod
    def _where(args: dict) -> tuple[str, dict]:
        """검색어·시장 조건과 바인딩. 검색어는 코드·종목명 양쪽에 건다 — 사용자는 「삼성전자」를
        알지 「005930」을 모른다."""
        conditions = ["1 = 1"]
        params: dict = {}

        query = (args.get("q") or "").strip().upper()
        if query:
            params["pattern"] = f"%{_like_literal(query)}%"
            conditions.append("(UPPER(symbol) LIKE :pattern ESCAPE '\\' OR UPPER(issuer_nm) LIKE :pattern ESCAPE '\\')")
        market = (args.get("market") or "").strip().upper()
        if market:
            params["market"] = market
            conditions.append("market = :market")

        return "\n               AND ".join(conditions), params

    @staticmethod
    def _order_by(args: dict) -> tuple[str, dict]:
        """정확히 친 코드 → 코드 앞자리 → 종목명 앞자리 → 나머지 순. 「삼성」을 치면 「삼성전자」가
        「대덕삼성」보다 위에 온다."""
        query = (args.get("q") or "").strip().upper()
        if not query:
            return "issuer_nm ASC, market ASC, symbol ASC", {}
        literal = _like_literal(query)
        params = {"exact": query, "prefix": f"{literal}%"}
        rank = (
            "CASE WHEN UPPER(symbol) = :exact THEN 0"
            " WHEN UPPER(symbol) LIKE :prefix ESCAPE '\\' THEN 1"
            " WHEN UPPER(issuer_nm) LIKE :prefix ESCAPE '\\' THEN 2"
            " ELSE 3 END"
        )
        return f"{rank}, issuer_nm ASC, market ASC, symbol ASC", params

    def select_instrument_list(self, args: dict) -> tuple[list[dict], int]:
        sql_where, sql_params = self._where(args)
        order_by, order_params = self._order_by(args)
        sql_params.update(order_params)

        skip = int(args.get("skip", 0))
        take = int(args["take"])

        base_sql = f"""
            SELECT country
                 , market
                 , symbol
                 , issuer_nm
                 , currency
                 , is_active
              FROM tn_instrument
             WHERE {sql_where}
        """
        final_sql = f"""
            SELECT *
              FROM (
                        SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS rn
                             , TB.*
                          FROM ({base_sql}) TB
                   ) TB
             WHERE rn BETWEEN {skip + 1} AND {skip + take}
        """
        count_sql = f"SELECT COUNT(*) AS cnt FROM ({base_sql}) TB"

        with self.sql_client.connect() as conn:
            rows = conn.execute(text(final_sql), sql_params).mappings().all()
            count = conn.execute(text(count_sql), sql_params).scalar()
            return [dict(row) for row in rows], int(count)

    def has_any_instrument(self) -> bool:
        """마스터를 한 번이라도 받았는가 — 「검색 결과 0건」과 「아직 안 받았다」를 가르는 근거다.

        `BarRepository.has_any_instrument(market)` 는 시장 하나를 묻지만, 검색은 시장을 안 고른
        상태에서도 열리므로 전역으로 묻는다.
        """
        sql = "SELECT EXISTS (SELECT 1 FROM tn_instrument) AS present"
        with self.sql_client.connect() as conn:
            return bool(conn.execute(text(sql)).scalar_one())
