"""일봉의 **구간 표기**가 정직한가 (DB·네트워크 없음).

소스가 준 일봉이 어느 구간을 덮는지 우리는 모른다 — 소스마다, 같은 소스의 종목마다 다르다.
그래서 **모르면 모른다고 적는다**. 분봉으로 다시 접은 봉만 `regular` 다 (#255).

이 그물이 잠그는 것:

  ① 소스 일봉은 `session_scope='unknown'` 으로 저장된다 (「정규장」이라 부르면 거짓말이다)
  ② 정규장 창을 **캘린더가 준다** — 수능일 1시간 지연까지 (표로 굳히면 그날 종가를 놓친다)
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

from core.calendar import session_windows  # noqa: E402
from providers.models import NormalizedBar  # noqa: E402
from services.ingest.ingest_service import _daily_row  # noqa: E402

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

    # ② 정규장 창은 **캘린더가 준다** — 표로 굳히지 않는다
    windows = session_windows("KOSPI", dt.date(2026, 8, 17), dt.date(2026, 8, 19))
    check("휴장일(8/17)은 창이 없다", [w[0] for w in windows], [dt.date(2026, 8, 18), dt.date(2026, 8, 19)])
    for day, start, end in windows:
        check(f"{day} 시작 09:00", start, dt.time(9, 0))
        # 마감 동시호가 체결이 15:31 봉에 찍힌다 — 15:30 으로 끊으면 종가를 놓친다
        check(f"{day} 끝 15:31 (마감 동시호가 포함)", end, dt.time(15, 31))

    # **수능일은 전 일정이 1시간 늦다** — 고정 창으로 접으면 그날 종가가 장중 가격이 된다
    csat = session_windows("KOSPI", dt.date(2020, 12, 3), dt.date(2020, 12, 3))
    check("수능일도 창이 나온다", len(csat), 1)
    check("수능일 시작 10:00", csat[0][1], dt.time(10, 0))
    check("수능일 끝 16:31", csat[0][2], dt.time(16, 31))

    us = session_windows("NASDAQ", dt.date(2026, 8, 18), dt.date(2026, 8, 18))
    check("미국도 창이 나온다", len(us), 1)
    check("미국 시작 09:30", us[0][1], dt.time(9, 30))

    # ③·④ 배선 — 분봉 적재가 재구성을 부르고, 모르는 시장은 건너뛴다
    source = (_APP_DIR / "services" / "ingest" / "ingest_service.py").read_text(encoding="utf-8")
    check("분봉 적재가 재구성을 부른다", "rebuild_daily_from_minutes" in source, True)
    check("창을 못 구하면 건너뛴다", "windows = []" in source, True)
    check("창을 캘린더에서 받는다", "session_windows(market, date_from, date_to)" in source, True)

    repository = (_APP_DIR / "repositories" / "ingest" / "ingest_repository.py").read_text(encoding="utf-8")
    check("재구성이 regular 로 적는다", "'regular'" in repository, True)
    check("재구성이 날짜별 창으로 자른다", "win.open_at" in repository and "win.close_at" in repository, True)
    check("접은 행을 재적재가 못 덮는다", "IS DISTINCT FROM 'regular'" in repository, True)

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과 (창 {len(windows)}일 + 수능일·미국)")
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
