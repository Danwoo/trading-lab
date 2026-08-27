"""리비전 `0019` 전/후 대조 도구 — 기존 행이 기대한 인스턴트로 옮겨졌는지 행 단위로 본다 (#359).

**마이그레이션을 돌리기 전에 먼저 쓰는 도구다.** 되돌리기 어려운 작업이라, 무엇이 어떻게
바뀔지 숫자로 먼저 보고 판단한다. 리비전 안의 미래 시각 검사는 `src_tz` 를 실제보다 **동쪽**
으로 잡은 오류만 잡는다 — **서쪽** 오류(UTC DB 에 `Asia/Seoul`)는 감사 시각이 9시간 과거로
갈 뿐이라 그 검사에 안 걸린다. 그 자리를 이 도구가 막는다.

사용법 (cwd=backend-service):

  1. `audit [--db-url URL]`
     읽기만 한다. 대상 컬럼마다 행 수와 기원 분포(서버 tz / UTC)를 세고 표본을 보여준다.

  2. `snapshot --out FILE [--db-url URL]`
     마이그레이션 **전**에 대상 행의 PK + naive 값 + 그 값의 기원(=어느 tz 로 읽어야 하는가)을
     JSON 으로 떠 둔다. 기원 판정은 리비전과 **같은 함수**를 import 해서 쓴다 — 두 벌로 두면
     갈린다.

  3. `diff --snapshot FILE [--db-url URL]`
     마이그레이션 **후**에 같은 행을 다시 읽어, `naive AT TIME ZONE <기원 tz>` 로 계산한
     기대 인스턴트와 실제 값을 대조한다. 기대값 계산은 Postgres 에 그대로 물어본다(파이썬으로
     tz 산술을 다시 짜지 않는다 — 두 벌이 갈리면 대조가 거짓이 된다).
     **대조한 셀이 0건이면 실패한다**(fail-closed) — "검사할 게 없어 통과"를 "검사해서 문제
     없음"과 구분한다.

셋 다 읽기 전용이다 — 이 스크립트 자체는 아무것도 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import psycopg

BACKEND = Path(__file__).resolve().parent.parent
REVISION = BACKEND / "alembic" / "versions" / "0019_timestamptz_audit_columns.py"

# 로컬 스택 기본값 — 포트 SoT 는 process-compose.yaml 의 postgres (verify_dev_port_hygiene.py 가 본다).
DB_URL_DEFAULT = "postgresql://fintech:fintech@localhost:5442/fintech"


def _load_revision():
    """리비전 모듈을 직접 읽어 온다 — 파일명이 숫자로 시작해 일반 import 가 안 된다."""
    spec = importlib.util.spec_from_file_location("rev0019", REVISION)
    if spec is None or spec.loader is None:
        raise SystemExit(f"::error::리비전을 읽지 못했다: {REVISION}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REV = _load_revision()


def _targets() -> list[tuple[str, str, tuple[tuple[str, str], ...]]]:
    """(스키마, 테이블, ((컬럼, 기원), ...)) — 리비전의 목록 그대로."""
    return [("public", t, c) for t, c in REV.PUBLIC_COLUMNS] + [("frontend", t, c) for t, c in REV.FRONTEND_COLUMNS]


def _connect(db_url: str) -> psycopg.Connection:
    conn = psycopg.connect(db_url)
    conn.autocommit = True
    return conn


def _server_tz(conn: psycopg.Connection) -> str:
    row = conn.execute("SELECT reset_val FROM pg_settings WHERE name = 'TimeZone'").fetchone()
    if not row or not row[0]:
        raise SystemExit("::error::pg_settings 에서 서버 기본 TimeZone 을 읽지 못했다")
    return str(row[0])


def _table_exists(conn: psycopg.Connection, schema: str, table: str) -> bool:
    return bool(conn.execute("SELECT to_regclass(%s) IS NOT NULL", [f"{schema}.{table}"]).fetchone()[0])


def _primary_key(conn: psycopg.Connection, schema: str, table: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT a.attname
          FROM pg_index i
          JOIN pg_class c ON c.oid = i.indrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY (i.indkey)
         WHERE n.nspname = %s AND c.relname = %s AND i.indisprimary
         ORDER BY array_position(i.indkey, a.attnum)
        """,
        [schema, table],
    ).fetchall()
    return [r[0] for r in rows]


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _origin_tz_of_row(origin: str, row: dict, column: str, src_tz: str) -> str:
    """이 셀의 naive 자릿수를 어느 tz 벽시계로 읽어야 하는가."""
    if origin == REV.UTC:
        return "UTC"
    if origin == REV.SERVER_TZ:
        return src_tz
    if origin == REV.ACTOR:
        actor = row.get("reg_id" if column == "reg_dt" else "mod_id")
        return src_tz if actor in REV.NON_APP_ACTORS else "UTC"
    if origin == REV.ACTOR_VIA_USER:
        return src_tz if row.get("_owner_reg_id") in REV.NON_APP_ACTORS else "UTC"
    raise SystemExit(f"::error::모르는 기원: {origin!r}")


