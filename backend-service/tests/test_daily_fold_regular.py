"""일봉을 **조회 시점에 정규장으로 접는다** (DB·네트워크 없음) — #255 리드 결정 A′.

소스 일봉이 08:01–20:00 을 덮는 종목이 있어(표본 25종목 중 9종목) 그 종가로 체결하면 **정규장에서
낼 수 없는 가격**이 된다. 저장은 안 건드리고 물어볼 때 접는다.

이 그물이 잠그는 것은 다섯이다 — **안 접는 세 경우가 핵심**이다. 접는 것보다 「접으면 안 되는 날을
안 접는 것」이 어렵고, 틀리면 조용히 틀린 값을 준다:

  ① 정규장 창만 접는다 (창 밖 분봉은 버린다, 경계는 양쪽 포함)
  ② 세션이 안 끝난 날은 안 접는다 — 반쪽 캔들이 나온다
  ③ 세션 경계를 못 믿는 날은 안 접는다 — 수능일, 캘린더가 2021년 이후를 모른다
  ④ 분봉이 없는 날은 소스 값 그대로다
  ⑤ 접힌 날과 안 접힌 날이 섞이면 `mixed` 로 답한다

standalone 실행 겸용:
    cd backend-service && APP_ENV=development uv run python tests/test_daily_fold_regular.py
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

os.environ["APP_ENV"] = "daily-fold-test"
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

from core.calendar import session_bounds, unreliable_bounds  # noqa: E402
from services.bar.bar_service import BarService, fold_regular_session  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def minute(day: str, hhmm: str, *, o: float, h: float, low: float, c: float, v: int = 10) -> dict:
    return {"time": f"{day}T{hhmm}", "open": o, "high": h, "low": low, "close": c, "volume": v, "trade_value": 100.0}


class FakeRepository:
    """`select_minute_bar_list` 만 흉내낸다 — 접기가 부르는 유일한 조회다."""

    def __init__(self, minutes: list[dict]) -> None:
        self.minutes = minutes
        self.calls: list[dict] = []

    def select_minute_bar_list(self, args: dict) -> tuple[list[dict], int]:
        self.calls.append(args)
        return self.minutes, len(self.minutes)


def service(minutes: list[dict]) -> tuple[BarService, FakeRepository]:
    repo = FakeRepository(minutes)
    return BarService(bar_repository=repo, capability_service=None), repo


def daily(day: str, close: float, scope: str = "unknown") -> dict:
    return {
        "time": day,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 999,
        "trade_value": None,
        "source": "toss",
        "adj_policy": "raw",
        "ingested_at": None,
        "session_scope": scope,
    }


def main() -> int:
    #: 지난 거래일 — 세션이 확실히 끝난 날이라 「도는 세션」 축과 섞이지 않는다.
    past = "2026-08-19"
    bounds = session_bounds("KOSPI", dt.date.fromisoformat(past))
    check("지난 거래일의 경계를 안다", bounds is not None, True)

    # ① 정규장 창만 접는다 — 08:30·16:00 은 버리고 09:00~15:30 만
    minutes = [
        minute(past, "08:30", o=50, h=50, low=50, c=50),
        minute(past, "09:00", o=100, h=101, low=99, c=100),
        minute(past, "12:00", o=100, h=120, low=80, c=110),
        minute(past, "15:30", o=110, h=111, low=109, c=111),
        minute(past, "16:00", o=999, h=999, low=999, c=999),
    ]
    bar = fold_regular_session(minutes, bounds)
    check("시가 = 09:00 의 시가", bar["open"], 100)
    check("종가 = 15:30 의 종가", bar["close"], 111)
    check("고가는 창 안 최대", bar["high"], 120)
    check("저가는 창 안 최소", bar["low"], 80)
    check("거래량은 창 안 합", bar["volume"], 30)
    check("창 밖 999 가 안 샌다", 999 in (bar["high"], bar["low"], bar["close"]), False)

    # 거래대금은 하나라도 모르면 지어내지 않는다
    partial = [dict(minutes[1]), dict(minutes[2])]
    partial[0]["trade_value"] = None
    check("거래대금 일부 결측 → None", fold_regular_session(partial, bounds)["trade_value"], None)

    # ② 세션이 안 끝난 날은 안 접는다 — 오늘을 넣어 확인한다
    today = dt.date.today().isoformat()
    svc, repo = service([minute(today, "09:00", o=1, h=1, low=1, c=1)])
    out = svc._fold_to_regular("KOSPI", 7, [daily(today, 500.0)])
    check("도는 세션은 안 접힌다", out[0]["close"], 500.0)
    check("도는 세션은 unknown 그대로", out[0]["session_scope"], "unknown")

    # ③ 세션 경계를 못 믿는 날(수능)은 안 접는다
    csat = sorted(unreliable_bounds("KOSPI"))[-1].isoformat()
    check("수능일은 경계를 안 준다", session_bounds("KOSPI", dt.date.fromisoformat(csat)), None)
    svc, repo = service([minute(csat, "10:00", o=1, h=1, low=1, c=1)])
    out = svc._fold_to_regular("KOSPI", 7, [daily(csat, 700.0)])
    check("수능일은 안 접힌다", out[0]["close"], 700.0)
    check("수능일에는 분봉을 읽지도 않는다", repo.calls, [])

    # ④ 분봉이 없는 날은 소스 값 그대로
    svc, repo = service([])
    out = svc._fold_to_regular("KOSPI", 7, [daily(past, 300.0)])
    check("분봉 0건이면 소스 값", out[0]["close"], 300.0)
    check("분봉 0건이면 unknown 그대로", out[0]["session_scope"], "unknown")

    # ⑤ 접힌 날과 안 접힌 날이 섞이면 mixed
    older = "2026-08-18"
    svc, repo = service(
        [minute(past, "09:00", o=10, h=10, low=10, c=10), minute(past, "15:30", o=20, h=20, low=20, c=20)]
    )
    out = svc._fold_to_regular("KOSPI", 7, [daily(older, 111.0), daily(past, 222.0)])
    check("분봉 있는 날은 접힌다", out[1]["close"], 20)
    check("접힌 날은 regular", out[1]["session_scope"], "regular")
    check("분봉 없는 날은 그대로", out[0]["close"], 111.0)
    check("섞이면 mixed", BarService._session_scope(out), "mixed")

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 18:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 정규장 창만 접고, 도는 세션·못 믿는 날·분봉 없는 날은 소스 값 그대로다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
