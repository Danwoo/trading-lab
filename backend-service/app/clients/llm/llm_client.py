"""LLM 클라이언트 — qwen3(litellm OpenAI 호환) 기반.

- ``get_chat_client``: 챗 에이전트용 ChatOpenAI (스트리밍 tool-calling).
- ``get_llm_client``: non-streaming 요약용 ChatOpenAI.
"""

from langchain_openai import ChatOpenAI


def get_chat_client(config) -> ChatOpenAI:
    """챗 에이전트용 ChatOpenAI."""
    return ChatOpenAI(
        model=config.LLM_MODEL,
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
        temperature=0,
        seed=0,
        streaming=True,
        max_retries=2,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}},
    )


def get_llm_client(config) -> ChatOpenAI:
    """비스트리밍 요약용 ChatOpenAI. 요약은 CoT 이득 적고 지연만 커 reasoning off (에이전트만 on)."""
    return ChatOpenAI(
        model=config.LLM_MODEL,
        base_url=config.LLM_BASE_URL,
        api_key=config.LLM_API_KEY,
        temperature=0,
        seed=0,
        max_retries=2,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
