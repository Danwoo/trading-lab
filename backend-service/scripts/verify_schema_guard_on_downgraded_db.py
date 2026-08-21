"""한 판 되돌린 **실제 DB** 에서 기동 가드가 막는지 검증한다 (#311).

`tests/test_schema_version_guard.py` 는 판정 로직을 sqlite 로 본다(서버 없이 돈다). 여기서는
같은 가드를 **진짜 Postgres** 에 붙여, alembic 이 실제로 DDL 을 되돌린 상태를 만들고 본다:

  (1) `upgrade head` 상태에서는 가드가 통과한다 (정상 기동을 막지 않는다).
  (2) `alembic downgrade -1` 로 한 판 되돌리면 가드가 기동을 막고, 그 사유에 DB 리비전·코드
      head·`alembic upgrade head` 처방이 함께 나온다 — #311 이 걸렸던 바로 그 상태다.
  (3) 다시 `upgrade head` 하면 통과로 돌아온다 (검사가 DB 를 되돌려 놓는다).

**⚠ 이 스크립트는 대상 DB 의 스키마를 한 판 되돌렸다 되돌린다.** 그래서 두 겹으로 막는다 —
dbname 화이트리스트(`ci` 또는 `_verify_scratch` 접미사)와 `--i-know-this-downgrades-schema`
플래그. 둘 다여야 접속한다 (verify_workspace_member_default_unique.py 와 같은 규약).

대상은 `ALEMBIC_DB_URL`(SQLAlchemy URL — CI alembic-drift 잡이 이미 잡 수준에서 준다). 값이
없으면 검사할 대상이 없는 것이므로 통과가 아니라 실패다. CI 는 이 스크립트를 DB 없는
`test: backend` 스위트에서 빼고(`--skip`) alembic-drift 잡에서 돌린다.

    ALEMBIC_DB_URL=postgresql+psycopg://ci:ci@localhost:5432/ci \\
      uv run python scripts/verify_schema_guard_on_downgraded_db.py --i-know-this-downgrades-schema
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

_SERVICE_ROOT = Path(__file__).resolve().parents[1]
_ALEMBIC_DIR = _SERVICE_ROOT / "alembic"

# core.config 가 .env.{APP_ENV} 를 읽는다 — 존재하지 않는 이름으로 파일 간섭을 끊고 필수 필드만 채운다.
# (접속 대상은 아래 ALEMBIC_DB_URL 이며 이 값들로 접속하지 않는다.)
os.environ["APP_ENV"] = "schema-guard-db-verify"
for _key, _value in {
    "JWT_SECRET": "verify-secret",
    "BACKEND_SQL_DB_DRIVER": "postgresql+psycopg",
    "BACKEND_SQL_DB_HOST": "localhost",
    "BACKEND_SQL_DB_PORT": "5432",
    "BACKEND_SQL_DB_NAME": "unused",
    "BACKEND_SQL_DB_USER": "unused",
    "BACKEND_SQL_DB_PASSWORD": "unused",
    "SFTP_HOST": "localhost",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "unused",
    "SFTP_PASSWORD": "unused",
}.items():
    os.environ.setdefault(_key, _value)

sys.path.insert(0, str(_SERVICE_ROOT / "app"))

from core.schema_version import SchemaVersionError, code_head_revision, ensure_schema_matches_code  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

_SAFE_DB_NAMES = {"ci"}
_SAFE_DB_NAME_SUFFIXES = ("_verify_scratch",)

CHECKED = 0
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global CHECKED
    CHECKED += 1
    if ok:
        print(f"  ✓ {name}")
    else:
        FAILURES.append(f"{name}{f' — {detail}' if detail else ''}")
        print(f"  ✗ {name}{f' — {detail}' if detail else ''}")


def _fail(message: str) -> int:
    print(f"::error::{message}")
    return 1


def _assert_safe_target(url: str, *, confirmed: bool) -> str | None:
    dbname = urlsplit(url).path.lstrip("/")
    if not (dbname in _SAFE_DB_NAMES or dbname.endswith(_SAFE_DB_NAME_SUFFIXES)):
        return (
            f"대상 DB 이름 '{dbname}' 이 화이트리스트({_SAFE_DB_NAMES} 또는 접미사 "
            f"{_SAFE_DB_NAME_SUFFIXES})에 없습니다. 이 스크립트는 스키마를 한 판 되돌립니다 — "
            "개발·운영 DB 를 겨눈 것이라면 절대 실행하지 마세요."
        )
    if not confirmed:
        return "대상 DB 이름은 안전하지만 --i-know-this-downgrades-schema 플래그가 없습니다."
    return None


def _alembic(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_ALEMBIC_DIR,
        capture_output=True,
        text=True,
    )


def _guard_message(engine) -> str | None:
    try:
        ensure_schema_matches_code(engine, allow_drift=False)
    except SchemaVersionError as exc:
        return str(exc)
    return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--i-know-this-downgrades-schema", action="store_true", dest="confirmed")
    args = parser.parse_args(argv)

    url = os.getenv("ALEMBIC_DB_URL")
    if not url:
        return _fail(
            "ALEMBIC_DB_URL 이 없습니다 — 대상 DB 없이는 이 검사가 아무것도 보지 않습니다(fail-closed). "
            "CI 는 alembic-drift 잡에서 이 값을 줍니다."
        )
    if problem := _assert_safe_target(url, confirmed=args.confirmed):
        return _fail(problem)

    head, _ = code_head_revision()
    engine = create_engine(url, hide_parameters=True)

    # (1) 전제 — 대상 DB 가 head 여야 이 검사가 의미를 가진다.
    at_head = _guard_message(engine)
    check("head 인 DB 에서는 가드가 통과한다", at_head is None, str(at_head))
    if at_head is not None:
        print("::error::대상 DB 가 head 가 아닙니다 — 먼저 `alembic upgrade head` 를 적용하세요")
        return 1

    # (2) 한 판 되돌린다 — 컬럼이 실제로 사라진 상태 (#311 의 조건).
    downgraded = _alembic("downgrade", "-1")
    check("alembic downgrade -1 성공", downgraded.returncode == 0, downgraded.stderr.strip())
    if downgraded.returncode != 0:
        return 1

    try:
        message = _guard_message(engine)
        check("뒤진 DB 에서 가드가 기동을 막는다", message is not None)
        if message:
            check("사유에 코드 head 가 있다", head in message, message)
            check("처방에 alembic upgrade head 가 있다", "alembic upgrade head" in message, message)
            check("뒤처졌다고 이름을 붙인다", "뒤처졌다" in message, message)
            print(f"  판정 문구: {message}")
    finally:
        restored = _alembic("upgrade", "head")
        check("검사 후 head 로 복구", restored.returncode == 0, restored.stderr.strip())

    check("복구 후 가드가 다시 통과한다", _guard_message(engine) is None)

    if not CHECKED:
        return _fail("검사를 0건 실행했습니다 — 그물이 죽었습니다")
    print(f"\n검사 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
