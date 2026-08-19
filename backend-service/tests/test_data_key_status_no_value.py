"""#225 — **키 상태 조회가 값을 흘리지 않는다** (DB·네트워크 없음).

「어디에 무엇을 넣어야 하나」를 화면이 답하려면 상태를 내보내야 한다. 그 응답이 값을
조금이라도 실으면 화면·로그·브라우저 기록·프록시 어디에나 키가 남는다 — 앞자리 몇 글자도
전체를 좁히는 단서라 안 낸다.

이 검사가 잠그는 것:
  ① 응답 어디에도 키 값이 없다 (부분 문자열도)
  ② `filled` 는 불리언이다 — 길이·앞자리 같은 파생값이 아니다
  ③ 응답 스키마에 값을 담을 필드가 애초에 없다
  ④ 표에 있는 소스가 전부 나온다 — 하나 빠지면 화면이 그 키를 영영 안 보여준다

standalone 실행 겸용:
    cd app && APP_ENV=development uv run python ../tests/test_data_key_status_no_value.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 설정을 세우고 나서 서비스를 import 한다 — `data_key_service` 는 `core.logger` →
# `core.config.settings = Settings()` 를 물고 들어오고, 그 Settings 는 DB·SFTP·JWT 를
# 요구한다. `.env.development` 는 gitignore 라 CI 러너에 없다.
# 이 관용구는 `test_data_source_key_leak.py` 가 이미 쓰는 것과 같다 — 값은 쓰이지 않고
# **존재만** 필요하므로 더미다.
os.environ["APP_ENV"] = "data-key-status-test"
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

from schemas.data_key.data_key_schema import DataKeyStatusOut  # noqa: E402
from services.data_key.data_key_service import (  # noqa: E402
    COMPOSITE_KEY_SETTINGS,
    CONTACT_SETTING,
    NON_SECRET_CONTACT_SOURCES,
    SOURCE_KEY_SETTINGS,
    DataKeyService,
)

FAILURES: list[str] = []
CHECKED = 0

SECRET = "sk-live-0123456789abcdefGHIJKLMNOP"


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


class FakeConfig:
    """모든 키가 채워진 설정 — 값이 새면 여기서 드러난다."""

    def __init__(self) -> None:
        for setting in SOURCE_KEY_SETTINGS.values():
            setattr(self, setting, SECRET)
        for names in COMPOSITE_KEY_SETTINGS.values():
            for name in names:
                setattr(self, name, SECRET)
        setattr(self, CONTACT_SETTING, "lead@example.com")


def main() -> int:
    rows = DataKeyService(FakeConfig()).list_key_status()
    blob = repr(rows)

    # ① 값이 통째로도, 조각으로도 안 나온다
    check("키 값이 응답에 없다", SECRET in blob, False)
    check("키 앞자리도 없다", SECRET[:8] in blob, False)
    check("키 뒷자리도 없다", SECRET[-8:] in blob, False)

    # ② filled 는 불리언이다 — 길이·앞자리 같은 파생값이 아니다
    for row in rows:
        check(f"{row['source']} filled 가 불리언", isinstance(row["filled"], bool), True)
    check("채워졌으면 True", all(row["filled"] for row in rows), True)

    # ③ 스키마에 값을 담을 필드가 없다
    fields = set(DataKeyStatusOut.model_fields)
    check("스키마 필드가 넷뿐이다", fields, {"source", "setting", "filled", "secret", "guidance"})
    leaky = {f for f in fields if any(w in f.lower() for w in ("key", "value", "secret_", "token"))}
    check("값을 담을 이름의 필드가 없다", leaky, set())

    # ④ 표의 소스가 전부 나온다 — 빠지면 화면이 그 키를 영영 안 보여준다
    expected_sources = set(SOURCE_KEY_SETTINGS) | set(COMPOSITE_KEY_SETTINGS) | set(NON_SECRET_CONTACT_SOURCES)
    check("표의 소스가 전부 나온다", {row["source"] for row in rows}, expected_sources)
    check("연락처는 비밀이 아니라고 표시된다", [r["secret"] for r in rows if r["source"] == "sec"], [False])

    # 비어 있으면 False 로 나온다
    class Empty:
        pass

    empty_rows = DataKeyService(Empty()).list_key_status()
    check("설정이 없으면 전부 안 채워짐", any(row["filled"] for row in empty_rows), False)

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 10:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 키 상태 조회가 값을 흘리지 않는다 (#225)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
