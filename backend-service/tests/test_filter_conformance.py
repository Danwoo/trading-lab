"""#295·#306 — backend-service 파서가 두 언어 공유 입력 세트에서 기대한 방향으로 반응하는지 검증.

    cd backend-service && uv run python tests/test_filter_conformance.py

입력 세트는 이 파일이 만들지 않는다 — scripts/fixtures/filter_conformance_cases.json 하나를
frontend 쪽 scripts/verify_filter_conformance.mjs 와 **같이** 읽는다. 파서 산출물이 언어마다
다른 모양(SQL 문자열 vs Prisma where 객체)이라 문자 그대로 비교할 수 없으므로, "결과가 같다"를
그 JSON 이 못박은 행동 분류(expect: reject|false|accept)로 조작화했다 — 자세한 근거는 그 파일의
_comment 를 본다. 둘 다 같은 제3의 값(이 JSON)과 일치하면 서로도 일치한다.

검사 대상이 0건이거나 fixture 의 M-2~M-7·#306 커버리지가 줄면 실패한다(fail-closed) — 리드
결정의 필수 조건이다.

교차 리뷰 지적(#306 재발) — 파서 함수만 대조하는 걸로는 부족하다. `parse_filter([])` 는
"(1 = 0)" 을 내지만, 프로덕션의 유일한 소비자 `build_filter_params`(모든 리포지토리가
거치는 공유 함수)는 예전에 `if filter_obj:` 로 빈 리스트를 falsy 로 걸러 그 호출 자체를
건너뛰었다 — `?filter=[]` 가 실제 HTTP 경로에서는 여전히 전건을 반환했다. 파서 단위
검사(`test_conformance_cases`)만으로는 이 갈림이 안 보인다. 그래서 아래
`test_build_filter_params_matches_fixture` 는 같은 fixture 를 **`build_filter_params`
를 통해서**(라우터가 실제로 부르는 진입점) 다시 돌린다 — 파서가 옳아도 소비자가 삼키면
잡아야 한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
_REPO_ROOT = _TESTS_DIR.parent.parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.exceptions import BadRequestError  # noqa: E402
from utils.common.devextreme_utils import build_filter_params, parse_filter  # noqa: E402

_FIXTURE_PATH = _REPO_ROOT / "scripts" / "fixtures" / "filter_conformance_cases.json"

# 이슈 #295 가 못박은 발산 목록 — 이 문자열들이 fixture 의 ref 필드에서 하나씩은 나와야
# "M-2~M-7 을 전부 포함"이라는 리드의 필수 조건을 지킨 것이다. 문자열 검색(startswith)이라
# "M-5 control" 같은 대조 케이스도 "M-5" 커버리지로 잡힌다.
#
# "#389" 은 형식 오류 축이다 — 두 파서가 같은 방향으로 틀려서(둘 다 "필터 없음"으로 삼켜 전건
# 반환) 이 대조만으로는 구조적으로 못 잡던 모양들이라, 기대값의 근거를 DevExtreme 평가기에서
# 가져왔다 (scripts/verify_filter_negation.mjs 의 malformed_never_returns_all_rows).
_REQUIRED_REFS = ("M-2", "M-3", "M-4", "M-5", "M-6", "M-7", "#306", "#389", "#401")

_MIN_CASES = 36


def _load_cases() -> list[dict]:
    assert _FIXTURE_PATH.exists(), f"공유 입력 세트가 없다 — {_FIXTURE_PATH}"
    data = json.loads(_FIXTURE_PATH.read_text())
    cases = data["cases"]
    assert len(cases) >= _MIN_CASES, f"검사 대상이 {len(cases)}건 — 최소 {_MIN_CASES}건 필요 (fail-closed)"

    refs = {c["ref"] for c in cases}
    missing = [req for req in _REQUIRED_REFS if not any(ref.startswith(req) for ref in refs)]
    assert not missing, f"필수 발산 항목이 fixture 에서 빠졌다: {missing}"

    return cases


def test_conformance_cases() -> str:
    """공유 fixture 의 각 케이스를 파이썬 파서에 먹여 expect 대로 반응하는지 확인."""
    cases = _load_cases()

    failures = []
    counts = {"reject": 0, "false": 0, "accept": 0}
    for case in cases:
        expect = case["expect"]
        counts[expect] = counts.get(expect, 0) + 1
        label = f"[{case['id']}] {case['name']}"

        if expect == "reject":
            try:
                sql, params = parse_filter(case["input"])
            except BadRequestError:
                continue
            failures.append(f"{label}: 거절돼야 하는데 통과했다 — {sql!r} / {params!r}")
            continue

        if expect == "false":
            try:
                sql, params = parse_filter(case["input"])
            except BadRequestError as exc:
                failures.append(f"{label}: 항상 거짓을 내야 하는데 거절됐다 — {exc}")
                continue
            if (sql, params) != ("(1 = 0)", {}):
                failures.append(f"{label}: 항상 거짓이 아니다 — {sql!r} / {params!r}")
            continue

        if expect == "accept":
            try:
                sql, params = parse_filter(case["input"])
            except BadRequestError as exc:
                failures.append(f"{label}: 정상 입력인데 거절됐다 — {exc}")
                continue
            if not sql:
                failures.append(f"{label}: 정상 입력인데 빈 SQL 이 나왔다")
            continue

        failures.append(f"{label}: fixture 의 expect 값을 모른다 — {expect!r}")

    print(
        f"     (검사 {len(cases)}건 — reject {counts.get('reject', 0)} · "
        f"false {counts.get('false', 0)} · accept {counts.get('accept', 0)})"
    )

    assert not failures, "conformance 불일치:\n" + "\n".join(f"  {f}" for f in failures)
    return "test_conformance_cases"


def test_build_filter_params_matches_fixture() -> str:
    """종단 경로 — 라우터가 실제로 부르는 `build_filter_params(args)` 를 통해 같은 fixture 를
    재검사한다. `parse_filter` 를 직접 부르는 `test_conformance_cases` 와 달리, 리포지토리
    5곳(file·portfolio·research_document·scheduler·watchlist)이 실제로 타는 경로를 그대로
    재현한다 — args 딕셔너리에 "filter" 키로 값을 넣고, 반환된 sql_where 문자열을 본다.

    reject 는 build_filter_params 도 그대로 예외를 전파해야 한다(내부에서 parse_filter 를
    부르고 감싸지 않는다). false 는 sql_where 에 "(1 = 0)" 이 있어야 한다(형태는
    f" AND {filter_sql}" 라 raw parse_filter 출력과 접두사가 다르다 — 여기서는 포함 여부로
    본다). accept 는 sql_where 가 비어 있지 않아야 한다(제약이 실제로 걸렸다는 뜻)."""
    cases = _load_cases()

    failures = []
    for case in cases:
        expect = case["expect"]
        label = f"[{case['id']}] {case['name']}"
        args = {"filter": case["input"]}

        if expect == "reject":
            try:
                sql_where, sql_params = build_filter_params(args)
            except BadRequestError:
                continue
            failures.append(f"{label}: build_filter_params 가 거절 없이 통과시켰다 — {sql_where!r} / {sql_params!r}")
            continue

        if expect == "false":
            try:
                sql_where, sql_params = build_filter_params(args)
            except BadRequestError as exc:
                failures.append(f"{label}: build_filter_params 가 항상 거짓 대신 거절했다 — {exc}")
                continue
            if "(1 = 0)" not in sql_where or sql_params:
                failures.append(
                    f"{label}: build_filter_params 종단 경로에서 항상 거짓이 아니다 — "
                    f"sql_where={sql_where!r} / sql_params={sql_params!r}"
                )
            continue

        if expect == "accept":
            try:
                sql_where, sql_params = build_filter_params(args)
            except BadRequestError as exc:
                failures.append(f"{label}: build_filter_params 가 정상 입력을 거절했다 — {exc}")
                continue
            if not sql_where.strip():
                failures.append(f"{label}: build_filter_params 가 제약 없이 통과시켰다(sql_where 비어 있음)")
            continue

        failures.append(f"{label}: fixture 의 expect 값을 모른다 — {expect!r}")

    print(f"     (build_filter_params 종단 검사 {len(cases)}건)")

    assert not failures, "build_filter_params 종단 conformance 불일치:\n" + "\n".join(f"  {f}" for f in failures)
    return "test_build_filter_params_matches_fixture"


def test_build_filter_params_distinguishes_missing_filter_from_empty_list() -> str:
    """`args` 에 "filter" 키가 아예 없음(None)과 빈 리스트([])는 다르다 — 하나는 "필터
    파라미터 자체가 없음"(제약 없음), 하나는 "필터가 왔는데 내용이 비어 있음"(#306, 항상
    거짓)이다. `if filter_obj:` 같은 truthy 검사는 이 둘을 못 가른다 — `[]` 가 falsy 라서
    "필터 없음"과 같은 값(sql_where="")을 냈다. `?filter=[]` 실 요청으로 재현·확인:
    watchlist(workspace_id=1, 8건 시딩)에 이 결함이 있을 때 total_count=8(전건), 고친
    뒤 total_count=0 — 이 유닛 테스트는 그 축소판이다."""
    # filter 키 자체가 없음 — 제약 없음이어야 한다
    sql_where, sql_params = build_filter_params({})
    assert sql_where == "" and sql_params == {}, f"필터 파라미터가 없을 때 제약이 생겼다: {sql_where!r}"

    # filter: None — 위와 동일해야 한다(쿼리스트링이 안 왔을 때 parse_filter_sort 가 만드는 값)
    sql_where, sql_params = build_filter_params({"filter": None})
    assert sql_where == "" and sql_params == {}, f"filter=None 인데 제약이 생겼다: {sql_where!r}"

    # filter: [] — #306, 항상 거짓이어야 한다(제약 없음과 달라야 한다)
    sql_where, sql_params = build_filter_params({"filter": []})
    assert "(1 = 0)" in sql_where and not sql_params, f"filter=[] 인데 제약이 없다(전건 반환 재발): {sql_where!r}"

    return "test_build_filter_params_distinguishes_missing_filter_from_empty_list"


def test_date_like_values_are_never_coerced() -> str:
    """M-6 — 파이썬은 애초에 날짜꼴 coercion 을 하지 않는다. dateShape 케이스가 문자열 그대로
    바인드되는지 대조해, 이 불변식이 fixture 편집으로 조용히 깨지지 않게 고정한다."""
    cases = [c for c in _load_cases() if "dateShape" in c]
    assert len(cases) >= 2, f"M-6 dateShape 케이스가 {len(cases)}건 — 목록이 줄었다"

    for case in cases:
        field, op, value = case["input"]
        sql, params = parse_filter(case["input"])
        assert isinstance(value, str), f"[{case['id']}] fixture 값이 문자열이 아니다: {value!r}"
        (bound_value,) = params.values()
        assert bound_value == value, (
            f"[{case['id']}] 파이썬이 값을 바꿨다 — 이 파서는 coercion 을 하지 않는 게 불변식이다: "
            f"{value!r} → {bound_value!r}"
        )
        assert isinstance(bound_value, str), f"[{case['id']}] 바인드 값이 문자열이 아니게 됐다: {bound_value!r}"

    return "test_date_like_values_are_never_coerced"


def _main() -> int:
    tests = [
        test_conformance_cases,
        test_build_filter_params_matches_fixture,
        test_build_filter_params_distinguishes_missing_filter_from_empty_list,
        test_date_like_values_are_never_coerced,
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
