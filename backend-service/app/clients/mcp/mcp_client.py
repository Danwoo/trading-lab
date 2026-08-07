"""MCP tool 호출 전용 클라이언트 — langchain_mcp_adapters 0.2.2 기반."""

import json
from datetime import timedelta

from clients.mcp.mcp_auth import ServiceJwtAuth
from core.exceptions import ServiceUnavailableError
from core.logger import logger
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

# tool 목록·서버 instructions 는 런타임에 변하지 않으므로 한 번 조회 후 캐싱
_cached_tools: list[BaseTool] | None = None
_cached_instructions: list[str] | None = None


async def get_cached_tools(client: MultiServerMCPClient) -> list[BaseTool]:
    """tool 목록 일차 캐싱. 매 호출 반복 조회 방지."""
    global _cached_tools
    if _cached_tools is None:
        _cached_tools = await client.get_tools()
    return _cached_tools


async def get_cached_instructions(client: MultiServerMCPClient) -> list[str]:
    """연결된 각 MCP 서버의 instructions(도메인 자기소개) 수집·캐싱.

    langchain 어댑터는 서버 instructions 를 LLM 에 전달하지 않으므로, initialize
    핸드셰이크에서 직접 끌어와 시스템 프롬프트에 합친다. 도메인 지식은 서버가 소유하니
    서버를 늘려도 이 함수·소비자 코드는 그대로 — MCP_SERVERS 설정만으로 자동 반영된다.
    """
    global _cached_instructions
    if _cached_instructions is None:
        blocks: list[str] = []
        for name in client.connections:
            try:
                async with client.session(name, auto_initialize=False) as session:
                    result = await session.initialize()
            except Exception:
                logger.warning("MCP 서버 instructions 조회 실패: %s", name)
                continue
            text = (result.instructions or "").strip()
            if text:
                blocks.append(text)
        _cached_instructions = blocks
    return _cached_instructions


def build_mcp_connections(config) -> dict[str, dict]:
    """config.MCP_SERVERS 로부터 MultiServerMCPClient 연결 설정 생성."""
    return {
        s.name: {
            "transport": "streamable_http",
            "url": s.url.rstrip("/") + s.path,
            "auth": ServiceJwtAuth(),
            "timeout": timedelta(seconds=30),
            "sse_read_timeout": timedelta(seconds=300),
        }
        for s in config.MCP_SERVERS
        if s.enabled
    }


def get_mcp_client(config) -> MultiServerMCPClient:
    """MCP 서버 연결 클라이언트 생성."""
    return MultiServerMCPClient(build_mcp_connections(config))


async def call_mcp_tool(client: MultiServerMCPClient, tool_name: str, tool_args: dict | None = None) -> dict:
    """MCP tool 호출 후 JSON dict 반환.

    ``ainvoke()`` 결과는 ``list[dict]`` content block 배열 (``type: "text"`` 또는 ``"json"``).

    아래 실패는 전부 서버측 원인이다 — ``tool_name`` 은 호출부가 하드코딩한 값이라 사용자 입력이
    끼어들 자리가 없다(요청 값으로 도구를 고르지 않는다). 그런데도 예전엔 ``ValueError`` 로 던져
    전역 핸들러(``handle_value_error``)가 400(BadRequestError)으로 응답했다 — "네가 잘못 보냈다"는
    뜻이 되어 진짜 원인(MCP_SERVERS 미설정·MCP 서버 다운·응답 형식 이상)을 가렸다(#246,
    ``GET /chat/accounts`` 400 재현: 로컬 dev 는 ``MCP_SERVERS`` 가 비어 tool 목록이 항상 빈
    배열이라 이 분기로 떨어진다). ``stream_mcp_agent``(clients/mcp/mcp_agent.py)가 이미 같은 부류의
    실패를 ``ServiceUnavailableError``(503)로 옮겨 놓은 것과 맞춘다.
    """
    tools = await get_cached_tools(client)
    matched = next((t for t in tools if t.name == tool_name), None)

    if matched is None:
        logger.warning("Unknown MCP tool: %s. Available: %s", tool_name, [t.name for t in tools])
        raise ServiceUnavailableError(f"도구 '{tool_name}'을(를) 찾을 수 없습니다.")

    # ainvoke(plain dict) → list[dict] content block 배열
    result = await matched.ainvoke(tool_args or {})

    if not isinstance(result, list):
        logger.debug(f"MCP tool {tool_name} 예상 밖 응답 타입: {type(result).__name__}")
        raise ServiceUnavailableError("MCP tool 응답 형식이 유효하지 않습니다.")

    raw_payload = _extract_payload(result, tool_name)
    return _parse_json(raw_payload)


def _extract_payload(result: list, tool_name: str):
    """content block 배열에서 text 또는 json 블록의 payload 추출."""
    for block in result:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            return block["text"]  # JSON 문자열
        if block_type == "json":
            return block["json"]  # 이미 파싱된 dict

    logger.debug(f"MCP tool {tool_name} raw 응답: {str(result)[:500]}")
    raise ServiceUnavailableError("MCP tool 응답에서 text/json 블록을 찾을 수 없습니다.")


def _parse_json(raw_payload) -> dict:
    """text 블록의 JSON 문자열 파싱 또는 이미 파싱된 dict 원본 반환."""
    if isinstance(raw_payload, str):
        try:
            content = json.loads(raw_payload)
        except json.JSONDecodeError as e:
            logger.warning(f"MCP tool 응답 JSON 파싱 실패: {raw_payload[:200]}")
            raise ServiceUnavailableError("MCP tool 응답을 해석할 수 없습니다.") from e
    else:
        content = raw_payload

    return content if isinstance(content, dict) else {"data": content}
