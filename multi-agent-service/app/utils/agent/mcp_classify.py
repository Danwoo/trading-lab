"""MCP tool 이름 → 서비스 분류 + enabled 집합으로 tool_map 필터.

tool 이름은 라우터 operation_id (서비스 접두사). switch 게이팅이 이 분류로 tool 을 거른다.
"""

# 접두사 → MCP 서비스명 (긴 접두사 우선 — doc_search 가 web 보다 먼저)
_PREFIX_TO_SERVICE = [
    ("doc_search_", "doc-search"),
    ("market_", "market-data"),
    ("disclosure_", "disclosure"),
    ("news_", "news"),
    ("portfolio_", "portfolio"),
    ("web_", "web"),
]

ALL_MCP_SERVICES = {"market-data", "disclosure", "news", "web", "doc-search", "portfolio"}


def classify_tool(tool_name: str) -> str | None:
    """tool 이름 → MCP 서비스명. 미분류는 None."""
    for prefix, service in _PREFIX_TO_SERVICE:
        if tool_name.startswith(prefix):
            return service
    return None


def filter_tool_map(tool_map: dict, enabled_mcps: set[str]) -> dict:
    """enabled 서비스에 속한 tool 만 남김. 미분류 tool 은 보존(안전)."""
    out = {}
    for name, tool in tool_map.items():
        service = classify_tool(name)
        if service is None or service in enabled_mcps:
            out[name] = tool
    return out
