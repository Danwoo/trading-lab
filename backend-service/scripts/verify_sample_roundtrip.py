#!/usr/bin/env python3
"""적재본이 **소스와 값이 같은지** 확인한다 — M2 완료 판정의 그 줄 (#217).

## 왜 이 그물이 있나

M2 완료 판정에 *"차트가 적재된 캔들로 그려지고 **값이 소스와 일치한다**"* 가 있다.
그 조건은 **적재 → 저장 → 조회**를 한 줄로 통과시켜야 확인되는데, 각 단계의 단위 테스트는
자기 층만 본다 — 그 사이에서 값이 변형돼도(반올림·타임존·형변환) 아무도 못 잡는다.

실제로 그 계통에서 하나 잡혔다: `load_series` 가 `dt` 를 읽는데 계약은 `time` 이었다.
층 사이 경계는 **끝까지 태워야** 드러난다.

## 무엇을 대조하나

생성기가 내는 값과 DB 에서 조회한 값을 **같은 구간으로** 비교한다. 샘플 소스는 결정론적이라
(같은 씨앗 = 같은 값) 이 대조가 성립한다 — 실데이터 소스로는 못 하는 검증이다.

    BACKTEST_TEST_DB_URL=postgresql+psycopg://u:p@host:port/db \
      uv run python scripts/verify_sample_roundtrip.py

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

MARKET = "KR"
SYMBOL = "SAMPLE001"
DATE_FROM = dt.date(2026, 1, 1)
DATE_TO = dt.date(2026, 3, 31)


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def main() -> int:
    url = os.environ.get("BACKTEST_TEST_DB_URL")
    if not url:
        print("건너뜀: BACKTEST_TEST_DB_URL 없음 (DB 필요 검사)")
        return 0

    import asyncio
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from providers.sample.adapter import SampleProvider
    from providers.sample.generator import daily_bars
    from sqlalchemy import create_engine, text

    schema = "sample_roundtrip"
    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {schema}"))

    engine = create_engine(url, hide_parameters=True, connect_args={"options": f"-csearch_path={schema}"})

    # 시세 테이블은 0012 가 만든다 — 마이그레이션을 그대로 태운다(사본을 두지 않는다).
    # 종목 마스터(0011) 가 먼저다 — 일봉(0012)이 그 FK 를 건다.
    for rev in ("0011_instrument_master", "0012_market_bars"):
        path = BACKEND / "alembic" / "versions" / f"{rev}.py"
        if not path.is_file():
            print(f"::error::마이그레이션이 없다: {path}", file=sys.stderr)
            return 1
        spec = importlib.util.spec_from_file_location(f"_m_{rev}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as conn:
            ops = Operations(MigrationContext.configure(conn))
            ops._install_proxy()
            try:
                module.upgrade()
            finally:
                ops._remove_proxy()

    # ── 생성기 자체가 안 변했는가 (고정값) ──────────────────────────────────
    #
    # 아래 두 대조(소스↔어댑터, 소스↔DB)는 **양쪽이 같은 생성기를 읽으므로** 생성기가
    # 바뀌면 함께 바뀌어 못 잡는다. 그래서 몇 개를 값으로 박는다 — 샘플이 결정론적이라는
    # 약속이 깨지면 여기가 먼저 빨개진다(「어제 본 곡선을 오늘 본다」가 그 약속이다).
    #
    # 값을 의도적으로 바꿨다면 이 표도 함께 고친다. 조용히 통과시키지 않는 것이 목적이다.
    from providers.sample.generator import close_price

    GOLDEN = {
        dt.date(2026, 1, 5): 115726.73,
        dt.date(2026, 2, 2): 115410.67,
        dt.date(2026, 3, 2): 125994.29,
    }
    for day, expected in GOLDEN.items():
        check(f"생성기 고정값 {day}", close_price(SYMBOL, day), expected)

    # ── 소스가 말하는 값 ────────────────────────────────────────────────────
    source_bars = daily_bars(SYMBOL, DATE_FROM, DATE_TO)
    check("소스가 캔들을 낸다", len(source_bars) > 0, True)
    check("1~3월 거래일 수", len(source_bars), 64)

    # ── 어댑터를 거친 값 (적재가 쓰는 그 경로) ──────────────────────────────
    provider = SampleProvider()
    normalized = asyncio.run(provider.fetch_daily(SYMBOL, MARKET, DATE_FROM, DATE_TO))
    check("어댑터가 같은 개수를 낸다", len(normalized), len(source_bars))

    by_date = {b["dt"].isoformat(): b for b in source_bars}
    mismatched: list[str] = []
    for bar in normalized:
        key = bar.ts.date().isoformat()
        src = by_date.get(key)
        if src is None:
            mismatched.append(f"{key}: 소스에 없는 날짜")
            continue
        for field in ("open", "high", "low", "close"):
            if Decimal(str(src[field])) != getattr(bar, field):
                mismatched.append(f"{key}.{field}: 소스 {src[field]} ≠ 어댑터 {getattr(bar, field)}")
    global CHECKED
    CHECKED += 1
    if mismatched:
        FAILURES.append(f"소스와 어댑터가 어긋난다 ({len(mismatched)}건): {mismatched[:3]}")

    # ── 저장 → 조회를 거친 값 ───────────────────────────────────────────────
    # 적재 워커 전체를 돌리지 않고, 그 워커가 쓰는 **같은 표현**을 넣고 읽는다 —
    # 이 검사의 대상은 「값이 변형되는가」이지 잡 스케줄링이 아니다.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tn_instrument (market, symbol, issuer_nm, country, currency) "
                "VALUES (:m, :s, '샘플', 'KR', 'KRW')"
            ),
            {"m": MARKET, "s": SYMBOL},
        )
        iid = conn.execute(
            text("SELECT instrument_id FROM tn_instrument WHERE market=:m AND symbol=:s"), {"m": MARKET, "s": SYMBOL}
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO tn_daily_bar (instrument_id, trade_date, open, high, low, close, volume, "
                "source, adj_policy, ingested_at) "
                "VALUES (:i, :d, :o, :h, :l, :c, :v, 'sample', 'raw', now())"
            ),
            [
                {"i": iid, "d": b.ts.date(), "o": b.open, "h": b.high, "l": b.low, "c": b.close, "v": b.volume}
                for b in normalized
            ],
        )

    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT trade_date, open, high, low, close FROM tn_daily_bar "
                    "WHERE instrument_id = :i ORDER BY trade_date"
                ),
                {"i": iid},
            )
            .mappings()
            .all()
        )

    check("저장된 개수가 같다", len(rows), len(normalized))
    drift: list[str] = []
    for row in rows:
        src = by_date.get(row["trade_date"].isoformat())
        if src is None:
            drift.append(f"{row['trade_date']}: 소스에 없는 날짜")
            continue
        for field in ("open", "high", "low", "close"):
            if Decimal(str(src[field])) != row[field]:
                drift.append(f"{row['trade_date']}.{field}: 소스 {src[field]} ≠ DB {row[field]}")
    CHECKED += 1
    if drift:
        FAILURES.append(f"소스와 DB 가 어긋난다 ({len(drift)}건): {drift[:3]}")

    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))

    print(f"소스 {len(source_bars)}봉을 어댑터·DB 두 단계로 대조 · 단언 {CHECKED}건 (REQUIRE=db 실행됨)")

    if CHECKED < 9:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 적재본의 값이 소스와 일치한다 (M2 완료 판정)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
