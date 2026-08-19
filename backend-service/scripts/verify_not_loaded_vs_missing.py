#!/usr/bin/env python3
"""「아직 적재를 안 했다」와 「진짜 없는 종목이다」가 다른 답을 내는지 확인한다 (#223).

## 왜 이 그물이 있나

두 상태가 같은 문구(`종목 마스터에 없는 종목입니다`)로 나왔다. 소스가 실제로 주는 종목
(`SAMPLE001`)과 아무 데도 없는 종목(`NOPE`)이 구분되지 않아, 사용자가 멀쩡한 종목 코드를
의심하고 다음에 무엇을 할지도 잃는다.

**이 구멍은 키 없이 도는 샘플 소스(#217)가 들어오면서 처음 드러났다.** 그전에는 키가 없으면
늘 「소스 없음」 사유가 나와 `_unavailable` 갈래를 탔다. 소스가 **가용한데 아직 안 돌린**
상태는 그때 처음 생겼다.

가르는 근거는 **그 시장의 마스터가 통째로 비었는가** 하나다 — 비었으면 둘 중 무엇인지 알 수
없고, 모르는 것을 아는 척 답하지 않는다.

## 무엇을 확인하나

    마스터가 빔 → 「아직 한 번도 받지 않았습니다」 + 다음 걸음
    마스터에 다른 종목이 있음 + 이 종목은 없음 → 「없는 종목입니다」

세 진입점(`_instrument`·일봉·분봉) 전부를 태운다 — 한 자리만 고치면 나머지가 옛 문구로 남는다.

    BACKTEST_TEST_DB_URL=postgresql+psycopg://u:p@host:port/db \
      uv run python scripts/verify_not_loaded_vs_missing.py

URL 이 없으면 건너뛴다(exit 0). 실제로 돌면 `REQUIRE=db 실행됨` 을 찍는다.
**사람의 개발 DB 를 쓰지 마라** — 전용 스키마를 만들고 지운다.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

FAILURES: list[str] = []
CHECKED = 0

MARKET = "KR"
ASKED = "SAMPLE001"
OTHER = "SAMPLE002"

NOT_LOADED = "아직 한 번도 받지 않았습니다"
MISSING = "종목 마스터에 없는 종목입니다"


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def message_of(fn) -> str:
    """호출이 내는 예외 메시지. 예외가 안 나면 그 사실을 문자열로 돌려 단언이 잡게 한다."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 — 어떤 예외든 문구를 보는 것이 이 검사의 목적이다
        return str(exc)
    return "<예외가 나지 않았다>"


def main() -> int:
    url = os.environ.get("BACKTEST_TEST_DB_URL")
    if not url:
        print("건너뜀: BACKTEST_TEST_DB_URL 없음 (DB 필요 검사)")
        return 0

    # `core.config` 의 `env_file` 은 **cwd 상대**라 `app` 에서 읽어야 한다 (`.env.development`).
    # CI 는 `backend-service` 에서 돌리므로 import 전에 옮긴다 — 안 옮기면 설정 검증이 죽는다.
    os.chdir(BACKEND / "app")

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from repositories.bar.bar_repository import BarRepository
    from services.bar.bar_service import BarService
    from sqlalchemy import create_engine, text

    schema = "not_loaded_vs_missing"
    admin = create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        conn.execute(text(f"CREATE SCHEMA {schema}"))

    engine = create_engine(url, hide_parameters=True, connect_args={"options": f"-csearch_path={schema}"})

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

    # 소스가 가용하다고 답하게 세운다 — 이 검사의 대상은 「소스는 있는데 안 받았다」이다.
    capability = SimpleNamespace(
        list_capabilities=lambda workspace_id, market=None: [
            {"source": "sample", "market": MARKET, "data_kind": "instrument_master", "available": True, "reason": None}
        ]
    )
    service = BarService(bar_repository=BarRepository(sql_client=engine), capability_service=capability)

    daily = {
        "market": MARKET,
        "symbol": ASKED,
        "date_from": dt.date(2026, 1, 1).isoformat(),
        "date_to": dt.date(2026, 3, 31).isoformat(),
    }
    minute = {
        "market": MARKET,
        "symbol": ASKED,
        "ts_from": "2026-01-01T00:00:00",
        "ts_to": "2026-01-02T00:00:00",
        "interval_min": 1,
    }

    # ── 마스터가 통째로 빈 상태 — 「없는 종목」이라 단정하면 안 된다 ─────────
    check(
        "일봉 — 아직 안 받았다고 답한다",
        NOT_LOADED in message_of(lambda: service.select_daily_bar_list(dict(daily))),
        True,
    )
    check(
        "일봉 — 없는 종목이라 단정하지 않는다",
        MISSING in message_of(lambda: service.select_daily_bar_list(dict(daily))),
        False,
    )
    check(
        "분봉 — 아직 안 받았다고 답한다",
        NOT_LOADED in message_of(lambda: service.select_minute_bar_list(dict(minute))),
        True,
    )
    check(
        "마스터 해석 — 아직 안 받았다고 답한다",
        NOT_LOADED in message_of(lambda: service._instrument(MARKET, ASKED)),
        True,
    )
    check("다음 걸음이 문구에 있다", "적재" in message_of(lambda: service._instrument(MARKET, ASKED)), True)

    # ── 마스터를 한 번 받은 뒤 — 진짜 없는 종목은 없다고 답해야 한다 ────────
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tn_instrument (market, symbol, issuer_nm, country, currency) "
                "VALUES (:m, :s, '샘플', 'KR', 'KRW')"
            ),
            {"m": MARKET, "s": OTHER},
        )

    check("받은 뒤 — 없는 종목이라 답한다", MISSING in message_of(lambda: service._instrument(MARKET, ASKED)), True)
    check(
        "받은 뒤 — 안 받았다고 하지 않는다", NOT_LOADED in message_of(lambda: service._instrument(MARKET, ASKED)), False
    )
    check("받은 뒤 — 일봉도 같다", MISSING in message_of(lambda: service.select_daily_bar_list(dict(daily))), True)
    check("받은 뒤 — 분봉도 같다", MISSING in message_of(lambda: service.select_minute_bar_list(dict(minute))), True)

    # 다른 시장은 여전히 빈 상태다 — 판정이 시장별인지 확인한다.
    check(
        "시장별로 가른다",
        NOT_LOADED in message_of(lambda: service._instrument("US", ASKED)),
        True,
    )

    with admin.begin() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과 (REQUIRE=db 실행됨)")

    if CHECKED < 10:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 「아직 안 받았다」와 「없는 종목이다」가 다른 답을 낸다 (#223)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
