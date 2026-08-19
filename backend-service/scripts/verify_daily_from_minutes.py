#!/usr/bin/env python3
"""#255 — 분봉이 있으면 일봉을 **정규장 구간만 접어** 다시 만드는가 (DB 필요).

## 왜 이 그물이 있나

실측(2026-08-19, 토스 실적재)에서 **같은 컬럼이 종목마다 다른 것을 뜻한다**가 드러났다.
토스 일봉은 시간외까지 포함하는 종목이 있고(보통주 표본 25종목 중 9종목), 그 종목의
일봉 종가는 정규장 종가(15:31 봉)와 −1.86%·+4.04% 어긋났다. 백테스트가 「종가에 판다」를
계산하면 **정규장에서 낼 수 없는 가격에 체결**한 것이 된다.

그래서 분봉이 있으면 우리가 직접 접는다(MD-AD-26 — 저장은 1분봉, 상위 주기는 합성).
이 검사는 그 접기가 **맞는 값**을 내는지 실제 SQL 로 확인한다:

    분봉을 심는다 → 일봉을 다시 만든다 → 시가·고가·저가·종가·거래량이 정규장 구간의 것이다
                 → 시간외 봉은 안 섞인다 → session_scope 가 `regular` 로 바뀐다

## 쓰는 법

    DAILY_FOLD_TEST_DB_URL=postgresql+psycopg://u:p@host:port/db \
      uv run python scripts/verify_daily_from_minutes.py

URL 이 없으면 건너뛴다(exit 0). 실제로 돌면 `REQUIRE=db 실행됨` 을 찍는다.
**사람의 개발 DB 를 쓰지 마라** — 전용 스키마를 만들고 지운다.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

FAILURES: list[str] = []
CHECKED = 0

SCHEMA = "daily_fold"


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def main() -> int:
    url = os.environ.get("DAILY_FOLD_TEST_DB_URL")
    if not url:
        print("건너뜀: DAILY_FOLD_TEST_DB_URL 없음 (DB 필요 검사)")
        return 0

    from types import SimpleNamespace

    from repositories.ingest.ingest_repository import IngestRepository
    from sqlalchemy import create_engine, text

    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {SCHEMA}"))

    engine = create_engine(url, hide_parameters=True, connect_args={"options": f"-csearch_path={SCHEMA}"})

    # 이 검사에 필요한 두 표만 세운다 — 파티션·FK 는 접기와 무관하고, 세우면 이 검사가
    # 「접기가 맞나」가 아니라 「스키마를 옮겨 적었나」를 보게 된다.
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE TABLE tn_minute_bar (
                instrument_id int NOT NULL, ts timestamp NOT NULL, interval_min int NOT NULL DEFAULT 1,
                open numeric(18,4), high numeric(18,4), low numeric(18,4), close numeric(18,4),
                volume bigint, source varchar(30), adj_policy varchar(20),
                PRIMARY KEY (instrument_id, ts, interval_min))
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE tn_daily_bar (
                instrument_id int NOT NULL, trade_date date NOT NULL,
                open numeric(18,4), high numeric(18,4), low numeric(18,4), close numeric(18,4),
                volume bigint, trade_value numeric(20,2), source varchar(30), adj_policy varchar(20),
                session_scope varchar(20) NOT NULL DEFAULT 'unknown',
                ingest_run_id int, ingested_at timestamp,
                PRIMARY KEY (instrument_id, trade_date))
        """)
        )

    # 실측을 그대로 옮긴 하루 — 시간외가 정규장 범위 **밖**에 있고, 마감 동시호가가 15:31 이다.
    day = dt.date(2026, 8, 19)
    minutes = [
        ("08:01", 257500, 257500, 251500, 253000, 436517),  # 장전(시간외) — 접기에서 빠져야 한다
        ("09:00", 252000, 252000, 252000, 252000, 0),  # 시가 동시호가
        ("09:01", 251500, 252000, 250000, 251250, 690540),
        ("12:00", 249000, 249500, 246500, 248500, 100000),  # 저가가 여기 있다
        ("15:30", 248250, 248250, 248250, 248250, 0),
        ("15:31", 247500, 247500, 247500, 247500, 2502579),  # 마감 동시호가 — 종가는 이것이다
        ("16:00", 255000, 256000, 254500, 255500, 90169),  # 장후(시간외) — 접기에서 빠져야 한다
        ("20:00", 256500, 261500, 256500, 257500, 93976),  # 고가가 여기 있다 — 섞이면 안 된다
    ]
    with engine.begin() as conn:
        for hhmm, o, h, low, c, v in minutes:
            conn.execute(
                text("""INSERT INTO tn_minute_bar (instrument_id, ts, open, high, low, close, volume, source, adj_policy)
                        VALUES (1, :ts, :o, :h, :l, :c, :v, 'toss', 'raw')"""),
                {"ts": dt.datetime.combine(day, dt.time.fromisoformat(hhmm)), "o": o, "h": h, "l": low, "c": c, "v": v},
            )
        # 소스가 준 일봉 — 시간외까지 덮은 값이다 (실측 그대로)
        conn.execute(
            text("""INSERT INTO tn_daily_bar (instrument_id, trade_date, open, high, low, close, volume,
                                              source, adj_policy, session_scope)
                    VALUES (1, :d, 257500, 261500, 246500, 257500, 45473207, 'toss', 'raw', 'unknown')"""),
            {"d": day},
        )

    repository = IngestRepository(SimpleNamespace(engine=engine))
    repository.rebuild_daily_from_minutes(
        {
            "instrument_ids": [1],
            "date_from": day,
            "date_to": day,
            "session_open": dt.time(9, 0),
            "session_close": dt.time(15, 31),
            "ingest_run_id": None,
        }
    )

    with engine.begin() as conn:
        row = (
            conn.execute(
                text("SELECT open, high, low, close, volume, session_scope FROM tn_daily_bar WHERE instrument_id=1")
            )
            .mappings()
            .one()
        )

    # 정규장(09:00~15:31)만 접은 값 — 시간외 봉의 고가 261500·시가 257500 이 섞이면 안 된다
    check("시가는 정규장 첫 봉", row["open"], Decimal("252000.0000"))
    check("고가에 시간외가 안 섞인다", row["high"], Decimal("252000.0000"))
    check("저가는 정규장 안에서", row["low"], Decimal("246500.0000"))
    check("종가는 마감 동시호가", row["close"], Decimal("247500.0000"))
    check("거래량은 정규장 합", row["volume"], 690540 + 100000 + 2502579)
    check("무엇인지 아는 값이 됐다", row["session_scope"], "regular")

    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))

    print(f"REQUIRE=db 실행됨 — 검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 6:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 분봉이 있으면 일봉이 정규장 구간의 값이 되고, 시간외가 안 섞인다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
