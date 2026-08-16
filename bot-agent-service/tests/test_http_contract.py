"""#150 B2 — HTTP 경계를 실제 요청으로 확인한다 (키 없이 되는 데까지).

정적 단언이 못 보는 것 둘을 여기서 본다:

- **공백만 담긴 메시지가 422 로 막히는가.** 종전에는 스키마를 통과한 뒤 서비스가 던졌고, 그
  예외는 이미 시작된 SSE 제너레이터 안이라 `exception_handler` 가 못 잡아 **200 + 제너릭
  에러**가 됐다 (PR #154 독립 리뷰 공격 3).
- **키가 없을 때 대화가 조용히 비지 않고 이유를 내는가.**

standalone 실행:
    APP_ENV=development uv run python tests/test_http_contract.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))
os.environ.setdefault("APP_ENV", "development")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _client(*, role: str = "operator", workspace_id: int | None = 1) -> TestClient:
    """라우터를 실물 그대로 태우되 토큰 검증만 대신한다.

    **권한 게이트는 대신하지 않는다** — 신원을 ContextVar 에 실제로 박아 게이트가 그것을 읽게
    한다. 게이트까지 우회하면 「게스트가 소유자 자격증명을 태운다」를 막았는지 여기서 못 본다.
    """
    from core.auth_context import set_auth_context
    from core.container import Container
    from core.exception_handler import get_exception_handlers
    from core.security import verify_access_token
    from routers.bot_agent import bot_agent_router

    container = Container()
    container.wire(modules=[bot_agent_router])

    # 동기 의존성은 스레드풀에서 돌아 ContextVar 가 요청 컨텍스트로 안 넘어온다 — async 여야 한다.
    async def _as_caller() -> None:
        set_auth_context(user_id="u1", email="lead@local", role=role, workspace_id=workspace_id)

    # 실물과 같은 예외 핸들러를 단다 — 안 달면 게이트가 던진 403/401 이 응답이 되지 않는다.
    app = FastAPI(exception_handlers=get_exception_handlers())
    app.include_router(bot_agent_router.router)
    app.dependency_overrides[verify_access_token] = _as_caller
    return TestClient(app)


def _sse_events(response) -> list:
    events = []
    for line in response.text.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            events.append(json.loads(line[len("data: ") :]))
    return events


def test_blank_message_is_rejected_at_the_boundary() -> str:
    client = _client()
    for raw in ["   ", "\t\n", ""]:
        response = client.post("/bot-agent", json={"message": raw})
        assert response.status_code == 422, f"{raw!r} → {response.status_code} (200 이면 SSE 로 샌 것이다)"
    return "test_blank_message_is_rejected_at_the_boundary (3건)"


def test_missing_key_answers_with_a_reason_not_silence() -> str:
    """키가 없는 환경(=CI·지금 로컬)에서 대화가 이유를 담은 이벤트로 끝난다."""
    from core.config import settings

    if settings.ANTHROPIC_API_KEY:
        return "test_missing_key_answers_with_a_reason_not_silence (키가 있어 건너뜀)"

    response = _client().post("/bot-agent", json={"message": "눌림목 봇 만들어줘"})
    assert response.status_code == 200
    events = _sse_events(response)
    assert events, "이벤트가 하나도 없다 — 빈 대화창이 된다"
    assert events[0]["type"] == "unavailable", events[0]
    assert events[0]["reasons"], "이유 없는 unavailable 은 반쪽이다"
    assert response.text.rstrip().endswith("data: [DONE]"), "스트림이 [DONE] 으로 닫히지 않는다"
    return f"test_missing_key_answers_with_a_reason_not_silence (사유 {len(events[0]['reasons'])}건)"


def test_readiness_tells_why_not() -> str:
    response = _client().get("/bot-agent/readiness")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"ready", "reasons", "strategies_dir"}, body
    assert body["ready"] is bool(body["ready"])
    if not body["ready"]:
        assert body["reasons"], "못 쓰는데 이유가 없다"
    return f"test_readiness_tells_why_not (ready={body['ready']})"


def test_session_id_is_not_accepted_from_the_client() -> str:
    """세션 id 를 요청으로 못 준다 — 받으면 남의 세션 id 를 넣어 남의 대화를 이어받을 수 있다."""
    from schemas.bot_agent.bot_agent_schema import BotAgentIn

    # 필드가 늘면 여기서 걸린다 — 세션 id 같은 「남의 것을 가리키는 손잡이」가 조용히 생기지 않게.
    fields = set(BotAgentIn.model_fields)
    assert fields == {"message", "reset", "form"}, f"요청 필드가 늘었다: {fields}"

    # 몰래 실어 보내도 무시된다 (pydantic 기본이 무시지만, 그 기본이 바뀌면 여기서 걸린다).
    parsed = BotAgentIn(message="안녕", session_id="남의-세션")  # type: ignore[call-arg]
    assert not hasattr(parsed, "session_id")
    return "test_session_id_is_not_accepted_from_the_client"


def test_continuation_is_keyed_by_caller() -> str:
    """이어가기는 **신원별**이다 — 한 사람의 세션이 다른 사람에게 새면 안 된다."""
    from core.config import settings
    from services.bot_agent.bot_agent_service import BotAgentService

    service = BotAgentService(config=settings)
    service._sessions["user-a"] = "session-a"
    assert service._sessions.get("user-b") is None, "다른 신원이 남의 세션을 본다"

    # reset 은 그 신원의 기억만 지운다.
    service._sessions["user-b"] = "session-b"
    service._sessions.pop("user-a", None)
    assert service._sessions == {"user-b": "session-b"}
    return "test_continuation_is_keyed_by_caller"


def test_read_only_guest_cannot_burn_the_owners_credentials() -> str:
    """대화 한 턴은 기계 소유자의 LLM 자격증명을 소모한다 — 읽기전용 게스트는 못 건드린다.

    개인 워크스페이스 모델이 **읽기전용 게스트 초대**를 전제하므로, 로그인만 하면 닿는
    엔드포인트로 두면 초대받은 사람이 소유자 구독을 태울 수 있다.
    """
    guest = _client(role="user")
    for method, path, body in [
        ("post", "/bot-agent", {"message": "봇 만들어줘"}),
        ("get", "/bot-agent/readiness", None),
    ]:
        response = guest.post(path, json=body) if method == "post" else guest.get(path)
        assert response.status_code == 403, f"{path} → {response.status_code} (게스트가 통과했다)"
    return "test_read_only_guest_cannot_burn_the_owners_credentials (2건)"


def test_service_token_and_missing_workspace_are_refused() -> str:
    """워크스페이스가 없는 토큰은 어느 워크스페이스의 자격증명을 쓰는지 말할 수 없다 — 거부."""
    no_workspace = _client(role="operator", workspace_id=None)
    response = no_workspace.get("/bot-agent/readiness")
    assert response.status_code == 401, f"workspace 없음 → {response.status_code}"
    return "test_service_token_and_missing_workspace_are_refused"


TESTS = [
    test_blank_message_is_rejected_at_the_boundary,
    test_session_id_is_not_accepted_from_the_client,
    test_continuation_is_keyed_by_caller,
    test_missing_key_answers_with_a_reason_not_silence,
    test_readiness_tells_why_not,
    test_read_only_guest_cannot_burn_the_owners_credentials,
    test_service_token_and_missing_workspace_are_refused,
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
    if len(TESTS) < 7:
        print(f"  FAIL 검사가 {len(TESTS)}건뿐이다 — 그물이 죽어 있다 (하한 7)")
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
