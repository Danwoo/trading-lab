"""#311 — 코드보다 뒤진 DB 에 붙었을 때 기동 가드가 실제로 막는지.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    cd backend-service && uv run python tests/test_schema_version_guard.py

**서버 DB 없이 돈다.** 「스키마를 한 판 되돌린 DB」는 임시 sqlite 파일에 `alembic_version` 을
직접 세워 만든다 — 리비전 값은 합성이 아니라 이 레포의 `alembic/versions/` 에서 읽은 실제
head 와 그 직전 리비전이다. 가드가 보는 것이 그 테이블 하나뿐이라 sqlite 로도 판정 경로가
그대로 재현된다 (컬럼 부재는 가드의 관심사가 아니다 — 가드는 그 전에 멈춰 세우는 쪽이다).

**개발 DB 는 건드리지 않는다.** 이 테스트가 쓰는 DB 는 매 실행 새로 만드는 임시 파일이다.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Settings 가 env_file(.env.{APP_ENV})을 읽는다 — 존재하지 않는 이름을 줘 파일 간섭을 끊고,
# 필수 필드는 env 로 채운다 (여기서 만드는 엔진은 sqlite 라 이 값들로 접속하지 않는다).
os.environ["APP_ENV"] = "schema-version-guard-test"
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("BACKEND_SQL_DB_DRIVER", "sqlite")
os.environ.setdefault("BACKEND_SQL_DB_HOST", "")
os.environ.setdefault("BACKEND_SQL_DB_PORT", "5432")
os.environ.setdefault("BACKEND_SQL_DB_NAME", ":memory:")
os.environ.setdefault("BACKEND_SQL_DB_USER", "")
os.environ.setdefault("BACKEND_SQL_DB_PASSWORD", "")
os.environ.setdefault("SFTP_HOST", "localhost")
os.environ.setdefault("SFTP_PORT", "22")
os.environ.setdefault("SFTP_USERNAME", "test")
os.environ.setdefault("SFTP_PASSWORD", "test")

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND / "app") not in sys.path:
    sys.path.insert(0, str(_BACKEND / "app"))

from alembic.script import ScriptDirectory  # noqa: E402
from core import schema_version  # noqa: E402
from core.schema_version import (  # noqa: E402
    SchemaVersionError,
    code_head_revision,
    ensure_schema_matches_code,
    version_table_name,
)
from sqlalchemy import create_engine, text  # noqa: E402

CHECKED = 0
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global CHECKED
    CHECKED += 1
    if not ok:
        FAILURES.append(f"{name}{f' — {detail}' if detail else ''}")


def _engine_with_revisions(tmpdir: str, *revisions: str, create_table: bool = True):
    """`alembic_version` 만 가진 임시 DB. revisions 가 비면 빈 테이블(미적용 상태)."""
    path = Path(tmpdir) / f"drift-{len(os.listdir(tmpdir))}.db"
    engine = create_engine(f"sqlite+pysqlite:///{path}", hide_parameters=True)
    if create_table:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            for revision in revisions:
                connection.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": revision})
    return engine


def _raised(engine, **kwargs) -> str | None:
    try:
        ensure_schema_matches_code(engine, **kwargs)
    except SchemaVersionError as exc:
        return str(exc)
    return None


def main() -> int:
    head, known = code_head_revision()
    script = ScriptDirectory(str(schema_version.ALEMBIC_DIR))
    previous = script.get_revision(head).down_revision
    check("head 직전 리비전을 읽었다", isinstance(previous, str), f"down_revision={previous!r}")
    print(f"  실제 리비전 {len(known)}개 · head={head} · 직전={previous}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # ① 판이 맞으면 통과한다 (가드가 정상 기동을 막지 않는다).
        at_head = _engine_with_revisions(tmpdir, head)
        check("head 와 같은 DB 는 통과", _raised(at_head) is None)

        # ② 한 판 뒤진 DB — #311 이 실제로 걸린 상태. 사유·양쪽 리비전·처방이 다 나와야 한다.
        behind = _engine_with_revisions(tmpdir, previous)
        message = _raised(behind)
        check("뒤진 DB 는 기동을 막는다", message is not None)
        if message:
            check("사유에 DB 리비전이 있다", previous in message, message)
            check("사유에 코드 head 가 있다", head in message, message)
            check("처방에 alembic upgrade head 가 있다", "alembic upgrade head" in message, message)
            check("탈출구를 함께 안내한다", "ALLOW_SCHEMA_DRIFT" in message, message)
            check("뒤처졌다고 이름을 붙인다", "뒤처졌다" in message, message)

        # ③ 코드가 모르는 리비전 — 체크아웃이 DB 보다 뒤진 반대 방향. 이것도 통과가 아니다.
        ahead = _engine_with_revisions(tmpdir, "9999_from_the_future")
        message = _raised(ahead)
        check("모르는 리비전도 기동을 막는다", message is not None)
        if message:
            check("모르는 리비전이라고 말한다", "모르는 리비전" in message, message)

        # ④~⑥ 읽지 못하는 상태는 전부 실패다 (fail-closed).
        no_table = _engine_with_revisions(tmpdir, create_table=False)
        check("버전 테이블이 없으면 실패", _raised(no_table) is not None)
        empty = _engine_with_revisions(tmpdir)
        check("적용된 리비전이 없으면 실패", _raised(empty) is not None)
        two_rows = _engine_with_revisions(tmpdir, head, previous)
        check("리비전이 여러 개면 실패", _raised(two_rows) is not None)

        # ⑦ 탈출구 — 켜면 뜨되 조용하지 않다.
        logged: list[str] = []
        original_error = schema_version.logger.error
        schema_version.logger.error = lambda msg, *a, **kw: logged.append(str(msg))  # type: ignore[assignment]
        try:
            check("ALLOW_SCHEMA_DRIFT 인자로 켜면 통과", _raised(behind, allow_drift=True) is None)
            check("켜도 ERROR 로 남는다", any(head in line and previous in line for line in logged), str(logged))
            # env(Settings) 배선도 같은 경로를 탄다 — 인자 없이 호출했을 때 기본이 막는 쪽인지 함께 본다.
            check("기본(Settings)은 막는다", schema_version.settings.ALLOW_SCHEMA_DRIFT is False)
            schema_version.settings.ALLOW_SCHEMA_DRIFT = True
            try:
                check("Settings 로 켜도 통과", _raised(behind) is None)
            finally:
                schema_version.settings.ALLOW_SCHEMA_DRIFT = False
        finally:
            schema_version.logger.error = original_error  # type: ignore[assignment]

    # ⑧ 좌표가 살아 있는지 — 가드는 이 두 파일을 런타임에 읽는다. 하나라도 어긋나면 가드가
    #    "판정 불가"로 모든 기동을 막게 되므로, 여기서 먼저 시끄럽게 깨져야 한다.
    check("버전 테이블 이름을 alembic.ini 에서 읽는다", version_table_name() == "alembic_version")
    check("리비전을 0건이 아니라 여럿 수집했다", len(known) >= 10, f"{len(known)}건")
    dockerfile = (_BACKEND / "Dockerfile").read_text()
    check(
        "이미지가 alembic 디렉터리를 함께 담는다",
        "COPY ./alembic ./alembic" in dockerfile,
        "컨테이너에서 코드 head 를 못 읽어 기동이 전부 막힌다",
    )

    if not CHECKED:
        print("::error::검사를 0건 실행했다 — 그물이 죽었다")
        return 1
    for failure in FAILURES:
        print(f"  ✗ {failure}")
    print(f"\n검사 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
