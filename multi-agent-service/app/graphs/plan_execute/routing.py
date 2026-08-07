"""조건 분기(라우터) — 진입 게이트·재계획 후 다음 노드를 state 로 결정.

deps 를 참조하는 라우터(guardrail/execute/replan)는 build 시 functools.partial 로 바인딩된다.
분기 대상 문자열은 그래프 add_conditional_edges 의 path_map 키와 lockstep (topology 계약).
"""

from __future__ import annotations

from core.logger import logger
from langgraph.graph import END

from .deps import _GraphDeps
from .domains_map import _count_active_domains
from .schemas import PlanExecuteState


def _route_after_guardrail(deps: _GraphDeps, state: PlanExecuteState) -> str:
    if state.get("guardrail_blocked"):
        return END
    return "보충질문확인" if deps.enable_clarify else "계획수립"


def _route_after_clarify(state: PlanExecuteState) -> str:
    intent = state.get("clarify_intent") or "proceed"
    return "계획수립" if intent == "proceed" else END


def _route_after_execute(deps: _GraphDeps, state: PlanExecuteState) -> str:
    """stage_results 의 활성 도메인 수로 분기 — 임계 이상이면 Map-Reduce, 미만이면 single answer."""
    stage_results = state.get("stage_results") or []
    active_domains = _count_active_domains(stage_results)
    if active_domains >= deps.map_reduce_domain_threshold:
        logger.info("[route] map_reduce 경로 진입: %d 활성 도메인", active_domains)
        return "도메인별답변"
    return "답변작성"


def _route_after_replan(deps: _GraphDeps, state: PlanExecuteState) -> str:
    """재계획 후 분기 — 실행 대기 stage 가 있으면 단계실행 루프, 없으면 답변 경로로."""
    if state.get("pending_stages"):
        return "도메인실행"
    return _route_after_execute(deps, state)
