#!/usr/bin/env python3
"""종목 마스터 검색이 **진짜 Postgres 위에서** 무엇을 답하는지 확인한다 (#318).

## 왜 DB 앞에 세우나

이 기능의 값은 전부 SQL 안에 있다 — LIKE 이스케이프·순위 CASE·`ROW_NUMBER()` 상한. 리포지토리를
대역으로 갈아 끼운 단위 테스트는 그 SQL 이 DB 앞에 한 번도 서지 않아, 깨진 이스케이프나 틀린
정렬이 그대로 새어 나간다 (`verify_minute_partition_query.py` 가 같은 이유로 존재한다).

## 무엇을 잠그나

  ① 마스터가 비면 「아직 한 번도 받지 않았습니다」 + 다음 걸음 — 「그런 종목 없음」과 다른 답
  ② 마스터가 차 있으면 0건은 그냥 0건이다 (사유를 붙이지 않는다)
  ③ 이름으로 찾아진다 — 사용자는 「삼성전자」를 알지 「005930」을 모른다
  ④ 코드로도 찾아지고, 정확히 친 코드가 맨 위에 온다
  ⑤ 사용자가 친 `%`·`_` 는 와일드카드가 아니라 **글자**다 (안 막으면 `_` 한 글자가 전 종목을 훑는다)
  ⑥ 4,303행을 한 번에 내려보내지 않는다 — `take` 만큼 자르고 전체 건수는 따로 답한다
  ⑦ 상한을 넘는 `take` 는 조용히 잘리지 않고 400 이다

    BACKTEST_TEST_DB_URL=postgresql+psycopg://u:p@host:port/db \
      uv run python scripts/verify_instrument_search.py

URL 이 없으면 건너뛴다(exit 0). 실제로 돌면 `REQUIRE=db 실행됨` 을 찍는다.
**사람의 개발 DB 를 쓰지 마라** — 전용 스키마를 만들고 지운다.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

FAILURES: list[str] = []
CHECKED = 0

SCHEMA = "instrument_search_check"
NOT_LOADED = "아직 한 번도 받지 않았습니다"

# 검색이 실제로 겪는 모양들을 한 판에 심는다.
#   · 같은 낱말이 앞·뒤에 오는 두 종목 (순위)
#   · 종목명에 LIKE 특수문자가 든 종목 (이스케이프)
#   · 영문 종목명 (대소문자)
SEED: list[tuple[str, str, str, str, str]] = [
    ("KR", "KOSPI", "005930", "삼성전자", "KRW"),
    ("KR", "KOSPI", "008060", "대덕삼성", "KRW"),
    ("KR", "KOSDAQ", "247540", "에코프로비엠", "KRW"),
    ("KR", "KOSPI", "999001", "퍼센트%종목", "KRW"),
    ("KR", "KOSPI", "999002", "언더_종목", "KRW"),
    ("US", "NASDAQ", "AAPL", "Apple Inc.", "USD"),
]


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

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from core.exceptions import BadRequestError
    from repositories.instrument.instrument_repository import InstrumentRepository
    from services.instrument.instrument_service import InstrumentService
    from sqlalchemy import create_engine, text

    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {SCHEMA}"))

    engine = create_engine(url, hide_parameters=True, connect_args={"options": f"-csearch_path={SCHEMA}"})

    path = BACKEND / "alembic" / "versions" / "0011_instrument_master.py"
    if not path.is_file():
        print(f"::error::마이그레이션이 없다: {path}", file=sys.stderr)
        return 1
    spec = importlib.util.spec_from_file_location("_m_0011", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with engine.begin() as conn:
        ops = Operations(MigrationContext.configure(conn))
        ops._install_proxy()
        try:
            module.upgrade()
        finally:
            ops._remove_proxy()

    service = InstrumentService(instrument_repository=InstrumentRepository(sql_client=engine))

    # ── ① 마스터가 통째로 빈 상태 ─────────────────────────────────────────
    empty = service.select_instrument_list({"q": "삼성"})
    check("빈 마스터 — 0건", empty["total_count"], 0)
    check("빈 마스터 — 아직 안 받았다고 답한다", NOT_LOADED in (empty["unavailable_reason"] or ""), True)
    check("빈 마스터 — 다음 걸음이 문구에 있다", "적재" in (empty["unavailable_reason"] or ""), True)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tn_instrument (country, market, symbol, issuer_nm, currency)"
                " VALUES (:country, :market, :symbol, :issuer_nm, :currency)"
            ),
            [dict(zip(("country", "market", "symbol", "issuer_nm", "currency"), row, strict=True)) for row in SEED],
        )

    # ── ② 마스터가 차 있으면 0건은 그냥 0건이다 ───────────────────────────
    none_matched = service.select_instrument_list({"q": "없는종목이름"})
    check("찬 마스터 — 0건", none_matched["total_count"], 0)
    check("찬 마스터 — 사유를 붙이지 않는다", none_matched["unavailable_reason"], None)

    # ── ③ 이름으로 찾아진다 ───────────────────────────────────────────────
    by_name = service.select_instrument_list({"q": "삼성전자"})
    check("이름 검색 — 1건", by_name["total_count"], 1)
    check("이름 검색 — 코드를 준다", by_name["items"][0]["symbol"], "005930")
    check("이름 검색 — 시장도 준다", by_name["items"][0]["market"], "KOSPI")

    # ── ④ 코드로도 찾아지고, 정확히 친 코드·앞자리가 위에 온다 ────────────
    by_code = service.select_instrument_list({"q": "005930"})
    check("코드 검색 — 1건", by_code["total_count"], 1)
    check("코드 검색 — 종목명을 준다", by_code["items"][0]["issuer_nm"], "삼성전자")

    ranked = service.select_instrument_list({"q": "삼성"})
    check("낱말 검색 — 둘 다 찾는다", ranked["total_count"], 2)
    check("낱말 검색 — 앞자리가 먼저다", ranked["items"][0]["issuer_nm"], "삼성전자")

    lowered = service.select_instrument_list({"q": "apple"})
    check("대소문자 무시", [row["symbol"] for row in lowered["items"]], ["AAPL"])

    # ── ⑤ LIKE 특수문자는 글자다 ──────────────────────────────────────────
    underscore = service.select_instrument_list({"q": "_"})
    check("언더스코어는 와일드카드가 아니다", [row["symbol"] for row in underscore["items"]], ["999002"])
    percent = service.select_instrument_list({"q": "%"})
    check("퍼센트는 와일드카드가 아니다", [row["symbol"] for row in percent["items"]], ["999001"])

    # ── ⑥ 전체를 한 번에 내려보내지 않는다 ────────────────────────────────
    bulk = [("KR", "KOSPI", f"1{index:05d}", f"대량종목{index:04d}", "KRW") for index in range(300)]
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tn_instrument (country, market, symbol, issuer_nm, currency)"
                " VALUES (:country, :market, :symbol, :issuer_nm, :currency)"
            ),
            [dict(zip(("country", "market", "symbol", "issuer_nm", "currency"), row, strict=True)) for row in bulk],
        )

    paged = service.select_instrument_list({"q": "대량종목", "take": 20})
    check("상한만큼만 준다", len(paged["items"]), 20)
    check("전체 건수는 따로 답한다", paged["total_count"], 300)
    check("기본 take 도 전체를 안 준다", len(service.select_instrument_list({"q": "대량종목"})["items"]), 20)

    second = service.select_instrument_list({"q": "대량종목", "take": 20, "skip": 20})
    check("페이징이 다음 묶음을 준다", second["items"][0]["symbol"] != paged["items"][0]["symbol"], True)

    # ── ⑦ 상한을 넘는 take 는 조용히 잘리지 않는다 ────────────────────────
    try:
        service.select_instrument_list({"q": "대량종목", "take": 101})
        check("상한 초과 take 는 거절한다", "통과됨", "BadRequestError")
    except BadRequestError as exc:
        check("상한 초과 take 는 거절한다", "100" in str(exc), True)

    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과 (REQUIRE=db 실행됨)")

    if CHECKED < 18:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 이름·코드로 찾아지고, 빈 마스터가 「없음」으로 읽히지 않으며, 전체를 한 번에 안 준다 (#318)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
