"""개인 워크스페이스 「멤버 0 고아」 정합성 검사 (#280).

배경: 탈퇴(`deleteUserCascade`, frontend/lib/auth/authUtils.ts)가 사용자·멤버십·세션·계정은
지우지만 그 사용자가 소유한 개인 워크스페이스(`tn_workspace.is_personal=true`) 행 자체는 남겼다
— 멤버 0 의 고아가 되고, 같은 이메일로 재가입할 때마다 누적됐다. 리드 결정(2026-08-02, #280)은
**하드 삭제**이고, 「그 검사가 새는 경로를 잡아야 한다」는 정합성 검사를 함께 요구했다.

이 스크립트가 하는 일은 authUtils.ts 의 TypeScript 코드를 실행하는 것이 **아니다** — **감사
SQL(`_ORPHAN_QUERY`) 자신의 정밀도·재현율**만 scratch DB 에 직접 심은 3행으로 검증한다.
`deleteUserCascade` 는 이 스크립트 안에서 한 번도 호출되지 않으므로, 그 함수를 통째로
되돌려도(또는 새로 깨져도) 이 스크립트는 초록으로 남을 수 있다 — 특히 [A] 류(삭제가 **예외를
던져 통째로 실패**하는 회귀)는 "멤버 0 워크스페이스가 DB 에 남는다"는 이 스크립트의 관측 대상
자체가 아니라서 원리적으로 이 검사의 시야 밖이다.

`deleteUserCascade` 실행 자체를 검증하는 그물은 별도로 있다 —
`frontend/tests/lib/auth/deleteUserCascade.dbtest.ts`(`npm run test:db`, cwd=frontend,
`frontend-ci.yml` 의 `delete-user-cascade` 잡). 이 스크립트는 그 그물과 상호 보완이지 대체가
아니다: 이쪽은 "감사 SQL 자체가 옳은가", 저쪽은 "삭제 코드가 실제로 안전한가"를 본다.

검사 3가지 (fail-closed — 셋 다 반드시 통과해야 한다, 하나라도 없으면 검사가 아무것도
못 본 것과 같다):
  (1) 정상 개인 워크스페이스(멤버 1명) → 감사 쿼리가 위반으로 잡지 않음 (오탐 방지)
  (2) 정상 공용 워크스페이스(is_personal=false, 멤버 0명) → 위반으로 잡지 않음 (이슈 범위는
      개인 워크스페이스뿐 — 공용 워크스페이스가 일시적으로 멤버 0 인 것은 이 검사의 대상이 아니다)
  (3) 멤버 0 개인 워크스페이스(고아 시나리오를 직접 시딩) → **반드시 위반으로 잡힘**. 이 케이스가
      안 잡히면 감사 쿼리 자체가 깨진 것이므로 검사를 실패시킨다 — "대상이 없어 통과"가 아니라
      "심어 놓은 위반을 못 찾았다"는 뜻이라 조용한 초록이 될 수 없다.

이 스크립트가 쓰는 감사 SQL(`_ORPHAN_QUERY`)은 실제 dev/운영 DB를 겨눠 그대로 재사용할 수 있는
운영 점검 쿼리이기도 하다 — 이 스크립트 자체는 격리된 scratch DB 에서 SQL 의 정확성만 본다.

대상 테이블(`frontend.tn_workspace`·`tn_workspace_member`)은 Prisma 소유라 이 서비스
SQLAlchemy 모델에 없다 — `verify_workspace_member_default_unique.py`(#253)와 동일하게
`frontend/prisma/init/tables.sql` 을 그대로 적용해 실제와 같은 테이블 구조를 만든다.

접속 대상은 `ORPHAN_WORKSPACE_TEST_DB_URL` 또는 기본값 `postgresql://ci:ci@localhost:5432/ci`.
`uv run python scripts/verify_no_orphan_personal_workspaces.py` (cwd=서비스 루트).

**⚠ DB 파괴 경고 — frontend 스키마 16개 테이블을 DROP 한다** — verify_workspace_member_default_unique.py
와 동일한 이중 가드(DB 이름 화이트리스트 + `--i-know-this-drops-tables` 명시 플래그)를 쓴다.
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

DB_URL = os.getenv("ORPHAN_WORKSPACE_TEST_DB_URL", "postgresql://ci:ci@localhost:5432/ci")

# dbname 화이트리스트 — verify_workspace_member_default_unique.py 와 같은 목록·정책.
_SAFE_DB_NAMES = {"ci"}
_SAFE_DB_NAME_SUFFIXES = ("_verify_scratch",)

# 이슈 #280 이 검출 대상으로 삼은 불변식: 개인 워크스페이스는 멤버가 1명 이상이어야 한다.
_ORPHAN_QUERY = """
    SELECT w.id, w.workspace_code
    FROM frontend.tn_workspace w
    WHERE w.is_personal
      AND NOT EXISTS (
        SELECT 1 FROM frontend.tn_workspace_member m WHERE m.workspace_id = w.id
      )
