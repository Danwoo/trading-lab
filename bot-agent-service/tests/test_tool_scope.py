"""#150 B2 — 읽기 도구의 경로 스코프를 공격 입력으로 두들긴다.

PR #154 독립 리뷰가 잡은 차단급 결함(bare-name 허용은 `cwd` 로 안 좁혀진다)의 회귀 그물이다.
**정적 설정 대조가 아니라 판정 함수를 실제로 호출한다** — 종전 `test_agent_boundary.py` 가
상수만 봤기 때문에 이 구멍을 못 봤다.

standalone 실행:
    APP_ENV=development uv run python tests/test_tool_scope.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("APP_ENV", "test")

from agents.tool_scope import PATH_ARGS, check_tool_scope, scope_hook  # noqa: E402

# 리뷰가 적은 공격 둘 + 이번에 새로 시도한 것들. `None` 이 아니어야(=거부) 통과다.
BLOCKED: list[tuple[str, dict]] = [
    # 리뷰 공격 1 — 절대경로로 시스템 파일
    ("Read", {"file_path": "/etc/passwd"}),
    # 리뷰 공격 2 — 상대경로 traversal 로 다른 서비스의 운영 설정
    ("Read", {"file_path": "../../backend-service/.env.production"}),
    # 새 입력 — 중간에 낀 `..`
    ("Read", {"file_path": "sub/../../secrets.txt"}),
    # 새 입력 — 패턴으로 나가기 (Glob 은 path 없이 pattern 만으로 밖을 훑을 수 있다)
    ("Glob", {"pattern": "../../**/*.env*"}),
    ("Glob", {"pattern": "/home/**/.ssh/id_*"}),
    # 새 입력 — Grep 의 검색 뿌리
    ("Grep", {"pattern": "JWT_SECRET", "path": "/home/tjeksdn1"}),
    ("Grep", {"pattern": "JWT_SECRET", "glob": "../../**"}),
    # 새 입력 — 노트북 경로 (Read 의 두 번째 인자 이름)
    ("Read", {"notebook_path": "/tmp/x.ipynb"}),
    # 새 입력 — 값이 문자열이 아니면 fail-closed
    ("Read", {"file_path": ["/etc/passwd"]}),
    ("Read", {"file_path": {"path": "/etc/passwd"}}),
    # 새 입력 — 루트 자체를 벗어나는 형제 디렉터리 (접두사만 같은 경로)
    ("Read", {"file_path": "../strategies-secret/key.txt"}),
]

ALLOWED: list[tuple[str, dict]] = [
    ("Read", {"file_path": "ma_pullback.py"}),
    ("Read", {"file_path": "nested/deep.py"}),
    ("Glob", {"pattern": "*.py"}),
    ("Glob", {"pattern": "**/*.py", "path": "."}),
    ("Grep", {"pattern": "STRATEGY"}),
    # 스코프 대상이 아닌 도구는 이 함수가 판정하지 않는다 (도구 허용은 별도 경계)
    ("TodoWrite", {"anything": "/etc/passwd"}),
]


def _root(tmp: str) -> Path:
    root = Path(tmp) / "strategies"
    (root / "nested").mkdir(parents=True)
    (root / "ma_pullback.py").write_text("# x", encoding="utf-8")
    (root / "nested" / "deep.py").write_text("# x", encoding="utf-8")
    return root


def test_escapes_are_denied() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        root = _root(tmp)
        for tool, args in BLOCKED:
            reason = check_tool_scope(tool, args, root)
            assert reason is not None, f"통과됐다: {tool} {args}"
    return f"test_escapes_are_denied ({len(BLOCKED)}건 전부 거부)"


def test_inside_is_allowed() -> str:
    with tempfile.TemporaryDirectory() as tmp:
        root = _root(tmp)
        for tool, args in ALLOWED:
            reason = check_tool_scope(tool, args, root)
            assert reason is None, f"막혔다: {tool} {args} → {reason}"
    return f"test_inside_is_allowed ({len(ALLOWED)}건 전부 통과)"


def test_symlink_out_is_denied() -> str:
    """전략 디렉터리 안의 심링크가 밖을 가리켜도 막는다 — 이름만 안쪽인 경로."""
    with tempfile.TemporaryDirectory() as tmp:
        root = _root(tmp)
        outside = Path(tmp) / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        (root / "link.txt").symlink_to(outside)
        assert check_tool_scope("Read", {"file_path": "link.txt"}, root) is not None
    return "test_symlink_out_is_denied"


def test_hook_emits_sdk_deny_shape() -> str:
    """훅이 SDK 가 읽는 모양으로 거부를 낸다 — 모양이 틀리면 조용히 통과된다."""
    with tempfile.TemporaryDirectory() as tmp:
        root = _root(tmp)

        async def run(tool_input: dict) -> dict:
            return await scope_hook({"tool_name": "Read", "tool_input": tool_input}, "tool-1", None, root=root)

        denied = asyncio.run(run({"file_path": "/etc/passwd"}))
        specific = denied["hookSpecificOutput"]
        assert specific["hookEventName"] == "PreToolUse"
        assert specific["permissionDecision"] == "deny"
        assert specific["permissionDecisionReason"]

        allowed = asyncio.run(run({"file_path": "ma_pullback.py"}))
        assert allowed == {}, f"통과인데 판정을 냈다: {allowed}"
    return "test_hook_emits_sdk_deny_shape"


def test_options_actually_install_the_hook() -> str:
    """옵션에 훅이 실제로 물려 있다 — 판정 함수만 옳고 배선이 빠지면 아무것도 안 막는다."""
    from agents.bot_agent import build_options

    with tempfile.TemporaryDirectory() as tmp:
        root = _root(tmp)
        options = build_options(strategies_dir=root, max_turns=2)
        matchers = (options.hooks or {}).get("PreToolUse") or []
        callbacks = [callback for matcher in matchers for callback in matcher.hooks]
        assert callbacks, "PreToolUse 훅이 하나도 안 걸려 있다"

        async def call() -> dict:
            return await callbacks[0]({"tool_name": "Read", "tool_input": {"file_path": "/etc/shadow"}}, "t", None)

        assert asyncio.run(call())["hookSpecificOutput"]["permissionDecision"] == "deny"
    return f"test_options_actually_install_the_hook (훅 {len(callbacks)}개)"


def test_scoped_tools_cover_the_allowed_read_tools() -> str:
    """자동승인하는 읽기 도구가 전부 스코프 대상이다 — 하나라도 빠지면 그 도구로 나간다."""
    from agents.bot_agent import ALLOWED_TOOLS

    missing = [tool for tool in ALLOWED_TOOLS if tool not in PATH_ARGS]
    assert not missing, f"스코프가 안 걸린 자동승인 도구: {missing}"
    assert ALLOWED_TOOLS, "자동승인 목록이 비었다 — 그물이 아무것도 안 본다"
    return f"test_scoped_tools_cover_the_allowed_read_tools ({len(ALLOWED_TOOLS)}종)"


TESTS = [
    test_escapes_are_denied,
    test_inside_is_allowed,
    test_symlink_out_is_denied,
    test_hook_emits_sdk_deny_shape,
    test_options_actually_install_the_hook,
    test_scoped_tools_cover_the_allowed_read_tools,
]


def _unregistered() -> list[str]:
    registered = {test.__name__ for test in TESTS}
    return sorted(
        name
        for name, value in globals().items()
        if name.startswith("test_") and callable(value) and name not in registered
    )


if __name__ == "__main__":
    missing = _unregistered()
    if missing:
        print(f"  FAIL TESTS 목록에 없는 테스트: {', '.join(missing)}")
        raise SystemExit(1)
    failures = 0
    for test in TESTS:
        try:
            print(f"  PASS {test()}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {test.__name__}: {exc}")
    print(f"\n검사한 케이스 {len(TESTS)}건 중 {len(TESTS) - failures}건 통과, {failures}건 실패")
    raise SystemExit(1 if failures else 0)
