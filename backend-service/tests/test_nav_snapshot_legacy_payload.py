"""nav 스냅샷 소비가 리네임 전 페이로드(company_id)도 유실 없이 받는지 검증.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_nav_snapshot_legacy_payload.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

왜 필요한가 — 배포는 큐를 비우고 시작하지 않는다. 발행 키가 company_id → workspace_id 로 바뀌는
순간, 이미 큐에 들어가 있던 메시지는 구 키로 실려 있다. 소비 측이 새 키만 읽으면 KeyError →
재시도 소진 → dead-letter 로 **조용히 유실**된다. JWT 는 검증측 폴백을 발급측보다 먼저 넣어 이
창을 막았는데, 같은 성격의 in-flight 데이터인 큐 페이로드에는 그 배려가 없었다.

검증 대상 불변식:
- 새 키(workspace_id) 페이로드는 그대로 그 테넌트로 적재된다.
- 구 키(company_id) 페이로드도 같은 테넌트로 적재된다 — 유실되지 않는다.
- 두 키가 함께 오면 새 키가 이긴다 (전환 중 혼입이 스코프를 가르지 않는다).
- 테넌트가 아예 없으면 조용히 넘어가지 않고 큰소리로 실패한다 (fail-loud).

외부 의존(repository)은 기록용 대역으로 두고 서비스 로직만 돌린다. DB 접속은 하지 않는다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# import 사슬이 core.config(settings)까지 닿는다 — 존재하지 않는 APP_ENV 로 .env 간섭을 끊고
# 필수 설정만 더미로 채운다 (tests/test_ingest_status_boundary.py 와 같은 방식).
os.environ["APP_ENV"] = "nav-legacy-payload-test"
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

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from services.nav.nav_service import NavService  # noqa: E402

_WORKSPACE_ID = 7
_MESSAGE_ID = 4321
_METRICS = {"nav": 1010.5, "benchmark": 999.25, "daily_return": 0.4, "drawdown": -1.5}


class _RecordingNavRepository:
    """insert_nav 로 넘어온 행을 그대로 모아 두는 대역 (DB 접속 없음)."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def insert_nav(self, row: dict) -> None:
        self.rows.append(row)


def _record(snapshot: dict) -> list[dict]:
    repository = _RecordingNavRepository()
    NavService(repository).record_snapshot(snapshot, _MESSAGE_ID)
    return repository.rows


def test_new_payload_is_recorded() -> None:
    rows = _record({"workspace_id": _WORKSPACE_ID, **_METRICS})
    assert len(rows) == 1, rows
    assert rows[0]["workspace_id"] == _WORKSPACE_ID
    assert rows[0]["source_message_id"] == _MESSAGE_ID
    assert rows[0]["nav"] == _METRICS["nav"]


def test_legacy_company_id_payload_is_not_lost() -> None:
    """리네임 배포 시점에 큐에 남아 있던 메시지 — 유실되면 그 구간의 NAV 시계열에 구멍이 난다."""
    rows = _record({"company_id": _WORKSPACE_ID, **_METRICS})
    assert len(rows) == 1, rows
    assert rows[0]["workspace_id"] == _WORKSPACE_ID


def test_new_key_wins_when_both_present() -> None:
    rows = _record({"workspace_id": _WORKSPACE_ID, "company_id": _WORKSPACE_ID + 1, **_METRICS})
    assert rows[0]["workspace_id"] == _WORKSPACE_ID


def test_missing_tenant_fails_loudly() -> None:
    """테넌트 없는 스냅샷을 조용히 적재하면 남의 테넌트에 섞인다 — 반드시 실패해야 한다."""
    try:
        _record({**_METRICS})
    except ValueError:
        return
    raise AssertionError("테넌트 없는 스냅샷이 예외 없이 통과했다")


def main() -> int:
    tests = [
        test_new_payload_is_recorded,
        test_legacy_company_id_payload_is_not_lost,
        test_new_key_wins_when_both_present,
        test_missing_tenant_fails_loudly,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001 — standalone 러너
            failed += 1
            print(f"FAIL {test.__name__}: {exc}")
        else:
            print(f"ok   {test.__name__}")
    print(f"검사한 케이스: {len(tests)}건 (통과 {len(tests) - failed} / 실패 {failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
