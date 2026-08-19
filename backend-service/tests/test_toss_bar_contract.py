"""토스 캔들의 **저장 계약** — 시각은 시장 벽시계 naive, 이상 행은 적재를 죽이지 않는다.

네트워크 없음. 이 그물이 잠그는 것:

  ① 시각이 tz 없는 naive 로 나온다 (`timestamp without time zone` 컬럼의 계약)
  ② offset 이 붙어 오든 안 붙어 오든 같은 벽시계로 수렴한다
  ③ 미국 시장은 미국 현지 벽시계다 (시장마다 다른 tz 를 쓴다)
  ④ 숫자가 아닌 값이 섞인 행은 `SkippedRow` 로 건너뛴다 — 종목 전체를 죽이지 않는다
  ⑤ 어댑터의 구간 경계가 매퍼 결과와 같은 성질이라 비교가 성립한다

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_toss_bar_contract.py
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

# 설정을 세우고 나서 import 한다 — providers 가 core.logger → core.config 를 물고 들어온다.
os.environ["APP_ENV"] = "toss-bar-contract-test"
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

from providers.toss.mapper import SkippedRow, to_bar, to_ts  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} 실제 {actual!r}")


def row(ts: str, **over) -> dict:
    base = {
        "timestamp": ts,
        "openPrice": "70000",
        "highPrice": "71000",
        "lowPrice": "69500",
        "closePrice": "70500",
        "volume": 12345,
    }
    base.update(over)
    return base


def main() -> int:
    # ① · ② 국내 — offset 이 붙어 와도, 안 붙어 와도 같은 KST 벽시계로 수렴한다
    with_offset = to_ts("2026-03-25T09:00:00+09:00", "KOSPI")
    check("offset 붙은 값이 naive 로 나온다", with_offset.tzinfo, None)
    check("벽시계가 보존된다", with_offset, dt.datetime(2026, 3, 25, 9, 0))

    naive_utc = to_ts("2026-03-25T00:00:00", "KOSPI")
    check("offset 없는 값은 UTC 로 읽어 KST 로 옮긴다", naive_utc, dt.datetime(2026, 3, 25, 9, 0))
    check("두 표기가 같은 값으로 수렴한다", with_offset, naive_utc)

    # ③ 미국 — 같은 UTC 순간이 뉴욕 벽시계로 간다 (3월 25일은 서머타임 → UTC-4)
    us = to_ts("2026-03-25T13:30:00+00:00", "NASDAQ")
    check("미국은 미국 현지 벽시계다", us, dt.datetime(2026, 3, 25, 9, 30))
    check("미국도 naive 다", us.tzinfo, None)

    # 정상 행이 그대로 통과한다
    bar = to_bar(row("2026-03-25T09:00:00+09:00"), "005930", "KOSPI")
    check("캔들 시각이 naive 다", bar.ts.tzinfo, None)
    check("캔들 시각이 벽시계다", bar.ts, dt.datetime(2026, 3, 25, 9, 0))
    check("종가가 그대로다", str(bar.close), "70500")
    check("무수정 원본 라벨이다", bar.adj_policy, "raw")

    # ④ 숫자가 아닌 값 — Decimal 은 ValueError 가 아니라 InvalidOperation 을 던진다
    bad_values = {
        "천단위 쉼표": "1,234",
        "빈 문자열": "",
        "None": None,
        "문자열 NaN": "해당없음",
    }
    for label, value in bad_values.items():
        try:
            to_bar(row("2026-03-25T09:00:00+09:00", closePrice=value), "005930", "KOSPI")
            check(f"이상 종가({label})를 건너뛴다", "예외 없음", "SkippedRow")
        except SkippedRow:
            check(f"이상 종가({label})를 건너뛴다", "SkippedRow", "SkippedRow")
        except Exception as exc:  # noqa: BLE001 — 무엇이 새는지 이름으로 남긴다
            check(f"이상 종가({label})를 건너뛴다", type(exc).__name__, "SkippedRow")

    try:
        to_bar(row("2026-03-25T09:00:00+09:00", volume=None), "005930", "KOSPI")
        check("이상 거래량을 건너뛴다", "예외 없음", "SkippedRow")
    except SkippedRow:
        check("이상 거래량을 건너뛴다", "SkippedRow", "SkippedRow")

    try:
        to_bar({"timestamp": "2026-03-25T09:00:00+09:00"}, "005930", "KOSPI")
        check("필드 결손을 건너뛴다", "예외 없음", "SkippedRow")
    except SkippedRow:
        check("필드 결손을 건너뛴다", "SkippedRow", "SkippedRow")

    # ⑤ 어댑터 구간 경계와 매퍼 결과가 같은 성질이라야 비교가 성립한다.
    #    적재 서비스도 분봉 경계를 naive 로 만들어 넘긴다 (ingest_service `dt.datetime.combine`).
    keep_from = dt.datetime.combine(dt.date(2026, 3, 25), dt.time.min)
    keep_to = dt.datetime.combine(dt.date(2026, 3, 25), dt.time.max)
    try:
        inside = keep_from <= bar.ts <= keep_to
        check("구간 비교가 성립한다", inside, True)
    except TypeError as exc:
        check("구간 비교가 성립한다", f"TypeError: {exc}", True)

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 15:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 시각은 시장 벽시계 naive 로 저장되고, 이상 행은 종목 전체를 죽이지 않는다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
