"""frontend 스키마 FK 의 참조 동작(ON DELETE/ON UPDATE) 계약 검증 (#238).

## 왜 필요한가 — 같은 스키마가 부트스트랩 경로마다 다르게 세워졌다

`frontend` 스키마를 세우는 길은 둘이다:

  (ㄱ) `prisma db push` — 개발·스테이징·운영이 쓰는 길 (package.json 의 `*:prisma:push`)
  (ㄴ) `frontend/prisma/init/tables.sql` — CI 잡·`verify_*.py` 의 scratch DB·수동 부트스트랩
       (`.docs/5-인프라셋팅/로컬-postgres.md`)이 쓰는 길

(ㄱ)은 Prisma 기본값대로 `ON UPDATE CASCADE ON DELETE RESTRICT` 를 붙이는데 (ㄴ)의 생성기는
참조 동작을 아예 안 적어 Postgres 기본값 `NO ACTION` 이 됐다 — **13개 FK 전부**가 갈렸다.
실측(#238 조사): 부모 키 `tn_user.email` 을 바꾸면 (ㄱ)에서는 `tn_author_member.user_id` 로
전파되고 (ㄴ)에서는 FK 위반으로 거부된다. 즉 이메일 변경 기능을 켜는 순간 **환경마다 다르게**
동작한다 — 한쪽에서 통과한 테스트가 다른 쪽의 안전을 증명하지 못한다.

생성기(`frontend/prisma/table-generator.cjs`)를 고쳐 두 길을 맞췄고, 이 스크립트가 그 계약을 잠근다.

## 무엇을 보는가

  (1) tables.sql 로 세운 DB 의 FK 참조 동작이 아래 `EXPECTED_FK_ACTIONS` 와 일치한다.
      검사한 FK 수를 세고 **0건이거나 기대 수와 다르면 실패**한다 — 생성기가 FK 를 통째로
      안 내보내도 "위반 0건"으로 초록이 되는 것을 막는다.
  (2) 권한 매핑이 이메일 변경을 따라간다 (`tn_author_member.user_id` 는 email 자연키다 — #238 의
      본래 걱정. 참조 무결성은 FK 가 이미 지키고 있고, 이 검사가 그 사실을 고정한다).
  (3) 사용자 이메일을 값으로 들고 있는 컬럼 목록이 `EMAIL_IDENTITY_COLUMNS` 인벤토리와 일치한다.
      새 컬럼이 생기면 실패한다 — 이메일로 사람을 식별하는 자리는 늘어날 때마다 사람이
      "FK 로 묶을 것인가 / 이메일 변경 시 함께 옮길 것인가"를 판단해야 한다.
      **한계(정직하게)**: 이 스크립트가 세우는 DB 는 `frontend` 스키마뿐이라 `public` 스키마
      (alembic 소유: `tn_research_document.user_id` · `tn_scheduler_member.email` ·
      `workspace_doc_chunk.user_id`)는 이 인벤토리에 들어오지 않는다. 그쪽은 스키마를 가로지르는
      FK 가 없어 이메일 변경 시 조용히 끊긴다 — 별도 이슈로 추적한다.

접속·안전 가드 규약은 `verify_workspace_member_default_unique.py` 와 같다 (DB 이름 화이트리스트
AND 명시 플래그). 이 스크립트도 tables.sql 을 적용하므로 **frontend 스키마를 DROP·재생성한다.**

실행: `uv run python scripts/verify_frontend_fk_referential_actions.py --i-know-this-drops-tables`
(cwd=backend-service). 대상은 `FRONTEND_FK_TEST_DB_URL` 또는 기본 `postgresql://ci:ci@localhost:5432/ci`.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlsplit

import psycopg

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent.parent
_TABLES_SQL = _REPO_ROOT / "frontend" / "prisma" / "init" / "tables.sql"

DB_URL = os.getenv("FRONTEND_FK_TEST_DB_URL", "postgresql://ci:ci@localhost:5432/ci")

_SAFE_DB_NAMES = {"ci"}
_SAFE_DB_NAME_SUFFIXES = ("_verify_scratch",)

# (테이블, 제약명) → (ON UPDATE, ON DELETE).
# 값의 근거는 `prisma db push` 가 실제로 만드는 것 — schema.prisma 가 명시한 관계는 그 값,
# 안 적은 관계는 Prisma 기본값(필수 관계: UPDATE CASCADE / DELETE RESTRICT).
# 관계를 더하거나 `onDelete`/`onUpdate` 를 바꾸면 여기도 함께 고친다 (안 고치면 이 검사가 막는다).
EXPECTED_FK_ACTIONS: dict[tuple[str, str], tuple[str, str]] = {
    ("tn_user", "fk_tn_user_workspace_id"): ("NO ACTION", "NO ACTION"),
    ("tn_menu", "fk_tn_menu_upper_menu_id"): ("NO ACTION", "NO ACTION"),
    ("tn_workspace_member", "fk_tn_workspace_member_workspace_id"): ("CASCADE", "RESTRICT"),
    ("tn_workspace_member", "fk_tn_workspace_member_user_id"): ("CASCADE", "RESTRICT"),
    ("tn_workspace_menu", "fk_tn_workspace_menu_workspace_id"): ("CASCADE", "RESTRICT"),
    ("tn_workspace_domain", "fk_tn_workspace_domain_workspace_id"): ("CASCADE", "RESTRICT"),
    ("ba_session", "fk_ba_session_userId"): ("CASCADE", "RESTRICT"),
    ("ba_account", "fk_ba_account_userId"): ("CASCADE", "RESTRICT"),
    ("tn_author_member", "fk_tn_author_member_author_id"): ("CASCADE", "RESTRICT"),
    # #238 의 초점 — 권한 매핑이 email 자연키다. ON UPDATE CASCADE 라야 이메일 변경이
    # 매핑을 끊지 않고 함께 옮긴다.
    ("tn_author_member", "fk_tn_author_member_user_id"): ("CASCADE", "RESTRICT"),
    ("tn_author_menu", "fk_tn_author_menu_author_id"): ("CASCADE", "RESTRICT"),
    ("tn_author_menu", "fk_tn_author_menu_menu_id"): ("CASCADE", "RESTRICT"),
    ("tc_code", "fk_tc_code_group_code"): ("CASCADE", "RESTRICT"),
}

# 사용자 이메일을 **값으로** 담는 frontend 스키마 컬럼 인벤토리 → 그 자리의 판정.
# 감사 컬럼(reg_id·mod_id)은 "그때 그 사람"을 적는 이력이라 이 축이 아니다(제외 근거를 여기 남긴다).
EMAIL_IDENTITY_COLUMNS: dict[tuple[str, str], str] = {
    ("tn_user", "email"): "정본(UNIQUE). 다른 자리는 전부 이 값을 가리킨다.",
    ("tn_author_member", "user_id"): "FK → tn_user.email, ON UPDATE CASCADE 로 변경을 따라간다.",
    ("ai_chat_history", "email"): "FK 없음 — 이메일이 바뀌면 이력이 끊긴다. 탈퇴 시 삭제는 #363 에서 붙였다.",
    ("th_email_log", "to"): "FK 없음. 발송 시점 사실을 적는 로그라 과거 주소가 남는 것이 맞다.",
}

_FK_ACTION_CODES = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")
    raise SystemExit(1)


def _assert_safe_target(url: str, *, confirmed: bool) -> None:
    dbname = urlsplit(url).path.lstrip("/")
    if not (dbname in _SAFE_DB_NAMES or dbname.endswith(_SAFE_DB_NAME_SUFFIXES)):
        _fail(
            f"대상 DB 이름 '{dbname}' 이 화이트리스트({_SAFE_DB_NAMES} 또는 접미사 "
            f"{_SAFE_DB_NAME_SUFFIXES})에 없습니다. 이 스크립트는 frontend 스키마를 DROP 합니다."
        )
    if not confirmed:
        _fail("--i-know-this-drops-tables 플래그가 없습니다 (frontend 스키마 DROP·재생성 동의).")


def setup_schema(conn: psycopg.Connection) -> None:
    if not _TABLES_SQL.is_file():
        _fail(f"{_TABLES_SQL} 없음 — frontend/prisma/init/tables.sql 생성물이 커밋돼 있어야 한다")
    conn.execute(_TABLES_SQL.read_text())


def check_fk_actions(conn: psycopg.Connection) -> None:
    rows = conn.execute(
        """
        SELECT c.conrelid::regclass::text, c.conname, c.confupdtype, c.confdeltype
        FROM pg_constraint c
        WHERE c.contype = 'f' AND c.connamespace = 'frontend'::regnamespace
        """
    ).fetchall()

    if not rows:
        _fail("frontend 스키마에서 FK 를 하나도 못 찾았다 — tables.sql 이 FK 를 안 만들었거나 스키마가 비었다")

    actual = {
        (table.replace("frontend.", ""), name): (_FK_ACTION_CODES[upd], _FK_ACTION_CODES[dele])
        for table, name, upd, dele in rows
    }

    missing = sorted(set(EXPECTED_FK_ACTIONS) - set(actual))
    unexpected = sorted(set(actual) - set(EXPECTED_FK_ACTIONS))
    if missing:
        _fail(f"기대한 FK 가 없다: {missing}")
    if unexpected:
        _fail(f"인벤토리에 없는 FK 가 생겼다 — 참조 동작을 판단해 EXPECTED_FK_ACTIONS 에 추가하라: {unexpected}")

    mismatched = [
        f"{table}.{name}: 기대 {EXPECTED_FK_ACTIONS[(table, name)]}, 실제 {value}"
        for (table, name), value in sorted(actual.items())
        if value != EXPECTED_FK_ACTIONS[(table, name)]
    ]
    if mismatched:
        _fail(
            "FK 참조 동작이 계약과 다르다 (prisma db push 가 만드는 것과 tables.sql 이 갈렸다):\n    "
            + "\n    ".join(mismatched)
        )
    print(f"  ✓ FK 참조 동작 {len(actual)}건 전부 계약과 일치 (기대 {len(EXPECTED_FK_ACTIONS)}건)")


def check_email_change_carries_author_member(conn: psycopg.Connection) -> None:
    """#238 — 이메일이 바뀌어도 권한 매핑이 같은 사람을 가리키는가."""
    conn.execute(
        """
        INSERT INTO frontend.tn_user (id, email, name, appr_at, use_at, "emailVerified")
        VALUES ('fk-u1', 'before@example.com', 'fk-test', 'Y', 'Y', false)
        """
    )
    conn.execute("INSERT INTO frontend.tn_author (author_id, author_nm) VALUES ('fk-a1', 'FK 테스트 권한')")
    conn.execute("INSERT INTO frontend.tn_author_member (author_id, user_id) VALUES ('fk-a1', 'before@example.com')")

    conn.execute("UPDATE frontend.tn_user SET email = 'after@example.com' WHERE id = 'fk-u1'")

    mapped = conn.execute(
        """
        SELECT count(*) FROM frontend.tn_author_member am
        JOIN frontend.tn_user u ON u.email = am.user_id
        WHERE u.id = 'fk-u1' AND am.author_id = 'fk-a1'
        """
    ).fetchone()[0]
    if mapped != 1:
        _fail(f"이메일 변경 후 권한 매핑이 끊겼다 (기대 1건, 실제 {mapped}건)")

    orphans = conn.execute(
        """
        SELECT count(*) FROM frontend.tn_author_member am
        LEFT JOIN frontend.tn_user u ON u.email = am.user_id
        WHERE u.id IS NULL
        """
    ).fetchone()[0]
    if orphans != 0:
        _fail(f"주인 없는 권한 매핑 행이 {orphans}건 남았다")
    print("  ✓ 이메일 변경이 권한 매핑을 함께 옮긴다 (고아 0건)")


