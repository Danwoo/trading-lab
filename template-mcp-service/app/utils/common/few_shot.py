"""MCP tool few-shot 예시 — 라우터 데코레이터 선언 → tool _meta 노출 (순수함수, IO 없음).

few-shot 은 operation_id 와 같은 "MCP tool 메타데이터"라 라우터 데코레이터에서 선언한다:
    @router.post("/x", operation_id="x", openapi_extra=few_shot([{"질문":..,"호출":{..}}]))
파서가 operation 의 x-* 를 HTTPRoute.extensions 에 담고, main.py 가 from_fastapi(mcp_component_fn=
attach_tool_meta) 로 걸면 tool.meta["few_shot_examples"] 로 노출된다 (FastMCP 공식 커스터마이즈 훅).
소비자(에이전트)는 tool _meta 를 모아 시스템 프롬프트에 주입 — 서버가 예시를 소유, 소비자는 수집만.
"""

from __future__ import annotations

from typing import Any

# operation 확장 키 — 선언(few_shot)·부착(attach_tool_meta) 양쪽이 공유하는 단일 매직스트링
FEW_SHOT_EXTENSION_KEY = "x-fewshot"

# 부착된 tool 이름 — 기동 시 main.py 가 개수를 로그해 "조용한 누락"을 가시화 (안전장치)
_attached_tools: list[str] = []


def few_shot(examples: list[dict[str, Any]]) -> dict[str, Any]:
    """라우터 데코레이터의 openapi_extra 로 넣을 few-shot 선언.

    examples: [{"질문": "사용자 질문", "호출": {인자}}] — '호출' 은 그 tool 의 In 스키마 인자 dict.
    예시 개념은 ai-chatbot(example-ai-agent) few_shot_examples 참조 — MCP tool _meta 로 노출 (wire: meta.few_shot_examples=[{질문,호출}]).
    """
    return {FEW_SHOT_EXTENSION_KEY: examples}


def attach_tool_meta(route, component) -> None:
    """from_fastapi(mcp_component_fn=) 훅 — route.extensions 의 few-shot 을 tool _meta 로 부착.

    operation x-* → HTTPRoute.extensions (파서) → 여기서 component.meta 로. 예시 없는 tool 은 무변경.
    """
    examples = (getattr(route, "extensions", None) or {}).get(FEW_SHOT_EXTENSION_KEY)
    if examples:
        component.meta = {**(component.meta or {}), "few_shot_examples": examples}
        _attached_tools.append(component.name)


def attached_tool_names() -> list[str]:
    """few-shot 이 부착된 tool 이름 목록 (기동 로그·검증용)."""
    return list(_attached_tools)
