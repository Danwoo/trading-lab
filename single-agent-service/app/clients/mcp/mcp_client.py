# ── [가이드 4/9] clients/mcp/mcp_client.py — MultiServerMCPClient 빌더 + 서버별 tool 캐시 ──
# 무엇: config.MCP_SERVERS → langchain_mcp_adapters 의 MultiServerMCPClient. get_cached_tools 가
#   서버별로 tool 을 부분 성공 허용으로 수집·캐싱한다 — 다운됐던 서버는 쿨다운 후 재시도돼 복구된다.
#   에이전트는 이 tool 들을 LLM 에 바인딩한다(수집이 늘면 chat_service 가 에이전트를 재빌드).
# 복사 후: MCP_SERVERS 기본값만 config 에서. 서버를 늘려도 이 파일은 불변(설정만 추가).
# 함정: tool 이름 = MCP 서버 router 의 operation_id (예: web_search) — 서버에서 이름이 바뀌면
#   못 찾는다(lockstep) · auth=ServiceJwtAuth() 매요청 재발급 · 어댑터 무인자 get_tools() 는 gather 를
#   return_exceptions 없이 돌려 한 서버 실패가 전체를 raise → 서버별 get_tools(server_name=) 로 나눠 부분
#   성공을 허용한다 · MCP 미기동이면 tool 0개(fail-soft, LLM 지식만으로 답) · 캐시는 워커별(in-process).

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
# (single-agent 는 web-mcp 1개만 소비해 "1대 다운 → 전체 0개" 는 degenerate 하지만, 다운 서버의
#  영구 미복구는 실제 문제라 아래 쿨다운 재시도로 해소한다 — #104.)
_tools_by_server: dict[str, list[BaseTool]] = {}
# 아직 못 모은(다운) 서버 재시도 스로틀 — 영구 다운 서버가 매 요청을 timeout 만큼 블록하지 않게.
_RETRY_COOLDOWN_S = 60.0
_last_attempt_monotonic: float = 0.0
_collect_lock = asyncio.Lock()


async def get_cached_tools(client: MultiServerMCPClient) -> list[BaseTool]:
    """서버별 tool 을 부분 성공 허용으로 수집·캐싱한다.

    아직 캐시 안 된 서버만 조회하므로 (1) 서버가 잠깐 다운돼도 정상 서버 tool 은 보존되고
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
    """넘긴 tool 들의 few-shot 예시(_meta)를 모아 시스템 프롬프트 블록 생성. 없으면 빈 문자열.

    서버가 tool _meta 로 노출(meta.few_shot_examples)하면 adapter 는 tool.metadata["_meta"] 로 전달한다.
    이 hop(서버 meta → wire → tool.metadata["_meta"])은 여기 한 곳에만 가둔다 — 직접 metadata 만지지 말 것.
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
