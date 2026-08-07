"""#207 — 시나리오별 라우터 LLM 호출 횟수 회귀 핀 (E-207 Tier 0, 실 LLM 호출 0회).

전 그래프(guardrail·clarify·plan → 도메인 RES → sub-agent 파이프라인 → replan → answer)를
호출 카운팅 스텁 LLM 으로 실행해 라우터 호출 수 상한을 박는다 — 이후 어떤 변경이 호출 수를
늘리면 여기서 잡힌다. 상한값은 스텁 실측으로 확정한 값이다 (추정치 아님):
  단일 도메인 질문 = 라우터 6회 (보안검사·보충질문·계획·에이전트선택·인자생성·재계획)
  도메인 외(tool 0개 기동) = 라우터 3회 (보안검사·보충질문·계획)

스텁은 라벨을 자칭하지 않고 프로덕션이 준 run_name 을 그대로 센다 — 스텁이 라벨을 하드코딩하면
프로덕션이 run_name 을 안 붙여도 핀은 초록이고, usage tracker 만 그 호출을 놓친다(#207 관측 사각).
그래서 호출 수 핀과 라벨 부착을 같은 실행에서 함께 단언한다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_router_call_budget.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from agents.registry import load_domain_registry  # noqa: E402
from agents.sub_agents import create_domain_agents, create_sub_agents, get_domain_descriptions  # noqa: E402
from graphs.pipeline_subagent import _RUN_NAME_PARAM, _RUN_NAME_WRITER  # noqa: E402
from graphs.plan_execute import build_plan_execute_graph  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langchain_core.tools import StructuredTool  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from services.agent.guardrail import check_guardrail  # noqa: E402

# 스텁 실측 핀 (상한) — 호출 수가 이 값을 넘으면 회귀. 줄어드는 것은 통과(개선).
_ROUTER_MAX_SINGLE_DOMAIN = 6
_ROUTER_MAX_OUT_OF_DOMAIN = 3
# fail-closed 바닥 — 그래프가 실제로 돌지 않아 0회로 초록이 되는 것을 막는다
_ROUTER_MIN_SINGLE_DOMAIN = 4
_ROUTER_MIN_OUT_OF_DOMAIN = 2


_UNLABELED_ROUTER = "라우터 무라벨"
_UNLABELED_GENERATOR = "generator 무라벨"


class _Counter:
    def __init__(self) -> None:
        self.by_label: dict[str, int] = {}

    def hit(self, label: str) -> None:
        self.by_label[label] = self.by_label.get(label, 0) + 1

    @property
    def total(self) -> int:
        return sum(self.by_label.values())


def _assert_all_labeled(router: _Counter, gen: _Counter) -> None:
    """호출 수 핀과 함께 라벨 부착도 실행 시점에 확인한다 (#207 관측 사각 재발 방지).

    호출 수만 세면 run_name 이 빠져도 초록이다 — 그러면 usage tracker 는 그 호출을 라우터로
    분류하지 못하는데 핀은 통과한다. 정적 전수 조사(test_usage_tracker)와 이중으로 막는다.
    """
    assert not [k for k in router.by_label if k.startswith(_UNLABELED_ROUTER)], (
        f"run_name 없는 라우터 호출: {router.by_label}"
    )
    assert not [k for k in gen.by_label if k.startswith(_UNLABELED_GENERATOR)], (
        f"run_name 없는 generator 호출: {gen.by_label}"
    )


class _StructuredStub:
    """with_structured_output 스텁 — 스키마 필드로 노드를 식별해 고정 응답 반환 + 카운트."""

    def __init__(self, counter: _Counter, schema: type, plan_payload: dict) -> None:
        self._counter = counter
        self._schema = schema
        self._plan_payload = plan_payload

    async def ainvoke(self, messages, config=None):
        run_name = (config or {}).get("run_name") or f"{_UNLABELED_ROUTER}({self._schema.__name__})"
        self._counter.hit(run_name)
        fields = self._schema.model_fields
        if "is_safe" in fields:
            return self._schema(is_safe=True)
        if "intent" in fields:
            return self._schema(intent="proceed")
        if "stages" in fields:
            return self._schema.model_validate(self._plan_payload)
        if "calls" in fields:  # RES route — financials_sub 1개 호출
            return self._schema.model_validate(
                {"calls": [{"agent": "financials_sub", "task": "재무 분석: 삼성전자 최근 분기 실적", "group": 0}]}
            )
        if "verdicts" in fields:
            return self._schema.model_validate({"verdicts": []})
        if "done" in fields:
            return self._schema.model_validate({"done": True, "reason": "충분"})
        raise AssertionError(f"예상 밖 구조화 스키마: {self._schema.__name__}")


class _BoundParamStub:
    """param(인자 생성) 스텁 — 라벨을 자칭하지 않고 프로덕션이 준 run_name 을 그대로 센다.

    스텁이 라벨을 하드코딩하면 프로덕션이 그 라벨을 안 붙여도 핀은 초록이 된다 — 실제로
    그 틈에서 관측 사각이 났다. 라벨 부재를 여기서 즉시 드러내려 config 를 읽는다.
    """

    def __init__(self, counter: _Counter, tool_name: str) -> None:
        self._counter = counter
        self._tool_name = tool_name

    async def ainvoke(self, messages, config=None):
        self._counter.hit((config or {}).get("run_name") or _UNLABELED_ROUTER)
        return AIMessage(
            content="", tool_calls=[{"name": self._tool_name, "args": {}, "id": "p1", "type": "tool_call"}]
        )


class _RouterStub:
    """라우터 LLM 스텁 — 모든 소비 형태(structured/bind_tools/plain)를 카운트."""

    def __init__(self, counter: _Counter, plan_payload: dict) -> None:
        self._counter = counter
        self._plan_payload = plan_payload

    def with_structured_output(self, schema):
        return _StructuredStub(self._counter, schema, self._plan_payload)

    def bind_tools(self, tools, tool_choice=None):
        return _BoundParamStub(self._counter, tool_choice or tools[0].name)

    async def ainvoke(self, messages, config=None):
        self._counter.hit((config or {}).get("run_name") or _UNLABELED_ROUTER)
        return AIMessage(content="합성 답변 " + "가" * 300)


class _GeneratorStub:
    """generator LLM 스텁 — sub-agent writer 와 그래프 answer 노드를 run_name 으로 분리 카운트."""

    def __init__(self, counter: _Counter) -> None:
        self._counter = counter

    async def ainvoke(self, messages, config=None):
        run_name = (config or {}).get("run_name") or _UNLABELED_GENERATOR
        self._counter.hit(run_name)
        if run_name != _RUN_NAME_WRITER:  # answer/reduce 등 — 평문 최종 답변
            return AIMessage(content="최종 답변 " + "가" * 120)
        prompt = messages[-1].content if messages else ""
        if "(아직 없음)" in prompt:  # 첫 진입 — 도구 선택
            return AIMessage(
                content='{"enough": false, "next_tool": "disclosure_financials", "intent": "재무 데이터 검색"}'
            )
        answer = "증거 기반 재무 분석 답변 " + "가" * 300  # ≥200자 — RES synthesize fast-path 조건 유지
        return AIMessage(content=json.dumps({"enough": True, "answer": answer}, ensure_ascii=False))


class _EmptyArgs(BaseModel):
    query: str = ""


def _stub_tool(name: str) -> StructuredTool:
    async def _run(query: str = "") -> str:
        return f"{name} 검색 결과: 매출 79조원, 영업이익 10.4조원 (2026Q2)" + " 상세" * 50

    return StructuredTool.from_function(coroutine=_run, name=name, description=f"{name} 스텁", args_schema=_EmptyArgs)


async def _build_graph(router_counter: _Counter, gen_counter: _Counter, plan_payload: dict):
    subagent_registry, domain_registry = load_domain_registry(["financials"])
    router = _RouterStub(router_counter, plan_payload)
    generator = _GeneratorStub(gen_counter)
    tool_map = {
        name: _stub_tool(name)
        for name in (
            "disclosure_financials",
            "disclosure_company",
            "doc_search_topic_earnings",
            "doc_search_topic_workspace",
        )
    }
    sub_agents = await create_sub_agents(router, generator, tool_map, subagent_registry)
    domain_agents, _ = await create_domain_agents(router, sub_agents, domain_registry, subagent_registry)
    return build_plan_execute_graph(
        planner_llm=router,
        generator_llm=generator,
        agents=domain_agents,
        agent_descriptions=get_domain_descriptions(domain_registry),
        clarifier_llm=router,
        guardrail_fn=check_guardrail,
        guardrail_llm=router,
        replanner_llm=router,
        writer_llm=generator,
    )


async def _run_scenario(question: str, plan_payload: dict) -> tuple[_Counter, _Counter, dict]:
    router_counter, gen_counter = _Counter(), _Counter()
    graph = await _build_graph(router_counter, gen_counter, plan_payload)
    out = await graph.ainvoke(
        {"messages": [HumanMessage(content=question)]},
        config={"recursion_limit": 100, "configurable": {"delegate_runtime": {}}},
    )
    return router_counter, gen_counter, out


async def test_single_domain_router_budget() -> str:
    """단일 도메인 질문 — 라우터 호출 상한 핀 (실측 6: 보안·보충·계획·선택·인자·재계획)."""
    plan_payload = {
        "reasoning": "재무 단일 도메인",
        "stages": [
            [{"agent_name": "financials_domain", "task": "재무 분석: 삼성전자 최근 분기 실적", "depends_on_agents": []}]
        ],
    }
    router, gen, out = await _run_scenario("삼성전자 최근 분기 실적 알려줘", plan_payload)
    print(f"  단일 도메인 라우터 호출: total={router.total} by={router.by_label}")
    print(f"  단일 도메인 generator 호출: total={gen.total} by={gen.by_label}")
    assert router.total <= _ROUTER_MAX_SINGLE_DOMAIN, (
        f"라우터 호출 증가 회귀: {router.total} > {_ROUTER_MAX_SINGLE_DOMAIN} ({router.by_label})"
    )
    assert router.total >= _ROUTER_MIN_SINGLE_DOMAIN, (
        f"호출 수가 비정상적으로 적음 — 그래프 미실행 의심: {router.by_label}"
    )
    _assert_all_labeled(router, gen)
    assert _RUN_NAME_PARAM in router.by_label, (
        f"sub-agent 인자 생성이 라우터 라벨로 안 잡힘 — evals _ROUTER_LABELS 와 어긋난다: {router.by_label}"
    )
    assert out.get("final_answer"), "최종 답변 없음 (시나리오가 끝까지 돌지 않음)"
    return "test_single_domain_router_budget"


async def test_out_of_domain_router_budget() -> str:
    """도메인 외(정당한 빈 계획, tool 0개 기동) — 라우터 호출 상한 핀 (실측 3)."""
    plan_payload = {"reasoning": "도메인 외", "stages": []}
    router, gen, out = await _run_scenario("다음 주 날씨 알려줘", plan_payload)
    print(f"  도메인 외 라우터 호출: total={router.total} by={router.by_label}")
    print(f"  도메인 외 generator 호출: total={gen.total} by={gen.by_label}")
    assert router.total <= _ROUTER_MAX_OUT_OF_DOMAIN, (
        f"라우터 호출 증가 회귀: {router.total} > {_ROUTER_MAX_OUT_OF_DOMAIN} ({router.by_label})"
    )
    assert router.total >= _ROUTER_MIN_OUT_OF_DOMAIN, (
        f"호출 수가 비정상적으로 적음 — 그래프 미실행 의심: {router.by_label}"
    )
    _assert_all_labeled(router, gen)
    assert out.get("final_answer"), "최종 답변 없음"
    return "test_out_of_domain_router_budget"


async def _main() -> int:
    tests = [test_single_domain_router_budget, test_out_of_domain_router_budget]
    passed = 0
    for tc in tests:
        name = await tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
