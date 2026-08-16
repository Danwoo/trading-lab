"""#150 B2 — 에이전트에게 무엇을 허용하는가를 코드로 못 박는다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_agent_boundary.py

**왜 테스트인가**: B2 의 완료 조건은 「그 턴이 무엇을 할 수 있는지 경계가 문서에 적힌다」다.
글로만 적으면 코드가 조용히 넓어진다 — 문서와 같은 내용을 실행되는 단언으로 한 번 더 둔다.

검증 대상 불변식:

- **쓰기·실행 도구가 자동승인 목록에 없다.** 지금 범위(대화가 폼을 채운다)는 값을 내놓는 일이라
  파일도 셸도 필요 없다.
- **위험 도구는 bare name 으로 deny** — 그래야 도구 정의가 요청에서 제거돼 모델이 시도조차 못 한다.
- **`bypassPermissions` 를 쓰지 않는다.** 그 모드는 `allowed_tools` 로 못 좁혀서 전부 승인된다.
- **설정 소스를 안 읽는다.** 리드의 `~/.claude`·레포 `.claude/` 의 훅·플러그인·MCP 가 딸려 오면
  이 파일이 선언한 경계 밖이 열린다.
- 옵션 필드 이름과 값 어휘가 **설치된 SDK 의 타입 정의와 일치한다** — SDK 가 올라가며 이름이
  바뀌면 조용히 무시되는 대신 여기서 빨강이 된다.
"""

from __future__ import annotations

import os
import sys
import typing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("APP_ENV", "development")

from agents.bot_agent import (  # noqa: E402
    ALLOWED_TOOLS,
    DISALLOWED_TOOLS,
    PERMISSION_MODE,
    PROPOSAL_TOOL_FULL_NAME,
    SETTING_SOURCES,
    build_options,
)
from claude_agent_sdk import ClaudeAgentOptions  # noqa: E402

# 파일을 쓰거나 명령을 돌리거나 밖으로 나가는 도구 — 지금 범위에서는 하나도 필요 없다.
WRITE_OR_EXEC_TOOLS = {"Bash", "Write", "Edit", "NotebookEdit", "WebSearch", "WebFetch", "Task"}

failures: list[str] = []
checked = 0


def check(condition: bool, message: str) -> None:
    global checked
    checked += 1
    if condition:
        print(f"  ok   {message}")
    else:
        failures.append(message)
        print(f"  FAIL {message}")


def test_allowlist_is_read_only() -> None:
    check(bool(ALLOWED_TOOLS), "자동승인 목록이 비어 있지 않다")
    overlap = sorted(set(ALLOWED_TOOLS) & WRITE_OR_EXEC_TOOLS)
    check(not overlap, f"자동승인 목록에 쓰기·실행 도구가 없다 (있으면: {overlap})")


def test_dangerous_tools_are_denied_by_bare_name() -> None:
    missing = sorted(WRITE_OR_EXEC_TOOLS - set(DISALLOWED_TOOLS))
    check(not missing, f"위험 도구가 전부 deny 목록에 있다 (빠진 것: {missing})")
    scoped = [t for t in DISALLOWED_TOOLS if "(" in t]
    check(not scoped, f"deny 는 bare name 이다 — 스코프 규칙은 도구를 남긴다 ({scoped})")


def test_permission_mode_is_not_bypass() -> None:
    check(PERMISSION_MODE == "dontAsk", f"권한 모드가 dontAsk 다 (지금 {PERMISSION_MODE!r})")
    check(
        PERMISSION_MODE != "bypassPermissions",
        "bypassPermissions 를 쓰지 않는다 — allowed_tools 로 못 좁혀 전부 승인된다",
    )


def test_settings_sources_are_not_loaded() -> None:
    check(SETTING_SOURCES == [], f"설정 소스를 안 읽는다 (지금 {SETTING_SOURCES!r})")


def test_built_options_carry_the_boundary() -> None:
    options = build_options(strategies_dir="/tmp/strategies", max_turns=7, api_key="sk-test-key")
    # 자동승인은 **읽기 셋 + 폼 채우기 도구 하나**뿐이다. 목록을 그대로 적어 비교한다 —
    # 「포함」으로 느슨하게 보면 도구가 하나 더 붙어도 통과한다.
    check(
        list(options.allowed_tools) == [*ALLOWED_TOOLS, PROPOSAL_TOOL_FULL_NAME],
        f"옵션의 allowed_tools 가 선언과 같다 (지금 {list(options.allowed_tools)!r})",
    )
    check(
        PROPOSAL_TOOL_FULL_NAME.startswith("mcp__"),
        "폼 채우기 도구는 in-process MCP 도구다 — 이름이 mcp__ 로 시작해야 SDK 가 그렇게 다룬다",
    )
    check(list(options.disallowed_tools) == list(DISALLOWED_TOOLS), "옵션의 disallowed_tools 가 선언과 같다")
    check(options.permission_mode == PERMISSION_MODE, "옵션의 permission_mode 가 선언과 같다")
    check(options.setting_sources == [], "옵션이 설정 소스를 안 읽는다")
    check(str(options.cwd) == "/tmp/strategies", f"cwd 가 전략 디렉터리로 못박힌다 ({options.cwd})")
    check(options.max_turns == 7, "max_turns 가 전달된다 — 폭주 시 비용 상한")
    check(bool(options.system_prompt), "시스템 프롬프트가 비어 있지 않다")
    # 설정한 키가 자식 프로세스로 **실제로 넘어가는지**. 안 넘기면 SDK 가 부모 환경을 통째로
    # 상속하므로(subprocess_cli 의 inherited_env), 문서가 말하는 인증 경로가 코드에 없게 된다 —
    # 실제로 그렇게 어긋나 있었고 독립 리뷰가 잡았다.
    check(
        dict(options.env or {}).get("ANTHROPIC_API_KEY") == "sk-test-key",
        f"설정한 키가 env 로 자식에게 넘어간다 (지금 {sorted((options.env or {}).keys())!r})",
    )


def test_option_names_match_installed_sdk() -> None:
    """SDK 가 올라가며 필드 이름·어휘가 바뀌면 조용히 무시되는 대신 여기서 걸린다."""
    hints = typing.get_type_hints(ClaudeAgentOptions)
    for field in ["allowed_tools", "disallowed_tools", "permission_mode", "setting_sources", "cwd", "max_turns"]:
        check(field in hints, f"SDK 에 {field} 필드가 있다")

    modes = typing.get_args(hints["permission_mode"])
    # Optional[Literal[...]] → (Literal[...], NoneType)
    literals = next((typing.get_args(m) for m in modes if typing.get_args(m)), ())
    check(PERMISSION_MODE in literals, f"{PERMISSION_MODE!r} 가 SDK 의 권한 모드 어휘에 있다 ({literals})")


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"\n검사 {checked}건 · 실패 {len(failures)}건")
    if checked < 18:
        print(f"::error::검사가 {checked}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    if failures:
        for message in failures:
            print(f"  · {message}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
