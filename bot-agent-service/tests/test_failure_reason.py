"""#423 — **실패의 사유가 화면까지 닿는다. 원문은 로그에만 남는다.**

배경: 무효 키로 대화를 걸면 CLI 가 원인을 일반 `text` 로 흘리고(`Invalid API key · Fix external
API key`) `result.subtype` 은 `success` 로 끝낸 뒤, 서버는 그 턴을 「대화 중 문제가 발생했습니다.
잠시 후 다시 시도해 주세요.」 하나로 닫았다. **다시 시도해도 안 된다** — 처방은 키 교체다.
사유를 코드로 실어 보내야 화면이 그 처방을 말할 수 있다 (#342 와 같은 구조).

이 파일이 잠그는 것 넷:
  ① 무효 키 턴이 `botAgent.invalid_api_key` 로 끝난다 (예외가 없어도).
  ② 예외로 끝난 턴이 `botAgent.turn_failed` 로 끝난다.
  ③ 봉투에 SDK 원문·내부 경로·키가 실리지 않는다.
  ④ **lockstep** — 여기서 내는 코드가 프론트의 닫힌 집합에 실제로 있다. 대조 대상이 0건이면 실패한다.

standalone 실행:
    APP_ENV=development uv run python tests/test_failure_reason.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_DIR))
os.environ.setdefault("APP_ENV", "development")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from services.bot_agent.failure_reasons import (  # noqa: E402
    FAILURE_INVALID_API_KEY,
    FAILURE_TURN_FAILED,
    looks_like_auth_failure,
)

# 응답에 실리면 안 되는 것 — 실제 값 대신 눈에 띄는 카나리를 쓴다.
KEY_CANARY = "-".join(["sk", "ant", "CANARY", "4d21"])
PATH_CANARY = "/home/canary-user/.claude/.credentials.json"


def _client() -> TestClient:
    from core.auth_context import set_auth_context
    from core.container import Container
    from core.exception_handler import get_exception_handlers
    from core.security import verify_access_token
    from routers.bot_agent import bot_agent_router

    container = Container()
    container.wire(modules=[bot_agent_router])

    async def _as_caller() -> None:
        set_auth_context(user_id="u1", email="lead@local", role="operator", workspace_id=1)

    app = FastAPI(exception_handlers=get_exception_handlers())
    app.include_router(bot_agent_router.router)
    app.dependency_overrides[verify_access_token] = _as_caller
    return TestClient(app)


def _sse_events(response) -> list:
    return [
        json.loads(line[len("data: ") :])
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]


def _post_with_fake_sdk(replies_factory) -> list:
    """SDK 를 가짜로 갈아 끼우고 한 턴을 태운다 — 실제 호출은 소유자 자격증명을 소모한다."""
    import claude_agent_sdk
    from core.config import settings

    async def _fake_query(*, prompt, options):  # noqa: ARG001
        for reply in replies_factory():
            if isinstance(reply, Exception):
                raise reply
            yield reply

    original_key = settings.ANTHROPIC_API_KEY
    original_query = claude_agent_sdk.query
    settings.ANTHROPIC_API_KEY = KEY_CANARY
    claude_agent_sdk.query = _fake_query
    try:
        response = _client().post("/bot-agent", json={"message": "눌림목 봇 만들어줘"})
        assert response.status_code == 200, response.status_code
        return _sse_events(response)
    finally:
        settings.ANTHROPIC_API_KEY = original_key
        claude_agent_sdk.query = original_query


def _assistant_text(text: str):
    import claude_agent_sdk

    block = claude_agent_sdk.TextBlock(text=text)
    return claude_agent_sdk.AssistantMessage(content=[block], model="canary")


def _result(subtype: str = "success"):
    import claude_agent_sdk

    message = claude_agent_sdk.ResultMessage.__new__(claude_agent_sdk.ResultMessage)
    message.subtype = subtype
    message.session_id = "sess-canary"
    return message


def test_invalid_key_turn_ends_with_a_reason_code() -> str:
    """CLI 가 인증 실패를 text 로만 흘리고 `success` 로 끝내도 그 턴은 **실패**로 닫힌다."""
    events = _post_with_fake_sdk(
        lambda: [_assistant_text("Invalid API key · Fix external API key"), _result("success")]
    )

    # 받은 원인은 버려지지 않는다 — 화면이 지우지 않게 이 자리에 그대로 있어야 한다.
    assert any(e["type"] == "text" and "Invalid API key" in e["text"] for e in events), events

    errors = [e for e in events if e["type"] == "error"]
    assert errors, f"인증이 거부됐는데 실패 이벤트가 없다: {events}"
    assert errors[-1]["code"] == FAILURE_INVALID_API_KEY, errors[-1]
    return "test_invalid_key_turn_ends_with_a_reason_code"


def test_other_failures_end_with_the_generic_reason_code() -> str:
    """인증 실패가 아닌 것을 「키 문제」로 말하지 않는다 — 틀린 처방은 없느니만 못하다."""
    events = _post_with_fake_sdk(lambda: [RuntimeError("session file is corrupted")])

    errors = [e for e in events if e["type"] == "error"]
    assert errors, f"실패했는데 실패 이벤트가 없다: {events}"
    assert errors[-1]["code"] == FAILURE_TURN_FAILED, errors[-1]
    return "test_other_failures_end_with_the_generic_reason_code"


def test_envelope_carries_no_raw_sdk_text() -> str:
    """봉투에는 사유 코드와 우리가 쓴 문구뿐 — 키·내부 경로·스택이 실릴 자리가 없다."""
    leaky = RuntimeError(f"spawn failed: ANTHROPIC_API_KEY={KEY_CANARY} credentials={PATH_CANARY}")
    events = _post_with_fake_sdk(lambda: [leaky])

    errors = [e for e in events if e["type"] == "error"]
    wire = json.dumps(errors, ensure_ascii=False)
    for secret in (KEY_CANARY, PATH_CANARY, "spawn failed", "RuntimeError"):
        assert secret not in wire, f"봉투에 {secret} 가 실렸다: {wire}"
    assert set(errors[-1]) == {"type", "code", "message"}, errors[-1]
    return "test_envelope_carries_no_raw_sdk_text (카나리 4종)"


def test_reason_codes_exist_in_the_frontend_closed_set() -> str:
    """lockstep — 이 서비스가 내는 코드가 프론트의 닫힌 집합에 실제로 있어야 한다.

    한쪽만 바꾸면 화면은 코드를 못 알아보고 조용히 일반 문구로 돌아간다 — 그게 이 이슈였다.
    대조 파일이 사라지면 실패한다(검사 0건은 통과가 아니다).
    """
    source = REPO_ROOT / "frontend/utils/common/errors/streamFailure.ts"
    assert source.is_file(), f"프론트 사유 코드 정본이 없다: {source}"
    text = source.read_text(encoding="utf-8")

    declared = set(re.findall(r'"(botAgent\.[a-z_]+|research\.[a-z_]+)"', text))
    assert declared, f"{source} 에서 코드를 0건 읽었다 — 대조가 죽었다"

    ours = {FAILURE_INVALID_API_KEY, FAILURE_TURN_FAILED}
    missing = ours - declared
    assert not missing, f"프론트 닫힌 집합에 없는 코드: {missing}"
    return f"test_reason_codes_exist_in_the_frontend_closed_set (프론트 {len(declared)}건 중 우리 {len(ours)}건 대조)"


def test_auth_marker_is_narrow_enough() -> str:
    """사용자가 그 단어를 말했다고 「키가 무효다」로 오진하지 않는다."""
    assert looks_like_auth_failure("Invalid API key · Fix external API key")
    assert looks_like_auth_failure("API Error: authentication_error")
    assert not looks_like_auth_failure("API 키를 어디에 넣는지 알려줘")
    assert not looks_like_auth_failure("눌림목 봇을 만들었습니다. 손절은 3%입니다.")
    return "test_auth_marker_is_narrow_enough (4건)"


TESTS = [
    test_invalid_key_turn_ends_with_a_reason_code,
    test_other_failures_end_with_the_generic_reason_code,
    test_envelope_carries_no_raw_sdk_text,
    test_reason_codes_exist_in_the_frontend_closed_set,
    test_auth_marker_is_narrow_enough,
]


if __name__ == "__main__":
    # 검사 0건은 통과가 아니다 — TESTS 가 비면(나쁜 머지·실수) 조용히 exit 0 이 된다.
    if len(TESTS) < 5:
        print(f"  FAIL 검사가 {len(TESTS)}건뿐이다 — 그물이 죽어 있다 (하한 5)")
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
