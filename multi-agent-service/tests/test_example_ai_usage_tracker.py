"""#283 — stream_query_example_ai 경로에 usage tracker 부착 (LLM 호출 0회).

#207 T1 의 UsageTracker 부착은 stream_query(native) 한정이었다. stream_query_example_ai 는
graph.astream 의 config["callbacks"] 에 tracker 가 없어 그 경로로 흐르는 토큰이 [usage] 로그·
관측 어디에도 잡히지 않았다 — 무료 티어 TPD 가 실질 한계인 상황(#207)에서 관측 사각.

AgentService._build_graph 를 캡처용 스텁으로 바꿔치기해(실제 그래프·MCP·LLM 미기동), 서비스가
astream 에 넘기는 config 와 title/follow_up 호출에 넘기는 config 를 그대로 검사한다 — 실제
스트리밍 코드 경로를 태우되 외부 호출은 0회.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_example_ai_usage_tracker.py
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

from langchain_core.messages import AIMessageChunk  # noqa: E402
from services.agent.agent_service import AgentService  # noqa: E402
from utils.agent.usage_tracker import UsageTracker  # noqa: E402


class _FakeChatHistoryRepo:
    async def select_history(self, email: str, gid: int) -> list:
        return []


class _FakeResponseCache:
    def get(self, key: str):
        return None

    def set(self, key: str, value: str) -> None:
        pass


class _FakeGenerator:
    """title/follow_up 생성용 스텁 — 넘겨받은 config 를 캡처(callbacks 전파 확인)."""

    def __init__(self) -> None:
        self.captured_configs: list = []

    async def ainvoke(self, prompt, config=None):
        self.captured_configs.append(config or {})

        class _Reply:
            content = "제목"

        return _Reply()


class _CapturingGraph:
    """graph.astream 스텁 — 서비스가 넘기는 config 를 캡처하고 최소 이벤트만 흘린다."""

    def __init__(self) -> None:
        self.captured_config: dict | None = None

    async def astream(self, state, config, stream_mode):
        self.captured_config = config
        yield ("messages", (AIMessageChunk(content="답변 본문입니다."), {"langgraph_node": "답변작성"}))
        yield ("custom", {"event": "execution_complete"})


def _make_service(generator: _FakeGenerator) -> tuple[AgentService, _CapturingGraph]:
    service = AgentService(
        config=None,
        mcp_client=None,
        router_llm=None,
        planner_llm=None,
        generator_llm=generator,
        evaluator_llm=None,
        chat_history_repository=_FakeChatHistoryRepo(),
        response_cache=_FakeResponseCache(),
    )
    graph = _CapturingGraph()

    async def _fake_build_graph(enabled_mcps):
        return graph

    service._build_graph = _fake_build_graph  # 실제 MCP·LLM 배선 없이 캡처 스텁으로 대체
    return service, graph


async def test_astream_config_carries_usage_tracker() -> str:
    """graph.astream 에 넘어가는 callbacks 에 UsageTracker 인스턴스가 포함된다 (관측 사각 해소)."""
    generator = _FakeGenerator()
    service, graph = _make_service(generator)

    events = [ev async for ev in service.stream_query_example_ai("질문", "user@test", 1, set())]

    assert any(ev.get("type") == "workflow_complete" for ev in events), "스트림이 정상 종료되지 않음"
    assert graph.captured_config is not None, "astream 이 호출되지 않음 — 그물 자체가 안 돎"
    callbacks = graph.captured_config.get("callbacks") or []
    trackers = [cb for cb in callbacks if isinstance(cb, UsageTracker)]
    assert len(trackers) == 1, f"UsageTracker 가 astream callbacks 에 정확히 1개 없음: {callbacks}"
    return "test_astream_config_carries_usage_tracker"


async def test_title_follow_up_config_carries_same_tracker() -> str:
    """title/follow_up(post-loop LLM 호출)도 같은 tracker 로 잡힌다 — 그래프 밖 토큰 관측 사각 해소."""
    generator = _FakeGenerator()
    service, graph = _make_service(generator)

    _ = [ev async for ev in service.stream_query_example_ai("질문", "user@test", 1, set())]

    assert graph.captured_config is not None
    astream_tracker = next(cb for cb in graph.captured_config["callbacks"] if isinstance(cb, UsageTracker))

    assert len(generator.captured_configs) == 2, (
        f"title·follow_up 호출 수 기대 2, 실제 {len(generator.captured_configs)}"
    )
    for cfg in generator.captured_configs:
        post_trackers = [cb for cb in (cfg.get("callbacks") or []) if isinstance(cb, UsageTracker)]
        assert post_trackers, f"title/follow_up config 에 UsageTracker 없음: {cfg}"
        assert post_trackers[0] is astream_tracker, (
            "title/follow_up 이 astream 과 다른 tracker 인스턴스를 씀 — 관측이 쪼개짐"
        )
    return "test_title_follow_up_config_carries_same_tracker"


async def _main() -> int:
    tests = [
        test_astream_config_carries_usage_tracker,
        test_title_follow_up_config_carries_same_tracker,
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
