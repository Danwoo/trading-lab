#!/usr/bin/env python3
"""async 함수 안의 **동기 DB 호출**을 막는다 — fail-closed (stdlib 전용).

## 왜 필요한가

`backend-service` 는 백그라운드 매니저 3종을 앱 안에서 돌리므로 `--workers=1` 이다. 그래서
async 경로의 동기 DB 호출은 **그 순간 이 앱의 모든 HTTP 요청을 함께 멈춘다** — 적재는 장중에
돌고, 그때 화면이 응답을 기다린다.

실제로 그렇게 새어 나갔다: 적재 매니저의 상태 갱신 네 자리가 `run_in_threadpool` 밖에 있었고,
같은 파일의 나머지 호출은 전부 감싸져 있어서 **사람이 눈으로 세지 않으면 안 보였다**(#189).

## 무엇을 하나

AST 로 훑어 `self.*_repository.*(...)` 호출이 `await run_in_threadpool(...)` 안에 있지
않으면 낸다. `await self._something()` 처럼 다른 async 로 위임한 것은 통과다 — 그 함수가
이 검사를 다시 받는다.

**async 함수만 보면 안 된다.** `_finish` 가 정확히 그 사각이었다 — sync `def` 인데
async 안에서만 불려, 「async 함수 안의 호출」만 세는 검사에는 안 걸리면서 실제로는 루프를
막았다. 그래서 **async 에서 (몇 단계를 거치든) 도달 가능한 sync 메서드**까지 async 취급한다.
호출 그래프를 클래스 안에서 따라간다.

**감싸기를 흉내만 낸 것도 잡는다.** `run_in_threadpool(...)` 을 `await` 없이 쓰면 코루틴이
실행되지 않아 **DB 쓰기가 조용히 사라진다** — 감싸진 것보다 나쁘다. 이건 별도 규칙으로
본다: 스레드풀에는 호출이 아니라 **메서드 참조**를 넘기므로(`run_in_threadpool(self.repo.foo, args)`)
안에 볼 `Call` 자체가 없다. 그래서 「await 없는 `run_in_threadpool`」을 그 자리에서 낸다 —
무엇을 감쌌든 틀린 코드다.

**로컬 별칭도 따라간다.** `repo = self.ingest_repository` 뒤의 `repo.foo(...)` 는
`self.*_repository.*` 패턴에 안 걸린다. 같은 함수 안의 그 대입을 읽어 별칭을 넓힌다.

    cd backend-service && uv run python scripts/verify_no_blocking_db_in_async.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"

# 이 아래로 내려가면 글롭이 어긋난 것이다.
MIN_FILES = 20

# 사유와 함께 적는다. 빈 사유는 등록으로 치지 않는다.
#
# **이 목록은 늘어나면 안 된다.** 등록된 둘은 이 그물을 놓기 **전부터** 있던 것이고,
# 고치는 것은 각자 별건이다(#189 는 적재 매니저만 닫는다) — 이 그물이 있으니 그 사실이
# 이제 눈에 보인다. 새 위반은 여기 넣지 말고 고쳐라.
EXEMPT: dict[str, str] = {
    "app/services/file/file_service.py": "이 그물 이전부터 있던 12건 — 별건으로 연다",
    "app/services/scheduler/scheduler_service.py": "이 그물 이전부터 있던 5건 — 별건으로 연다",
}


def _repository_aliases(node: ast.AST) -> set[str]:
    """`repo = self.x_repository` 류 대입에서 만들어진 지역 별칭 이름."""
    names: set[str] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Assign) or not isinstance(sub.value, ast.Attribute):
            continue
        value = sub.value
        if not (value.attr.endswith("_repository") and isinstance(value.value, ast.Name) and value.value.id == "self"):
            continue
        for target in sub.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _is_repository_call(call: ast.Call, aliases: set[str]) -> str | None:
    """이 호출이 repository 호출이면 사람이 읽을 표기를, 아니면 None."""
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None
    owner = func.value
    # self.<something>_repository.<method>(...)
    if (
        isinstance(owner, ast.Attribute)
        and owner.attr.endswith("_repository")
        and isinstance(owner.value, ast.Name)
        and owner.value.id == "self"
    ):
        return f"self.{owner.attr}.{func.attr}(...)"
    # 지역 별칭을 거친 같은 호출
    if isinstance(owner, ast.Name) and owner.id in aliases:
        return f"{owner.id}.{func.attr}(...)  # = self.*_repository"
    return None


def _safe_call_nodes(node: ast.AST) -> set[int]:
    """`await run_in_threadpool(...)` 의 인자로 넘어간 노드들.

    **`await` 를 요구한다.** await 없는 `run_in_threadpool(...)` 은 코루틴을 만들기만 하고
    실행하지 않아 DB 쓰기가 조용히 사라진다 — 감싸진 것보다 나쁘다.
    """
    safe: set[int] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Await) or not isinstance(sub.value, ast.Call):
            continue
        call = sub.value
        fname = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
        if fname != "run_in_threadpool":
            continue
        for arg in call.args:
            for inner in ast.walk(arg):
                safe.add(id(inner))
    return safe


def _own_calls(node: ast.AST) -> list[ast.Call]:
    """이 함수가 직접 하는 호출 (중첩 함수 것은 뺀다 — 그쪽은 자기 차례에 검사된다)."""
    calls: list[ast.Call] = []

    def walk(n: ast.AST, root: bool) -> None:
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.AsyncFunctionDef, ast.FunctionDef)) and not root:
                continue
            if isinstance(child, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            if isinstance(child, ast.Call):
                calls.append(child)
            walk(child, False)

    walk(node, True)
    return calls


def _self_methods_called(node: ast.AST) -> set[str]:
    """이 함수가 부르는 `self.<name>(...)` 의 이름들."""
    names: set[str] = set()
    for call in _own_calls(node):
        func = call.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "self":
            names.add(func.attr)
    return names


def _unawaited_threadpool(node: ast.AST) -> list[tuple[int, str]]:
    """`await` 없이 쓴 `run_in_threadpool(...)`.

    코루틴을 만들기만 하고 실행하지 않는다 — 감싸기의 겉모습은 갖췄는데 **DB 작업이 조용히
    사라진다.** 안 감싼 것보다 나쁘다(안 감싼 것은 최소한 동작은 한다).
    """
    awaited: set[int] = {
        id(n.value) for n in ast.walk(node) if isinstance(n, ast.Await) and isinstance(n.value, ast.Call)
    }
    out: list[tuple[int, str]] = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call) or id(sub) in awaited:
            continue
        fname = getattr(sub.func, "id", None) or getattr(sub.func, "attr", None)
        if fname == "run_in_threadpool":
            out.append((sub.lineno, "run_in_threadpool(...) 에 await 이 없다 — 코루틴이 실행되지 않는다"))
    return out


def blocking_calls(tree: ast.AST) -> list[tuple[int, str]]:
    """async 에서 도달 가능한 자리의 스레드풀 밖 repository 호출."""
    hits: list[tuple[int, str]] = []
    hits.extend(_unawaited_threadpool(tree))

    for klass in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        methods: dict[str, ast.AsyncFunctionDef | ast.FunctionDef] = {
            m.name: m for m in klass.body if isinstance(m, (ast.AsyncFunctionDef, ast.FunctionDef))
        }

        # async 에서 도달 가능한 메서드 — sync 헬퍼를 거쳐도 따라간다.
        # `_finish` 가 정확히 그 자리였다: sync def 인데 async 에서만 불렸다.
        reachable = {n for n, m in methods.items() if isinstance(m, ast.AsyncFunctionDef)}
        while True:
            grown = set(reachable)
            for name in reachable:
                grown |= _self_methods_called(methods[name]) & methods.keys()
            if grown == reachable:
                break
            reachable = grown

        for name in sorted(reachable):
            node = methods[name]
            safe = _safe_call_nodes(node)
            aliases = _repository_aliases(node)
            for call in _own_calls(node):
                if id(call) in safe:
                    continue
                shown = _is_repository_call(call, aliases)
                if shown:
                    hits.append((call.lineno, shown))

    return sorted(set(hits))


def main() -> int:
    files = sorted(APP.rglob("*.py"))
    problems: list[str] = []

    # 면제가 가리키는 파일이 사라지면 그 항목은 조용히 죽고, 출력은 여전히 「면제 N건」이라
    # 찍는다 — 「검사 0건은 통과가 아니다」와 같은 부류다. 존재를 확인하고 없으면 실패한다.
    for rel in EXEMPT:
        if not (BACKEND / rel).is_file():
            print(
                f"::error::면제 목록의 {rel} 가 없다 — 파일을 지웠거나 옮겼으면 "
                "EXEMPT 에서도 빼라 (죽은 면제는 그물에 뚫린 구멍이다)",
                file=sys.stderr,
            )
            return 1
    for path in files:
        rel = path.relative_to(BACKEND).as_posix()
        if rel in EXEMPT:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:  # noqa: PERF203
            print(f"::error::{rel} 를 파싱하지 못했다: {exc}", file=sys.stderr)
            return 1
        for lineno, call in blocking_calls(tree):
            problems.append(f"{rel}:{lineno} — async 에서 도달하는 동기 DB 호출: {call}")

    print(f"`app/**/*.py` {len(files)}건 검사 · 면제 {len(EXEMPT)}건 · 위반 {len(problems)}건")

    if len(files) < MIN_FILES:
        print(
            f"::error::검사 대상이 {len(files)}건뿐이다 — 그물이 죽어 있다 (하한 {MIN_FILES})",
            file=sys.stderr,
        )
        return 1

    if problems:
        for line in problems:
            print(f"::error::{line}", file=sys.stderr)
        print(
            "\n`await run_in_threadpool(<repo 메서드>, <인자>...)` 로 감싸세요. "
            "이 앱은 --workers=1 이라 동기 DB 호출이 전 요청을 멈춥니다.",
            file=sys.stderr,
        )
        return 1

    print("판정: async 경로에 동기 DB 호출 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
