"""#150 B0 — 봇 마이그레이션과 raw SQL 의 컬럼 이름이 어긋나지 않는지 검증한다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_bot_schema_sql_consistency.py

**왜 이 그물인가**: raw SQL 은 컬럼 이름을 문자열로 적으므로, 마이그레이션과 어긋나도 파이썬은
아무 말이 없고 실패가 **DB 에 붙는 순간까지** 미뤄진다. 이 레포에는 지금 Postgres 가 없어
저장·조회를 실행으로 증명할 수 없으므로(#150 B0 검증 경계), 이름 대조만이라도 정적으로 잡는다.

**이 테스트가 못 잡는 것**: 타입 불일치, 제약 위반, 트랜잭션 경계, SQL 문법. 그건 DB 가 붙어야
드러난다. 여기서 초록이라고 「저장·조회가 된다」는 뜻이 아니다.

검사 대상이 0건이면 실패로 끝난다 — 리팩토링으로 파일이 옮겨가면 조용히 초록이 되는 것을 막는다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "0014_bot.py"
REPOSITORY = ROOT / "app" / "repositories" / "bot" / "bot_repository.py"

BOT_TABLES = ("tn_bot", "tn_bot_strategy")
# 마이그레이션에 없지만 SQL 에 나오는 것 — 별칭·계산 컬럼이라 대조 대상이 아니다.
SQL_ONLY_IDENTIFIERS = {"rn", "cnt"}


def _migration_columns() -> dict[str, set[str]]:
    """`op.create_table("t", sa.Column("c", ...), ...)` 에서 테이블별 컬럼을 뽑는다."""
    source = MIGRATION.read_text(encoding="utf-8")
    columns: dict[str, set[str]] = {}
    for match in re.finditer(r'op\.create_table\(\s*"(?P<table>\w+)"(?P<body>.*?)\n    \)', source, re.S):
        names = set(re.findall(r'sa\.Column\(\s*"(\w+)"', match.group("body")))
        columns[match.group("table")] = names
    return columns


def _sql_blocks() -> list[str]:
    """레포지토리 안의 SQL 문자열 리터럴만 모은다."""
    source = REPOSITORY.read_text(encoding="utf-8")
    blocks = re.findall(r'"""(.*?)"""', source, re.S)
    return [block for block in blocks if re.search(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", block)]


def _referenced_columns(sql: str) -> set[str]:
    """SQL 에서 컬럼처럼 쓰인 식별자를 모은다 — 키워드·함수·바인드 파라미터는 뺀다."""
    # f-string 자리(`{base_sql}`)와 바인드 파라미터(`:workspace_id`)는 컬럼이 아니다.
    cleaned = re.sub(r"\{[^}]*\}", " ", sql)
    cleaned = re.sub(r":\w+", " ", cleaned)
    # 대문자가 섞인 식별자도 잡는다 — `[a-z]` 로만 훑으면 `bot_descX` 같은 오타가 조용히 빠진다.
    words = {word.lower() for word in re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", cleaned)}
    keywords = {
        "select",
        "from",
        "where",
        "and",
        "or",
        "insert",
        "into",
        "values",
        "update",
        "set",
        "delete",
        "order",
        "by",
        "asc",
        "desc",
        "as",
        "cast",
        "float",
        "jsonb",
        "count",
        "row_number",
        "over",
        "to_char",
        "current_timestamp",
        "returning",
        "null",
        "is",
        "not",
        "between",
        "on",
        "a",
        "tb",
        "yyyy",
        "mm",
        "dd",
        "hh24",
        "mi",
        "ss",
    }
    return words - keywords - set(BOT_TABLES) - SQL_ONLY_IDENTIFIERS


def test_migration_declares_both_tables() -> None:
    columns = _migration_columns()
    assert set(columns) == set(BOT_TABLES), f"마이그레이션이 만드는 테이블: {sorted(columns)}"
    for table in BOT_TABLES:
        assert len(columns[table]) >= 5, f"{table} 컬럼이 {len(columns[table])}개다 — 파싱이 깨진 것 아닌가"


def test_repository_sql_columns_exist_in_migration() -> None:
    """SQL 이 부르는 컬럼이 전부 마이그레이션에 있다 — 0건 검사면 실패."""
    columns = _migration_columns()
    known = set().union(*columns.values())
    assert known, "마이그레이션에서 컬럼을 하나도 못 읽었다"

    blocks = _sql_blocks()
    assert len(blocks) >= 5, f"레포지토리에서 SQL 블록을 {len(blocks)}개만 찾았다 — 파일이 옮겨졌나"

    checked = 0
    unknown: set[str] = set()
    for sql in blocks:
        referenced = _referenced_columns(sql)
        checked += len(referenced)
        unknown |= referenced - known
    assert checked > 0, "SQL 에서 컬럼을 하나도 못 읽었다 — 이 그물은 죽어 있다"
    assert not unknown, f"마이그레이션에 없는 컬럼을 SQL 이 부른다: {sorted(unknown)}"
    print(f"     (SQL 블록 {len(blocks)}개 · 컬럼 참조 {checked}건 대조)")


def test_check_constraint_values_match_service_and_schema() -> None:
    """CHECK 제약의 허용값이 스키마·서비스의 목록과 같다 — 한쪽만 늘면 저장이 500 으로 터진다."""
    migration = MIGRATION.read_text(encoding="utf-8")
    schema = (ROOT / "app" / "schemas" / "bot" / "bot_schema.py").read_text(encoding="utf-8")
    service = (ROOT / "app" / "services" / "bot" / "bot_service.py").read_text(encoding="utf-8")

    pairs = [
        ("COMBINE_RULES", "CombineRule", migration, schema),
        ("UNIVERSE_KINDS", "UniverseKind", migration, schema),
        ("BOT_ROLES", "BotRole", migration, schema),
        ("PARAM_SOURCES", "ParamSource", service, schema),
    ]
    for constant, alias, source_a, source_b in pairs:
        declared = set(re.findall(r'"(\w+)"', _assignment(source_a, constant)))
        allowed = set(re.findall(r'"(\w+)"', _assignment(source_b, alias)))
        assert declared, f"{constant} 을 못 읽었다"
        assert declared == allowed, f"{constant}({sorted(declared)}) != {alias}({sorted(allowed)})"


def _assignment(source: str, name: str) -> str:
    match = re.search(rf"^{name}(?::.*?)? = (.*)$", source, re.M)
    assert match, f"{name} 선언을 못 찾았다"
    return match.group(1)


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as error:
            failures += 1
            print(f"FAIL {test.__name__}: {error}")
        else:
            print(f"ok   {test.__name__}")
    print(f"\n{len(tests)}건 검사 · 실패 {failures}건")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
