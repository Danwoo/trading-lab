"""검색 근거 유무 결정론적 판정 — LLM 프롬프트 의존 없이 tool_calls trace 로.

도메인이 실제 MCP 데이터 도구를 ok 상태 + 비어있지 않은 결과로 1건 이상 호출했으면 "sourced", 아니면 "no_evidence".
sub-agent 래퍼 호출(financials_sub 등)은 LLM 지식만으로도 비어있지 않은 텍스트를 내므로 근거에서 제외 — 실제 외부 데이터 조회만 인정.
"""

import json

from utils.agent.mcp_classify import classify_tool


def _has_payload(output) -> bool:
    """tool 출력에 실제 데이터가 있는지 — 인식된 data array 가 비어있지 않을 때만 True.

    DART 공시 응답은 {status, message, list:[...]} 형태(정상)거나 {status, message}(에러코드,
    데이터 없음) 형태다. dict 는 data/results/items/list 중 비어있지 않은 리스트가 있을 때만
    sourced 로 인정 — status/message 만 있는 에러 shape 나 빈 list 는 근거로 보지 않는다.
    (MCP-services 에이전트가 클라이언트 경계에서 list→data 정규화하지만 그와 무관하게 견고하게.)
    """
    if not output:
        return False
    text = output if isinstance(output, str) else str(output)
    try:
        obj = json.loads(text)
    except (TypeError, ValueError):
        return bool(text.strip())
    if isinstance(obj, dict):
        for key in ("data", "results", "items", "list"):
            v = obj.get(key)
            if isinstance(v, list):
                return len(v) > 0
        return False
    if isinstance(obj, list):
        return len(obj) > 0
    return bool(obj)


def compute_grounding(tool_calls: list[dict]) -> dict[str, str]:
    """{agent: "sourced"|"no_evidence"}. agent = tool_calls trace 의 도메인/sub-agent 이름."""
    grounding: dict[str, str] = {}
    for tc in tool_calls or []:
        if classify_tool(tc.get("tool", "") or "") is None:
            continue  # sub-agent 래퍼 등 비-MCP 도구는 근거로 안 셈
        agent = tc.get("agent") or "unknown"
        cur = grounding.get(agent)
        if cur == "sourced":
            continue
        ok = tc.get("status") == "ok" and _has_payload(tc.get("output"))
        grounding[agent] = "sourced" if ok else (cur or "no_evidence")
    return grounding


def any_sourced(grounding: dict[str, str]) -> bool:
    return any(v == "sourced" for v in grounding.values())
