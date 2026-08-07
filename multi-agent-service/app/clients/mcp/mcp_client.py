"""MCP tool 수집 전용 클라이언트 — langchain_mcp_adapters 0.2.2 기반.

5개 MCP 서버(market-data/disclosure/news/web/doc-search)의 tool 을 모아 sub-agent 에 분배한다.
tool 호출 자체는 LangGraph 에이전트(ReAct)가 수행 — 이 모듈은 연결·수집·캐싱만.
"""

import asyncio
import json
import time
from datetime import timedelta

from clients.mcp.mcp_auth import ServiceJwtAuth
from core.logger import logger
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

# 서버별 tool 캐시 — 성공한 서버만 담긴다. 어댑터의 무인자 get_tools() 는 gather 를
# return_exceptions 없이 돌려 한 서버 실패가 전체를 raise 하므로, 서버별로 나눠 부분 성공을 허용한다.
_tools_by_server: dict[str, list[BaseTool]] = {}
# 아직 못 모은(다운) 서버 재시도 스로틀 — 영구 다운 서버가 매 요청을 timeout 만큼 블록하지 않게.
_RETRY_COOLDOWN_S = 60.0
_last_attempt_monotonic: float = 0.0
_collect_lock = asyncio.Lock()


async def get_cached_tools(client: MultiServerMCPClient) -> list[BaseTool]:
    """서버별 tool 을 부분 성공 허용으로 수집·캐싱한다.

    아직 캐시 안 된 서버만 조회하므로 (1) 한 서버가 잠깐 다운돼도 정상 서버 tool 은 보존되고
    (2) 다음 호출에서 실패했던 서버만 재시도돼 복구된다. 재시도는 쿨다운으로 스로틀링해
    영구 다운 서버가 매 호출을 블록하지 않게 한다. 전량 수집되면 이후 호출은 네트워크 없이 캐시 반환.
    """
    global _last_attempt_monotonic
    server_names = list(client.connections.keys())
    if _pending(server_names) and _cooldown_elapsed():
        async with _collect_lock:
            # 락 대기 중 앞선 호출이 이미 수집했을 수 있어 재확인.
            pending = _pending(server_names)
            if pending and _cooldown_elapsed():
                _last_attempt_monotonic = time.monotonic()
                results = await asyncio.gather(
                    *(client.get_tools(server_name=name) for name in pending),
                    return_exceptions=True,
                )
                for name, result in zip(pending, results, strict=True):
                    if isinstance(result, BaseException):
                        logger.warning(
                            "[mcp_client] '%s' MCP tool 수집 실패 — 이번 수집 제외, 최대 %ds 후 재시도: %r",
                            name,
                            int(_RETRY_COOLDOWN_S),
                            result,
                        )
                        continue
                    _tools_by_server[name] = result
    return [tool for name in server_names if name in _tools_by_server for tool in _tools_by_server[name]]


def _pending(server_names: list[str]) -> list[str]:
    """아직 성공 수집 안 된 서버 목록."""
    return [name for name in server_names if name not in _tools_by_server]


def _cooldown_elapsed() -> bool:
    """마지막 수집 시도 이후 쿨다운이 지났는지 (기동 직후 최초 시도는 항상 허용)."""
    return (time.monotonic() - _last_attempt_monotonic) >= _RETRY_COOLDOWN_S


def collect_tool_examples(tools: list[BaseTool]) -> str:
    """넘긴 tool 들의 few-shot 예시(_meta)를 모아 프롬프트 블록 생성. 없으면 빈 문자열.

    서버가 tool _meta 로 노출(meta.few_shot_examples)하면 adapter 는 tool.metadata["_meta"] 로 전달한다.
    multi-agent 는 sub-agent 마다 자기 바인딩 tool 만 넘겨 호출 → 각 sub-agent 가 자기 예시만 받는다.
    이 hop(서버 meta → wire → tool.metadata["_meta"])은 여기 한 곳에만 가둔다.
    """
    lines: list[str] = []
    for t in tools:
        meta = (getattr(t, "metadata", None) or {}).get("_meta") or {}
        for ex in meta.get("few_shot_examples") or []:
            lines.append(f'- {t.name}: "{ex.get("질문", "")}" → {json.dumps(ex.get("호출", {}), ensure_ascii=False)}')
    return "### 도구 호출 예시 (질문 → 인자)\n" + "\n".join(lines) if lines else ""


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
