"""계층형 멀티에이전트 sub/domain 팩토리.

12개 sub-agent + 4개 domain-agent 를 생성한다.

아키텍처:
    4 도메인 에이전트 (RES pipeline, sub-agent 를 도구로 보유)
    └── 12 sub-agent (ReAct + MCP 도구)

도구는 MultiServerMCPClient 가 모든 MCP 서버에서 수집한 tool 목록을
SubAgentSpec.mcp_tools 이름으로 필터해 분배한다 — 미존재 도구는 경고 후 제외
(서버 확장 시 자동 바인딩).
"""

from __future__ import annotations

from typing import Any

from agents.builders import get_builder
from agents.specs import _SECURITY_FOOTER, DomainSpec, SubAgentSpec
from core.logger import logger
from graphs.pipeline_subagent import build_pipeline_subagent
from graphs.shared import wrap_agent_as_tool
from langchain_core.tools import StructuredTool


async def create_sub_agents(
    router_llm: Any,
    generator_llm: Any,
    tool_map: dict[str, Any],
    subagent_registry: dict[str, SubAgentSpec],
) -> dict[str, Any]:
    """sub-agent 생성 — 모두 writer 게이트 명시 파이프라인 엔진.

    판단·도구선택·최종답은 강한 generator_llm(writer), 인자 생성은 약한 router_llm(param).

    Args:
        router_llm: param 노드(인자 생성)용 소형 LLM
        generator_llm: writer 노드(판단·도구선택·답변)용 대형 LLM
        tool_map: {tool_name: BaseTool} — MultiServerMCPClient 수집 결과
        subagent_registry: load_domain_registry() 의 SUBAGENT_REGISTRY

    Returns:
        {sub_agent_name: compiled_pipeline_graph}
    """
    agents: dict[str, Any] = {}

    for name, spec in subagent_registry.items():
        tools: list[Any] = []
        for tool_name in spec.mcp_tools:
            t = tool_map.get(tool_name)
            if t is not None:
                tools.append(t)
            else:
                logger.warning("[sub_agents] MCP 도구 없음: %s (하위 에이전트: %s)", tool_name, name)

        base_prompt = spec.prompt or f"당신은 투자 리서치 전문 에이전트({name})입니다."
        agents[name] = build_pipeline_subagent(generator_llm, router_llm, tools, base_prompt, _SECURITY_FOOTER)
        logger.info("[sub_agents] 생성: %s (domain=%s, tools=%d, pipeline writer=gen)", name, spec.domain, len(tools))

    return agents


async def create_domain_agents(
    router_llm: Any,
    sub_agents: dict[str, Any],
    domain_registry: dict[str, DomainSpec],
    subagent_registry: dict[str, SubAgentSpec],
    sub_agent_timeout: float = 60.0,
    max_sub_calls: int = 2,
) -> tuple[dict[str, Any], dict[str, list[StructuredTool]]]:
    """도메인 에이전트 생성. DomainSpec.builder 값으로 RES pipeline / ReAct 빌더 dispatch.

    sub-agent 단위 writer 분리는 pipeline_subagent 가 담당하므로 wrap 단계는 ReAct 결과를 그대로 감싼다.

    Returns:
        ({domain_name: compiled_graph}, {domain_name: [wrapped_sub_tool, ...]})
    """
    domain_agents: dict[str, Any] = {}
    sub_tool_registry: dict[str, list[StructuredTool]] = {}

    for domain_name, domain_spec in domain_registry.items():
        domain_tools: list[StructuredTool] = []

        for sub_name in domain_spec.sub_agents:
            sub_agent = sub_agents.get(sub_name)
            if sub_agent is None:
                logger.warning("[domain_agents] 하위 에이전트 없음: %s (도메인: %s)", sub_name, domain_name)
                continue
            sub_spec = subagent_registry[sub_name]
            tool = wrap_agent_as_tool(
                agent=sub_agent,
                name=sub_name,
                description=sub_spec.description,
                timeout=sub_agent_timeout,
                max_calls=max_sub_calls,
            )
            domain_tools.append(tool)

        builder = get_builder(domain_spec.builder)
        domain_agents[domain_name] = builder(
            domain_name,
            router_llm,
            domain_tools,
            f"{domain_spec.prompt}\n\n{_SECURITY_FOOTER}",
            sub_agent_timeout,
        )
        logger.info(
            "[domain_agents] 생성: %s (builder=%s, sub_agents=%d)",
            domain_name,
            domain_spec.builder,
            len(domain_tools),
        )

        sub_tool_registry[domain_name] = domain_tools

    return domain_agents, sub_tool_registry


def get_domain_descriptions(domain_registry: dict[str, DomainSpec]) -> dict[str, str]:
    """도메인 에이전트 설명 딕셔너리 (플래너 프롬프트 구성용)."""
    return {name: spec.description for name, spec in domain_registry.items()}
