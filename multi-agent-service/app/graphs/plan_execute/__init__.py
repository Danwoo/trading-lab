"""Plan-then-Execute StateGraph — 결정론적 멀티 에이전트 실행 엔진.

ReAct Supervisor 와의 핵심 차이: LLM 은 "계획"만 세우고 실행은 코드가 담당해
순차/병렬을 강제한다 (LLM 이 언제 멈출지 결정하지 않음).

플로우:
  [Query]
    → clarify_node(LLM)                     # proceed/clarify/refuse 분기
    → plan_node(LLM)                        # depends_on_agents 포함 ExecutionPlan → pending_stages 큐 적재
    → run_stage_node(결정론적)              # 큐에서 stage 1개 pop 실행 (stage 내 병렬)
    → replan_node(LLM, 별도):               # 실행과 분리된 '재계획' — 순차 의존 후속을 동적 재배정
         · pending 남음/추가      → run_stage_node 루프
         · done or 상한(max_replan) → _route_after_execute:
              · 1-2 도메인  → answer_node(LLM)              → [Answer]
              · 3+ 도메인   → map_answer(도메인별 sub-answer) → reduce(통합) → [Answer]

사용:
    graph = build_plan_execute_graph(planner_llm=..., generator_llm=..., agents={...})
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=query)]},
        config={"recursion_limit": 100},
    )

모듈 경계 (상세: .docs/guides/multi-agent-plan-execute.md):
    builder      — build_plan_execute_graph (deps 생성 + StateGraph 배선)
    deps         — _GraphDeps + 동적 라우팅 스키마 팩토리
    nodes        — 코어 노드 (guardrail·clarify·plan·run_stage·replan·answer)
    map_reduce   — 도메인별 sub-answer(Map) + 통합(Reduce) 노드
    routing      — 조건 분기 라우터 4종
    schemas      — Pydantic 모델 + State
    tool_trace   — _ToolTraceCallback + tool 출력 텍스트 추출
    context      — 쿼리/히스토리/이전결과 프롬프트 포매팅
    compliance   — COMPLIANCE_DISCLAIMER + 결정론적 고지 백스톱
    domains_map  — 도메인 라벨·분류 + Map-Reduce 그룹핑 (★ 새 도메인 추가 지점)
    topology     — depends_on_agents 위상 정렬
    invocation   — 에이전트 안전 호출

내부 헬퍼도 `graphs.plan_execute.<name>` 경로로 재노출한다 — 서브모듈 구조와 무관하게
심볼에 닿아야 하는 검증 하네스(scripts/verify_plan_execute_refactor.py)의 접근 경로다.
"""

from __future__ import annotations

from .builder import build_plan_execute_graph as build_plan_execute_graph
from .compliance import COMPLIANCE_DISCLAIMER as COMPLIANCE_DISCLAIMER
from .compliance import _ensure_disclaimer as _ensure_disclaimer
from .context import _build_history_ctx as _build_history_ctx
from .context import _extract_query as _extract_query
from .context import _format_all_results_for_answer as _format_all_results_for_answer
from .context import _format_prior_stage_results as _format_prior_stage_results
from .domains_map import _DOMAIN_LABELS as _DOMAIN_LABELS
from .domains_map import _SUBAGENT_DOMAIN_MAP as _SUBAGENT_DOMAIN_MAP
from .domains_map import _build_subagent_domain_map as _build_subagent_domain_map
from .domains_map import _classify_domain as _classify_domain
from .domains_map import _count_active_domains as _count_active_domains
from .domains_map import _format_domain_results as _format_domain_results
from .domains_map import _group_results_by_domain as _group_results_by_domain
from .invocation import _invoke_agent_safe as _invoke_agent_safe
from .schemas import VALID_AGENTS as VALID_AGENTS
from .schemas import ClarifyDecision as ClarifyDecision
from .schemas import ExecutionPlan as ExecutionPlan
from .schemas import PlanExecuteState as PlanExecuteState
from .schemas import ReplanDecision as ReplanDecision
from .schemas import StageTask as StageTask
from .tool_trace import _tool_output_text as _tool_output_text
from .tool_trace import _ToolTraceCallback as _ToolTraceCallback
from .topology import _normalize_stages as _normalize_stages

__all__ = [
    "COMPLIANCE_DISCLAIMER",
    "VALID_AGENTS",
    "ClarifyDecision",
    "ExecutionPlan",
    "PlanExecuteState",
    "ReplanDecision",
    "StageTask",
    "build_plan_execute_graph",
]
