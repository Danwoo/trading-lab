"""#303 — `getKSTTime()` 쓰기 시프트 보정(alembic 0006_kst_write_shift_correction) 전/후 대조 도구.

**마이그레이션을 실제로 돌리기 전에 먼저 쓰는 도구다** — 되돌리기 어려운 작업이라, 무엇이 바뀌는지
숫자로 먼저 보고 판단한다.

사용법 (cwd=backend-service, `uv run python scripts/kst_timestamp_correction.py <subcommand>`):

  1. `audit [--db-url URL]`
     마이그레이션 없이 **읽기만** 한다. 테이블마다 전체 행 수 / reg_dt 보정 대상 / mod_dt 보정
     대상 건수를 세고, 대상 행 몇 건의 현재값 → 보정 후 예상값 샘플을 출력한다. 대상 판정 로직은
     alembic 리비전과 동일한 함수(`_eligible`)를 그대로 재사용한다 — 두 벌로 두면 갈린다.

  2. `snapshot --out FILE [--db-url URL]`
     마이그레이션 적용 **전** 대상 테이블의 PK + reg_dt/mod_dt/reg_id/mod_id 를 JSON 으로 떠 둔다.

  3. `diff --snapshot FILE [--db-url URL]`
     마이그레이션 적용 **후** 같은 행을 다시 읽어, 스냅샷 시점 판정대로 보정됐어야 할 값과 실제
     현재값이 정확히 일치하는지 행 단위로 대조한다. 판정 대상이 0건이면 실패한다(fail-closed) —
     "검사할 게 없어 통과"를 "검사해서 문제없음"과 구분한다.

셋 다 읽기 전용이다(diff 도 SELECT 만 한다) — 이 스크립트 자체는 아무것도 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import psycopg

# 대상 테이블은 frontend 스키마(Prisma 소유)라 커넥션 search_path 를 그쪽으로 돌린다.
# 쿼리 파라미터 값 안의 `=` 는 반드시 `%3D` 로 인코딩한다 — 날것의 `=` 는 libpq URI 파서가
# "extra key/value separator" 로 거절해 접속 전에 죽는다.
DB_URL_DEFAULT = "postgresql://fintech:fintech@localhost:5442/fintech?options=-csearch_path%3Dfrontend"

# alembic/versions/0006_kst_write_shift_correction.py 와 반드시 같은 값을 쓴다 — 갈리면 감사·스냅샷이
# 실제 마이그레이션이 보정하는 행과 다른 행을 본다.
_NON_APP_ACTORS = ("MGR", "migration")
_SHIFT = timedelta(hours=9)

# (테이블, PK 컬럼 목록, reg_id/mod_id 컬럼 보유 여부)
TABLES: list[tuple[str, list[str], bool]] = [
    ("tn_user", ["id"], True),
    ("tn_workspace", ["id"], True),
    ("tn_workspace_member", ["workspace_id", "user_id"], True),
    ("tn_workspace_menu", ["workspace_id", "menu_id"], True),
    ("tn_workspace_domain", ["domain"], True),
    ("tn_author", ["author_id"], True),
    ("tn_author_member", ["author_id", "user_id"], True),
    ("tn_author_menu", ["author_id", "menu_id"], True),
    ("tn_menu", ["menu_id"], True),
    ("tc_group_code", ["group_code"], True),
    ("tc_code", ["group_code", "code"], True),
    ("th_email_log", ["id"], False),
]


def _eligible(actor: str | None) -> bool:
    """reg_id/mod_id 값 하나가 getKSTTime() 앱 쓰기 경로로 보이면 True (보정 대상)."""
    return actor is None or actor not in _NON_APP_ACTORS


def _connect(db_url: str) -> psycopg.Connection:
    conn = psycopg.connect(db_url)
    conn.autocommit = True
    return conn


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _from_iso(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s is not None else None


def cmd_audit(args: argparse.Namespace) -> None:
    conn = _connect(args.db_url)
    total_reg_eligible = 0
    total_mod_eligible = 0
    for table, pk_cols, has_actors in TABLES:
        total = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        if not has_actors:
            reg_eligible = total  # th_email_log — 조건 없이 전체
            mod_eligible = 0  # mod_dt 컬럼 자체가 없음
        else:
            rows = conn.execute(f"SELECT reg_id, mod_id FROM {table}").fetchall()
            reg_eligible = sum(1 for reg_id, _ in rows if _eligible(reg_id))
            mod_eligible = sum(1 for _, mod_id in rows if _eligible(mod_id))
        total_reg_eligible += reg_eligible
        total_mod_eligible += mod_eligible
        print(f"{table:24s} 전체 {total:5d}  reg_dt 보정대상 {reg_eligible:5d}  mod_dt 보정대상 {mod_eligible:5d}")

        # 대상이 있으면 최대 2건 표본으로 현재값 → 예상 보정값을 보여준다.
        if has_actors and (reg_eligible or mod_eligible):
            pk_list = ", ".join(pk_cols)
            sample = conn.execute(
                f"SELECT {pk_list}, reg_id, reg_dt, mod_id, mod_dt FROM {table} "
                f"WHERE reg_dt IS NOT NULL OR mod_dt IS NOT NULL LIMIT 2"
            ).fetchall()
            for row in sample:
                pk_vals = row[: len(pk_cols)]
                reg_id, reg_dt, mod_id, mod_dt = row[len(pk_cols) :]
                pk_str = ",".join(str(v) for v in pk_vals)
                reg_note = f"reg_dt {reg_dt} → {reg_dt - _SHIFT if reg_dt and _eligible(reg_id) else reg_dt}"
                mod_note = f"mod_dt {mod_dt} → {mod_dt - _SHIFT if mod_dt and _eligible(mod_id) else mod_dt}"
                print(f"    표본 [{pk_str}] {reg_note} | {mod_note}")

    print(f"\n합계: reg_dt 보정 대상 {total_reg_eligible}건 · mod_dt 보정 대상 {total_mod_eligible}건")
    if total_reg_eligible == 0 and total_mod_eligible == 0:
        print(
            "보정 대상이 0건입니다 — DB 가 비어있거나 이미 보정됐을 수 있습니다. 마이그레이션 전에 원인을 확인하세요."
        )


def cmd_snapshot(args: argparse.Namespace) -> None:
    conn = _connect(args.db_url)
    snapshot: dict[str, list[dict]] = {}
    total_rows = 0
    for table, pk_cols, has_actors in TABLES:
        pk_list = ", ".join(pk_cols)
        if has_actors:
            rows = conn.execute(f"SELECT {pk_list}, reg_id, reg_dt, mod_id, mod_dt FROM {table}").fetchall()
            entries = []
            for row in rows:
                pk_vals = row[: len(pk_cols)]
                reg_id, reg_dt, mod_id, mod_dt = row[len(pk_cols) :]
                entries.append(
                    {
                        "pk": [str(v) for v in pk_vals],
                        "reg_id": reg_id,
                        "reg_dt": _iso(reg_dt),
                        "mod_id": mod_id,
                        "mod_dt": _iso(mod_dt),
                    }
                )
        else:
            rows = conn.execute(f"SELECT {pk_list}, reg_dt FROM {table}").fetchall()
            entries = [{"pk": [str(v) for v in row[: len(pk_cols)]], "reg_dt": _iso(row[-1])} for row in rows]
        snapshot[table] = entries
        total_rows += len(entries)

    Path(args.out).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"스냅샷 저장: {args.out} (테이블 {len(TABLES)}개 · 행 {total_rows}건)")
    if total_rows == 0:
        print("행이 0건입니다 — DB 연결 대상을 다시 확인하세요.", file=sys.stderr)
        sys.exit(1)


def cmd_diff(args: argparse.Namespace) -> None:
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    conn = _connect(args.db_url)

    checked = 0
    mismatches: list[str] = []

    for table, pk_cols, has_actors in TABLES:
        entries = snapshot.get(table, [])
        where_pk = " AND ".join(f"{c} = %s" for c in pk_cols)

        for entry in entries:
            pk_vals = entry["pk"]
            if has_actors:
                row = conn.execute(f"SELECT reg_dt, mod_dt FROM {table} WHERE {where_pk}", pk_vals).fetchone()
                if row is None:
                    mismatches.append(f"{table} [{','.join(pk_vals)}] — 행이 사라짐")
                    continue
                current_reg_dt, current_mod_dt = row

                expected_reg_dt = _from_iso(entry["reg_dt"])
                if expected_reg_dt is not None and _eligible(entry["reg_id"]):
                    expected_reg_dt = expected_reg_dt - _SHIFT
                if expected_reg_dt != current_reg_dt:
                    mismatches.append(
                        f"{table} [{','.join(pk_vals)}] reg_dt 기대 {expected_reg_dt} 실제 {current_reg_dt}"
                    )
                checked += 1

                expected_mod_dt = _from_iso(entry["mod_dt"])
                if expected_mod_dt is not None and _eligible(entry["mod_id"]):
                    expected_mod_dt = expected_mod_dt - _SHIFT
                if expected_mod_dt != current_mod_dt:
                    mismatches.append(
                        f"{table} [{','.join(pk_vals)}] mod_dt 기대 {expected_mod_dt} 실제 {current_mod_dt}"
                    )
                checked += 1
            else:
                row = conn.execute(f"SELECT reg_dt FROM {table} WHERE {where_pk}", pk_vals).fetchone()
                if row is None:
                    mismatches.append(f"{table} [{','.join(pk_vals)}] — 행이 사라짐")
                    continue
                (current_reg_dt,) = row
                expected_reg_dt = _from_iso(entry["reg_dt"])
                if expected_reg_dt is not None:
                    expected_reg_dt = expected_reg_dt - _SHIFT  # th_email_log 는 무조건 대상
                if expected_reg_dt != current_reg_dt:
                    mismatches.append(
                        f"{table} [{','.join(pk_vals)}] reg_dt 기대 {expected_reg_dt} 실제 {current_reg_dt}"
                    )
                checked += 1

    print(f"대조 완료: {checked}건 검사 · 불일치 {len(mismatches)}건")
    if checked == 0:
        print("검사 대상이 0건입니다 — 스냅샷이 비었거나 테이블명이 갈렸을 수 있습니다.", file=sys.stderr)
        sys.exit(1)
    if mismatches:
        print("불일치 목록 (최대 20건):", file=sys.stderr)
        for m in mismatches[:20]:
            print(f"  ✗ {m}", file=sys.stderr)
        sys.exit(1)
    print("✓ 모든 대상 행이 스냅샷 기반 기대값과 정확히 일치합니다.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--db-url",
        default=os.environ.get("KST_TIMESTAMP_DB_URL", DB_URL_DEFAULT),
        help="접속 대상 (기본: %(default)s, 환경변수 KST_TIMESTAMP_DB_URL 로도 지정 가능)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("audit", help="마이그레이션 없이 대상 건수·표본만 본다 (읽기 전용)")

    p_snap = sub.add_parser("snapshot", help="마이그레이션 전 대상 행을 JSON 으로 뜬다")
    p_snap.add_argument("--out", required=True, help="스냅샷 저장 경로")

    p_diff = sub.add_parser("diff", help="마이그레이션 후 스냅샷과 실제값을 대조한다")
    p_diff.add_argument("--snapshot", required=True, help="snapshot 이 만든 JSON 경로")

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    {"audit": cmd_audit, "snapshot": cmd_snapshot, "diff": cmd_diff}[args.command](args)


if __name__ == "__main__":
    main()