def _select_rows(conn: psycopg.Connection, schema: str, table: str, columns, pk: list[str]) -> list[dict]:
    """PK + 대상 컬럼 + 기원 판정에 필요한 배우 컬럼을 한 번에 읽는다."""
    origins = {origin for _c, origin in columns}
    select = [f"{_quote(c)} AS {_quote(c)}" for c in pk]
    select += [f"{_quote(c)} AS {_quote(c)}" for c, _o in columns]
    if REV.ACTOR in origins:
        select += ['"reg_id" AS "reg_id"', '"mod_id" AS "mod_id"']
    join = ""
    if REV.ACTOR_VIA_USER in origins:
        source = REV.ACTOR_SOURCE_COLUMNS[table]
        select.append(
            f'(SELECT u.reg_id FROM {_quote(schema)}."tn_user" u WHERE u.id = t.{_quote(source)}) AS "_owner_reg_id"'
        )
        join = " t"
    sql = f"SELECT {', '.join(select)} FROM {_quote(schema)}.{_quote(table)}{join}"
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql)
        return cur.fetchall()


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def cmd_audit(args: argparse.Namespace) -> int:
    conn = _connect(args.db_url)
    src_tz = _server_tz(conn)
    print(f"서버 기본 TimeZone(reset_val) = {src_tz} — 리비전의 기본 src_tz 와 같은 값이다\n")
    cells = 0
    for schema, table, columns in _targets():
        if not _table_exists(conn, schema, table):
            print(f"{schema}.{table:24s} — 테이블 없음 (건너뜀)")
            continue
        pk = _primary_key(conn, schema, table)
        rows = _select_rows(conn, schema, table, columns, pk)
        by_tz: dict[str, int] = {}
        for row in rows:
            for column, origin in columns:
                if row[column] is None:
                    continue
                tz = _origin_tz_of_row(origin, row, column, src_tz)
                by_tz[tz] = by_tz.get(tz, 0) + 1
                cells += 1
        spread = " · ".join(f"{tz} {n}" for tz, n in sorted(by_tz.items())) or "값 있는 셀 없음"
        print(f"{schema}.{table:24s} 행 {len(rows):6d}  대상 셀 기원: {spread}")
    print(f"\n합계: 대조 대상 셀 {cells}건")
    if cells == 0:
        print("::error::대상 셀이 0건이다 — DB 연결 대상이 맞는지 확인하라(fail-closed)", file=sys.stderr)
        return 1
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    conn = _connect(args.db_url)
    src_tz = args.src_tz or _server_tz(conn)
    snapshot: dict = {"src_tz": src_tz, "tables": []}
    cells = 0
    for schema, table, columns in _targets():
        if not _table_exists(conn, schema, table):
            continue
        pk = _primary_key(conn, schema, table)
        if not pk:
            raise SystemExit(f"::error::{schema}.{table} 에 기본키가 없다 — 행을 다시 찾을 수 없다")
        entries = []
        for row in _select_rows(conn, schema, table, columns, pk):
            values = {}
            for column, origin in columns:
                if row[column] is None:
                    continue
                values[column] = [_iso(row[column]), _origin_tz_of_row(origin, row, column, src_tz)]
                cells += 1
            if values:
                entries.append({"pk": [str(row[c]) for c in pk], "values": values})
        snapshot["tables"].append({"schema": schema, "table": table, "pk": pk, "rows": entries})

    Path(args.out).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"스냅샷 저장: {args.out} (src_tz={src_tz} · 테이블 {len(snapshot['tables'])}개 · 대상 셀 {cells}건)")
    if cells == 0:
        print("::error::대상 셀이 0건이다 — 스냅샷이 아무것도 안 담았다(fail-closed)", file=sys.stderr)
        return 1
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    conn = _connect(args.db_url)
    checked = 0
    mismatches: list[str] = []

    for spec in snapshot["tables"]:
        schema, table, pk = spec["schema"], spec["table"], spec["pk"]
        if not spec["rows"]:
            continue
        if not _table_exists(conn, schema, table):
            mismatches.append(f"{schema}.{table} — 테이블이 사라짐")
            continue
        where = " AND ".join(f"{_quote(c)}::text = %s" for c in pk)
        columns = sorted({c for row in spec["rows"] for c in row["values"]})
        select = ", ".join(f"{_quote(c)} AS {_quote(c)}" for c in columns)
        for row in spec["rows"]:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute(f"SELECT {select} FROM {_quote(schema)}.{_quote(table)} WHERE {where}", row["pk"])
                current = cur.fetchone()
            if current is None:
                mismatches.append(f"{schema}.{table} [{','.join(row['pk'])}] — 행이 사라짐")
                continue
            for column, (naive_iso, origin_tz) in row["values"].items():
                # 기대값은 Postgres 에게 물어본다 — tz 산술을 파이썬으로 다시 짜면 두 벌이 갈린다.
                expected = conn.execute("SELECT %s::timestamp AT TIME ZONE %s", [naive_iso, origin_tz]).fetchone()[0]
                actual = current[column]
                checked += 1
                if expected != actual:
                    mismatches.append(
                        f"{schema}.{table} [{','.join(row['pk'])}] {column} "
                        f"— naive {naive_iso} 을 {origin_tz} 로 읽으면 {expected} 인데 실제는 {actual}"
                    )

    print(f"대조한 셀 {checked}건 · 어긋난 셀 {len(mismatches)}건")
    for line in mismatches[:40]:
        print(f"  ✗ {line}")
    if len(mismatches) > 40:
        print(f"  … 외 {len(mismatches) - 40}건")
    if checked == 0:
        print("::error::대조한 셀이 0건이다 — 스냅샷이 비었거나 대상이 사라졌다(fail-closed)", file=sys.stderr)
        return 1
    if mismatches:
        print("::error::기존 값이 기대한 인스턴트로 옮겨지지 않았다", file=sys.stderr)
        return 1
    print("모든 셀이 기대한 인스턴트와 일치한다")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", default=DB_URL_DEFAULT)
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="읽기만 — 대상 셀 수와 기원 분포")
    p_audit.set_defaults(func=cmd_audit)

    p_snap = sub.add_parser("snapshot", help="마이그레이션 전 상태를 JSON 으로")
    p_snap.add_argument("--out", required=True)
    p_snap.add_argument(
        "--src-tz", default=None, help="서버 기본값 대신 쓸 tz (리비전의 ALEMBIC_NAIVE_SOURCE_TZ 와 같은 값)"
    )
    p_snap.set_defaults(func=cmd_snapshot)

    p_diff = sub.add_parser("diff", help="마이그레이션 후 대조")
    p_diff.add_argument("--snapshot", required=True)
    p_diff.set_defaults(func=cmd_diff)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
