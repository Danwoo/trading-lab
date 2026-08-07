"""노드 프롬프트 system/user 2분할 조립 — graphs 노드가 llm.ainvoke 에 넘길 메시지 리스트 생성.

고정 지시는 SystemMessage, 동적 데이터는 HumanMessage 로 분리해 Gemma 4 native system role 을 탄다
(guardrail.py 의 [SystemMessage, HumanMessage] 패턴과 동일 — vLLM 이 role 별로 직렬화).
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage


def build_node_messages(system: str, user: str = "", user_template: str = "", **fields: str) -> list[BaseMessage]:
    """고정 system + 동적 user → [SystemMessage, HumanMessage].

    user 를 직접 주거나(가변 라벨 조립이 노드에 있는 clarify/plan), user_template + fields 로 .format 한다
    (정적 라벨 블록인 answer/map/reduce 등).
    """
    content = user_template.format(**fields) if user_template else user
    return [SystemMessage(content=system), HumanMessage(content=content)]
