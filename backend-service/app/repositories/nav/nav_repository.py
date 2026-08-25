# repositories/nav/nav_repository.py
from sqlalchemy import text


class NavRepository:
    def __init__(self, sql_client):
        self.sql_client = sql_client

    def insert_nav(self, args: dict) -> None:
        # source_message_id 로 멱등 — 같은 메시지의 재소비는 WHERE NOT EXISTS 로 스킵.
        # 하드 보장은 ux_nav_source_message(필터드 유니크); 이 SELECT 는 정상경로 no-op 삽입 회피.
        #
        # `nav_dt` 는 naive 인 채로 남는다 — 2026-07-30 결정의 **시장 현지 벽시계** 계열이고,
        # 차트 시간축이 그 계약 위에 서 있다(#359 ㉠(a)). 감사 컬럼(reg_dt·mod_dt)만 timestamptz 로
        # 옮겼다. 세션 tz 가 UTC 로 고정된 뒤에는 맨 `CURRENT_TIMESTAMP` 가 UTC 벽시계를 내므로,
        # 시장 벽시계를 원하는 자리에는 `AT TIME ZONE 'Asia/Seoul'` 을 **명시**한다 — 안 적으면
        # 뜻이 세션 설정에 딸려 가고, 그러면 옛 행은 KST·새 행은 UTC 벽시계로 갈린다.
        sql = """
            INSERT INTO tn_nav (
                 workspace_id
               , source_message_id
               , nav_dt
               , nav
               , benchmark
               , daily_return
               , drawdown
               , reg_id
               , reg_dt
               , mod_id
               , mod_dt
            )
            SELECT
                 :workspace_id
               , :source_message_id
               , CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul'
               , :nav
               , :benchmark
               , :daily_return
               , :drawdown
               , :reg_id
               , CURRENT_TIMESTAMP
               , :reg_id
               , CURRENT_TIMESTAMP
             WHERE NOT EXISTS (
                   SELECT 1 FROM tn_nav WHERE source_message_id = :source_message_id
             )
        """
        with self.sql_client.connect() as conn:
            with conn.begin():
                conn.execute(text(sql), args)

    def select_history(self, args: dict) -> list[dict]:
        # 비교 대상이 naive `nav_dt` 라 오른쪽도 같은 시장 벽시계여야 한다 — 맨 CURRENT_TIMESTAMP
        # 를 두면 Postgres 가 `nav_dt` 를 세션 tz 로 암시 캐스트해 창 크기가 세션마다 달라진다
        # (실측: 30분 창이 Asia/Seoul 111행 · UTC 3,265행 · America/New_York 4,704행).
        # 표시 포맷도 그대로 둔다 — 오프셋을 붙이면 시장 벽시계가 인스턴트로 읽혀 축이 밀린다.
        sql = """
            SELECT to_char(nav_dt, 'YYYY-MM-DD"T"HH24:MI:SS') AS timestamp
                 , CAST(nav AS float)          AS nav
                 , CAST(benchmark AS float)    AS benchmark
                 , CAST(daily_return AS float) AS daily_return
                 , CAST(drawdown AS float)     AS drawdown
              FROM tn_nav
             WHERE nav_dt >= (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul') - (:minutes * INTERVAL '1 minute')
               AND workspace_id = :workspace_id
             ORDER BY nav_dt ASC
        """
        with self.sql_client.connect() as conn:
            result = conn.execute(text(sql), args).mappings().all()
            return [dict(row) for row in result]
