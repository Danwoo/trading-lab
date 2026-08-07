# ── [가이드 5/9] clients/llm/llm_client.py — 에이전트용 ChatOpenAI(vLLM/litellm) 빌더 ──
# 무엇: tool-calling + 스트리밍을 켠 ChatOpenAI 한 개. 단일 에이전트라 LLM 도 하나(ROUTER_LLM_*).
# 복사 후: ROUTER_LLM_* 를 새 게이트웨이/모델로 (config). reasoning 모델이 아니면 extra_body 제거.
# 함정: streaming=True 여야 토큰 SSE 가 흐른다 · temperature=0,seed=0 으로 재현성 고정 ·
#   base_url 은 /v1 까지(OpenAI 호환 경로).

from langchain_openai import ChatOpenAI


def get_chat_client(config) -> ChatOpenAI:
    """에이전트용 ChatOpenAI (스트리밍 tool-calling)."""
    return ChatOpenAI(
        model=config.ROUTER_LLM_MODEL,
        base_url=config.ROUTER_LLM_BASE_URL,
        api_key=config.ROUTER_LLM_API_KEY,
        temperature=0,
        seed=0,
        streaming=True,
        max_retries=2,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}},
    )
