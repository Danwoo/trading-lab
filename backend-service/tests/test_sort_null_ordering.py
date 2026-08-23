"""#352 — 격자 정렬이 값 없는 행의 자리를 못박는지 검증.

이 레포는 아직 pytest 를 도입하지 않았으므로 standalone 실행형이다:
    cd backend-service && uv run python tests/test_sort_null_ordering.py

지키는 불변식:
- **정렬 절은 NULL 위치를 항상 적는다.** PostgreSQL 은 `DESC` 에서 NULL 을 가장 큰 값으로 보므로,
  위치를 안 적으면 목표가 내림차순의 1등이 「목표가가 없는 행」이 된다 (#352 재현).
- **호출부의 기본 정렬 절도 같은 규율을 따른다.** 사용자가 열을 안 눌렀을 때 쓰는 문자열이라
  파서를 안 거친다 — 지금은 NOT NULL 컬럼뿐이라 결과가 같지만, nullable 컬럼으로 바뀌는 순간
  같은 함정이 파서 바깥에서 되살아난다.
- **사용자 sort 는 이 파서 말고 다른 길로 SQL 이 되지 않는다.** 한 자리라도 새로 직접 조립하면
  #352 가 그 자리에서만 되살아난다 — 그래서 호출부를 세고, 0건이면 실패한다(fail-closed).

문법 유효성은 stdlib sqlite3 를 독립 심판으로 세워 본다. **의미는 sqlite3 로 못 본다** —
sqlite3 는 NULL 을 가장 작은 값으로 봐서 `x DESC` 만으로도 NULL 이 뒤로 간다. 방언마다 기본이
갈린다는 그 사실이 바로 위치를 명시해야 하는 이유다. PostgreSQL 의 실제 정렬은 backend-service
:8100/:8152 에 같은 요청을 보내 확인했다 (PR 본문의 「재현」·「검증」).
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
_REPOSITORIES_DIR = _APP_DIR / "repositories"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from utils.common.devextreme_utils import parse_sort  # noqa: E402

# 호출부는 전부 `parse_sort(args.get("sort")) or "<기본 정렬 절>"` 한 줄이다 — 사용자 sort 가
# 들어오는 유일한 입구이자, 파서를 안 타는 기본값이 사는 유일한 자리다.
_CALL_SITE_RE = re.compile(r'parse_sort\(\s*args\.get\("sort"\)\s*\)\s*or\s*"([^"]+)"')

# 사용자 sort 를 읽는 표현. 이것이 `parse_sort(...)` 안에 있지 않으면 새 길이 생긴 것이다.
_SORT_ARG = 'args.get("sort")'

# 실측 호출부 수 (2026-08-23, origin/main 449aa5e): 7개 리포지토리에 9곳.
# 줄어들면 실패한다 — 파일이 옮겨지거나 이름이 바뀌어 "대상 없음 = 위반 없음"으로 조용히
# 초록이 되는 것을 막는다. 늘어나는 것은 정상이므로 하한만 본다.
_MIN_CALL_SITES = 9

_NULLS_POSITION_RE = re.compile(r"\bNULLS\s+(FIRST|LAST)$", re.IGNORECASE)


def _terms(order_by: str) -> list[str]:
    return [t.strip() for t in order_by.split(",") if t.strip()]


def _assert_valid_sql(order_by: str) -> None:
    """sqlite3 를 문법 심판으로 세운다 — 의미가 아니라 성립 여부만 본다.

    절이 부르는 컬럼으로 표를 즉석에서 만든다 — 그래야 "컬럼이 없다"가 문법 오류로 오인되지 않는다.
    """
    columns = sorted({term.split()[0] for term in _terms(order_by)})
    assert columns, f"정렬 절에서 컬럼을 못 읽었다: {order_by!r}"
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE t (" + ", ".join(f"{c} TEXT" for c in columns) + ")")
        conn.execute(f"SELECT * FROM t ORDER BY {order_by}")
    finally:
        conn.close()


def test_parse_sort_pins_null_position() -> str:
    """파서가 만드는 모든 절이 NULL 위치를 적는다 — 방향과 개수를 가리지 않는다."""
    cases = [
        [{"selector": "target_price", "desc": True}],
        [{"selector": "target_price", "desc": False}],
        [{"selector": "target_price"}],
        [{"selector": "target_price", "desc": True}, {"selector": "ticker"}],
        '[{"selector":"reg_dt","desc":true}]',
    ]

    checked = 0
    for case in cases:
        clause = parse_sort(case)
        assert clause, f"정렬 절이 비었다: {case!r}"
        _assert_valid_sql(clause)
        for term in _terms(clause):
            assert _NULLS_POSITION_RE.search(term), f"NULL 위치가 없다: {term!r} (입력 {case!r})"
            checked += 1

    # 이 절이 무엇으로 굳었는지 한 자리는 문자 그대로 못박는다 — #352 를 되돌리는 변경이
    # 정규식만 통과하고 지나가지 않게.
    assert parse_sort([{"selector": "target_price", "desc": True}]) == "target_price DESC NULLS LAST"
    assert parse_sort([{"selector": "target_price"}]) == "target_price ASC NULLS LAST"

    assert checked >= 6, f"검사한 정렬 항이 {checked}건 — 대상이 사라졌다 (fail-closed)"
    print(f"     (파서가 만든 정렬 항 {checked}건 검사, 전부 NULL 위치 명시)")
    return "test_parse_sort_pins_null_position"


def test_default_order_by_at_every_call_site_pins_null_position() -> str:
    """호출부의 기본 정렬 절도 NULL 위치를 적는다 — 그리고 호출부가 0건이면 실패한다."""
    assert _REPOSITORIES_DIR.is_dir(), f"검사 대상 디렉터리가 없다 — {_REPOSITORIES_DIR}"

    files = sorted(_REPOSITORIES_DIR.rglob("*.py"))
    assert files, f"검사 대상이 0건 — {_REPOSITORIES_DIR} 아래에 .py 가 없다 (경로가 바뀌었나)"

    found: list[tuple[str, str]] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        for default_order_by in _CALL_SITE_RE.findall(source):
            found.append((path.relative_to(_REPOSITORIES_DIR).as_posix(), default_order_by))

    assert len(found) >= _MIN_CALL_SITES, (
        f"정렬 호출부를 {len(found)}곳 찾았다 — 최소 {_MIN_CALL_SITES}곳이어야 한다 (fail-closed). "
        "옮겼거나 이름을 바꿨다면 이 테스트의 상수도 같이 갱신하라."
    )

    for name, default_order_by in found:
        _assert_valid_sql(default_order_by)
        for term in _terms(default_order_by):
            assert _NULLS_POSITION_RE.search(term), f"{name}: 기본 정렬 절에 NULL 위치가 없다 — {term!r}"

    print(f"     (정렬 호출부 {len(found)}곳 검사: {', '.join(sorted({n for n, _ in found}))})")
    return "test_default_order_by_at_every_call_site_pins_null_position"


def test_user_sort_has_no_second_path_into_sql() -> str:
    """사용자 sort 가 파서를 우회해 SQL 이 되는 자리가 없다."""
    files = sorted(_REPOSITORIES_DIR.rglob("*.py"))
    assert files, f"검사 대상이 0건 — {_REPOSITORIES_DIR}"

    occurrences = 0
    bypassed: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        start = 0
        while (idx := source.find(_SORT_ARG, start)) != -1:
            occurrences += 1
            line_no = source.count("\n", 0, idx) + 1
            head = source.rfind("parse_sort(", 0, idx)
            wrapped = head != -1 and source[head:idx].strip() == "parse_sort("
            if not wrapped:
                bypassed.append(f"{path.relative_to(_REPOSITORIES_DIR).as_posix()}:{line_no}")
            start = idx + len(_SORT_ARG)

    assert occurrences >= _MIN_CALL_SITES, (
        f"`{_SORT_ARG}` 를 {occurrences}곳에서 찾았다 — 최소 {_MIN_CALL_SITES}곳이어야 한다 (fail-closed)."
    )
    assert not bypassed, "사용자 sort 가 parse_sort 를 안 거치고 SQL 로 간다:\n  " + "\n  ".join(bypassed)

    print(f"     (사용자 sort 사용처 {occurrences}곳 검사, 전부 parse_sort 경유)")
    return "test_user_sort_has_no_second_path_into_sql"


def _main() -> int:
    tests = [
        test_parse_sort_pins_null_position,
        test_default_order_by_at_every_call_site_pins_null_position,
        test_user_sort_has_no_second_path_into_sql,
    ]
    failed = []
    for tc in tests:
        try:
            name = tc()
        except AssertionError as exc:
            failed.append(tc.__name__)
            print(f"FAIL {tc.__name__}\n     {exc}")
        else:
            print(f"PASS {name}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
