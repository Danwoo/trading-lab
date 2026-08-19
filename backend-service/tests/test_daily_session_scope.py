"""일봉의 **구간 표기**가 정직한가 (DB·네트워크 없음).

소스가 준 일봉이 어느 구간을 덮는지 우리는 모른다 — 소스마다, 같은 소스의 종목마다 다르다
(실측: 보통주 표본 25종목 중 9종목이 시간외를 포함하고, 그 종가는 정규장 종가와 최대 4%
어긋났다). 그래서 **모르면 모른다고 적는다** (#255).

분봉으로 접어 `regular` 로 만드는 것은 **아직 안 한다** — 접는 방식(쓰기 시점 vs 조회 시점)이
적재 설계를 바꾸는 결정이라 리드 판단을 기다린다. 이 그물이 잠그는 것은 둘이다:

  ① 소스가 준 일봉을 「정규장」이라 부르지 않는다 (`unknown`)
  ② 조회가 그 사실을 전하고, 구간 안에서 **섞이면 `mixed`** 라고 답한다

**함수를 실제로 부른다** — 소스 문자열을 grep 하면 로직이 바뀌어도 초록이 난다.

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_daily_session_scope.py
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from decimal import Decimal
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

from providers.models import NormalizedBar  # noqa: E402
from services.bar.bar_service import BarService  # noqa: E402
from services.ingest.ingest_service import _daily_row  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def bar_row(scope: str | None) -> dict:
    return {"source": "toss", "adj_policy": "raw", "ingested_at": None, "session_scope": scope}


def main() -> int:
    # ① 소스가 준 일봉은 「모른다」로 저장된다 — **함수를 실제로 부른다**
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
    check("행에 그 축이 실린다", "session_scope" in row, True)

    # ② 조회가 구간을 전한다 — 섞이면 mixed (한쪽으로 뭉개면 절반만 참인 말이 화면에 나간다)
    for rows, expected, label in (
        ([bar_row("unknown"), bar_row("unknown")], "unknown", "전부 모름"),
        ([bar_row("regular"), bar_row("regular")], "regular", "전부 정규장"),
        ([bar_row("regular"), bar_row("unknown")], "mixed", "섞임"),
        ([bar_row(None), bar_row("unknown")], "unknown", "빈 값은 모름으로"),
        ([], None, "행이 없으면 답도 없음"),
    ):
        check(f"구간 요약({label})", BarService._session_scope(rows), expected)

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 8:
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
