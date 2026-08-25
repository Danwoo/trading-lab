"""세션 타임존 기동 가드가 실제 커넥션 위에서 판정하는지 본다 — fail-closed (#359).

`core/session_timezone.ensure_session_timezone_utc` 는 앱이 뜨기 전 `SHOW timezone` 을 읽어
UTC 가 아니면 기동을 멈춘다. 이 검사는 그 판정을 **진짜 Postgres 커넥션 두 개**에 태운다:

  - `-c timezone=Asia/Seoul` 로 붙인 엔진 → `SessionTimezoneError` 가 나야 한다.
  - `-c timezone=UTC` 로 붙인 엔진 → 통과해야 한다.

단위 테스트로는 이 자리를 못 지킨다 — 대역을 끼우면 "옵션이 실제로 서버까지 가는가"가 빠지고,
그게 이 가드가 지키려는 바로 그것이다(PgBouncer 가 startup 옵션을 떼는 사고).

**검사 2건 미만이면 실패한다.** 판정이 하나도 안 돌았는데 초록으로 끝나는 자리를 막는다.

    SESSION_TIMEZONE_TEST_DB_URL=postgresql+psycopg://ci:ci@localhost:5432/ci \\
      uv run python scripts/verify_session_timezone_guard.py     (cwd=backend-service)

DB URL 이 없으면 사유를 적고 건너뛴다 — `test: backend` 스위트(DB 없음)와 `test: backend-db`
잡(DB 있음)에 둘 다 걸리는 옆 스크립트들의 관례다. 실제로 돌았는지는 CI 가 아래 `REQUIRE=db
실행됨` 표식을 grep 해 확인한다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "app"))

# `core.session_timezone` → `core.logger` → `core.config.settings` 라 필수 env 가 있어야 import
# 된다. 이 검사의 대상은 판정 함수 자체이지 설정이 아니므로 더미로 채운다 —
# `verify_lifespan_manager_rollback.py` 와 같은 관례. 실제 접속은 아래 TEST_DB_URL 로만 한다.
_DUMMY_ENV = {
    "APP_ENV": "production",
    "BACKEND_SQL_DB_DRIVER": "x",
    "BACKEND_SQL_DB_ODBC_DRIVER": "x",
    "BACKEND_SQL_DB_HOST": "x",
    "BACKEND_SQL_DB_PORT": "1433",
    "BACKEND_SQL_DB_NAME": "x",
    "BACKEND_SQL_DB_USER": "x",
    "BACKEND_SQL_DB_PASSWORD": "x",
    "SFTP_HOST": "x",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "x",
    "SFTP_PASSWORD": "x",
    "JWT_SECRET": "x",
}
for _key, _value in _DUMMY_ENV.items():
    os.environ.setdefault(_key, _value)

CHECKS_EXPECTED = 2


def _engine(url: str, timezone: str):
    import sqlalchemy as sa

    return sa.create_engine(url, connect_args={"options": f"-c timezone={timezone}"}, poolclass=sa.pool.NullPool)


def main() -> int:
    url = os.environ.get("SESSION_TIMEZONE_TEST_DB_URL") or os.environ.get("BACKEND_TEST_DB_URL")
    if not url:
        print(
            "SESSION_TIMEZONE_TEST_DB_URL 이 없어 건너뜁니다 — "
            "이 검사는 실제 Postgres 커넥션이 있어야 의미가 있습니다 (test: backend-db 잡이 돌립니다).",
        )
        return 0

    from core.session_timezone import SessionTimezoneError, ensure_session_timezone_utc

    print("세션 타임존 기동 가드 검증")
    checked = 0
    failures: list[str] = []

    seoul = _engine(url, "Asia/Seoul")
    try:
        ensure_session_timezone_utc(seoul)
    except SessionTimezoneError as exc:
        checked += 1
        if "Asia/Seoul" not in str(exc):
            failures.append(f"세션이 Asia/Seoul 인데 사유에 실제 값이 안 적혔다: {exc}")
        else:
            print("  ✓ 세션 Asia/Seoul → SessionTimezoneError (실제 값이 사유에 적힘)")
    except Exception as exc:  # noqa: BLE001 — 어떤 예외든 계약 위반으로 보고한다
        checked += 1
        failures.append(f"세션이 Asia/Seoul 인데 SessionTimezoneError 가 아닌 예외: {type(exc).__name__}: {exc}")
    else:
        checked += 1
        failures.append("세션이 Asia/Seoul 인데 가드가 통과시켰다 — 기동이 안 막힌다")
    finally:
        seoul.dispose()

    utc = _engine(url, "UTC")
    try:
        ensure_session_timezone_utc(utc)
    except Exception as exc:  # noqa: BLE001
        checked += 1
        failures.append(f"세션이 UTC 인데 가드가 막았다: {type(exc).__name__}: {exc}")
    else:
        checked += 1
        print("  ✓ 세션 UTC → 통과")
    finally:
        utc.dispose()

    print(f"검사한 판정 {checked}건 (기대 {CHECKS_EXPECTED}건)")
    if checked < CHECKS_EXPECTED:
        print(f"::error::판정이 {checked}건뿐이다 — 검사가 대상을 다 못 봤다(fail-closed)", file=sys.stderr)
        return 1
    for line in failures:
        print(f"  ✗ {line}")
    if failures:
        print("::error::세션 타임존 가드가 계약대로 판정하지 않는다", file=sys.stderr)
        return 1

    print("판정: 세션 tz 가 UTC 가 아니면 기동이 막힌다 (REQUIRE=db 실행됨)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
