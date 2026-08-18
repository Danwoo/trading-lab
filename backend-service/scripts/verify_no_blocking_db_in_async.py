#!/usr/bin/env python3
"""async 함수 안의 **동기 DB 호출**을 막는다 — fail-closed (stdlib 전용).

## 왜 필요한가

`backend-service` 는 백그라운드 매니저 3종을 앱 안에서 돌리므로 `--workers=1` 이다. 그래서
async 경로의 동기 DB 호출은 **그 순간 이 앱의 모든 HTTP 요청을 함께 멈춘다** — 적재는 장중에
돌고, 그때 화면이 응답을 기다린다.

실제로 그렇게 새어 나갔다: 적재 매니저의 상태 갱신 네 자리가 `run_in_threadpool` 밖에 있었고,
같은 파일의 나머지 호출은 전부 감싸져 있어서 **사람이 눈으로 세지 않으면 안 보였다**(#189).

## 무엇을 하나

AST 로 각 async 함수를 훑어, `self.*_repository.*(...)` 호출이 `await run_in_threadpool(...)`
안에 있지 않으면 낸다. `await self._something()` 처럼 다른 async 로 위임한 것은 통과다 —
그 함수가 이 검사를 다시 받는다.

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


def repository_calls_in_async(tree: ast.AST) -> list[tuple[int, str]]:
    """async 함수 안에서 스레드풀 밖에 있는 repository 호출."""
    hits: list[tuple[int, str]] = []

    class Scan(ast.NodeVisitor):
        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            # 이 async 함수 안에서 `run_in_threadpool(...)` 의 **인자로** 넘어간 노드는 안전하다.
            safe: set[int] = set()
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                fname = getattr(sub.func, "id", None) or getattr(sub.func, "attr", None)
                if fname == "run_in_threadpool":
                    for arg in sub.args:
                        for inner in ast.walk(arg):
                            safe.add(id(inner))

            for sub in ast.walk(node):
                if isinstance(sub, (ast.AsyncFunctionDef, ast.FunctionDef)) and sub is not node:
                    continue  # 중첩 함수는 자기 차례에 검사된다
                if not isinstance(sub, ast.Call) or id(sub) in safe:
                    continue
                func = sub.func
                if not isinstance(func, ast.Attribute):
                    continue
                owner = func.value
                # `self.<something>_repository.<method>(...)`
                if (
                    isinstance(owner, ast.Attribute)
                    and owner.attr.endswith("_repository")
                    and isinstance(owner.value, ast.Name)
                    and owner.value.id == "self"
                ):
                    hits.append((sub.lineno, f"self.{owner.attr}.{func.attr}(...)"))
            self.generic_visit(node)

    Scan().visit(tree)
    return hits


def main() -> int:
    files = sorted(APP.rglob("*.py"))
    problems: list[str] = []
    for path in files:
        rel = path.relative_to(BACKEND).as_posix()
        if rel in EXEMPT:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:  # noqa: PERF203
            print(f"::error::{rel} 를 파싱하지 못했다: {exc}", file=sys.stderr)
            return 1
        for lineno, call in repository_calls_in_async(tree):
            problems.append(f"{rel}:{lineno} — async 안에서 동기 DB 호출: {call}")

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
