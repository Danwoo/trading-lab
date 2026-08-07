"""Graph 빌더 — 해결된 의존성(_GraphDeps)을 만들고 top-level 노드/라우터를 StateGraph 에 배선한다.

노드/라우터 로직은 형제 모듈(nodes·map_reduce·routing)의 top-level 함수로 분리하고, 여기서는
functools.partial 로 deps 를 바인딩해 등록만 한다. 그래프 구조(노드·엣지·조건분기)는
scripts/verify_plan_execute_refactor.py 의 topology 축이 계약으로 고정한다.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from graphs.system import (
    PLAN_SYSTEM,
    PLAN_SYSTEM_TEMPLATE,
    REPLAN_SYSTEM,
    REPLAN_SYSTEM_TEMPLATE,
)
from langgraph.graph import END, START, StateGraph

from .deps import _build_dynamic_schemas, _GraphDeps
from .map_reduce import _map_answer_node, _reduce_node
from .nodes import (
    _answer_node,
    _clarify_node,
    _guardrail_node,
    _plan_node,
    _replan_node,
    _run_stage_node,
)
from .routing import (
    _route_after_clarify,
    _route_after_execute,
    _route_after_guardrail,
    _route_after_replan,
)
from .schemas import ClarifyDecision, PlanExecuteState


def _named(fn: Callable, deps: _GraphDeps, trace_name: str) -> Callable:
    """deps 바인딩 라우터에 trace 표시명(__name__)을 부여 — LangSmith/langfuse 가독용."""
    bound = functools.partial(fn, deps)
    bound.__name__ = trace_name  # type: ignore[attr-defined]
    return bound


def build_plan_execute_graph(
    planner_llm,
    generator_llm,
    agents: dict,
    agent_timeout: float = 90.0,
    agent_max_retries: int = 0,
    agent_retry_delay: float = 1.0,
    agent_descriptions: dict[str, str] | None = None,
    *,
    plan_timeout_s: float = 60.0,
    answer_timeout_s: float = 180.0,
    react_recursion_limit: int = 20,
    clarifier_llm=None,
    clarify_timeout_s: float = 15.0,
    enable_clarify: bool = True,
    guardrail_fn=None,
    guardrail_llm=None,
    guardrail_timeout_s: float = 15.0,
    enable_guardrail: bool = True,
    replanner_llm=None,
    max_replan: int = 2,
    map_reduce_domain_threshold: int = 3,
    map_concurrency: int = 2,
    map_timeout_s: float = 50.0,
    reduce_mode: str = "full",
    writer_llm=None,
    history_max_chars: int = 8000,
):
    """Plan-then-Execute StateGraph 빌드.

    Args:
        planner_llm: 계획 생성 LLM (with_structured_output 지원 필요)
        generator_llm: 최종 답변 생성 LLM
        agents: {에이전트 이름: 에이전트 객체} — keys() 로 동적 스키마 생성, 런타임 확장 가능
        agent_descriptions: 주어지면 PLAN_SYSTEM 의 에이전트 목록 섹션을 동적 구성
        clarifier_llm: Clarification 노드용 LLM. None 이면 planner_llm 재사용
        enable_clarify: True 면 START→clarify→[plan|END], False 면 START→plan
        guardrail_fn: 보안 판정 함수(check_guardrail) — 서비스가 주입(graphs→services 역의존 회피)
        guardrail_llm: 보안검사 노드용 LLM. None 이면 planner_llm 재사용
        enable_guardrail: True 면 진입 노드가 보안검사(차단 시 END). 현재 질문만 검사(히스토리 격리)
        replanner_llm: 재계획 노드용 LLM (빠른 router 권장). None 이면 planner_llm 재사용
        max_replan: 재계획으로 추가 가능한 stage 횟수 상한 (무한 루프 방지)
        map_reduce_domain_threshold: 활성 도메인 수가 이 값 이상이면 map_answer→reduce 경로
        writer_llm: 주어지면 Map 단계가 tool evidence 기반 Writer 권한 분리로 동작
                    (MA_WRITER_AS_MAP=false 환경변수로 비상 우회 가능)
        history_max_chars: 노드당 히스토리 프롬프트 주입 총량 상한(문자, MA_HISTORY_MAX_CHARS)
    """
    # agents.keys() 를 description 에 포함해 LLM 라우팅 정확도를 높인 동적 스키마 → 구조화 출력 바인딩.
    agent_names_str = ", ".join(sorted(agents.keys()))
    _, execution_plan_cls, replan_decision_cls = _build_dynamic_schemas(agent_names_str)

    resolved_clarifier_llm = clarifier_llm if clarifier_llm is not None else planner_llm
    resolved_guardrail_llm = guardrail_llm if guardrail_llm is not None else planner_llm
    resolved_replanner_llm = replanner_llm if replanner_llm is not None else planner_llm

    if agent_descriptions:
        agent_list_lines = "\n".join(f"- {name:<22}: {desc}" for name, desc in agent_descriptions.items())
        plan_system = PLAN_SYSTEM_TEMPLATE.format(agents_section=agent_list_lines)
        replan_system = REPLAN_SYSTEM_TEMPLATE.format(agents_section=agent_list_lines)
    else:
        plan_system = PLAN_SYSTEM
        replan_system = REPLAN_SYSTEM

    deps = _GraphDeps(
        planner=planner_llm.with_structured_output(execution_plan_cls),
        clarifier=resolved_clarifier_llm.with_structured_output(ClarifyDecision),
        replanner=resolved_replanner_llm.with_structured_output(replan_decision_cls),
        generator_llm=generator_llm,
        guardrail_llm=resolved_guardrail_llm,
        guardrail_fn=guardrail_fn,
        guardrail_timeout_s=guardrail_timeout_s,
        writer_llm=writer_llm,
        agents=agents,
        agent_timeout=agent_timeout,
        agent_max_retries=agent_max_retries,
        agent_retry_delay=agent_retry_delay,
        react_recursion_limit=react_recursion_limit,
        plan_system=plan_system,
        replan_system=replan_system,
        plan_timeout_s=plan_timeout_s,
        answer_timeout_s=answer_timeout_s,
        clarify_timeout_s=clarify_timeout_s,
        map_timeout_s=map_timeout_s,
        history_max_chars=history_max_chars,
        enable_clarify=enable_clarify,
        enable_guardrail=enable_guardrail,
        max_replan=max_replan,
        map_reduce_domain_threshold=map_reduce_domain_threshold,
        map_concurrency=map_concurrency,
        reduce_mode=reduce_mode,
    )

    graph = StateGraph(PlanExecuteState)
    graph.add_node("계획수립", functools.partial(_plan_node, deps))
    graph.add_node("도메인실행", functools.partial(_run_stage_node, deps))
    graph.add_node("재계획", functools.partial(_replan_node, deps))
    graph.add_node("답변작성", functools.partial(_answer_node, deps))
    graph.add_node("도메인별답변", functools.partial(_map_answer_node, deps))
    graph.add_node("답변통합", functools.partial(_reduce_node, deps))

    # trace 가독을 위한 한글 분기명. 라우터 함수명은 영어로 두고 trace 표시명만 __name__ 으로 한글화.
    route_after_clarify = _route_after_clarify
    route_after_clarify.__name__ = "보충질문_분기"
    if enable_clarify:
        graph.add_node("보충질문확인", functools.partial(_clarify_node, deps))
        graph.add_conditional_edges("보충질문확인", route_after_clarify, {"계획수립": "계획수립", END: END})

    # 진입 노드 체인: (보안검사) → (보충질문확인) → 계획수립. 게이트는 차단 시 END.
    _entry_after_gate = "보충질문확인" if enable_clarify else "계획수립"
    if enable_guardrail:
        graph.add_node("보안검사", functools.partial(_guardrail_node, deps))
        graph.add_edge(START, "보안검사")
        graph.add_conditional_edges(
            "보안검사",
            _named(_route_after_guardrail, deps, "보안검사_분기"),
            {_entry_after_gate: _entry_after_gate, END: END},
        )
    else:
        graph.add_edge(START, _entry_after_gate)
    graph.add_edge("계획수립", "도메인실행")
    graph.add_edge("도메인실행", "재계획")
    graph.add_conditional_edges(
        "재계획",
        _named(_route_after_replan, deps, "재계획_분기"),
        {"도메인실행": "도메인실행", "답변작성": "답변작성", "도메인별답변": "도메인별답변"},
    )
    graph.add_edge("답변작성", END)
    graph.add_edge("도메인별답변", "답변통합")
    graph.add_edge("답변통합", END)

    return graph.compile()


# _route_after_execute 는 _route_after_replan 이 위임 호출 — 직접 등록되지 않으나 trace 명 부여.
_route_after_execute.__name__ = "답변경로_분기"
