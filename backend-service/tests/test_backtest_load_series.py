#!/usr/bin/env python3
"""`load_series` 가 **`bar_service` 의 실제 계약**을 읽는지 확인한다 (#217).

## 왜 이 그물이 있나

엔진 단위 테스트는 `BarSeries` 를 **직접 만들어** 넣는다. 그래서 「조회 결과를 BarSeries 로
옮기는」 경계를 한 번도 안 태웠고, 그 자리가 틀린 채로 CI 를 전부 통과했다:

    KeyError: 'dt'      ← 실제 적재본으로 처음 돌린 순간 500

`bar_service._to_item` 의 계약은 `time` 이고 `dt` 가 아니다. 그리고 `instrument_id` 는
아예 안 온다 — 그 표현은 종목이 아니라 캔들만 담는다.

이 그물은 **`bar_service` 가 실제로 내는 모양**을 고정해 그 어긋남을 잡는다.

    cd backend-service && APP_ENV=development uv run python tests/test_backtest_load_series.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

# import 사슬이 core.config(settings)까지 닿는다 — 존재하지 않는 APP_ENV 로 .env 간섭을 끊고
# 필수 설정만 더미로 채운다. DB 접속은 하지 않는다 (기존 테스트와 같은 방식).
import os  # noqa: E402

os.environ["APP_ENV"] = "backtest-load-series-test"
for key, value in {
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
    os.environ.setdefault(key, value)

from services.backtest.backtest_service import BacktestService  # noqa: E402
from services.bar.bar_service import BarService  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


# `bar_service` 가 실제로 내는 항목 모양 — `_to_item` 에서 그대로 가져온다.
# 손으로 적으면 그 사본이 갈라져 이 그물이 「내가 적어 둔 계약」을 검사하게 된다.
def item_contract() -> set[str]:
    row = {"time": "2026-01-02", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 100, "trade_value": None}
    return set(BarService._to_item(row))


def fake_bar_service(items: list[dict], reason: str | None = None):
    return SimpleNamespace(
        select_daily_bar_list=lambda args: {
            "items": items,
            "total_count": len(items),
            "unavailable_reason": reason,
        }
    )


def sample_items(n: int = 5) -> list[dict]:
    import datetime as dt

    start = dt.date(2026, 1, 1)
    return [
        BarService._to_item(
            {
                "time": (start + dt.timedelta(days=i)).isoformat(),
                "open": 100 + i,
                "high": 102 + i,
                "low": 99 + i,
                "close": 101 + i,
                "volume": 1000 + i,
                "trade_value": None,
            }
        )
        for i in range(n)
    ]


def service_with(items, reason=None) -> BacktestService:
    return BacktestService(
        backtest_repository=SimpleNamespace(),
        bar_service=fake_bar_service(items, reason),
        strategy_loader=lambda key: None,
    )


def test_contract_has_time_not_dt() -> None:
    """계약 확인 — `time` 이 있고 `dt` 는 없다. 이 전제가 깨지면 아래가 다 무의미하다."""
    keys = item_contract()
    check("time 이 있다", "time" in keys, True)
    check("dt 는 없다", "dt" in keys, False)
    check("instrument_id 는 없다", "instrument_id" in keys, False)


def test_load_series_reads_the_contract() -> None:
    """조회 결과가 그대로 `BarSeries` 가 된다 — 키를 잘못 읽으면 여기서 터진다."""
    svc = service_with(sample_items(5))
    s = svc.load_series({"market": "KR", "symbol": "SAMPLE001", "period_from": "2026-01-01", "period_to": "2026-01-31"})
    check("봉 수", len(s), 5)
    check("날짜가 YYYY-MM-DD", s.dt[0], "2026-01-01")
    check("정렬돼 있다", s.dt == sorted(s.dt), True)
    check("종가", s.close[0], 101.0)


def test_empty_says_why() -> None:
    """빈 결과는 사유를 그대로 낸다 — 「없는 종목」과 「못 받은 종목」을 안 뭉갠다."""
    global CHECKED
    svc = service_with([], reason="KR 시장의 소스가 등록되어 있지 않습니다")
    CHECKED += 1
    try:
        svc.load_series({"market": "KR", "symbol": "X", "period_from": "2026-01-01", "period_to": "2026-01-31"})
    except Exception as exc:  # noqa: BLE001
        if "등록되어 있지 않습니다" not in str(exc):
            FAILURES.append(f"사유가 전달되지 않았다: {exc}")
        return
    FAILURES.append("빈 결과인데 던지지 않았다")


def test_timestamp_form_is_trimmed() -> None:
    """`time` 이 타임스탬프로 와도 날짜만 남는다 — `BarSeries` 는 날짜 오름차순을 요구한다."""
    items = [
        BarService._to_item(
            {
                "time": f"2026-01-0{i + 1}T09:00:00",
                "open": 1,
                "high": 2,
                "low": 0.5,
                "close": 1.5,
                "volume": 1,
                "trade_value": None,
            }
        )
        for i in range(3)
    ]
    svc = service_with(items)
    s = svc.load_series({"market": "KR", "symbol": "S", "period_from": "2026-01-01", "period_to": "2026-01-31"})
    check("날짜만 남는다", s.dt, ["2026-01-01", "2026-01-02", "2026-01-03"])


def main() -> int:
    for name, fn in [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            global CHECKED
            CHECKED += 1
            FAILURES.append(f"{name} 이 터졌다: {type(exc).__name__}: {exc}")
    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < 8:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
