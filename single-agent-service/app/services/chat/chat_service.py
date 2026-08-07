# ── [가이드 7/9] services/chat/chat_service.py — 에이전트 보유 + 스트리밍 오케스트레이션 ──
# 무엇: initialize() 가 기동 시 MCP tool 을 수집해 에이전트를 빌드·보관(Singleton). stream_chat 이
#   요청마다 _ensure_agent 로 tool 을 재확인해 집합이 바뀌었을 때만(다운됐던 MCP 복구) 에이전트를 재빌드하고,
#   agent.astream 을 돌며 tool 호출 시작 → step 이벤트, 답변 토큰 → token 이벤트를 yield.
# 복사 후: 도메인 메서드/프롬프트. tool 수집·에이전트 빌드 골격은 그대로.
# 함정: 재빌드는 tool 집합이 변할 때만(전량 수집 후 _ensure_agent 는 네트워크 없이 no-op — 매 요청 재빌드 아님) ·
#   MCP 미기동이면 tool 0개로 fail-soft (에이전트는 LLM 지식만으로 답, 스트림은 안 깨짐) ·
#   stream_mode=["updates","messages"] 면 astream 이 (mode, chunk) 튜플을 준다 · token 은 messages 모드의
#   AIMessageChunk content 델타(tool 노드 메시지 제외).

from collections.abc import AsyncGenerator

from agents.chat_agent import build_chat_agent
from clients.mcp.mcp_client import collect_tool_examples, get_cached_tools
from core.logger import logger
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

_RECURSION_LIMIT = 20


class ChatService:
    """웹 검색 tool 을 호출하는 단일 ReAct 에이전트 챗. MCP tool 은 기동 시 수집해 보관하고,
    다운됐던 서버가 복구돼 tool 이 늘면 요청 경로에서 에이전트를 재빌드한다."""

    def __init__(self, mcp_client: MultiServerMCPClient, llm: ChatOpenAI):
        self.mcp_client = mcp_client
        self.llm = llm
        self.agent = None
        self._bound_tool_names: frozenset[str] = frozenset()  # 현재 에이전트에 바인딩된 tool 이름 — 변하면 재빌드

    async def initialize(self) -> None:
        """lifespan 에서 1회 호출 — MCP tool 수집 후 에이전트 프리빌드. MCP 미기동이면 tool 0개로 fail-soft.
        이후 복구(기동 때 다운됐던 web-mcp 가 살아남)는 stream_chat 의 _ensure_agent 가 반영한다."""
        await self._ensure_agent()

    async def _ensure_agent(self) -> None:
        """MCP tool 을 재수집해 tool 집합이 바뀌었을 때만 에이전트를 재빌드한다.

        에이전트는 기동 시 tool 을 LLM 에 바인딩해 1회 빌드되므로, 기동 때 다운됐던 서버가 살아나
        tool 이 늘어도 재빌드하지 않으면 영구히 반영되지 않는다(#104). get_cached_tools 는 서버별
        캐시라 수집값이 늘거나 유지만 될 뿐 줄지 않으므로(플래핑 없음), 전량 수집 후에는 네트워크 없이
        캐시를 반환해 이 검사는 사실상 no-op 이다 — tool 집합이 그대로면 기존 에이전트를 유지한다."""
        try:
            tools = await get_cached_tools(self.mcp_client)
        except Exception as e:
            if self.agent is not None:
                logger.warning("MCP tool 재수집 실패 — 현 에이전트 유지 (다음 요청 재시도): %r", e)
                return
            logger.warning("MCP tool 수집 실패 — tool 0개로 기동 (LLM 지식만으로 답): %r", e)
            tools = []  # 콜드 스타트 수집 실패 — tool 0개로라도 에이전트를 세워 stream 이 안 깨지게
        tool_names = frozenset(t.name for t in tools)
        if self.agent is not None and tool_names == self._bound_tool_names:
            return  # tool 집합 불변 — 재빌드 불필요
        examples = collect_tool_examples(tools)  # tool _meta 의 few-shot → 프롬프트 블록
        self.agent = build_chat_agent(self.llm, tools, examples)
        self._bound_tool_names = tool_names
        logger.info("ChatService 에이전트 (재)빌드: tools=%d, few-shot=%s", len(tools), "있음" if examples else "없음")

    async def stream_chat(self, question: str) -> AsyncGenerator[dict, None]:
        """질문 → 에이전트 수행 → 이벤트 스트리밍.

        tool 호출 시작은 ``{"type":"step", ...}``, 답변 토큰은 ``{"type":"token","content": ...}`` 이벤트로 yield.
        """
        # 기동 때 다운됐던 web-mcp 가 복구되면 tool 이 늘어 에이전트를 재빌드한다. tool 집합이 그대로면
        # (전량 수집 완료 후 매 요청) 네트워크 없이 no-op — 콜드 스타트면 여기서 최초 빌드된다.
        await self._ensure_agent()

        announced: set[str] = set()  # tool step 중복 방지 (tool 이름은 첫 chunk 에만 옴)
        async for mode, chunk in self.agent.astream(
            {"messages": [HumanMessage(content=question)]},
            {"recursion_limit": _RECURSION_LIMIT},
            stream_mode=["updates", "messages"],
        ):
            if mode == "messages":
                msg, meta = chunk
                if meta.get("langgraph_node") == "tools" or not isinstance(msg, AIMessageChunk):
                    continue
                for tc in msg.tool_call_chunks or []:
                    name = tc.get("name")
                    if name and name not in announced:
                        announced.add(name)
                        yield {"type": "step", "tool": name, "message": f"{name} 호출 중"}
                if isinstance(msg.content, str) and msg.content:
                    yield {"type": "token", "content": msg.content}
