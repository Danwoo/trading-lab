"""tn_workspace_member.is_default 유일성 DB 제약 검증 (#253).

계약 (alembic/versions/0006_workspace_member_unique.py):
  (1) 사용자당 `is_default=true` 멤버십을 두 번째로 넣으면(다른 워크스페이스) DB 가 유니크 위반으로
      거부한다 — 이전에는 애플리케이션 규약에만 의존해 조용히 통과했다.
  (2) 같은 사용자가 워크스페이스별로 `is_default=false` 멤버십은 여러 개 가질 수 있다(인덱스가
      `WHERE is_default` 부분 인덱스이므로 false 행은 유니크 대상이 아니다).
  (3) 서로 다른 사용자는 각자 `is_default=true` 멤버십을 하나씩 가질 수 있다(인덱스 키가
      user_id 이므로 사용자 간 충돌은 없다).

대상 테이블(`frontend.tn_workspace_member`)은 Prisma 소유라 이 서비스의 SQLAlchemy 모델에 없다 —
`frontend/prisma/init/tables.sql`(Prisma 생성물, 로컬-postgres.md 가 문서화한 수동 부트스트랩 경로)을
그대로 적용해 실제와 같은 테이블 구조를 만든 뒤, 0006 리비전의 UPGRADE_SQL 을 직접 실행해 검증한다
(alembic 버전 추적과 무관하게 이 리비전의 SQL 자체가 올바른지만 본다).

접속 대상은 `WORKSPACE_MEMBER_TEST_DB_URL`(순수 libpq 형태 — `psycopg.connect` 가 직접 받는다,
alembic 의 `ALEMBIC_DB_URL` 과 달리 `+psycopg` 드라이버 접미사가 없다) 또는 기본값
`postgresql://ci:ci@localhost:5432/ci` — CI 서비스 컨테이너 규약과 동일.
`uv run python scripts/verify_workspace_member_default_unique.py` (cwd=서비스 루트).

**⚠ DB 파괴 경고 — 이 스크립트는 접속 대상 DB 의 `frontend` 스키마 16개 테이블을 통째로
DROP 한다** (`tables.sql` 첫머리가 `DROP TABLE IF EXISTS` 16개). #253 최초 도입 때 이 위험이
가드 없이 나갈 뻔했다(리뷰 지적으로 되돌림 — #333 코멘트). 그래서 실행 전 두 겹으로 막는다:

  1. **DB 이름 화이트리스트** — dbname 이 `ci` 이거나 `_verify_scratch` 로 끝나야 한다(아래
     `_SAFE_DB_NAME_SUFFIXES`/`_SAFE_DB_NAMES`). 개발 DB(`fintech`) 등 다른 이름이면 즉시 거부한다.
  2. **명시 플래그** — `--i-know-this-drops-tables` 없이는 화이트리스트를 통과해도 실행하지 않는다.
     사람이 실수로 기본 인자 없이 돌려도(CI 러너 예외) 막히도록, CI 는 워크플로 스텝에서
     플래그를 명시한다.

두 조건을 모두 충족해야(AND) 실제 접속·DROP 이 일어난다. 화이트리스트만 믿고 플래그를 생략하지 않는다
— dbname 판별은 URL 파싱이라 오탈자·프록시 경유 시 우회될 수 있어 사람의 명시 동의를 겹쳐 둔다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import psycopg

_SCRIPT_DIR = Path(__file__).resolve().parent
_ALEMBIC_DIR = _SCRIPT_DIR.parent / "alembic"
_REPO_ROOT = _SCRIPT_DIR.parent.parent
_TABLES_SQL = _REPO_ROOT / "frontend" / "prisma" / "init" / "tables.sql"

sys.path.insert(0, str(_ALEMBIC_DIR / "versions"))

DB_URL = os.getenv("WORKSPACE_MEMBER_TEST_DB_URL", "postgresql://ci:ci@localhost:5432/ci")

# dbname 화이트리스트 — CI 서비스 컨테이너 규약(ci)과, 로컬에서 일회용으로 만든 이름만 허용한다.
# 개발 DB(fintech)·운영 DB 이름은 여기 들어가지 않는다.
_SAFE_DB_NAMES = {"ci"}
_SAFE_DB_NAME_SUFFIXES = ("_verify_scratch",)


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")
    raise SystemExit(1)


def _dbname_from_url(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def _assert_safe_target(url: str, *, confirmed: bool) -> None:
    dbname = _dbname_from_url(url)
    is_whitelisted = dbname in _SAFE_DB_NAMES or dbname.endswith(_SAFE_DB_NAME_SUFFIXES)
    if not is_whitelisted:
        _fail(
            f"대상 DB 이름 '{dbname}' 이 화이트리스트({_SAFE_DB_NAMES} 또는 접미사 "
            f"{_SAFE_DB_NAME_SUFFIXES})에 없습니다. 이 스크립트는 frontend 스키마 테이블 16개를 "
            "DROP 합니다 — 개발·운영 DB 를 겨눈 것이라면 절대 실행하지 마세요."
        )
    if not confirmed:
        _fail(
            "대상 DB 이름은 안전하지만 --i-know-this-drops-tables 플래그가 없습니다. "
            "이 스크립트가 frontend 스키마를 DROP 후 재생성한다는 것을 확인했다면 플래그를 붙이세요."
        )


def _connect() -> psycopg.Connection:
    conn = psycopg.connect(DB_URL)
    conn.autocommit = True
    return conn


def setup_schema(conn: psycopg.Connection) -> None:
    if not _TABLES_SQL.is_file():
        _fail(f"{_TABLES_SQL} 없음 — frontend/prisma/init/tables.sql 생성물이 커밋돼 있어야 한다")
    conn.execute(_TABLES_SQL.read_text())


def apply_revision_sql(conn: psycopg.Connection) -> None:
    import importlib

    module = importlib.import_module("0006_workspace_member_unique")
    conn.execute(module.UPGRADE_SQL)


def _make_user(conn: psycopg.Connection, user_id: str) -> None:
    conn.execute(
        """
        INSERT INTO frontend.tn_user (id, email, name, appr_at, use_at, reg_dt, reg_id, mod_dt, mod_id)
        VALUES (%s, %s, %s, 'Y', 'Y', now(), 'test', now(), 'test')
        """,
        (user_id, f"{user_id}@example.com", user_id),
    )


def _make_workspace(conn: psycopg.Connection, code: str) -> int:
    row = conn.execute(
        """
        INSERT INTO frontend.tn_workspace (workspace_code, workspace_nm, use_at, is_personal, reg_dt, reg_id, mod_dt, mod_id)
        VALUES (%s, %s, 'Y', false, now(), 'test', now(), 'test')
        RETURNING id
        """,
        (code, code),
    ).fetchone()
    return row[0]


def _insert_member(conn: psycopg.Connection, workspace_id: int, user_id: str, is_default: bool) -> None:
    conn.execute(
        """
        INSERT INTO frontend.tn_workspace_member (workspace_id, user_id, role, is_default, reg_dt, reg_id, mod_dt, mod_id)
        VALUES (%s, %s, 'owner', %s, now(), 'test', now(), 'test')
        """,
        (workspace_id, user_id, is_default),
    )


def check_duplicate_default_rejected(conn: psycopg.Connection) -> None:
    """(1) 같은 사용자에 is_default=true 두 번째 삽입은 거부된다."""
    _make_user(conn, "u1")
    ws_a = _make_workspace(conn, "ws-u1-a")
    ws_b = _make_workspace(conn, "ws-u1-b")
    _insert_member(conn, ws_a, "u1", True)
    try:
        _insert_member(conn, ws_b, "u1", True)
    except psycopg.errors.UniqueViolation:
        pass  # 기대: 유니크 인덱스 위반으로 거부
    else:
        _fail("같은 사용자의 두 번째 is_default=true 삽입이 거부되지 않음")
    print("  ✓ 중복 is_default=true 거부됨 (사용자 1명, 워크스페이스 2개)")


def check_multiple_nondefault_allowed(conn: psycopg.Connection) -> None:
    """(2) is_default=false 는 같은 사용자에 여러 개 허용된다 (부분 인덱스 — false 는 대상 밖)."""
    _make_user(conn, "u2")
    ws_a = _make_workspace(conn, "ws-u2-a")
    ws_b = _make_workspace(conn, "ws-u2-b")
    _insert_member(conn, ws_a, "u2", False)
    _insert_member(conn, ws_b, "u2", False)
    count = conn.execute("SELECT count(*) FROM frontend.tn_workspace_member WHERE user_id = 'u2'").fetchone()[0]
    if count != 2:
        _fail(f"is_default=false 다건 허용 실패 (기대 2, 실제 {count})")
    print("  ✓ is_default=false 는 같은 사용자에 여러 개 허용됨 (부분 인덱스가 false 를 배제)")


def check_different_users_each_have_default(conn: psycopg.Connection) -> None:
    """(3) 서로 다른 사용자는 각자 is_default=true 를 가질 수 있다 (인덱스 키가 user_id)."""
    _make_user(conn, "u3")
    _make_user(conn, "u4")
    ws3 = _make_workspace(conn, "ws-u3")
    ws4 = _make_workspace(conn, "ws-u4")
    _insert_member(conn, ws3, "u3", True)
    _insert_member(conn, ws4, "u4", True)
    print("  ✓ 서로 다른 사용자는 각자 is_default=true 를 문제없이 가질 수 있음")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--i-know-this-drops-tables",
        action="store_true",
        help="대상 DB 의 frontend 스키마 16개 테이블이 DROP·재생성된다는 것을 확인했다는 명시 동의",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _assert_safe_target(DB_URL, confirmed=args.i_know_this_drops_tables)
    print(f"workspace_member is_default 유일성 검증 (대상: {DB_URL.split('@')[-1]})")
    conn = _connect()
    setup_schema(conn)
    apply_revision_sql(conn)
    check_duplicate_default_rejected(conn)
    check_multiple_nondefault_allowed(conn)
    check_different_users_each_have_default(conn)
    conn.close()
    print("모든 검증 통과")


if __name__ == "__main__":
    main()
