"""일봉의 **구간 표기**가 정직한가 (DB·네트워크 없음).

소스가 준 일봉이 어느 구간을 덮는지 우리는 모른다 — 소스마다, 같은 소스의 종목마다 다르다
(실측: 보통주 표본 25종목 중 9종목이 시간외를 포함하고, 그 종가는 정규장 종가와 최대 4%
어긋났다). 그래서 **모르면 모른다고 적는다** (#255).

분봉으로 접어 `regular` 로 만드는 것은 **아직 안 한다** — 접는 방식(쓰기 시점 vs 조회 시점)이
적재 설계를 바꾸는 결정이라 리드 판단을 기다린다. 지금 이 그물이 잠그는 것은 「모른다고 정직히
적는가」와 「조회가 그 사실을 전하는가」다.

이 그물이 잠그는 것:

  ① 소스 일봉은 `session_scope='unknown'` 으로 저장된다 (「정규장」이라 부르면 거짓말이다)
  ② 정규장 창을 **캘린더가 준다** — 수능일 1시간 지연까지 (표로 굳히면 그날 종가를 놓친다)
  ③ 조회가 「어느 구간인지」를 싣고, 섞이면 `mixed` 로 답한다

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

    # **수능일 구멍은 아직 안 닫혔다 — 그물이 그것을 감추지 않게 여기에 적어 둔다.**
    # KRX 는 수능일에 전 일정을 1시간 늦추는데, `exchange_calendars` 의 `precomputed_csat_days`
    # 는 2020-12-03 에서 끊겨 있다. 즉 **2021년 이후 수능일은 라이브러리도 모른다.**
    # 아래 두 단언은 「라이브러리가 아는 해는 맞다」와 「모르는 해는 아직 틀리다」를 **둘 다**
    # 못 박는다 — 뒤엣것이 초록이면 그것은 통과가 아니라 **남은 구멍의 기록**이다.
    known = session_windows("KOSPI", dt.date(2020, 12, 3), dt.date(2020, 12, 3))
    check("라이브러리가 아는 수능일은 10:00 개장", known[0][1], dt.time(10, 0))
    later = session_windows("KOSPI", dt.date(2024, 11, 14), dt.date(2024, 11, 14))
    check("2021년 이후 수능일은 아직 09:00 으로 나온다 (남은 구멍)", later[0][1] if later else None, dt.time(9, 0))

    us = session_windows("NASDAQ", dt.date(2026, 8, 18), dt.date(2026, 8, 18))
    check("미국도 창이 나온다", len(us), 1)
    check("미국 시작 09:30", us[0][1], dt.time(9, 30))

    # ③ 소스가 준 일봉을 「정규장」이라 부르지 않는다 — 지금은 그것이 우리가 아는 전부다
    source = (_APP_DIR / "services" / "ingest" / "ingest_service.py").read_text(encoding="utf-8")
    check("적재가 unknown 으로만 쓴다", '"session_scope": "unknown"' in source, True)
    check("쓰기 시점 접기를 하지 않는다", "rebuild_daily_from_minutes" in source, False)

    bar_service = (_APP_DIR / "services" / "bar" / "bar_service.py").read_text(encoding="utf-8")
    check("조회가 구간 표기를 싣는다", "_session_scope" in bar_service, True)
    check("섞이면 mixed 로 답한다", '"mixed"' in bar_service, True)

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과 (창 {len(windows)}일 + 수능일·미국)")
    if CHECKED < 15:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 소스 일봉을 「정규장」이라 부르지 않고, 조회가 어느 구간인지 말한다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
