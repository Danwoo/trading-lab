"""#163 — 적재 잡이 **요청 구간을 정직하게 다루는가**.

이 레포는 아직 pytest 를 도입하지 않았으므로 standalone 실행 겸용으로 작성한다:
    APP_ENV=ingest-period-test uv run python tests/test_ingest_period_handling.py

지키는 불변식 둘 — 둘 다 「요청 구간을 안 본다」는 같은 뿌리에서 나온 결함이었다:

- **일봉이 `period_from` 을 버리지 않는다.** 저장분보다 앞선 구간을 요청하면 소급 적재다.
  버리면 화면이 `find_gaps` 로 보여준 결측을 메울 유일한 레버가 **무음으로 죽고** 우회로도
  없다 — 게다가 응답도 `tn_ingest_run` 도 `succeeded` 라 실패한 줄도 모른다.
  단, MD-AD-22(마지막 저장일을 항상 다시 받는다)는 깨지지 않아야 한다.
- **분봉이 파티션 밖 구간을 psycopg 원문으로 죽지 않는다.** 사유는 사람이 읽을 문장이어야 하고,
  파티션 구간을 코드에 박지 않고 카탈로그에서 읽어야 한다(보존 회전으로 움직인다).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys
from pathlib import Path

# import 사슬이 core.config(settings)까지 닿는다 — 존재하지 않는 APP_ENV 로 `.env` 간섭을 끊고
# 필수 설정만 더미로 채운다 (형제 테스트와 같은 방식). **DB 접속은 하지 않는다** — 이 파일이
# 태우는 것은 판정 로직뿐이고, 레포지토리는 대역으로 갈아 끼운다.
os.environ["APP_ENV"] = "ingest-period-test"
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from core.exceptions import BadRequestError  # noqa: E402
from services.ingest.ingest_service import IngestService  # noqa: E402


class _Repo:
    """레포지토리 대역 — DB 없이 판정 로직만 태운다."""

    def __init__(self, last_saved=None, partition=None):
        self._last_saved = last_saved
        self._partition = partition

    def select_last_trade_date(self, instrument_id):  # noqa: ARG002
        return self._last_saved

    def select_minute_partition_range(self):
        return self._partition

    def select_instrument_id_map(self, market, symbols):  # noqa: ARG002
        return {symbol: 1 for symbol in symbols}


def _service(repo) -> IngestService:
    service = IngestService.__new__(IngestService)
    service.ingest_repository = repo
    return service


def _start(repo, run) -> dt.date:
    return asyncio.run(_service(repo)._daily_start_date(1, run))


# ── 일봉 ────────────────────────────────────────────────────────────────────


def test_backfill_request_is_honoured() -> str:
    """저장분보다 앞선 `period_from` 은 소급 적재 요청이다 — 버리지 않는다."""
    repo = _Repo(last_saved=dt.date(2026, 8, 1))
    start = _start(repo, {"period_from": "2026-01-01"})
    assert start == dt.date(2026, 1, 1), f"소급 요청이 버려졌다: {start}"
    return "test_backfill_request_is_honoured"


def test_last_saved_day_is_still_refetched() -> str:
    """MD-AD-22 — 마지막 저장일은 여전히 구간 안이다 (장중 반쪽 캔들을 덮어쓰려고)."""
    last = dt.date(2026, 8, 1)
    # 소급 요청이 있어도 시작이 더 앞이라 그 하루는 포함된다.
    assert _start(_Repo(last_saved=last), {"period_from": "2026-01-01"}) <= last
    # 요청이 없으면 그 하루부터 다시 받는다.
    assert _start(_Repo(last_saved=last), {}) == last
    return "test_last_saved_day_is_still_refetched (2건)"


def test_forward_request_does_not_skip_saved_day() -> str:
    """저장분보다 **뒤**를 요청해도 마지막 저장일부터 받는다 — 사이를 건너뛰면 구멍이 난다."""
    repo = _Repo(last_saved=dt.date(2026, 8, 1))
    assert _start(repo, {"period_from": "2026-08-10"}) == dt.date(2026, 8, 1)
    return "test_forward_request_does_not_skip_saved_day"


def test_empty_history_uses_request_or_one_year() -> str:
    """저장분이 없으면 요청 구간을, 그것도 없으면 1년치를 받는다."""
    assert _start(_Repo(), {"period_from": "2020-03-01"}) == dt.date(2020, 3, 1)
    fallback = _start(_Repo(), {})
    assert (dt.date.today() - fallback).days == 365, f"기본 구간이 1년이 아니다: {fallback}"
    return "test_empty_history_uses_request_or_one_year (2건)"


# ── 분봉 파티션 ──────────────────────────────────────────────────────────────


def _guard(repo, date_from, date_to):
    return asyncio.run(_service(repo)._require_minute_partition(date_from, date_to))


def test_partition_outside_range_is_refused_in_korean() -> str:
    """파티션 밖은 psycopg 원문이 아니라 사람이 읽을 문장으로 거절한다."""
    repo = _Repo(partition=(dt.date(2026, 8, 1), dt.date(2027, 8, 1)))
    for date_from, date_to in [
        (dt.date(2026, 1, 1), dt.date(2026, 1, 31)),  # 아래로 벗어남
        (dt.date(2027, 7, 1), dt.date(2027, 9, 1)),  # 위로 벗어남
    ]:
        try:
            _guard(repo, date_from, date_to)
        except BadRequestError as exc:
            assert "파티션" in str(exc), f"사유가 파티션을 말하지 않는다: {exc}"
            assert "no partition of relation" not in str(exc), "psycopg 원문이 샜다"
        else:  # pragma: no cover - 실패 경로
            raise AssertionError(f"{date_from}~{date_to} 가 통과했다")
    return "test_partition_outside_range_is_refused_in_korean (2건)"


def test_partition_inside_range_passes() -> str:
    """덮는 구간은 통과한다 — 상계는 배타적이라 마지막 날 직전까지다."""
    repo = _Repo(partition=(dt.date(2026, 8, 1), dt.date(2027, 8, 1)))
    _guard(repo, dt.date(2026, 8, 1), dt.date(2027, 7, 31))
    return "test_partition_inside_range_passes"


def test_no_partition_at_all_is_refused() -> str:
    """파티션이 하나도 없으면 무엇을 하면 되는지까지 말한다."""
    try:
        _guard(_Repo(partition=None), dt.date(2026, 8, 1), dt.date(2026, 8, 2))
    except BadRequestError as exc:
        assert "마이그레이션" in str(exc), f"할 일을 안 알려준다: {exc}"
    else:  # pragma: no cover - 실패 경로
        raise AssertionError("파티션이 없는데 통과했다")
    return "test_no_partition_at_all_is_refused"


def test_guard_is_actually_wired_into_the_run() -> str:
    """가드를 **직접 부르는 것만** 검사하면 배선이 빠져도 초록이다 — 실제로 그랬다.

    그래서 `_run_minute_bar` 를 태운다. provider 는 「불리면 실패」 대역이라, 가드가 안 걸려
    통과하면 그 사실이 드러난다.
    """

    class _NeverCalled:
        async def fetch_minute(self, *args, **kwargs):  # noqa: ARG002
            raise AssertionError("가드가 안 걸려 provider 까지 갔다 — 배선이 빠졌다")

    repo = _Repo(partition=(dt.date(2026, 8, 1), dt.date(2027, 8, 1)))
    run = {
        "job_kind": "minute_bar",
        "scope": "KRX:005930",
        "period_from": "2020-01-01",  # 파티션 아래로 한참 벗어남
        "period_to": "2020-01-31",
    }
    try:
        asyncio.run(_service(repo)._run_minute_bar(run, _NeverCalled()))
    except BadRequestError as exc:
        assert "파티션" in str(exc), f"사유가 파티션을 말하지 않는다: {exc}"
    else:  # pragma: no cover - 실패 경로
        raise AssertionError("파티션 밖 구간이 통과했다")
    return "test_guard_is_actually_wired_into_the_run"


TESTS = [
    test_backfill_request_is_honoured,
    test_last_saved_day_is_still_refetched,
    test_forward_request_does_not_skip_saved_day,
    test_empty_history_uses_request_or_one_year,
    test_partition_outside_range_is_refused_in_korean,
    test_partition_inside_range_passes,
    test_no_partition_at_all_is_refused,
    test_guard_is_actually_wired_into_the_run,
]


def _unregistered() -> list[str]:
    registered = {test.__name__ for test in TESTS}
    return sorted(
        name
        for name, value in globals().items()
        if name.startswith("test_") and callable(value) and name not in registered
    )


if __name__ == "__main__":
    missing = _unregistered()
    if missing:
        print(f"  FAIL TESTS 목록에 없는 테스트: {', '.join(missing)}")
        raise SystemExit(1)
    # 검사 0건은 통과가 아니다 — TESTS 가 비면 조용히 exit 0 이 된다.
    if len(TESTS) < 8:
        print(f"  FAIL 검사가 {len(TESTS)}건뿐이다 — 그물이 죽어 있다 (하한 8)")
        raise SystemExit(1)
    failures = 0
    for test in TESTS:
        try:
            print(f"  PASS {test()}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {test.__name__}: {exc}")
    print(f"\n검사한 케이스 {len(TESTS)}건 중 {len(TESTS) - failures}건 통과, {failures}건 실패")
    raise SystemExit(1 if failures else 0)
