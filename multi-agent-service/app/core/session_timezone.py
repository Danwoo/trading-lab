"""기동 시 DB 세션 타임존이 UTC 인지 본다 — 아니면 기동을 멈춘다 (#359).

## 왜 필요한가

감사·운영 시각 컬럼을 `timestamptz` 로 옮긴 뒤(alembic `0019`), 세션 타임존은 **저장값**이 아니라
**해석**을 정한다:

- psycopg 로 들어가는 naive `datetime` 파라미터와, Prisma 어댑터가 보내는 오프셋 없는 문자열은
  서버가 **세션 tz 로** 읽는다 — 세션이 UTC 가 아니면 그만큼 어긋난 인스턴트가 저장된다.
- `to_char` 로 만드는 응답 문자열의 벽시계도 세션 tz 를 따른다.

그래서 세션 tz 는 환경(사용자 `.env`·서버 `postgresql.conf`)이 아니라 **코드**가 정한다 —
`utils/common/database_utils.create_sql_engine_from_settings` 가 커넥션마다 `-c timezone=UTC` 를
startup 옵션으로 붙인다. 옵션이 코드에 있으므로 정상 배포에서는 이 검사가 항상 통과한다.

**그래서 이 검사가 빨개진다는 것은 「앱과 DB 사이의 무언가가 startup 옵션을 떼어냈다」는 뜻이다** —
예: `ignore_startup_parameters` 가 설정된 PgBouncer, 트랜잭션 풀링. 우회 스위치를 두면 그 사고를
조용히 통과시키게 되므로 **두지 않는다**(fail-closed, `ALLOW_SCHEMA_DRIFT` 같은 탈출구 없음).
알고도 띄우고 싶다면 코드에서 옵션을 빼는 편이 정직하다 — 그건 눈에 띄는 변경이다.

sqlite 드라이버는 건너뛴다 — 테스트 엔진이고 세션 타임존 개념이 없다.
"""

from __future__ import annotations

from core.logger import logger
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

EXPECTED_TIMEZONE = "UTC"


class SessionTimezoneError(RuntimeError):
    """DB 세션 타임존을 UTC 로 맞출 수 없다."""


def how_to_fix() -> str:
    return (
        "앱과 DB 사이에서 커넥션 startup 옵션(`-c timezone=UTC`)이 유지되는지 보세요 — "
        "PgBouncer 의 ignore_startup_parameters·트랜잭션 풀링이 대표적인 원인입니다. "
        "DB 서버의 기본 타임존은 바꾸지 않아도 됩니다(옵션이 세션 단위로 이깁니다)."
    )


def read_session_timezone(engine: Engine) -> str:
    """세션 타임존 한 값. 읽지 못하면 통과가 아니라 실패다(fail-closed)."""
    try:
        with engine.connect() as connection:
            value = connection.execute(text("SELECT current_setting('TimeZone')")).scalar()
    except SQLAlchemyError as exc:
        raise SessionTimezoneError(f"세션 타임존을 읽지 못했다 ({type(exc).__name__}) — DB 에 닿지 못한다") from exc
    if not value:
        raise SessionTimezoneError("세션 타임존이 비어 있다 — 값을 읽지 못했다")
    return str(value)


def ensure_session_timezone_utc(engine: Engine) -> None:
    """세션 타임존이 UTC 가 아니면 SessionTimezoneError. 우회 env 는 없다."""
    if "sqlite" in engine.dialect.name.lower():
        logger.info("DB 세션 타임존 검사 건너뜀 — sqlite 엔진 (테스트)")
        return
    actual = read_session_timezone(engine)
    if actual == EXPECTED_TIMEZONE:
        logger.info(f"DB 세션 타임존 확인 — {actual}")
        return
    raise SessionTimezoneError(
        f"DB 세션 타임존이 {EXPECTED_TIMEZONE} 이 아니다: {actual}. "
        "이 상태로 뜨면 감사 시각이 조용히 어긋난다 (#359). " + how_to_fix()
    )
