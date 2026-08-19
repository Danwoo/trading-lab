"""일봉의 **구간 표기**가 정직한가 (DB·네트워크 없음).

소스가 준 일봉이 어느 구간을 덮는지 우리는 모른다 — 소스마다, 같은 소스의 종목마다 다르다.
그래서 **모르면 모른다고 적는다**. 분봉으로 다시 접은 봉만 `regular` 다 (#255).

이 그물이 잠그는 것:

  ① 소스 일봉은 `session_scope='unknown'` 으로 저장된다 (「정규장」이라 부르면 거짓말이다)
  ② 정규장 구간 표가 시장마다 있고, 국내는 마감 동시호가(15:31)를 포함한다
  ③ 분봉 적재가 끝나면 일봉 재구성을 **실제로 부른다** (배선)
  ④ 정규장 구간을 모르는 시장은 접지 않는다 — 틀린 창으로 접으면 소스 값보다 나쁘다

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_daily_session_scope.py
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

os.environ["APP_ENV"] = "daily-scope-test"
for _name, _value in {
    "BACKEND_SQL_DB_DRIVER": "postgresql+psycopg",
    "BACKEND_SQL_DB_HOST": "localhost",
    "BACKEND_SQL_DB_PORT": "5432",
    "BACKEND_SQL_DB_NAME": "test",
    "BACKEND_SQL_DB_USER": "test",
    "BACKEND_SQL_DB_PASSWORD": "test",
    "SFTP_HOST": "localhost",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "test",
    "SFTP_PASSWORD": "test",
    "JWT_SECRET": "test-secret",
}.items():
    os.environ.setdefault(_name, _value)

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from decimal import Decimal  # noqa: E402

from providers.models import NormalizedBar  # noqa: E402
from services.ingest.ingest_service import REGULAR_SESSION, _daily_row  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def main() -> int:
    # ① 소스가 준 일봉은 「모른다」로 저장된다
    bar = NormalizedBar(
        symbol="005930",
        market="KOSPI",
        ts=dt.datetime(2026, 8, 19),
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("1"),
        close=Decimal("2"),
        volume=10,
        adj_policy="raw",
    )
    row = _daily_row(bar, 7, {"source": "toss", "run_id": 1})
    check("소스 일봉은 unknown", row["session_scope"], "unknown")
    check("regular 이라 부르지 않는다", row["session_scope"] == "regular", False)

    # ② 정규장 구간 표
    check("국내 3시장 + 미국 3시장", len(REGULAR_SESSION), 6)
    for market in ("KOSPI", "KOSDAQ", "KONEX"):
        start, end = REGULAR_SESSION[market]
        check(f"{market} 시작 09:00", start, dt.time(9, 0))
        # 마감 동시호가 체결이 15:31 봉에 찍힌다 — 15:30 으로 끊으면 종가를 놓친다
        check(f"{market} 끝 15:31 (마감 동시호가 포함)", end, dt.time(15, 31))
    for market in ("NASDAQ", "NYSE", "AMEX"):
        start, end = REGULAR_SESSION[market]
        check(f"{market} 시작 09:30", start, dt.time(9, 30))
        check(f"{market} 끝 16:00", end, dt.time(16, 0))

    # ③·④ 배선 — 분봉 적재가 재구성을 부르고, 모르는 시장은 건너뛴다
    source = (_APP_DIR / "services" / "ingest" / "ingest_service.py").read_text(encoding="utf-8")
    check("분봉 적재가 재구성을 부른다", "rebuild_daily_from_minutes" in source, True)
    check("모르는 시장은 건너뛴다", "REGULAR_SESSION.get(market)" in source, True)

    repository = (_APP_DIR / "repositories" / "ingest" / "ingest_repository.py").read_text(encoding="utf-8")
    check("재구성이 regular 로 적는다", "'regular'" in repository, True)
    check("재구성이 구간으로 자른다", "session_open" in repository and "session_close" in repository, True)

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과 (시장 {len(REGULAR_SESSION)}종)")
    if CHECKED < 15:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 모르는 것은 모른다고 적고, 접은 것만 regular 다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
