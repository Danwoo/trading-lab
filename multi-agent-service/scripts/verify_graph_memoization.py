"""그래프 메모이즈 계약 검증 — 재사용·무효화·요청 격리·동시성 (#120).

계약:
  (1) _build_graph 는 (enabled_mcps, tool_map 버전) 키로 컴파일 그래프를 재사용한다
      (같은 키 → 동일 객체. 재컴파일 0 이 이벤트루프 블록 제거의 실체).
  (2) tool 집합이 변하면(MCP 서버 복구 — 단조 증가) 버전이 올라 캐시가 무효화되고 재빌드된다.
  (3) 공유 그래프의 sub-agent 호출한도(max_calls)·limit_soft 기수집 출력은 요청 스코프
      config["configurable"]["delegate_runtime"] 에 격리된다 — 요청 간 한도 누적 없음,
      타 요청 출력의 프롬프트 유입(교차 유출) 없음.
  (4) delegate_runtime 은 서비스 config → plan_execute 노드 → res 노드 → tool 까지
      명시 스레딩으로 도달한다 (res 그래프 end-to-end 로 증명).

실제 AgentService._build_graph / wrap_agent_as_tool / build_res_domain_graph 를
FakeLLM·FakeTool 로 구동한다. 동시 실행(같은 컴파일 그래프에 요청 2건 병행)까지 공격한다.

import 체인이 Settings() 를 인스턴스화하므로 env 없는 실행(CI)용 placeholder 를 setdefault.
`uv run python scripts/verify_graph_memoization.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from clients.mcp import mcp_client as mcp_client_module  # noqa: E402
from core.config import settings  # noqa: E402
from graphs.res_pipeline import (  # noqa: E402
    _ExecuteEvaluation,
    _ResultVerdict,
    _SubAgentCall,
    _SubAgentPlan,
    build_res_domain_graph,
)
from graphs.shared import wrap_agent_as_tool  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langchain_core.tools import StructuredTool  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from services.agent.agent_service import AgentService  # noqa: E402
from utils.agent.mcp_classify import ALL_MCP_SERVICES  # noqa: E402


class _FakeLLM:
    """빌드 경로 대역 — 빌드 시점엔 with_structured_output/bind_tools 만 호출된다."""

    def with_structured_output(self, schema):
        return self

    def bind_tools(self, tools, **kwargs):
        return self

    async def ainvoke(self, *args, **kwargs):
        raise AssertionError("빌드 검증에서 LLM 이 호출되면 안 됨")


class _McpToolInput(BaseModel):
    query: str = ""


async def _noop_tool(query: str = "") -> str:
    return ""


def _make_mcp_tool(name: str) -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=_noop_tool, name=name, description=f"{name} mock", args_schema=_McpToolInput
    )


def _make_service() -> AgentService:
    llm = _FakeLLM()
    return AgentService(
        config=settings,
        mcp_client=SimpleNamespace(connections={"fake": None}),
        router_llm=llm,
        planner_llm=llm,
        generator_llm=llm,
        evaluator_llm=llm,
        chat_history_repository=None,
        response_cache=None,
    )


async def _memoization_cases(check) -> None:
    # get_cached_tools 의 서버별 모듈 캐시를 직접 시딩 — 네트워크 없이 수집 완료 상태 재현
    mcp_client_module._tools_by_server.clear()
    mcp_client_module._tools_by_server["fake"] = [
        _make_mcp_tool("web_search"),
        _make_mcp_tool("market_get_price"),
        _make_mcp_tool("news_get_sentiment"),
    ]
    svc = _make_service()
    await svc.initialize()

    all_key = (frozenset(ALL_MCP_SERVICES), svc._tool_map_version)
    check("M1 initialize 프리웜", all_key in svc._graph_cache, f"cache keys={list(svc._graph_cache)}")

    g1 = await svc._build_graph(set(ALL_MCP_SERVICES))
    g2 = await svc._build_graph(set(ALL_MCP_SERVICES))
    check("M2 같은 키 → 동일 객체(재컴파일 0)", g1 is g2 and g1 is svc._graph_cache[all_key], "identity 불일치")

    g_web = await svc._build_graph({"web"})
    g_web2 = await svc._build_graph({"web"})
    check("M3 다른 enabled_mcps → 별도 그래프", g_web is not g1 and g_web is g_web2, "enabled 별 캐시 분리 실패")

    # 서버 복구 시뮬레이션 — tool 추가(단조 증가) → 버전업 + 캐시 무효화
    v_before = svc._tool_map_version
    mcp_client_module._tools_by_server["fake"].append(_make_mcp_tool("disclosure_search_filings"))
    g3 = await svc._build_graph(set(ALL_MCP_SERVICES))
    check(
        "M4 tool 증가 → 버전업", svc._tool_map_version == v_before + 1, f"v={svc._tool_map_version} (before={v_before})"
    )
    check("M4 버전업 → 재빌드", g3 is not g1, "구버전 그래프가 재사용됨 (복구 tool 미반영)")
    check(
        "M4 새 tool 반영",
        "disclosure_search_filings" in svc._tool_map,
        f"tool_map keys={sorted(svc._tool_map)}",
    )

    g4 = await svc._build_graph(set(ALL_MCP_SERVICES))
    check("M5 버전업 후 재수렴(동일 객체)", g4 is g3, "identity 불일치")
    check("M5 변화 없으면 버전 유지", svc._tool_map_version == v_before + 1, f"v={svc._tool_map_version}")


class _FakeSubAgent:
    """wrap_agent_as_tool 이 감싸는 sub-agent 대역 — 호출마다 고유 출력 OUT{n}."""

    def __init__(self) -> None:
        self.call_count = 0

    async def ainvoke(self, inp, config=None):
        self.call_count += 1
        await asyncio.sleep(0.01)  # 동시성 케이스에서 요청 인터리빙 강제
        return {"messages": [AIMessage(content=f"OUT{self.call_count}")]}


_LIMIT_SOFT_MARKER = "호출한도도달"
_LIMIT_HARD_MARKER = "데이터수집실패"


def _cfg(runtime: dict) -> dict:
    return {"configurable": {"delegate_runtime": runtime}}


async def _wrap_isolation_cases(check) -> None:
    agent = _FakeSubAgent()
    tool = wrap_agent_as_tool(agent=agent, name="sub", description="테스트 sub", timeout=5.0, max_calls=1)

    # 요청 A — 한도 내 정상 호출 후 초과분은 limit_soft 로 기수집 출력 재사용
    rt_a: dict = {}
    out1 = await tool.ainvoke({"task": "t1"}, config=_cfg(rt_a))
    out2 = await tool.ainvoke({"task": "t2"}, config=_cfg(rt_a))
    check("W1 요청 내 한도 계수", out1 == "OUT1" and _LIMIT_SOFT_MARKER in out2, f"out1={out1!r} out2={out2[:60]!r}")
    check("W1 limit_soft 는 자기 요청 출력 재사용", "OUT1" in out2, f"out2={out2[:80]!r}")

    # 요청 B — 같은 tool(=캐시 그래프 공유 상황), 새 runtime → 한도 미누적·A 출력 미유입
    # (A 의 2회차는 한도로 sub-agent 미호출이라 B 의 실호출은 OUT2)
    rt_b: dict = {}
    out3 = await tool.ainvoke({"task": "t3"}, config=_cfg(rt_b))
    check(
        "W2 요청 간 한도 비누적",
        _LIMIT_SOFT_MARKER not in out3 and _LIMIT_HARD_MARKER not in out3,
        f"out3={out3[:80]!r}",
    )
    check("W2 타 요청 출력 미유입", "OUT1" not in out3 and out3 == "OUT2", f"out3={out3[:80]!r}")

    # 요청 C — 성공 출력이 없는 초과는 limit_hard (기수집 재사용 없음)
    class _FailAgent:
        async def ainvoke(self, inp, config=None):
            raise RuntimeError("강제 실패")

    fail_tool = wrap_agent_as_tool(agent=_FailAgent(), name="failsub", description="실패 sub", timeout=5.0, max_calls=1)
    rt_c: dict = {}
    err1 = await fail_tool.ainvoke({"task": "t"}, config=_cfg(rt_c))
    err2 = await fail_tool.ainvoke({"task": "t"}, config=_cfg(rt_c))
    check(
        "W3 실패만 있으면 limit_hard",
        "오류" in err1 and _LIMIT_HARD_MARKER in err2,
        f"err1={err1!r} err2={err2[:60]!r}",
    )

    # delegate_runtime 미주입 — 비용 게이트라 fail-soft (한도 계수 없이 정상 동작)
    out4 = await tool.ainvoke({"task": "t4"})
    out5 = await tool.ainvoke({"task": "t5"})
    check(
        "W4 runtime 미주입 fail-soft",
        _LIMIT_SOFT_MARKER not in out4 + out5 and _LIMIT_HARD_MARKER not in out4 + out5,
        f"out4={out4[:60]!r} out5={out5[:60]!r}",
    )


class _StructuredLLM:
    def __init__(self, value) -> None:
        self._value = value

    async def ainvoke(self, messages, config=None):
        return self._value


class _FakeRouterLLM:
    """res 그래프 router 대역 — route 는 고정 plan, synthesize 는 입력 캡처."""

    def __init__(self, plan: _SubAgentPlan) -> None:
        self._plan = plan
        self.synth_inputs: list[str] = []

    def with_structured_output(self, schema):
        if schema is _SubAgentPlan:
            return _StructuredLLM(self._plan)
        return _StructuredLLM(_ExecuteEvaluation(verdicts=[_ResultVerdict(agent="sub", verdict="accept")]))

    async def ainvoke(self, messages, config=None):
        self.synth_inputs.append(str(messages[-1].content))
        return AIMessage(content="[SYNTH]")


async def _res_threading_cases(check) -> None:
    # group 0 → group 1 순차 plan 으로 같은 sub 를 2회 호출 — 2회차는 limit_soft (요청 내 계수 증명)
    agent = _FakeSubAgent()
    tool = wrap_agent_as_tool(agent=agent, name="sub", description="테스트 sub", timeout=5.0, max_calls=1)
    plan = _SubAgentPlan(
        calls=[
            _SubAgentCall(agent="sub", task="1차 조회", group=0),
            _SubAgentCall(agent="sub", task="2차 조회", group=1),
        ]
    )
    llm = _FakeRouterLLM(plan)
    graph = build_res_domain_graph(
        domain_name="verify", router_llm=llm, domain_tools=[tool], domain_prompt="테스트 도메인", sub_agent_timeout=5.0
    )

    # 요청 1 — config 가 res 노드를 거쳐 tool 까지 도달해야 한도 계수가 생긴다
    rt1: dict = {}
    await graph.ainvoke({"messages": [HumanMessage(content="작업")]}, config=_cfg(rt1))
    check("R1 config 스레딩 도달(계수 생성)", rt1.get("sub", {}).get("count") == 2, f"rt1={rt1!r}")
    check("R1 1회 실행 + 1회 limit", agent.call_count == 1, f"agent.call_count={agent.call_count}")
    synth1 = llm.synth_inputs[-1]
    check(
        "R1 limit_soft 자기 출력 재사용", _LIMIT_SOFT_MARKER in synth1 and "OUT1" in synth1, f"synth={synth1[:200]!r}"
    )

    # 요청 2 — 같은 컴파일 그래프 재사용, 새 runtime → 한도 비누적 (실제 호출이 다시 일어남)
    rt2: dict = {}
    await graph.ainvoke({"messages": [HumanMessage(content="작업")]}, config=_cfg(rt2))
    check(
        "R2 요청 간 한도 비누적",
        rt2.get("sub", {}).get("count") == 2 and agent.call_count == 2,
        f"rt2={rt2!r} call_count={agent.call_count}",
    )
    synth2 = llm.synth_inputs[-1]
    check("R2 타 요청 출력 미유입", "OUT1" not in synth2 and "OUT2" in synth2, f"synth={synth2[:200]!r}")


async def _concurrency_cases(check) -> None:
    # 같은 컴파일 그래프에 요청 2건 병행 — runtime 이 요청별이면 출력이 섞이지 않는다
    agent = _FakeSubAgent()
    tool = wrap_agent_as_tool(agent=agent, name="sub", description="테스트 sub", timeout=5.0, max_calls=1)
    plan = _SubAgentPlan(
        calls=[
            _SubAgentCall(agent="sub", task="1차 조회", group=0),
            _SubAgentCall(agent="sub", task="2차 조회", group=1),
        ]
    )
    llm = _FakeRouterLLM(plan)
    graph = build_res_domain_graph(
        domain_name="verify", router_llm=llm, domain_tools=[tool], domain_prompt="테스트 도메인", sub_agent_timeout=5.0
    )
    rt_x: dict = {}
    rt_y: dict = {}
    await asyncio.gather(
        graph.ainvoke({"messages": [HumanMessage(content="작업X")]}, config=_cfg(rt_x)),
        graph.ainvoke({"messages": [HumanMessage(content="작업Y")]}, config=_cfg(rt_y)),
    )
    check(
        "X1 동시 요청 계수 독립",
        rt_x.get("sub", {}).get("count") == 2 and rt_y.get("sub", {}).get("count") == 2,
        f"rt_x={rt_x!r} rt_y={rt_y!r}",
    )
    check("X1 요청당 실제 호출 1회씩", agent.call_count == 2, f"agent.call_count={agent.call_count}")
    # 각 synthesize 입력에는 자기 요청의 OUT{n} 하나만 등장해야 한다 (교차 유출 0)
    mixed = []
    for synth in llm.synth_inputs:
        tokens = {t for t in ("OUT1", "OUT2") if t in synth}
        if len(tokens) != 1:
            mixed.append(synth[:120])
    check("X2 동시 요청 출력 비혼입", not mixed, f"mixed={mixed!r}")


def main() -> int:
    problems: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        if not ok:
            problems.append(f"{name}: {detail}")

    asyncio.run(_memoization_cases(check))
    asyncio.run(_wrap_isolation_cases(check))
    asyncio.run(_res_threading_cases(check))
    asyncio.run(_concurrency_cases(check))

    if problems:
        print("그래프 메모이즈 계약 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        "그래프 메모이즈 OK — 같은 키 identity 재사용 + tool 증가 버전 무효화 + "
        "delegate_runtime 요청 격리(한도 비누적·교차 유출 0) + res end-to-end config 스레딩 + 동시 요청 비혼입 성립"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
