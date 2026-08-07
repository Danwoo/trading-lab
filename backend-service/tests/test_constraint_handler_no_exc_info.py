"""#255 — 무결성/데이터 오류 핸들러에 exc_info=True 가 재유입되지 않는지 검증.

배경: `hide_parameters=True`(#234)는 SQLAlchemy 가 붙이는 `[parameters: {...}]` 만 지운다.
PostgreSQL 이 원 예외 메시지에 붙이는 DETAIL(`Failing row contains (...)`)은 그대로 남아 있고,
지금 로그에 안 보이는 이유는 오직 `_handle_constraint_error`(core/exception_handler.py)가
`exc_info` 없이 allowlist 진단(제약·테이블·컬럼명, DIAG_FIELDS)만 찍기 때문이다. 이 경로의
로그 호출에 누군가 `exc_info=True` 를 한 줄 붙이면(예: "스택이 안 보이네" 하고 디버깅 중 추가),
그 트레이스백 마지막 줄이 드라이버 예외의 `str(orig)`(DETAIL 포함)를 그대로 실어 즉시 재발한다.
주석은 이 결합을 설명할 뿐 강제하지 않으므로, 이 스캔이 강제한다.

## 헬퍼 한 겹 우회를 막는다 (#376)

종전 스캔은 `_handle_constraint_error` **함수 본문의 `ast.Call` 만** 봤다. 그래서 로그 호출을
모듈 안 헬퍼로 한 겹 빼면 통과했다 — 실증(#376): 로그 호출을 `_log_db_error(msg, exc)` 로 빼고
그 헬퍼에서 `exc_info=True` 를 찍자 스캔은 `PASS`, 실제 로그는 `Failing row contains (...)` 를
그대로 실었다. **#255 가 막으려던 바로 그 누출이 그물 안에서 재현됐다.**

지금은 `_handle_constraint_error` 에서 **모듈 로컬 호출로 도달하는 함수 전부**(전이 폐포)를
검사한다. 헬퍼를 몇 겹으로 빼든, 그 헬퍼가 같은 모듈에 있는 한 폐포 안이다.

폐포를 끊는 간선은 `SAFE_EDGES` 한 자리에서만 선언한다 — 사유와 함께. 선언한 간선이 실제
그래프에 없으면 실패한다(낡은 예외 차단).

## 남는 한계 (#376 이 요구한 명시)

이 스캔이 **못 보는 것**을 적어 둔다 — "그물이 있으니 안전하다"고 읽히지 않게:

  · **다른 모듈의 헬퍼** — `from core.logger import log_db_error` 처럼 파일 밖으로 뺀 로그
    호출은 따라가지 않는다(모듈 로컬 이름만 해석한다). 파일 경계를 넘는 호출 그래프를
    정적으로 따라가려면 임포트 해석이 필요하고, 그건 이 값싼 스캔의 범위 밖이다.
  · **간접 디스패치** — `handlers[code](...)` · `getattr(mod, name)(...)` · 데코레이터가
    감싸는 로깅 · 부분 적용(`functools.partial`)은 호출자 이름이 `ast.Name` 이 아니라 안 잡힌다.
  · **exc_info 없이 새는 경로** — `logger.warning(f"... {exc.orig}")` 처럼 드라이버 메시지를
    **직접 포맷 문자열에 넣는** 것은 이 스캔의 규칙(`exc_info` 키워드)이 아니다. 그 축은
    `_safe_diagnostics` 의 allowlist 설계(#216)와 코드 리뷰가 맡는다.
  · **런타임 로거 설정** — 로거 핸들러·포매터가 트레이스백을 어떻게 렌더하는지는 정적으로 안 본다.

`core/exception_handler.py` 는 10개 서비스에 byte-identical 로 복제되어 있고
(scripts/verify_auth_lockstep.py REPLICA_GROUPS 가 그 동일성을 강제) 그중 하나만 봐도 될 것 같지만,
그 검사가 깨지거나 우회되는 경우까지 방어하기 위해 **복제본 전부**를 직접 스캔한다 —
sql-param-hiding(test_sql_parameter_hiding.py)이 "사본 동일성을 가정하지 않는다"고 명시한 것과
같은 이유(REPO 루트 CLAUDE.md 무관, 이 파일 자체의 관례).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 겸용으로 작성한다:
    uv run python tests/test_constraint_handler_no_exc_info.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

CI 배선: .github/workflows/repo-scans.yml 의 `test: repo-scan` 잡 (경로 필터 없음) — 서비스
이름을 가리지 않는 레포 전수 스캔이라 sql-param-hiding·date-literals 와 같은 파일에 둔다(#302 의
"서비스 단위 on.paths 에 얹으면 새 서비스가 스캔에서 빠진다" 교훈과 동일 이유).

외부 DB 없이 순수 AST 파싱만으로 돈다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_FUNCTION = "_handle_constraint_error"
RELATIVE_PATH = "app/core/exception_handler.py"
EXCEPTIONS_RELATIVE_PATH = "app/core/exceptions.py"

FuncDef = ast.FunctionDef | ast.AsyncFunctionDef

# 전이 폐포를 여기서 끊는다 — (호출자, 피호출자) → 사유. **이 목록이 그물에 뚫는 유일한 구멍이다.**
# 항목을 더하려면 "왜 이 너머는 안 봐도 되는가"를 적고, 가능하면 그 사유 자체를 강제하는 검사를
# 함께 둬라 (아래 handle_http_error 항목이 그 예다 — 사유가 다른 테스트로 강제된다).
SAFE_EDGES: dict[tuple[str, str], str] = {
    (TARGET_FUNCTION, "handle_http_error"): (
        "도메인 예외를 HTTP 응답으로 바꾸는 공용 출구다. 그 함수의 exc_info=True 는 status_code 가"
        " 5xx 인 가지에서만 켜지는데, 이 경로가 넘기는 예외(SQLSTATE_MAP 의 전 값 + 두 fallback)는"
        " 전부 4xx 라 그 가지에 닿지 않는다. 4xx 성은 test_constraint_path_never_maps_to_5xx 가"
        " 강제한다 — 누가 5xx 를 끼워 넣으면 그 테스트가 빨개진다."
    ),
}

# `status.HTTP_409_CONFLICT` 같은 어트리뷰트 이름에서 코드 숫자만 꺼낸다.
_STATUS_ATTR = re.compile(r"^HTTP_(\d{3})_")


def _module_functions(tree: ast.Module) -> dict[str, FuncDef]:
    """모듈에 정의된 함수 이름 → 정의 노드 (중첩 함수 포함 — 헬퍼를 안쪽에 숨겨도 잡는다)."""
    found: dict[str, FuncDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found[node.name] = node
    return found


def _local_callees(func: FuncDef, known: set[str]) -> set[str]:
    """`func` 본문이 직접 부르는 **모듈 로컬** 함수 이름 (`name(...)` · `await name(...)`)."""
    callees: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in known:
            callees.add(node.func.id)
    return callees


def _closure(start: str, functions: dict[str, FuncDef]) -> tuple[list[str], set[tuple[str, str]]]:
    """`start` 에서 모듈 로컬 호출로 도달하는 함수들 + 실제로 밟은 간선.

    SAFE_EDGES 에 선언된 간선은 **기록하되 넘어가지 않는다** — 그래야 선언이 낡았는지
    (간선이 사라졌는지) 호출자가 확인할 수 있다.
    """
    known = set(functions)
    reached = [start]
    seen = {start}
    edges: set[tuple[str, str]] = set()
    queue = [start]
    while queue:
        current = queue.pop(0)
        for callee in sorted(_local_callees(functions[current], known)):
            edges.add((current, callee))
            if (current, callee) in SAFE_EDGES or callee in seen:
                continue
            seen.add(callee)
            reached.append(callee)
            queue.append(callee)
    return reached, edges


def _exc_info_violations(func: FuncDef, path: Path) -> list[str]:
    """`func` 안의 모든 호출에서 `exc_info` 키워드를 찾는다.

    리터럴 `False` 만 안전으로 인정한다 — 리터럴이 아닌 표현식(변수·조건식 등)은 참인지 증명할
    수 없으므로 위반으로 잡는다(fail-closed, sql-param-hiding 의 "오탐 방향이지만 시끄럽게
    실패하는 쪽이 낫다"와 같은 태도).
    """
    violations: list[str] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "exc_info":
                continue
            is_literal_false = isinstance(kw.value, ast.Constant) and kw.value.value is False
            if not is_literal_false:
                violations.append(
                    f"{path.relative_to(_REPO_ROOT)}:{node.lineno}: "
                    f"{func.name}() 안에서 exc_info 가 안전하지 않음(리터럴 False 아님)"
                )
    return violations


def _assigned_value(tree: ast.Module, name: str) -> ast.expr | None:
    """모듈 최상위 대입의 우변 (`X = ...` · `X: T = ...` 둘 다)."""
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node.value
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
    return None


def _exception_status_codes(tree: ast.Module) -> dict[str, int]:
    """core/exceptions.py 의 클래스명 → status_code 숫자."""
    codes: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign):
                target, value = stmt.target, stmt.value
            elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target, value = stmt.targets[0], stmt.value
            else:
                continue
            if not (isinstance(target, ast.Name) and target.id == "status_code"):
                continue
            if isinstance(value, ast.Attribute) and (m := _STATUS_ATTR.match(value.attr)):
                codes[node.name] = int(m.group(1))
    return codes


def _constraint_path_exceptions(tree: ast.Module) -> tuple[list[str], list[str]]:
    """이 경로가 handle_http_error 로 넘길 수 있는 도메인 예외 클래스명.

    돌려주는 것은 (SQLSTATE_MAP 값들, `_handle_constraint_error(...)` 의 fallback 인자들).
    두 출처를 나눠 돌려주는 이유: 한쪽이 파싱 실패로 0건이 돼도 다른 쪽 때문에 통과하는 일을
    막기 위해 호출자가 **각각** 비어 있지 않은지 확인한다.
    """
    mapped: list[str] = []
    mapping = _assigned_value(tree, "SQLSTATE_MAP")
    if isinstance(mapping, ast.Dict):
        for value in mapping.values:
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                mapped.append(value.func.id)

    fallbacks: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != TARGET_FUNCTION:
            continue
        # _handle_constraint_error(request, exc, fallback) — 위치 인자 3번째 또는 fallback= 키워드
        candidate: ast.expr | None = node.args[2] if len(node.args) >= 3 else None
        for kw in node.keywords:
            if kw.arg == "fallback":
                candidate = kw.value
        if isinstance(candidate, ast.Call) and isinstance(candidate.func, ast.Name):
            fallbacks.append(candidate.func.id)
    return mapped, fallbacks


def _replicas() -> list[Path]:
    candidates = sorted(_REPO_ROOT.glob(f"*-service/{RELATIVE_PATH}"))
    assert candidates, f"exception_handler.py 복제본이 0건 — 스캔 경로가 깨졌다: {_REPO_ROOT}/*-service/{RELATIVE_PATH}"
    return candidates


def test_constraint_handler_has_no_exc_info() -> str:
    """복제본 전부에서 `_handle_constraint_error` **의 전이 폐포**에 exc_info 유입이 없다 (#376)."""
    candidates = _replicas()

    checked: list[Path] = []
    missing_function: list[str] = []
    violations: list[str] = []
    stale_edges: list[str] = []
    closure_sizes: list[int] = []
    for path in candidates:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = _module_functions(tree)
        if TARGET_FUNCTION not in functions:
            missing_function.append(str(path.relative_to(_REPO_ROOT)))
            continue
        checked.append(path)

        reached, edges = _closure(TARGET_FUNCTION, functions)
        closure_sizes.append(len(reached))
        for name in reached:
            violations.extend(_exc_info_violations(functions[name], path))

        # 선언한 안전 간선이 실제 그래프에 없으면 예외 목록이 낡은 것이다 — 조용히 두지 않는다.
        for edge in SAFE_EDGES:
            if edge not in edges:
                stale_edges.append(
                    f"{path.relative_to(_REPO_ROOT)}: 선언된 안전 간선 {edge[0]} → {edge[1]} 가"
                    " 실제 호출 그래프에 없다 (SAFE_EDGES 가 낡았다)"
                )

    assert not missing_function, (
        f"{TARGET_FUNCTION} 함수를 찾지 못한 복제본이 있다 — 함수가 없어지거나 이름이 바뀌면 이 검사가"
        " 무엇을 보호하는지 불명확해진다:\n  " + "\n  ".join(missing_function)
    )
    assert checked, f"검사 대상이 0건 — 아무것도 보지 않았다 (후보 {len(candidates)}건 중 {TARGET_FUNCTION} 발견 0건)"
    assert not stale_edges, "SAFE_EDGES 낡음:\n  " + "\n  ".join(stale_edges)
    # 폐포가 1(자기 자신)로 쪼그라들면 호출 그래프 해석이 죽은 것이다 — 위반 0건이 "정말 없음"인지
    # "아무 데도 안 갔음"인지 구분하려면 여기서 시끄럽게 실패해야 한다 (fail-closed).
    assert closure_sizes and min(closure_sizes) >= 1, "폐포 계산이 0건 — 호출 그래프 해석이 깨졌다"
    assert not violations, (
        "무결성/데이터 오류 핸들러 경로에 exc_info 유입 — PostgreSQL DETAIL(행 값)이 트레이스백으로 샌다:\n  "
        + "\n  ".join(violations)
    )

    print(
        f"  {TARGET_FUNCTION} 전이 폐포 검사 {len(checked)}건 (복제본 {len(candidates)}개) — "
        f"복제본당 폐포 함수 {min(closure_sizes)}~{max(closure_sizes)}개, 안전 간선 선언 {len(SAFE_EDGES)}건:"
    )
    for path in checked:
        print(f"    {path.relative_to(_REPO_ROOT)}")
    return (
        f"test_constraint_handler_has_no_exc_info "
        f"(복제본 {len(candidates)}개 / 검사 {len(checked)}건 / 폐포 최대 {max(closure_sizes)}함수)"
    )


def test_constraint_path_never_maps_to_5xx() -> str:
    """SAFE_EDGES 의 사유를 강제한다 — 이 경로가 넘기는 도메인 예외는 전부 4xx 여야 한다.

    `handle_http_error` 는 5xx 일 때만 `exc_info=True` 를 켠다. 위 스캔이 그 함수 너머를 안 보는
    근거가 "여기로 오는 예외는 4xx 뿐"이므로, 그 근거 자체를 검사로 붙든다. 누가 SQLSTATE_MAP 에
    `InternalServerError` 를 넣거나 fallback 을 5xx 로 바꾸면 여기서 빨개진다.
    """
    candidates = _replicas()

    checked: list[Path] = []
    violations: list[str] = []
    empty_sources: list[str] = []
    total_classes = 0
    for path in candidates:
        relative = path.relative_to(_REPO_ROOT)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        exceptions_path = path.with_name("exceptions.py")  # 같은 app/core/ 안의 짝
        if not exceptions_path.is_file():
            empty_sources.append(f"{relative}: 짝이 되는 {EXCEPTIONS_RELATIVE_PATH} 가 없다")
            continue
        status_codes = _exception_status_codes(
            ast.parse(exceptions_path.read_text(encoding="utf-8"), filename=str(exceptions_path))
        )
        if not status_codes:
            empty_sources.append(f"{exceptions_path.relative_to(_REPO_ROOT)}: status_code 를 0건 읽었다")
            continue

        mapped, fallbacks = _constraint_path_exceptions(tree)
        # 두 출처를 각각 확인한다 — 한쪽이 조용히 0건이 되면 그 축은 아무것도 안 본 것이다.
        if not mapped:
            empty_sources.append(f"{relative}: SQLSTATE_MAP 값을 0건 읽었다 (파싱이 어긋났다)")
        if not fallbacks:
            empty_sources.append(f"{relative}: {TARGET_FUNCTION}(...) 의 fallback 인자를 0건 읽었다")
        checked.append(path)

        for source, names in (("SQLSTATE_MAP", mapped), ("fallback", fallbacks)):
            for name in names:
                total_classes += 1
                code = status_codes.get(name)
                if code is None:
                    violations.append(
                        f"{relative}: {source} 의 {name} 를 {EXCEPTIONS_RELATIVE_PATH} 에서 못 찾았다"
                        " — status_code 를 확인할 수 없으면 4xx 라고 가정하지 않는다(fail-closed)"
                    )
                elif code >= 500:
                    violations.append(
                        f"{relative}: {source} 의 {name} 가 {code} (5xx) — handle_http_error 의"
                        " exc_info=True 가지에 닿는다. SAFE_EDGES 의 근거가 무너진다"
                    )

    assert not empty_sources, "검사 입력이 비었다 (fail-closed):\n  " + "\n  ".join(empty_sources)
    assert checked, "검사 대상이 0건 — 아무것도 보지 않았다"
    assert not violations, "제약 오류 경로가 5xx 로 매핑된다:\n  " + "\n  ".join(violations)

    print(
        f"  제약 오류 경로의 도메인 예외 {total_classes}건 (복제본 {len(checked)}개) — 전부 4xx,"
        " handle_http_error 의 exc_info 가지에 닿지 않음."
    )
    return f"test_constraint_path_never_maps_to_5xx (복제본 {len(checked)}개 / 예외 {total_classes}건)"


def _main() -> int:
    tests = [test_constraint_handler_has_no_exc_info, test_constraint_path_never_maps_to_5xx]
    passed = 0
    for tc in tests:
        name = tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
