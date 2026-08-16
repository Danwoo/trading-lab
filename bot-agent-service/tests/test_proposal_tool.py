"""#150 B2 — 대화가 폼을 채우는 통로(제안 도구)의 계약.

키 없이 검증되는 것만 여기서 본다: **모양**과 **배선**. 모델이 실제로 이 도구를 부르는지는
실행으로 확인했고(PR 코멘트), 그 왕복은 이 파일이 검증하지 않는다.

standalone 실행:
    APP_ENV=development uv run python tests/test_proposal_tool.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("APP_ENV", "test")

from agents.proposal_tool import INPUT_SCHEMA, PROPOSAL_TOOL_NAME, normalize_proposal  # noqa: E402

REJECTED: list[dict] = [
    {},
    {"strategy_key": "", "params": {}},
    {"strategy_key": "ma_pullback"},
    {"strategy_key": "ma_pullback", "params": "period=20"},
    {"strategy_key": 3, "params": {}},
]


def test_shape_is_enforced() -> str:
    """모양이 아니면 제안으로 안 친다 — 폼에 쓰레기가 들어가면 사용자가 그걸 저장한다."""
    for args in REJECTED:
        assert normalize_proposal(args) is None, f"통과됐다: {args}"
    return f"test_shape_is_enforced ({len(REJECTED)}건 전부 거부)"


def test_scalars_only() -> str:
    """폼이 그릴 수 있는 값만 남긴다 — 중첩 구조는 컨트롤 세 종이 못 그린다."""
    event = normalize_proposal(
        {
            "strategy_key": " ma_pullback ",
            "params": {"period": 60, "depth": 3.5, "confirm": True, "label": "눌림목", "nested": {"a": 1}, "list": [1]},
            "note": "  ",
        }
    )
    assert event is not None
    assert event["strategy_key"] == "ma_pullback", "앞뒤 공백이 안 잘렸다"
    assert event["params"] == {"period": 60, "depth": 3.5, "confirm": True, "label": "눌림목"}
    assert event["note"] is None, "공백만 있는 note 는 없는 것으로 친다"
    assert event["type"] == "proposal"
    return "test_scalars_only"


def test_schema_declares_what_the_model_must_send() -> str:
    """스키마가 필수 둘을 요구한다 — 모델이 절반만 보내면 도구 단계에서 걸린다."""
    assert INPUT_SCHEMA["required"] == ["strategy_key", "params"]
    assert set(INPUT_SCHEMA["properties"]) == {"strategy_key", "params", "note"}
    return "test_schema_declares_what_the_model_must_send"


def test_tool_is_allowed_and_scoped_out() -> str:
    """도구가 자동승인 목록에 있고, **경로 스코프 대상은 아니다**(파일을 안 만진다)."""
    from agents.bot_agent import ALLOWED_TOOLS, PROPOSAL_TOOL_FULL_NAME, build_options
    from agents.tool_scope import PATH_ARGS, check_tool_scope

    assert PROPOSAL_TOOL_FULL_NAME.endswith(PROPOSAL_TOOL_NAME)
    assert PROPOSAL_TOOL_FULL_NAME not in ALLOWED_TOOLS, "읽기 도구 목록과 섞이면 스코프 검사가 이 도구를 찾는다"
    assert PROPOSAL_TOOL_FULL_NAME not in PATH_ARGS
    assert check_tool_scope(PROPOSAL_TOOL_FULL_NAME, {"params": {"x": 1}}, Path(".")) is None

    options = build_options(strategies_dir=Path("."), max_turns=2, api_key="sk-test-key")
    assert PROPOSAL_TOOL_FULL_NAME in options.allowed_tools, "허용 목록에 없으면 dontAsk 에서 거부된다"
    return "test_tool_is_allowed_and_scoped_out"


def test_server_is_wired_when_given() -> str:
    """서버를 넘기면 옵션에 실린다 — 안 실리면 모델에게 도구가 아예 안 보인다."""
    from agents.bot_agent import build_options
    from agents.proposal_tool import build_proposal_server

    collected: list[dict] = []
    options = build_options(
        strategies_dir=Path("."),
        max_turns=2,
        api_key="sk-test-key",
        proposal_server=build_proposal_server(collected.append),
    )
    assert "bot_form" in (options.mcp_servers or {}), "MCP 서버가 안 실렸다"
    assert build_options(strategies_dir=Path("."), max_turns=2, api_key="sk-test-key").mcp_servers == {}
    return "test_server_is_wired_when_given"


def test_system_prompt_tells_the_model_to_use_it() -> str:
    """프롬프트가 도구를 쓰라고 말한다 — 도구만 달고 말 안 하면 모델은 말로만 답한다."""
    from agents.bot_agent import SYSTEM_PROMPT

    assert PROPOSAL_TOOL_NAME in SYSTEM_PROMPT, "프롬프트가 도구 이름을 안 부른다"
    return "test_system_prompt_tells_the_model_to_use_it"


TESTS = [
    test_shape_is_enforced,
    test_scalars_only,
    test_schema_declares_what_the_model_must_send,
    test_tool_is_allowed_and_scoped_out,
    test_server_is_wired_when_given,
    test_system_prompt_tells_the_model_to_use_it,
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
    # 검사 0건은 통과가 아니다 — `TESTS` 가 비면(나쁜 머지·실수) 조용히 exit 0 이 된다.
    if len(TESTS) < 6:
        print(f"  FAIL 검사가 {len(TESTS)}건뿐이다 — 그물이 죽어 있다 (하한 6)")
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
