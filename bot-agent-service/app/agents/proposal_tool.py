"""대화가 **폼을 채우는** 통로 — 에이전트가 값을 말이 아니라 도구로 낸다.

왜 도구인가: 답변 글에서 값을 파싱하면 문장이 조금만 달라져도 폼이 안 채워진다. 도구 호출은
모양이 계약으로 고정되고, **무엇을 제안했는지 화면에 그대로 옮길 수 있다**(실험대 스펙 §8.6.3
「출처가 남는다」 — 폼의 그 칸에 `AI 제안 수락` 이 붙는다).

여기서 값의 **범위를 검증하지 않는다.** 전략 선언이 정한 범위는 전략 규약의 소유이고 그
판정자는 저장 시점의 backend-service 다. 이 서비스가 같은 검증을 한 벌 더 들고 있으면 두
구현이 갈라지고, 갈라지면 화면과 저장이 서로 다른 말을 한다. 여기서는 **모양만** 본다.
"""

from __future__ import annotations

from typing import Any

PROPOSAL_TOOL_NAME = "propose_settings"

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "strategy_key": {
            "type": "string",
            "description": "전략 파일이 선언한 key (예: ma_pullback). 전략을 바꾸자는 제안이면 그 key 를 준다.",
        },
        "params": {
            "type": "object",
            "description": "그 전략이 선언한 파라미터 이름 → 값. 선언에 없는 이름은 넣지 않는다.",
            "additionalProperties": True,
        },
        "note": {
            "type": "string",
            "description": "왜 이 값인지 한 줄. 판정('좋습니다')이 아니라 결과('이러면 이렇게 됩니다')로 적는다.",
        },
    },
    "required": ["strategy_key", "params"],
}

DESCRIPTION = (
    "봇 설정을 사용자의 폼에 채워 넣는다. 값을 정했으면 **말로만 하지 말고 반드시 이 도구를 부른다** — "
    "사용자 화면의 폼이 이 호출로만 채워진다. 사용자가 그 값을 그대로 둘지 고칠지는 사용자가 정한다."
)


def normalize_proposal(args: dict[str, Any]) -> dict[str, Any] | None:
    """도구 인자 → 화면에 흘릴 이벤트. 모양이 아니면 `None` (조용히 버리지 않고 호출자가 로그한다)."""
    if not isinstance(args, dict):
        return None
    key = args.get("strategy_key")
    params = args.get("params")
    if not isinstance(key, str) or not key.strip():
        return None
    if not isinstance(params, dict):
        return None
    # 값은 JSON 으로 실려 나가므로 직렬화 가능한 스칼라만 남긴다 — 중첩 구조는 폼이 그릴 수 없다.
    clean = {
        name: value
        for name, value in params.items()
        if isinstance(name, str) and isinstance(value, (str, int, float, bool))
    }
    note = args.get("note")
    return {
        "type": "proposal",
        "strategy_key": key.strip(),
        "params": clean,
        "note": note if isinstance(note, str) and note.strip() else None,
    }


def build_proposal_server(collect):
    """제안을 모으는 in-process MCP 서버. `collect(event)` 로 이벤트를 넘긴다.

    SDK 의 `tool`·`create_sdk_mcp_server` 를 **여기서** import 한다 — 키가 없는 환경에서도
    앱이 뜨고 readiness 가 답해야 하므로 모듈 최상단에서 SDK 를 물지 않는다.
    """
    from claude_agent_sdk import create_sdk_mcp_server, tool

    @tool(PROPOSAL_TOOL_NAME, DESCRIPTION, INPUT_SCHEMA)
    async def propose_settings(args: dict[str, Any]) -> dict[str, Any]:
        event = normalize_proposal(args)
        if event is None:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "제안 모양이 올바르지 않습니다 — strategy_key(문자열)와 params(객체)가 필요합니다.",
                    }
                ],
                "is_error": True,
            }
        collect(event)
        filled = ", ".join(f"{name}={value}" for name, value in event["params"].items()) or "(값 없음)"
        return {"content": [{"type": "text", "text": f"폼에 채웠습니다 — {event['strategy_key']}: {filled}"}]}

    return create_sdk_mcp_server(name="bot_form", version="1.0.0", tools=[propose_settings])
