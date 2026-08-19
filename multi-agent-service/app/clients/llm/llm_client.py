"""LLM 클라이언트 팩토리 — 외부타입(ChatOpenAI)이라 get_* 팩토리로 container 에 등록.

역할 분담 (example-ai-lab Phase 13/58 계측 결과):
    router_llm   : 소형 모델. sub-agent ReAct·RES route/evaluate·가드레일.
    planner_llm  : 소형 모델, temp=0. structured output(plan JSON)이 대형 모델에선 타임아웃.
    generator_llm: 대형 모델. 최종 답변·Reduce·Writer.
    evaluator_llm: 대형 모델, temp=0. clarify 판정 (생성과 평가 분리 — 자기평가 편향 방지).
"""

from clients.llm.providers import LlmProvider, resolve, unavailable_reason
from langchain_openai import ChatOpenAI

# Qwen 계열 OpenAI 호환 서버(vLLM)의 reasoning 모드 비활성 (structured output 지연 방지).
# vLLM 전용 파라미터라 Groq 등 상용 OpenAI 호환 API 는 400 으로 거부한다 (#188 Phase C)
# — 그런 제공자는 ROUTER_LLM_VLLM_COMPAT=false 로 전송을 끈다.
_NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}


def _vllm_compat_kwargs(config) -> dict:
    """vLLM 호환 모드일 때만 extra_body 를 얹는다 (기본 true — 기존 vLLM 배포 무영향)."""
    return {"extra_body": _NO_THINKING} if config.ROUTER_LLM_VLLM_COMPAT else {}


def _role(config, role: str) -> tuple[LlmProvider, str, str, str]:
    """역할별 `(제공자, base_url, model, api_key)`. Router 계열은 Router 설정, 나머지는 Generator."""
    if role == "router":
        provider_id, base_url = config.ROUTER_LLM_PROVIDER, config.ROUTER_LLM_BASE_URL
        model, api_key = config.ROUTER_LLM_MODEL, config.ROUTER_LLM_API_KEY
    else:
        provider_id, base_url = config.GENERATOR_LLM_PROVIDER, config.GENERATOR_LLM_BASE_URL
        model, api_key = config.GENERATOR_LLM_MODEL, config.GENERATOR_LLM_API_KEY
    provider, resolved = resolve(provider_id, base_url)
    return provider, resolved, model, api_key


def describe_roles(config) -> list[dict]:
    """지금 어떤 제공자·모델로 답하는지, 못 부르면 왜인지. **키는 담지 않는다.**

    화면이 「무슨 모델이 답했는지」를 보이려면 이 표가 있어야 한다 — 출처 라벨과 같은 축이다.
    """
    rows: list[dict] = []
    for role in ("router", "generator"):
        provider, base_url, model, api_key = _role(config, role)
        rows.append(
            {
                "role": role,
                "provider": provider.id,
                "provider_name": provider.name,
                "model": model or None,
                "reason": unavailable_reason(provider, base_url, model, api_key),
            }
        )
    return rows


def _parse_fallbacks(raw: str) -> list[tuple[str, str, str]]:
    """`"<provider>|<model>|<key>,…"` → 항목 목록. 모양이 어긋난 항목은 **조용히 버리지 않고** 건너뛴다.

    형식을 틀린 것을 무시하면 「폴백을 적었는데 안 도는」 상태가 조용히 생긴다 — 그래서
    `fallback_problems()` 가 같은 입력을 읽어 사유를 낸다.
    """
    out: list[tuple[str, str, str]] = []
    for chunk in (raw or "").split(","):
        parts = [part.strip() for part in chunk.split("|")]
        if len(parts) == 3 and all(parts):
            out.append((parts[0], parts[1], parts[2]))
    return out


def fallback_count(raw: str) -> int:
    """**실제로 체인에 들어가는** 폴백 수 — 「몇 곳으로 넘어갈 수 있는가」의 답이다.

    모양만 맞고 못 쓰는 것(모르는 제공자·주소 없는 custom)은 세지 않는다. 세어 버리면
    화면이 「2곳으로 넘어갈 수 있다」고 말하는데 실제로는 0곳인 상태가 된다.
    """
    usable = 0
    for provider_id, _model, _key in _parse_fallbacks(raw):
        try:
            _, base_url = resolve(provider_id, "")
        except ValueError:
            continue
        if base_url:
            usable += 1
    return usable


def fallback_problems(raw: str) -> list[str]:
    """폴백 설정에서 **못 쓰는 항목**의 사유. 값은 담지 않는다."""
    problems: list[str] = []
    for index, chunk in enumerate((raw or "").split(","), start=1):
        if not chunk.strip():
            continue
        parts = [part.strip() for part in chunk.split("|")]
        if len(parts) != 3 or not all(parts):
            problems.append(f"{index}번째 폴백: `<제공자>|<모델>|<키>` 세 칸이 모두 필요합니다")
            continue
        try:
            resolve(parts[0], "")
        except ValueError as exc:
            problems.append(f"{index}번째 폴백: {exc}")
    return problems


def _with_fallbacks(primary: ChatOpenAI, config, **kwargs):
    """주 제공자가 죽으면 다음으로 넘어간다 — 설정에 적힌 순서대로.

    폴백이 없으면 **아무것도 감싸지 않는다** — 빈 체인으로 감싸면 실패 모양이 달라져,
    「폴백이 없다」와 「폴백도 실패했다」가 구분되지 않는다.
    """
    chain = []
    for provider_id, model, api_key in _parse_fallbacks(config.LLM_FALLBACKS):
        try:
            _, base_url = resolve(provider_id, "")
        except ValueError:
            # **못 쓰는 폴백 하나가 기동을 막지 않는다.** 폴백은 주 경로가 죽었을 때의
            # 보험이라, 그 보험의 오타로 서비스를 못 띄우면 주객이 전도된다.
            # 사유는 `fallback_problems()` 가 내고 `GET /agent/llm` 이 화면에 보인다.
            continue
        if not base_url:
            continue  # custom 은 주소가 없어 폴백으로 못 쓴다
        chain.append(ChatOpenAI(base_url=base_url, api_key=api_key, model=model, **kwargs))
    return primary.with_fallbacks(chain) if chain else primary


def _build(config, role: str, **kwargs) -> ChatOpenAI:
    _, base_url, model, api_key = _role(config, role)
    kwargs.setdefault("max_tokens", 4096)
    return ChatOpenAI(base_url=base_url, api_key=api_key, model=model, **kwargs)


def get_router_llm(config) -> ChatOpenAI:
    return _with_fallbacks(
        _build(config, "router", temperature=0.0, **_vllm_compat_kwargs(config)),
        config,
        temperature=0.0,
        max_tokens=4096,
    )


def get_planner_llm(config) -> ChatOpenAI:
    return _with_fallbacks(
        _build(config, "router", temperature=0.0, **_vllm_compat_kwargs(config)),
        config,
        temperature=0.0,
        max_tokens=4096,
    )


def get_generator_llm(config) -> ChatOpenAI:
    return _with_fallbacks(_build(config, "generator", temperature=0.3), config, temperature=0.3, max_tokens=4096)


def get_evaluator_llm(config) -> ChatOpenAI:
    return _with_fallbacks(
        _build(config, "generator", temperature=0.0, max_tokens=1024),
        config,
        temperature=0.0,
        max_tokens=1024,
    )