"""


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


def _make_user(conn: psycopg.Connection, user_id: str) -> None:
    conn.execute(
        """
        INSERT INTO frontend.tn_user (id, email, name, appr_at, use_at, reg_dt, reg_id, mod_dt, mod_id)
        VALUES (%s, %s, %s, 'Y', 'Y', now(), 'test', now(), 'test')
        """,
        (user_id, f"{user_id}@example.com", user_id),
    )


def _make_workspace(conn: psycopg.Connection, code: str, *, is_personal: bool) -> int:
    row = conn.execute(
        """
        INSERT INTO frontend.tn_workspace (workspace_code, workspace_nm, use_at, is_personal, reg_dt, reg_id, mod_dt, mod_id)
        VALUES (%s, %s, 'Y', %s, now(), 'test', now(), 'test')
        RETURNING id
        """,
        (code, code, is_personal),
    ).fetchone()
    return row[0]


def _insert_member(conn: psycopg.Connection, workspace_id: int, user_id: str) -> None:
    conn.execute(
        """
        INSERT INTO frontend.tn_workspace_member (workspace_id, user_id, role, is_default, reg_dt, reg_id, mod_dt, mod_id)
        VALUES (%s, %s, 'owner', false, now(), 'test', now(), 'test')
        """,
        (workspace_id, user_id),
    )


def _orphan_ids(conn: psycopg.Connection) -> set[int]:
    return {row[0] for row in conn.execute(_ORPHAN_QUERY).fetchall()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--i-know-this-drops-tables",
        action="store_true",
        help="대상 DB 의 frontend 스키마 16개 테이블이 DROP·재생성된다는 것을 확인했다는 명시 동의",
    )
    args = parser.parse_args()

    _assert_safe_target(DB_URL, confirmed=args.i_know_this_drops_tables)
    print(f"개인 워크스페이스 멤버 0 고아 정합성 검사 (대상: {DB_URL.split('@')[-1]})")

    conn = _connect()
    setup_schema(conn)

    # (1) 정상 개인 워크스페이스(멤버 1) — 위반 아님
    _make_user(conn, "u-healthy")
    ws_healthy = _make_workspace(conn, "ws-healthy", is_personal=True)
    _insert_member(conn, ws_healthy, "u-healthy")

    # (2) 정상 공용 워크스페이스(멤버 0) — 이슈 범위 밖, 위반 아님
    ws_shared_empty = _make_workspace(conn, "ws-shared-empty", is_personal=False)

    # (3) 멤버 0 개인 워크스페이스 — 고아 시나리오 직접 시딩(탈퇴 후 정리 누락을 모사)
    ws_orphan = _make_workspace(conn, "ws-orphan", is_personal=True)

    found = _orphan_ids(conn)
    conn.close()

    problems: list[str] = []
    if ws_healthy in found:
        problems.append(f"오탐: 정상 개인 워크스페이스(id={ws_healthy}, 멤버 1)를 고아로 잘못 잡음")
    if ws_shared_empty in found:
        problems.append(f"오탐: 공용 워크스페이스(id={ws_shared_empty}, 멤버 0, is_personal=false)를 잘못 잡음")
    if ws_orphan not in found:
        problems.append(
            f"미탐: 심어 놓은 고아 개인 워크스페이스(id={ws_orphan})를 감사 쿼리가 못 찾음 — "
            "검사 로직 자체가 깨졌다는 뜻(검사 대상 0건 = 통과가 아니라 실패)"
        )

    if problems:
        print("FAIL:")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)

    print(f"  ✓ 정상 개인 워크스페이스 오탐 없음 (id={ws_healthy})")
    print(f"  ✓ 공용 워크스페이스(멤버 0) 오탐 없음 (id={ws_shared_empty})")
    print(f"  ✓ 심어 놓은 고아 개인 워크스페이스 정확히 검출 (id={ws_orphan})")
    print(f"  감사 쿼리 재사용(실제 DB 점검용):\n{_ORPHAN_QUERY}")
    print("모든 검증 통과")


if __name__ == "__main__":
    main()
