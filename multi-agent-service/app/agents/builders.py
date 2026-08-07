"""도메인 에이전트 그래프 빌더 전략 레지스트리.

새 패턴 추가 = BUILDERS dict 에 함수 1개 등록. DomainSpec.builder 필드로 선택.
  "res_pipeline" — Route-Execute-Synthesize 3단 파이프라인 (기본, 병렬 고속)
  "react"        — 표준 ReAct 에이전트 (폴백/단순 도메인용)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.logger import logger
from langchain.agents import create_agent
from langchain_core.tools import StructuredTool

DomainBuilder = Callable[[str, Any, list[StructuredTool], str, float], Any]


def _build_react_domain(
    domain_name: str,
    router_llm: Any,
    domain_tools: list[StructuredTool],
    domain_prompt: str,
    sub_agent_timeout: float = 60.0,
) -> Any:
    """표준 ReAct 에이전트로 도메인 그래프 구성 (폴백/단순 도메인용)."""
    return create_agent(router_llm, domain_tools, system_prompt=domain_prompt)


def _build_res_pipeline(
    domain_name: str,
    router_llm: Any,
    domain_tools: list[StructuredTool],
    domain_prompt: str,
    sub_agent_timeout: float = 60.0,
) -> Any:
    from graphs.res_pipeline import build_res_domain_graph

    return build_res_domain_graph(
        domain_name=domain_name,
        router_llm=router_llm,
        domain_tools=domain_tools,
        domain_prompt=domain_prompt,
        sub_agent_timeout=sub_agent_timeout,
    )


BUILDERS: dict[str, DomainBuilder] = {
    "res_pipeline": _build_res_pipeline,
    "react": _build_react_domain,
}


def get_builder(name: str) -> DomainBuilder:
    """BUILDERS 에서 빌더 반환. 없으면 기본값(res_pipeline)."""
    if name not in BUILDERS:
        logger.warning("[builders] 알 수 없는 빌더: %r → 기본값 'res_pipeline' 사용", name)
        name = "res_pipeline"
    return BUILDERS[name]
