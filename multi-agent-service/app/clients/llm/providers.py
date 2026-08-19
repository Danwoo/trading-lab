"""LLM 제공자 표 — **가진 키가 달라도 쓸 수 있게** 하는 자리 (#226).

설정에는 `BASE_URL`·`API_KEY`·`MODEL` 셋뿐이라 제공자 축이 없었다. 게이트웨이를 거치므로
모델명으로 간접 지정되는데, 받는 사람 입장에서는 **자기 키가 어느 제공자 것인지에 따라 무엇을
어떻게 적어야 하는지 알 길이 없었고**, 잘못 적으면 기동은 되고 질문할 때 터졌다.

이 표가 그 지식을 한 곳에 둔다: 어디로 부르는가(base_url) · 모델명을 어떻게 적는가(예시) ·
키는 어디서 받는가 · vLLM 전용 파라미터를 보내도 되는가.

**표에 없는 제공자를 막지 않는다** — `custom` 은 base_url 을 직접 적는 길이고, 사내 게이트웨이가
그 자리다. 표는 아는 것을 알려 주는 것이지 허용 목록이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass


class UnknownProvider(ValueError):
    """표에 없는 제공자. **메시지에 입력 값을 담지 않는다** — 이 문장은 API 로 나간다."""


@dataclass(frozen=True)
class LlmProvider:
    """한 제공자를 쓰는 데 필요한 것 전부."""

    id: str
    name: str
    #: OpenAI 호환 엔드포인트. `custom` 만 비어 있고, 그때는 설정의 BASE_URL 을 쓴다.
    base_url: str
    #: 모델명을 어떻게 적는지 — 목록이 아니라 **형식**이다. 제공자의 모델은 자주 바뀌므로
    #: 목록을 굳히면 곧 낡는다.
    model_example: str
    key_hint: str
    #: vLLM 전용 `extra_body`(reasoning 억제)를 보내도 되는가. 상용 API 는 400 으로 거절한다.
    vllm_compat: bool = False


PROVIDERS: tuple[LlmProvider, ...] = (
    LlmProvider(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        model_example="gpt-4o-mini",
        key_hint="platform.openai.com → API keys",
    ),
    LlmProvider(
        id="groq",
        name="Groq",
        base_url="https://api.groq.com/openai/v1",
        model_example="llama-3.3-70b-versatile",
        key_hint="console.groq.com → API Keys (무료 티어 있음)",
    ),
    LlmProvider(
        id="together",
        name="Together AI",
        base_url="https://api.together.xyz/v1",
        model_example="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        key_hint="api.together.ai → Settings → API Keys",
    ),
    LlmProvider(
        id="openrouter",
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        model_example="anthropic/claude-3.5-sonnet",
        key_hint="openrouter.ai → Keys (여러 제공자를 한 키로)",
    ),
    LlmProvider(
        id="vllm",
        name="자체 vLLM 서버",
        # **8000 은 이 레포의 backend-service 다** — 기본값으로 두면 주소를 안 적은 사람의
        # LLM 요청이 자기 백엔드로 간다. vLLM 기본 서빙 포트(8080)를 쓴다.
        base_url="http://localhost:8080/v1",
        model_example="Qwen/Qwen2.5-7B-Instruct",
        key_hint="자체 서빙이라 키가 없으면 EMPTY 로 둡니다",
        vllm_compat=True,
    ),
    LlmProvider(
        id="custom",
        name="직접 지정 (사내 게이트웨이 등)",
        base_url="",
        model_example="게이트웨이가 정한 이름",
        key_hint="BASE_URL 과 함께 직접 적습니다",
    ),
)

PROVIDER_BY_ID: dict[str, LlmProvider] = {provider.id: provider for provider in PROVIDERS}

#: 제공자를 안 고른 설치 — 종전대로 BASE_URL 을 직접 읽는다 (뒤로 호환).
DEFAULT_PROVIDER_ID = "custom"


def resolve(provider_id: str, base_url: str) -> tuple[LlmProvider, str]:
    """`(제공자, 실제로 부를 base_url)`.

    **설정의 `BASE_URL` 이 이긴다** — 표의 주소는 기본값이지, 적어 둔 것을 덮지 않는다.
    사내 게이트웨이로 OpenAI 를 우회 호출하는 구성이 실재한다.
    """
    provider = PROVIDER_BY_ID.get((provider_id or "").strip().lower() or DEFAULT_PROVIDER_ID)
    if provider is None:
        # **입력 원문을 담지 않는다.** 이 문장은 `fallback_problems()` 를 거쳐 API 응답으로
        # 나가는데, 폴백 항목의 칸 순서를 바꿔 적으면 그 자리에 **키**가 들어 있다.
        known = ", ".join(sorted(PROVIDER_BY_ID))
        raise UnknownProvider(f"모르는 LLM 제공자입니다 (아는 것: {known})")
    return provider, (base_url or "").strip() or provider.base_url


def sends_vllm_extra_body(provider: LlmProvider, toggle: bool) -> bool:
    """이 호출에 vLLM 전용 `extra_body` 를 실을 것인가.

    **제공자를 골랐으면 그 제공자가 이긴다.** 토글(`ROUTER_LLM_VLLM_COMPAT`)의 기본값이 `True`
    라, 무료 티어 Groq 키로 이 제품을 처음 쓰는 사람이 `ROUTER_LLM_PROVIDER=groq` 만 고르면
    상용 API 가 **400 으로 거절**해 plan·guardrail·clarify 가 전멸한다 — 이 PR 이 겨냥한 바로
    그 사람이다. `custom` 은 무엇인지 모르므로 토글을 따른다.
    """
    if provider.id == DEFAULT_PROVIDER_ID:
        return toggle
    return provider.vllm_compat


def address_mismatch(provider: LlmProvider, base_url: str) -> str | None:
    """고른 제공자와 **실제로 부르는 주소**가 다르면 그 사실. 다르지 않으면 `None`.

    설정의 `BASE_URL` 이 표를 이기는 것은 의도된 설계지만(사내 게이트웨이), 그 결과가
    조용하면 안 된다 — 배포되는 `.env.example` 은 vLLM 주소를 채운 채 나가므로, 제공자만
    고른 사람은 **Groq 키를 vLLM 주소로 보내면서** 화면에서는 「groq」를 본다.
    """
    if provider.id == DEFAULT_PROVIDER_ID or not provider.base_url:
        return None
    if (base_url or "").strip().rstrip("/") == provider.base_url.rstrip("/"):
        return None
    return f"{provider.name} 를 골랐는데 BASE_URL 이 다른 주소를 가리킵니다 — 표의 주소를 쓰려면 BASE_URL 을 비우세요"


def unavailable_reason(provider: LlmProvider, base_url: str, model: str, api_key: str) -> str | None:
    """지금 이 역할로 부를 수 없는 이유. 부를 수 있으면 `None`.

    **값은 담지 않는다** — 이 문장은 API 로 나간다.
    """
    if not base_url:
        return f"{provider.name}: 호출 주소가 없습니다 — BASE_URL 을 적으세요 ({provider.key_hint})"
    if not model:
        return f"{provider.name}: 모델명이 없습니다 — 예: {provider.model_example}"
    if not (api_key or "").strip():
        return f"{provider.name}: 키가 없습니다 — {provider.key_hint}"
    return None
