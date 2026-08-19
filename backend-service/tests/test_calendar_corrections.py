"""거래일 캘린더 보정이 **실제 조회 경로에서** 먹는가 (DB·네트워크 없음).

`exchange_calendars` 4.13.2 는 2026-06-03(지방선거)·2026-07-17(제헌절 재지정)을 거래일로 본다.
그 차이는 조용하지 않다 — 갭 검출이 영원히 못 채우는 결측을 매번 보고하고, 백테스트가 장이 안
선 날에 신호를 판정한다.

이 그물이 잠그는 것:

  ① 보정한 날이 `is_session` 에서 거래일이 아니다
  ② `sessions_between` 결과에도 안 들어온다 (갭 검출이 쓰는 경로)
  ③ 보정하지 않은 날은 그대로다 — 한 해를 통째로 지우지 않는다
  ④ 보정은 그 캘린더에만 적용된다 — 미국 시장이 함께 지워지지 않는다
  ⑤ 보정 목록이 비면 실패한다 (fail-closed — 검사 대상 0건은 통과가 아니다)

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_calendar_corrections.py
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

os.environ["APP_ENV"] = "calendar-corrections-test"
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

from core.calendar import EXTRA_CLOSURES, is_session, sessions_between  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def main() -> int:
    korea = sorted(EXTRA_CLOSURES.get("XKRX", frozenset()))
    if not korea:
        print("::error::국내 보정 목록이 비었다 — 검사 대상 0건이라 실패", file=sys.stderr)
        return 1

    # ①·② 보정한 날은 두 경로 모두에서 거래일이 아니다
    for day in korea:
        check(f"{day}: is_session=False", is_session("KOSPI", day), False)
        for market in ("KOSPI", "KOSDAQ", "KONEX"):
            window = sessions_between(market, day - dt.timedelta(days=3), day + dt.timedelta(days=3))
            check(f"{day}: {market} 구간 목록에 없다", day in window, False)

    # ③ 보정하지 않은 평일은 그대로 (한 해를 통째로 지우지 않는다)
    for day, expected in ((dt.date(2026, 6, 2), True), (dt.date(2026, 6, 4), True), (dt.date(2026, 7, 16), True)):
        check(f"{day}: 그대로 거래일", is_session("KOSPI", day), expected)

    year = sessions_between("KOSPI", dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    check("2026년 거래일이 충분히 남는다", len(year) > 200, True)
    check("2026년 거래일에 보정일이 없다", any(day in year for day in korea), False)

    # ④ 다른 캘린더(미국)는 안 건드린다 — 같은 날이 미국에선 거래일이다
    for day in korea:
        if day.weekday() < 5:
            check(f"{day}: 미국은 그대로", is_session("NASDAQ", day), True)

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과 (보정 {len(korea)}일)")
    if CHECKED < 15:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 보정한 날이 거래일에서 빠지고, 다른 날·다른 시장은 그대로다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
