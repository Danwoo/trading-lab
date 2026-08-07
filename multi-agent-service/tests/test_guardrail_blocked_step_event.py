"""#338 리뷰 지적 — guardrail 차단 시 step 이벤트 문구가 실제 사유와 어긋난다 (LLM 호출 0회).

agent_service.py 의 stream_query()/stream_query_example_ai() 는 그래프 "보안검사" 노드가
guardrail_blocked=True 를 내면 두 이벤트를 보낸다: step("guardrail","blocked", message=...) 와
text(refusal). 고치기 전엔 step 쪽 message 가 항상 고정 상수 MSG_GUARDRAIL_BLOCKED
("안전 검사에서 이 질문은 처리할 수 없습니다.")였다 — UNSAFE(injection/harmful) 차단이면 맞는
말이지만, #338 로 추가된 unavailable(가드레일 응답불가) 차단에도 똑같이 나가 사용자가
"내 질문이 위험 판정을 받았다"로 오해한다. 실제 원인은 node_output["refusal_message"]
(카테고리별 문구, GuardrailVerdict.refusal_message 정본)에 이미 있으므로 step 이벤트도
그 문구를 그대로 쓰게 한다.

AgentService._build_graph 를 캡처용 스텁으로 바꿔치기해(실제 그래프·MCP·LLM 미기동) "보안검사"
노드가 guardrail_blocked=True + refusal_message="unavailable" 문구를 낸 상황을 재현하고,
step 이벤트의 message 가 그 문구와 일치하는지(고정 상수가 아닌지) 확인한다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_guardrail_blocked_step_event.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from services.agent.agent_service import AgentService  # noqa: E402
from utils.agent.events import MSG_GUARDRAIL_BLOCKED  # noqa: E402

_UNAVAILABLE_MESSAGE = "보안 점검이 지금 응답하지 않아 요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요."


class _FakeChatHistoryRepo:
    async def select_history(self, email: str, gid: int) -> list:
        return []


class _FakeResponseCache:
    def get(self, key: str):
        return None

    def set(self, key: str, value: str) -> None:
        pass


class _FakeConfig:
    """post-loop 의 build_trace_metadata(trace_enabled=self._config.MA_TRACE_TOKEN_USAGE) 가
    참조하는 최소 설정 스텁 — 없으면 guardrail 차단 뒤 post-loop 에서 AttributeError 로 새어
    "스트리밍 오류" 로그가 섞여 정작 검증하려는 신호(step 이벤트 message)와 무관한 잡음이 낀다."""

    MA_TRACE_TOKEN_USAGE = False


class _GuardrailBlockedGraph:
    """astream 스텁 — "보안검사" 노드가 unavailable 차단을 낸 updates 청크 1건만 흘린다."""

    def __init__(self, refusal_message: str, stream_mode_keys: tuple[str, ...]) -> None:
        self._refusal_message = refusal_message
        self._stream_mode_keys = stream_mode_keys

    async def astream(self, state, config, stream_mode):
        assert list(stream_mode) == list(self._stream_mode_keys), stream_mode
        yield (
            "updates",
            {"보안검사": {"guardrail_blocked": True, "refusal_message": self._refusal_message}},
        )


def _make_service() -> AgentService:
    return AgentService(
        config=_FakeConfig(),
        mcp_client=None,
        router_llm=None,
        planner_llm=None,
        generator_llm=None,
        evaluator_llm=None,
        chat_history_repository=_FakeChatHistoryRepo(),
        response_cache=_FakeResponseCache(),
    )


async def test_native_stream_step_event_carries_refusal_not_generic_constant() -> str:
    """stream_query()(네이티브 SSE) — step("guardrail","blocked") 의 message 가 refusal_message 그대로."""
    service = _make_service()
    graph = _GuardrailBlockedGraph(_UNAVAILABLE_MESSAGE, ("updates", "custom"))

    async def _fake_build_graph(enabled_mcps):
        return graph

    service._build_graph = _fake_build_graph

    events = [ev async for ev in service.stream_query("질문", "user@test", 1, set())]

    step_events = [ev for ev in events if ev.get("type") == "step" and ev.get("phase") == "guardrail"]
    assert len(step_events) == 1, f"guardrail step 이벤트가 정확히 1개가 아님: {step_events}"
    assert step_events[0]["message"] == _UNAVAILABLE_MESSAGE, (
        f"step 이벤트 message 가 refusal_message 와 다름(#338 리뷰): {step_events[0]['message']!r}"
    )
    assert step_events[0]["message"] != MSG_GUARDRAIL_BLOCKED, (
        "step 이벤트가 고정 상수 MSG_GUARDRAIL_BLOCKED 로 되돌아감 — unavailable 도 "
        "'위험 판정' 문구로 오해시키는 결함이 재발"
    )
    text_events = [ev for ev in events if ev.get("type") == "text"]
    assert text_events and text_events[0]["content"] == _UNAVAILABLE_MESSAGE, text_events
    return "test_native_stream_step_event_carries_refusal_not_generic_constant"


async def test_native_stream_falls_back_to_generic_constant_when_refusal_absent() -> str:
    """refusal_message 가 없는 방어적 상황에서는 기존처럼 MSG_GUARDRAIL_BLOCKED 로 폴백(회귀 방향)."""
    service = _make_service()
    graph = _GuardrailBlockedGraph.__new__(_GuardrailBlockedGraph)
    graph._stream_mode_keys = ("updates", "custom")

    async def _astream(state, config, stream_mode):
        yield ("updates", {"보안검사": {"guardrail_blocked": True}})  # refusal_message 키 자체가 없음

    graph.astream = _astream

    async def _fake_build_graph(enabled_mcps):
        return graph

    service._build_graph = _fake_build_graph

    events = [ev async for ev in service.stream_query("질문", "user@test", 1, set())]
    step_events = [ev for ev in events if ev.get("type") == "step" and ev.get("phase") == "guardrail"]
    assert step_events[0]["message"] == MSG_GUARDRAIL_BLOCKED, step_events
    return "test_native_stream_falls_back_to_generic_constant_when_refusal_absent"


async def _main() -> int:
    tests = [
        test_native_stream_step_event_carries_refusal_not_generic_constant,
        test_native_stream_falls_back_to_generic_constant_when_refusal_absent,
    ]
    passed = 0
    for tc in tests:
        name = await tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
