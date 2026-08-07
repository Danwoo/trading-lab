"""MCP tool 을 활용하는 LangGraph 에이전트 러너."""

from collections.abc import AsyncGenerator

from clients.mcp.mcp_client import get_cached_tools
from core.exceptions import ServiceUnavailableError
from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

# 최대 에이전트 수행 단계: 복합 질문(+ 무한 tool 루프 방지)
_RECURSION_LIMIT = 20


async def stream_mcp_agent(
    chat_client: ChatOpenAI,
    mcp_client: MultiServerMCPClient,
    system_prompt: str,
    messages: list[BaseMessage],
    recursion_limit: int = _RECURSION_LIMIT,
) -> AsyncGenerator[dict, None]:
    """MCP tool 로 LangGraph 에이전트 수행, 진행/답변 스트리밍.

    ``{"status": ...}``(도구 준비·tool 호출 단계) / ``{"content": 델타}``(LLM 최종답 토큰) 이벤트를 yield.
    """
    yield {"status": "도구 준비 중…"}

    try:
        tools = await get_cached_tools(mcp_client)
    except Exception as e:
        raise ServiceUnavailableError("MCP 서버에 연결할 수 없습니다.") from e

    agent = create_agent(chat_client, tools, system_prompt=system_prompt)
    announced: set[str] = set()  # tool 호출 status 중복 방지
    thinking = False  # "생각 중…" 중복 emit 방지 (reasoning 구간은 빈 청크가 연달아 옴)
    async for msg, meta in agent.astream(
        {"messages": messages}, {"recursion_limit": recursion_limit}, stream_mode="messages"
    ):
        if meta.get("langgraph_node") == "tools":
            # 도구 결과 복귀 → 모델이 결과를 보고 다시 추론. 원문은 흘리지 않고 진행만 표시
            if not thinking:
                thinking = True
                yield {"status": "생각 중…"}
            continue
        if not isinstance(msg, AIMessageChunk):
            continue
        for tc in msg.tool_call_chunks or []:  # tool 이름은 첫 chunk 에만 있음
            if tc.get("name") and tc["name"] not in announced:
                announced.add(tc["name"])
                thinking = False
                yield {"status": f"{tc['name']} 호출 중…"}
        if isinstance(msg.content, str) and msg.content:  # ChatOpenAI reasoning_content 드롭
            thinking = False
            yield {"content": msg.content}
        elif not msg.tool_call_chunks and not thinking:
            # content·tool 없는 빈 청크 = reasoning 진행(langchain 이 reasoning_content 를 버림) — 대기 구간을 "생각 중…" 으로 채운다
            thinking = True
            yield {"status": "생각 중…"}
