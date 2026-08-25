"""#294 — parse_filter 가 만드는 WHERE 절의 바인드 규율·문법 유효성 검증.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    cd backend-service && uv run python tests/test_devextreme_filter_parser.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식:
- **바인드 이름은 형제끼리 겹치지 않는다.** 겹치면 뒤에 온 값이 앞의 조건을 덮어써, 오류 없이
  조용히 다른 행이 나온다 (3단 중첩에서 `priority = 1` 이 `priority = 'KOSPI'` 가 되던 것).
- **생성된 WHERE 는 SQL 파서를 통과한다.** 논리 연산자가 빠진 그룹이 피연산자를 나란히 붙여
  문법 오류 SQL 을 만들지 않는다.
- **부정을 조용히 잃지 않는다.** `["!", …]` 가 문법에 없는 형태면 통과시키지 말고 400 으로 거절한다.
- **파서 사본은 갈리지 않는다.** 서비스가 늘어 사본이 생기면 바이트 동일해야 한다 — 한 벌만
  고치면 같은 filter JSON 이 서비스마다 다른 SQL 이 된다.

문법 유효성은 **stdlib sqlite3 를 독립 심판으로** 세워 확인한다 — 기대 문자열과의 일치는
"내가 기대한 대로 나왔다"까지고, 그 문자열이 SQL 로서 성립하는지는 말해주지 않는다.
sqlite3 는 방언이 다르므로 `ILIKE` 는 `LIKE` 로 바꿔 **문법만** 본다(의미 검증 아님).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
_REPO_ROOT = _TESTS_DIR.parent.parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.exceptions import BadRequestError  # noqa: E402
from utils.common.devextreme_utils import (  # noqa: E402
    _MAX_FILTER_DEPTH,
    build_filter_params,
    parse_filter,
    parse_filter_sort,
    parse_sort,
)

_BIND_RE = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")

# sqlite3 심판이 쓸 더미 테이블의 컬럼 — 아래 케이스에 등장하는 필드 전부.
_PROBE_COLUMNS = ("a", "b", "c", "d", "memo", "priority", "market")


def _sql_syntax_error(sql: str, params: dict) -> str | None:
    """sqlite3 가 이 WHERE 절을 파싱하고 바인드를 전부 해소하면 None, 아니면 오류 문구."""
    if not sql:
        return None
    probe_sql = sql.replace(" ILIKE ", " LIKE ")
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(f"CREATE TABLE probe ({', '.join(_PROBE_COLUMNS)})")
        conn.execute(f"SELECT 1 FROM probe WHERE {probe_sql}", params).fetchall()
        return None
    except sqlite3.Error as exc:
        return f"{type(exc).__name__}: {exc}"
    finally:
        conn.close()


def _duplicate_binds(sql: str) -> list[str]:
    """WHERE 절에 두 번 이상 등장하는 바인드 이름 — 형제 조건이 서로를 덮어쓴 흔적."""
    names = _BIND_RE.findall(sql)
    return sorted({name for name in names if names.count(name) > 1})


def _assert_well_formed(label: str, expr) -> tuple[str, dict]:
    """어떤 표현식이든 지켜야 하는 것: 바인드 중복 없음 · SQL 파싱됨 · 바인드 전량 해소."""
    sql, params = parse_filter(expr)

    duplicated = _duplicate_binds(sql)
    assert not duplicated, f"[{label}] 바인드 이름 재사용 {duplicated}: {sql}"

    unresolved = sorted(set(_BIND_RE.findall(sql)) - set(params))
    assert not unresolved, f"[{label}] 값 없는 바인드 {unresolved}: {sql} / {params}"

    error = _sql_syntax_error(sql, params)
    assert error is None, f"[{label}] SQL 이 파서를 통과하지 못함 — {error}\n  {sql}\n  {params}"

    return sql, params


# ── #294 본체: 바인드 이름 충돌 ────────────────────────────────────────────────

_ISSUE_REPRO = [[["memo", "isblank", None], "and", ["priority", "=", 1]], "and", ["market", "=", "KOSPI"]]


def test_issue_repro_keeps_both_conditions() -> str:
    """이슈의 재현 입력이 서로 다른 두 바인드를 만들고 `priority = 1` 을 보존한다."""
    sql, params = _assert_well_formed("issue repro", _ISSUE_REPRO)

    assert sorted(params.values(), key=str) == [1, "KOSPI"], f"조건 값이 유실됨: {params}"
    assert len(params) == 2, f"바인드가 {len(params)} 개 — 두 조건이 한 이름을 나눠 씀: {params}"

    priority_bind = re.search(r"priority = :(\w+)", sql)
    market_bind = re.search(r"market = :(\w+)", sql)
    assert priority_bind and market_bind, f"두 조건이 SQL 에 다 남아 있지 않다: {sql}"
    assert priority_bind.group(1) != market_bind.group(1), f"두 조건이 같은 바인드를 가리킨다: {sql}"
    assert params[priority_bind.group(1)] == 1, f"priority 가 {params[priority_bind.group(1)]!r} 로 바뀜"
    assert params[market_bind.group(1)] == "KOSPI", f"market 가 {params[market_bind.group(1)]!r} 로 바뀜"
    return "test_issue_repro_keeps_both_conditions"


def test_deep_nesting_never_reuses_a_bind_name() -> str:
    """값 없는 연산자를 품은 3단·4단 중첩에서도 형제가 바인드를 나눠 쓰지 않는다."""
    blank = ["memo", "isblank", None]
    not_blank = ["memo", "isnotblank", None]
    cases = [
        ("3단 · isblank 선행", _ISSUE_REPRO),
        ("3단 · isblank 후행", [[["priority", "=", 1], "and", blank], "and", ["market", "=", "KOSPI"]]),
        ("3단 · 값없음 둘", [[blank, "and", not_blank], "and", ["market", "=", "KOSPI"]]),
        (
            "4단 · isblank 최심부",
            [[[blank, "and", ["a", "=", 1]], "and", ["b", "=", 2]], "and", ["c", "=", 3]],
        ),
        (
            "4단 · 좌우 균형",
            [
                [[blank, "and", ["a", "=", 1]], "or", [["b", "=", 2], "and", not_blank]],
                "and",
                [["c", "=", 3], "or", ["d", "=", 4]],
            ],
        ),
        ("3단 · between 혼합", [[["a", "between", [1, 2]], "and", blank], "and", ["b", "=", 3]]),
        ("3단 · in 혼합", [[["a", "in", [1, 2, 3]], "and", blank], "and", ["b", "=", 4]]),
        ("3단 · 부정 감싼 그룹", [["!", [blank, "and", ["a", "=", 1]]], "and", ["b", "=", 2]]),
        ("4단 · 부정 중첩", ["!", [[blank, "and", ["a", "=", 1]], "and", ["b", "=", 2]]]),
    ]

    for label, expr in cases:
        sql, params = _assert_well_formed(label, expr)
        literals = _leaf_literals(expr)
        assert sorted(params.values(), key=str) == sorted(literals, key=str), (
            f"[{label}] 조건 값이 {sorted(params.values(), key=str)} — 기대 {sorted(literals, key=str)}\n  {sql}"
        )

    assert len(cases) == 9, f"중첩 케이스가 {len(cases)} 건 — 목록이 줄었다"
    return "test_deep_nesting_never_reuses_a_bind_name"


def _leaf_literals(expr) -> list:
    """표현식 안의 잎 조건이 바인드로 내보내야 하는 값 전부 (기대값을 손으로 안 세도 되게)."""
    if not isinstance(expr, list):
        return []
    if len(expr) == 3 and isinstance(expr[0], str) and expr[0] != "!":
        _, op, value = expr
        if op in ("isblank", "isnotblank"):
            return []
        if op in ("between", "in", "anyof", "notin", "noneof"):
            return list(value) if isinstance(value, list) else [value]
        return [value]
    return [literal for item in expr for literal in _leaf_literals(item)]


# ── 인접 결함 M-9: 논리 연산자가 빠진 그룹 ────────────────────────────────────


def test_group_without_logical_operator_stays_valid_sql() -> str:
    """연산자가 없거나 and/or 가 아닌 값이 끼어도 피연산자를 나란히 붙이지 않는다."""
    cases = [
        ("연산자 자리에 숫자", [["a", "=", 1], 5, ["b", "=", 2]]),
        ("연산자 자체가 없음", [["a", "=", 1], ["b", "=", 2]]),
        ("연산자 없이 셋", [["a", "=", 1], ["b", "=", 2], ["c", "=", 3]]),
        ("빈 자식이 앞에", [[], "and", ["a", "=", 1]]),
        ("빈 자식이 뒤에", [["a", "=", 1], "and", []]),
        ("빈 자식이 가운데", [["a", "=", 1], "and", [], "and", ["b", "=", 2]]),
    ]
    for label, expr in cases:
        _assert_well_formed(label, expr)

    sql, _ = parse_filter([["a", "=", 1], 5, ["b", "=", 2]])
    assert sql == "(a = :filter_param_0 AND b = :filter_param_1)", f"연산자 누락 시 AND 결합이 아님: {sql}"

    # #306 의 파급: 빈 배열은 이제 "제약 없음"(조용히 건너뜀)이 아니라 "항상 거짓"이라, 그룹의
    # 자식으로 와도 형제를 무효화한다 — top-level 과 중첩 안에서 뜻이 갈리면 그 자체가 새 발산이다.
    sql, _ = parse_filter([[], "and", ["a", "=", 1]])
    assert sql == "((1 = 0) AND a = :filter_param_0)", f"빈 자식이 더 이상 항상 거짓으로 안 읽힘: {sql}"

    assert len(cases) == 6, f"M-9 케이스가 {len(cases)} 건 — 목록이 줄었다"
    return "test_group_without_logical_operator_stays_valid_sql"


# ── 인접 결함 M-10: 문법에 없는 `!` 형태 ──────────────────────────────────────


def test_negation_with_extra_terms_is_rejected_not_dropped() -> str:
    """`!` 뒤에 항이 더 붙은 형태는 400 — 조용히 부정을 버리고 통과시키지 않는다."""
    malformed = [
        ["!", ["a", "=", 1], "and", ["b", "=", 2]],
        ["!", ["a", "=", 1], "or", ["b", "=", 2]],
        ["!", ["a", "=", 1], "and", ["b", "=", 2], "and", ["c", "=", 3]],
        ["!", "a", "=", 1],
        ["!", ["a", "=", 1], "and"],
    ]
    for expr in malformed:
        try:
            sql, params = parse_filter(expr)
        except BadRequestError:
            continue
        raise AssertionError(f"{expr!r} 이 거절되지 않고 {sql!r} / {params!r} 로 통과했다")

    assert len(malformed) == 5, f"M-10 케이스가 {len(malformed)} 건 — 목록이 줄었다"

    # 문법 안의 부정은 그대로 통과해야 한다 — 거절이 정상 경로를 갉아먹지 않는지 대조.
    sql, params = parse_filter(["!", ["a", "=", 1]])
    assert sql == "NOT a = :filter_param_0", f"정상 부정이 {sql!r} 로 바뀜"
    assert params == {"filter_param_0": 1}, f"정상 부정의 바인드가 {params!r}"

    # `["!"]` 는 DevExtreme 이 "아무것도 안 맞음" 뜻으로 실제 회선에 올리는 형태다
    # (검색 패널이 검색 가능한 컬럼을 못 찾을 때 · combineFilters 의 and 단축).
    # 거절 대상이 아니다 — 그리고 이제 "필터 없음"(전건)이 아니라 "항상 거짓"으로 읽는다 (#306).
    assert parse_filter(["!"]) == ("(1 = 0)", {}), '`["!"]` 처리가 바뀌었다 — 도달 가능한 형태다'
    return "test_negation_with_extra_terms_is_rejected_not_dropped"


# ── 인접 결함 M-2: 그룹 안 and/or 혼용 (#295) ─────────────────────────────────


def test_mixed_logical_operators_in_flat_group_rejected() -> str:
    """`[A,"and",B,"or",C]` 처럼 한 그룹 안에 and 와 or 가 섞이면 400 — DevExtreme 자신의
    필터 컴파일러(m_utils.js compileGroup)도 같은 입력에 E4019 를 던진다. 예전엔 파이썬이
    SQL 의 AND-우선 규칙에 기대 "(A AND B OR C)" 를 조용히 냈는데, frontend/lib/grid/
    filters.ts 는 마지막 연산자가 이기는 `{OR:[A,B,C]}` 를 냈다 — 같은 입력이 경로에 따라
    다른 뜻이 됐다. 문법에 없는 입력이니 양쪽 다 거절한다."""
    malformed = [
        [["a", "=", 1], "and", ["b", "=", 2], "or", ["c", "=", 3]],
        [["a", "=", 1], "or", ["b", "=", 2], "and", ["c", "=", 3]],
        [["a", "=", 1], "and", ["b", "=", 2], "and", ["c", "=", 3], "or", ["d", "=", 4]],
    ]
    for expr in malformed:
        try:
            sql, params = parse_filter(expr)
        except BadRequestError:
            continue
        raise AssertionError(f"{expr!r} 이 거절되지 않고 {sql!r} / {params!r} 로 통과했다")
    assert len(malformed) == 3, f"M-2 케이스가 {len(malformed)} 건 — 목록이 줄었다"

    # 균일한 연산자(전부 and 거나 전부 or)는 그대로 통과해야 한다 — 거절이 정상 경로를 갉아먹지 않는지 대조.
    sql, _ = parse_filter([["a", "=", 1], "and", ["b", "=", 2], "and", ["c", "=", 3]])
    assert sql == "(a = :filter_param_0 AND b = :filter_param_1 AND c = :filter_param_2)", (
        f"균일 and 체인이 거절 로직에 걸렸다: {sql}"
    )
    return "test_mixed_logical_operators_in_flat_group_rejected"


# ── 회귀 0: 이미 옳던 형태는 그대로 ───────────────────────────────────────────


def test_supported_shapes_are_unchanged() -> str:
    """문법 안의 형태가 내는 SQL·바인드는 그대로다 (바인드 번호만 빈틈 없이 이어진다)."""
    expected = [
        (["a", "=", 1], "a = :filter_param_0", {"filter_param_0": 1}),
        (["a", "=", None], "a IS NULL", {"filter_param_0": None}),
        (["a", "<>", 1], "a <> :filter_param_0", {"filter_param_0": 1}),
        (["a", "contains", "x%y"], "a ILIKE :filter_param_0", {"filter_param_0": "%x\\%y%"}),
        (
            ["a", "between", [1, 2]],
            "(a BETWEEN :filter_param_0_start AND :filter_param_0_end)",
            {"filter_param_0_start": 1, "filter_param_0_end": 2},
        ),
        (
            ["a", "in", [1, 2]],
            "a IN (:filter_param_0_0, :filter_param_0_1)",
            {"filter_param_0_0": 1, "filter_param_0_1": 2},
        ),
        (["a", "in", []], "(1 = 0)", {}),
        (["a", "noneof", []], "(1 = 1)", {}),
        (["a", "isblank", None], "(a IS NULL OR a = '')", {}),
        (["a", "isnotblank", None], "(a IS NOT NULL AND a <> '')", {}),
        (["!", ["a", "=", 1]], "NOT a = :filter_param_0", {"filter_param_0": 1}),
        (
            ["!", [["a", "=", 1], "or", ["b", "=", 2]]],
            "NOT (a = :filter_param_0 OR b = :filter_param_1)",
            {"filter_param_0": 1, "filter_param_1": 2},
        ),
        (
            [["a", "=", 1], "and", ["b", "=", 2]],
            "(a = :filter_param_0 AND b = :filter_param_1)",
            {"filter_param_0": 1, "filter_param_1": 2},
        ),
        (
            [["a", "=", 1], "or", ["b", "=", 2]],
            "(a = :filter_param_0 OR b = :filter_param_1)",
            {"filter_param_0": 1, "filter_param_1": 2},
        ),
        (
            [[["a", "=", 1], "or", ["b", "=", 2]], "and", ["c", "=", 3]],
            "((a = :filter_param_0 OR b = :filter_param_1) AND c = :filter_param_2)",
            {"filter_param_0": 1, "filter_param_1": 2, "filter_param_2": 3},
        ),
        ([["a", "=", 1]], "(a = :filter_param_0)", {"filter_param_0": 1}),
        # 빈 배열은 "필터 없음"(전건)이 아니라 "항상 거짓"이다 — DevExtreme 이 검색 패널에서
        # "아무것도 안 맞음" 뜻으로 실제로 이 형태를 회선에 올린다 (#306).
        ([], "(1 = 0)", {}),
        # 파싱 가능한 JSON 문자열은 그대로 통과한다. 읽을 수 없는 문자열("not json")은 여기
        # 있었지만 ""(제약 없음 = 전건)를 기대하던 항목이라 #389 에서 거절로 옮겼다 —
        # test_malformed_filter_is_rejected_not_swallowed 참조.
        (
            '[["a","=",1],"and",["b","=",2]]',
            "(a = :filter_param_0 AND b = :filter_param_1)",
            {"filter_param_0": 1, "filter_param_1": 2},
        ),
    ]
    for expr, want_sql, want_params in expected:
        sql, params = parse_filter(expr)
        assert sql == want_sql, f"{expr!r}\n  기대 {want_sql!r}\n  실제 {sql!r}"
        assert params == want_params, f"{expr!r}\n  기대 {want_params!r}\n  실제 {params!r}"

    assert len(expected) == 18, f"회귀 케이스가 {len(expected)} 건 — 목록이 줄었다"
    return "test_supported_shapes_are_unchanged"


def test_malformed_filter_is_rejected_not_swallowed() -> str:
    """#389 — 형식이 깨진 필터를 "필터 없음"으로 삼키면 전건이 나간다.

    라우터가 실제로 부르는 종단 경로(`build_filter_params`)로 검사한다 — 파서가 옳아도
    소비자가 빈 SQL 을 "제약 없음"으로 읽으면 결과는 같으므로(#306 에서 겪은 갈림).
    `BadRequestError`(400) 가 아닌 예외는 전역 처리기를 타고 500 이 되므로 따로 가른다:
    `["a", ["="], 1]` 이 정확히 그 경우였다(TypeError: unhashable type: 'list').
    """
    malformed = [
        ["a", ["="], 1],
        ["a", None, 1],
        ["a", 5, 1],
        ["and"],
        ["a", "="],
        [1, "=", 1],
        ["a", "=", 1, "and", 2],
        ["!", "x"],
        ["a", "=", 1, "and"],
        ["and", ["a", "=", 1]],
        "{not json",
        {"a": 1},
    ]
    leaked, crashed = [], []
    for expr in malformed:
        try:
            sql_where, params = build_filter_params({"filter": expr})
        except BadRequestError:
            continue
        except Exception as exc:  # noqa: BLE001 — 400 이 아닌 것은 전부 500 클래스다
            crashed.append(f"{expr!r} → {type(exc).__name__}: {exc}")
            continue
        leaked.append(f"{expr!r} → sql_where={sql_where!r} / params={params!r}")

    assert not crashed, "클라이언트 입력이 서버 오류(500)가 됐다:\n" + "\n".join(f"  {c}" for c in crashed)
    assert not leaked, "형식 오류가 거절되지 않았다(전건 반환 위험):\n" + "\n".join(f"  {line}" for line in leaked)
    assert len(malformed) == 12, f"#389 케이스가 {len(malformed)} 건 — 목록이 줄었다"

    # 거절 로직이 정상 경로를 갉아먹지 않는지 대조 — 필터가 아예 없으면 제약도 없다.
    assert build_filter_params({}) == ("", {}), "필터 파라미터가 없을 때 제약이 생겼다"

    print(f"     (#389 형식 오류 {len(malformed)}건 — 전부 400)")
    return "test_malformed_filter_is_rejected_not_swallowed"


def test_unsupported_operator_still_rejected() -> str:
    """모르는 연산자는 400 그대로 — 거절 경로가 살아 있는지 대조."""
    for expr in (["a", "like", "x"], [["a", "=", 1], "and", ["b", "wat", 2]]):
        try:
            parse_filter(expr)
        except BadRequestError:
            continue
        raise AssertionError(f"{expr!r} 이 거절되지 않았다")

    for expr in (["a; DROP TABLE t", "=", 1], [["1bad", "=", 1], "and", ["b", "=", 2]]):
        try:
            parse_filter(expr)
        except BadRequestError:
            continue
        raise AssertionError(f"{expr!r} 의 필드명 검증이 뚫렸다")
    return "test_unsupported_operator_still_rejected"


# ── 세 벌 lockstep ────────────────────────────────────────────────────────────


def test_python_parser_copies_stay_identical() -> str:
    """파서를 복사해 쓰는 서비스가 늘면 사본끼리 바이트 동일해야 한다 —
    한 벌만 고치면 같은 filter JSON 이 서비스마다 다른 SQL 이 된다."""
    copies = sorted(_REPO_ROOT.glob("*/app/utils/common/devextreme_utils.py"))
    assert copies, f"검사 대상이 0건 — {_REPO_ROOT} 아래에서 파서를 못 찾았다 (경로가 바뀌었나)"

    digests = {
        path.relative_to(_REPO_ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in copies
    }
    unique = set(digests.values())
    assert len(unique) == 1, "파서 사본이 갈렸다:\n" + "\n".join(f"  {name}  {d[:12]}" for name, d in digests.items())

    print(f"     (파서 사본 {len(copies)}벌 대조: {', '.join(digests)})")
    return "test_python_parser_copies_stay_identical"


def test_client_input_never_becomes_a_server_error() -> str:
    """클라이언트가 보낸 값 하나가 500 이 되지 않는다 (#401).

    두 축을 본다 — 둘 다 `BadRequestError`(400) 로 접혀야 하고, 그 밖의 예외는 전역 처리기를
    타 500 이 된다(`RecursionError` 는 `RuntimeError` 서브클래스라 handle_runtime_error 로 간다).

    ① 표현식 재귀 깊이 — `_MAX_FILTER_DEPTH`. 상한 값은 frontend/lib/devextreme/filters.ts 의
       `MAX_FILTER_DEPTH` 와 같아야 하고, 그 대조는 공유 fixture(#401 케이스 쌍)가 한다.
    ② JSON 디코딩 재귀 — `json.loads` 자신이 약 1만 단에서 던진다(실측: 견디는 최대 9997).
       ①의 상한은 표현식 파싱에만 걸리므로 그보다 앞 단계인 이 층을 못 막는다.
    """

    def alternating(depth: int):
        node = ["a", "=", 1]
        for i in range(1, depth):
            node = ["!", node] if i % 2 else [node, "and", ["b", "=", 2]]
        return node

    checked = 0

    # ① 상한과 같은 깊이는 통과, 한 단 넘기면 400 — 부정 체인·그룹 중첩·둘의 교대 셋 다 본다.
    def not_chain(depth: int):
        node = ["a", "=", 1]
        for _ in range(1, depth):
            node = ["!", node]
        return node

    def group_chain(depth: int):
        node = ["a", "=", 1]
        for _ in range(1, depth):
            node = [node, "and", ["b", "=", 2]]
        return node

    for shape in (not_chain, group_chain, alternating):
        parse_filter(shape(_MAX_FILTER_DEPTH))  # 던지면 여기서 실패한다
        checked += 1
        try:
            parse_filter(shape(_MAX_FILTER_DEPTH + 1))
        except BadRequestError:
            checked += 1
        else:
            raise AssertionError(f"{shape.__name__}: 상한을 넘겼는데 통과했다")

    # 형제 가지 안에서 깊어져도 같다 — 깊이 카운터가 형제끼리 새면 여기서 드러난다.
    try:
        parse_filter([["a", "=", 1], "and", alternating(_MAX_FILTER_DEPTH)])
    except BadRequestError:
        checked += 1
    else:
        raise AssertionError("형제 가지 안의 초과 깊이를 통과시켰다")

    # 라우터가 실제로 부르는 진입점(build_filter_params)에서도 같은 판정이어야 한다.
    try:
        build_filter_params({"filter": alternating(_MAX_FILTER_DEPTH + 1)})
    except BadRequestError:
        checked += 1
    else:
        raise AssertionError("build_filter_params 가 초과 깊이를 통과시켰다")

    # ② JSON 디코딩 재귀 — 세 진입점 전부.
    deep_json = "[" * 100000 + '"a","=",1' + "]" * 100000
    for label, call in (
        ("parse_filter", lambda: parse_filter(deep_json)),
        ("parse_filter_sort(filter)", lambda: parse_filter_sort(deep_json, None)),
        ("parse_filter_sort(sort)", lambda: parse_filter_sort(None, deep_json)),
        ("parse_sort", lambda: parse_sort(deep_json)),
    ):
        try:
            call()
        except BadRequestError:
            checked += 1
        except Exception as exc:  # noqa: BLE001 — 400 이 아닌 것은 전부 500 이다
            raise AssertionError(f"{label}: 400 이 아니라 {type(exc).__name__} 로 샜다 (500)") from exc
        else:
            raise AssertionError(f"{label}: 약 20KB 중첩 JSON 을 통과시켰다")

    print(f"     (클라이언트 입력 → 500 없음: {checked}건 검사, 상한 {_MAX_FILTER_DEPTH}단)")
    return "test_client_input_never_becomes_a_server_error"


def test_sort_selector_is_validated_like_filter_selector() -> str:
    """sort 축도 filter 축과 같은 식별자 검증을 받는다 (#401 ①).

    예전엔 TS 만 sort 검증이 없어 같은 입력이 두 경로에서 다른 판정을 받았고(이 파일 쪽은
    `_validate_identifier` 가 있었다), 그 검증마저 **문자열이 아닌 값**에는 `re.match` 의
    TypeError 로 500 을 냈다.
    """
    rejected = 0
    # 빈 selector 는 두 파서 다 "그 항을 건너뛴다"(거절이 아니다) — 기존 규약이라 여기 없다.
    for bad in ("a; DROP TABLE t", "1bad", "with space", "이름", "a.b"):
        try:
            parse_sort([{"selector": bad}])
        except BadRequestError:
            rejected += 1
        else:
            raise AssertionError(f"selector={bad!r} 를 통과시켰다")

    # 문자열이 아닌 값 — 400 이어야 한다 (TypeError 면 500).
    for bad in ([["a"]], [{"selector": ["a"]}], [{"selector": {"x": 1}}], ["name"], [None], [1]):
        try:
            parse_sort(bad)
        except BadRequestError:
            rejected += 1
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f"sort={bad!r}: 400 이 아니라 {type(exc).__name__} 로 샜다 (500)") from exc
        else:
            raise AssertionError(f"sort={bad!r} 를 통과시켰다")

    # 대조 — 정상 selector 는 그대로 통과한다. NULL 위치는 #352 가 못박았다
    # (값 없는 행이 내림차순 1등으로 오지 않게) — 규율 자체는 test_sort_null_ordering.py 가 지킨다.
    assert parse_sort([{"selector": "reg_dt", "desc": True}]) == "reg_dt DESC NULLS LAST"

    print(f"     (sort selector 거절 {rejected}건 + 정상 통과 1건)")
    return "test_sort_selector_is_validated_like_filter_selector"


def _main() -> int:
    tests = [
        test_issue_repro_keeps_both_conditions,
        test_deep_nesting_never_reuses_a_bind_name,
        test_group_without_logical_operator_stays_valid_sql,
        test_negation_with_extra_terms_is_rejected_not_dropped,
        test_mixed_logical_operators_in_flat_group_rejected,
        test_supported_shapes_are_unchanged,
        test_malformed_filter_is_rejected_not_swallowed,
        test_unsupported_operator_still_rejected,
        test_client_input_never_becomes_a_server_error,
        test_sort_selector_is_validated_like_filter_selector,
        test_python_parser_copies_stay_identical,
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
