"""LLM 클라이언트 팩토리 — 외부타입(ChatOpenAI)이라 get_* 팩토리로 container 에 등록.

역할 분담 (example-ai-lab Phase 13/58 계측 결과):
    router_llm   : 소형 모델. sub-agent ReAct·RES route/evaluate·가드레일.
    planner_llm  : 소형 모델, temp=0. structured output(plan JSON)이 대형 모델에선 타임아웃.
    generator_llm: 대형 모델. 최종 답변·Reduce·Writer.
    evaluator_llm: 대형 모델, temp=0. clarify 판정 (생성과 평가 분리 — 자기평가 편향 방지).
"""

from langchain_openai import ChatOpenAI

# Qwen 계열 OpenAI 호환 서버(vLLM)의 reasoning 모드 비활성 (structured output 지연 방지).
# vLLM 전용 파라미터라 Groq 등 상용 OpenAI 호환 API 는 400 으로 거부한다 (#188 Phase C)
# — 그런 제공자는 ROUTER_LLM_VLLM_COMPAT=false 로 전송을 끈다.
_NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}


def _vllm_compat_kwargs(config) -> dict:
    """vLLM 호환 모드일 때만 extra_body 를 얹는다 (기본 true — 기존 vLLM 배포 무영향)."""
    return {"extra_body": _NO_THINKING} if config.ROUTER_LLM_VLLM_COMPAT else {}


def get_router_llm(config) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=config.ROUTER_LLM_BASE_URL,
        api_key=config.ROUTER_LLM_API_KEY,
        model=config.ROUTER_LLM_MODEL,
        temperature=0.0,
        max_tokens=4096,
        **_vllm_compat_kwargs(config),
    )


def get_planner_llm(config) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=config.ROUTER_LLM_BASE_URL,
        api_key=config.ROUTER_LLM_API_KEY,
        model=config.ROUTER_LLM_MODEL,
        temperature=0.0,
        max_tokens=4096,
        **_vllm_compat_kwargs(config),
    )


def get_generator_llm(config) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=config.GENERATOR_LLM_BASE_URL,
        api_key=config.GENERATOR_LLM_API_KEY,
        model=config.GENERATOR_LLM_MODEL,
        temperature=0.3,
        max_tokens=4096,
    )


def get_evaluator_llm(config) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=config.GENERATOR_LLM_BASE_URL,
        api_key=config.GENERATOR_LLM_API_KEY,
        model=config.GENERATOR_LLM_MODEL,
        temperature=0.0,
        max_tokens=1024,
    )