def check_email_identity_inventory(conn: psycopg.Connection) -> None:
    """이메일로 사람을 식별하는 컬럼이 늘면 사람이 판단하게 세운다."""
    rows = conn.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'frontend'
          AND data_type = 'character varying'
          AND (column_name IN ('email', 'to') OR column_name = 'user_id')
        """
    ).fetchall()
    found = {(t, c) for t, c in rows}

    # tn_workspace_member.user_id 는 tn_user.id(대리키)를 담는다 — 이메일 축이 아니다.
    found.discard(("tn_workspace_member", "user_id"))

    if not found:
        _fail("이메일 식별 컬럼을 하나도 못 찾았다 — 스키마가 비었거나 조회 조건이 낡았다")

    unknown = sorted(found - set(EMAIL_IDENTITY_COLUMNS))
    gone = sorted(set(EMAIL_IDENTITY_COLUMNS) - found)
    if unknown:
        _fail(
            "인벤토리에 없는 이메일 식별 컬럼이 생겼다 — FK 로 묶을지, 이메일 변경 시 함께 옮길지 "
            f"판단해 EMAIL_IDENTITY_COLUMNS 에 적어라: {unknown}"
        )
    if gone:
        _fail(f"인벤토리에 있는 컬럼이 사라졌다 — 인벤토리를 갱신하라: {gone}")
    print(f"  ✓ 이메일 식별 컬럼 {len(found)}건이 인벤토리와 일치")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="frontend FK 참조 동작 계약 검증 (#238)")
    parser.add_argument(
        "--i-know-this-drops-tables",
        action="store_true",
        help="대상 DB 의 frontend 스키마가 DROP·재생성된다는 것을 확인했다는 명시 동의",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _assert_safe_target(DB_URL, confirmed=args.i_know_this_drops_tables)
    print(f"frontend FK 참조 동작 검증 (대상: {DB_URL.split('@')[-1]})")
    conn = psycopg.connect(DB_URL)
    conn.autocommit = True
    setup_schema(conn)
    check_fk_actions(conn)
    check_email_change_carries_author_member(conn)
    check_email_identity_inventory(conn)
    conn.close()
    print("모든 검증 통과")


if __name__ == "__main__":
    main()
