"""#274 — RES 도메인 에이전트 route LLM 실패 시 무음 폴백 (E-274, LLM 호출 0회).

route LLM(에이전트 선택) 이 실패하면 스펙 순서 첫 2개 sub-agent 로 기본 계획을 세우는 폴백은
유지하되(#197 과 달리 이 경로는 결과 evaluate 노드가 뒤에서 관련성을 다시 거른다 — 처방 범위는
관측 부착), 그 사실이 route_status 상태 필드로 남는지 검증한다.
반대로 route LLM 이 정상 응답하면 route_status="ok" 로 남아 폴백과 구분된다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_res_route_fallback_status.py
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

from graphs.res_pipeline import _SubAgentCall, _SubAgentPlan, build_res_domain_graph  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langchain_core.tools import StructuredTool  # noqa: E402
from pydantic import BaseModel  # noqa: E402


class _TaskArgs(BaseModel):
    task: str = ""


async def _make_tool(name: str) -> StructuredTool:
    async def _run(task: str = "") -> str:
        return f"{name} 결과: 정상 데이터"

    return StructuredTool.from_function(coroutine=_run, name=name, description=f"{name} 설명", args_schema=_TaskArgs)


class _RaisingStructured:
    """route 구조화 출력 호출이 항상 실패 (429 등 스텁)."""

    async def ainvoke(self, messages, config=None):
        raise RuntimeError("429 rate limited (스텁)")


class _OkStructured:
    def __init__(self, plan: _SubAgentPlan) -> None:
        self._plan = plan

    async def ainvoke(self, messages, config=None):
        return self._plan


class _FakeRouterLLM:
    """with_structured_output 은 스텁 구조화기를 반환, 평문 ainvoke 는 synthesize 용 답변."""

    def __init__(self, structured) -> None:
        self._structured = structured

    def with_structured_output(self, model):
        return self._structured

    async def ainvoke(self, messages, config=None):
        return AIMessage(content="합성된 답")


async def _build_two_tools() -> list[StructuredTool]:
    return [await _make_tool("domain_a"), await _make_tool("domain_b")]


async def test_route_failure_marks_fallback_status() -> str:
    """route LLM 예외 → route_status='fallback' + 스펙 순서 첫 2개 계획 (무음 아님 — 상태에 남음)."""
    tools = await _build_two_tools()
    graph = build_res_domain_graph("financials", _FakeRouterLLM(_RaisingStructured()), tools, "도메인 설명")

    out = await graph.ainvoke({"messages": [HumanMessage(content="질문")]}, config={})

    assert out["route_status"] == "fallback", out["route_status"]
    chosen = [c.agent for c in out["sub_plan"].calls]
    assert chosen == ["domain_a", "domain_b"], f"스펙 순서 첫 2개 계약 위반: {chosen}"
    return "test_route_failure_marks_fallback_status"


async def test_route_success_marks_ok_status() -> str:
    """route LLM 정상 응답 → route_status='ok' — 폴백과 구분된다 (회귀 방향)."""
    tools = await _build_two_tools()
    normal_plan = _SubAgentPlan(calls=[_SubAgentCall(agent="domain_b", task="질문", group=0)])
    graph = build_res_domain_graph("financials", _FakeRouterLLM(_OkStructured(normal_plan)), tools, "도메인 설명")

    out = await graph.ainvoke({"messages": [HumanMessage(content="질문")]}, config={})

    assert out["route_status"] == "ok", out["route_status"]
    chosen = [c.agent for c in out["sub_plan"].calls]
    assert chosen == ["domain_b"], f"정상 경로 계획이 변형됨: {chosen}"
    return "test_route_success_marks_ok_status"


async def _main() -> int:
    tests = [
        test_route_failure_marks_fallback_status,
        test_route_success_marks_ok_status,
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
