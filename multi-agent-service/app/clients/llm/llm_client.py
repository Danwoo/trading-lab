"""LLM 클라이언트 팩토리 — 외부타입(ChatOpenAI)이라 get_* 팩토리로 container 에 등록.

역할 분담 (example-ai-lab Phase 13/58 계측 결과):
    router_llm   : 소형 모델. sub-agent ReAct·RES route/evaluate·가드레일.
    planner_llm  : 소형 모델, temp=0. structured output(plan JSON)이 대형 모델에선 타임아웃.
    generator_llm: 대형 모델. 최종 답변·Reduce·Writer.
    evaluator_llm: 대형 모델, temp=0. clarify 판정 (생성과 평가 분리 — 자기평가 편향 방지).
"""

from clients.llm.providers import (
    LlmProvider,
    UnknownProvider,
    address_mismatch,
    resolve,
    sends_vllm_extra_body,
    unavailable_reason,
)
from core.logger import logger
from langchain_openai import ChatOpenAI

# Qwen 계열 OpenAI 호환 서버(vLLM)의 reasoning 모드 비활성 (structured output 지연 방지).
# vLLM 전용 파라미터라 Groq 등 상용 OpenAI 호환 API 는 400 으로 거부한다 (#188 Phase C)
# — 그런 제공자는 ROUTER_LLM_VLLM_COMPAT=false 로 전송을 끈다.
_NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}


def _vllm_compat_kwargs(config, provider: LlmProvider | None = None) -> dict:
    """vLLM 전용 extra_body 를 얹을지 — **제공자를 골랐으면 그 제공자가 토글을 이긴다.**

    토글 기본값이 `True` 라, Groq 를 고른 사람이 그대로 두면 상용 API 가 400 으로 거절해
    plan·guardrail·clarify 가 전멸한다 (`config.py` 주석·`test_llm_client_vllm_compat.py` 가
    이미 못박은 상태다).
    """
    toggle = bool(getattr(config, "ROUTER_LLM_VLLM_COMPAT", False))
    send = toggle if provider is None else sends_vllm_extra_body(provider, toggle)
    return {"extra_body": _NO_THINKING} if send else {}


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


def role_extra_kwargs(config, role: str) -> dict:
    """이 역할이 **실제로 싣는** 추가 kwargs — 팩토리·상태·probe 가 이 함수 하나를 쓴다.

    갈라지면 화면이 실제와 다른 것을 말한다: generator 계열 팩토리는 `extra_body` 를 아예
    안 붙이는데 상태가 「보낸다」고 말하면, reasoning 이 섞여 나오는 것을 디버깅하는 사람이
    그 칸을 보고 「이미 억제돼 있다」고 결론낸다. probe 도 같은 이유로 **없는 실패**를 만든다.
    """
    if role != "router":
        # Generator·Evaluator 는 vLLM 전용 파라미터를 쓰지 않는다 (대형 모델은 reasoning 억제
        # 대상이 아니다 — 이 배선은 #188 Phase C 에서 정해졌다).
        return {}
    provider, _, _, _ = _role(config, role)
    return _vllm_compat_kwargs(config, provider)


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
                # **실제로 부르는 주소를 싣는다.** 설정의 BASE_URL 이 표를 이기므로, 이것이
                # 없으면 「groq 를 골랐는데 vLLM 주소로 보내는」 상태를 화면에서 볼 수 없다.
                # 주소는 비밀이 아니다 — 키는 담지 않는다.
                "base_url": base_url or None,
                "model": model or None,
                # **팩토리가 실제로 싣는 것**을 그대로 본다 — 규칙을 다시 계산하면 갈라진다.
                "sends_vllm_extra_body": "extra_body" in role_extra_kwargs(config, role),
                "reason": unavailable_reason(provider, base_url, model, api_key),
                # 「부를 수는 있는데 이상한」 상태 — 막지는 않되 조용하지도 않게 한다.
                "warning": address_mismatch(provider, base_url),
            }
        )
    return rows


#: 확인 호출의 상한 — 「통하는가」만 보는 호출이라 길게 기다릴 이유가 없다.
PROBE_TIMEOUT_S = 8.0
PROBE_MAX_TOKENS = 1
#: 확인 호출의 trace 이름 — usage tracker 가 이 호출을 따로 셀 수 있게.
PROBE_RUN_NAME = "llm-probe"


async def probe_role(config, role: str) -> dict:
    """그 역할로 **실제 한 번 불러** 통하는지 본다 (#225 와 같은 규율).

    설정 세 칸이 채워졌는지만 보면 「키가 틀렸다·만료됐다」를 못 잡는다 — 그 상태로
    `ready: true` 를 내면 화면이 사용자에게 거짓을 말하고, 실패는 질문할 때 터진다.
    이 PR 이 없애려던 상태가 바로 그것이다.

    **값은 응답에 담지 않는다.** 실패 사유는 예외 종류와 상태 코드까지다.
    """
    provider, base_url, model, api_key = _role(config, role)
    reason = unavailable_reason(provider, base_url, model, api_key)
    if reason is not None:
        return {"role": role, "ok": False, "checked": False, "detail": reason}

    probe_client = ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        max_tokens=PROBE_MAX_TOKENS,
        timeout=PROBE_TIMEOUT_S,
        max_retries=0,
        # probe 는 **그 역할의 팩토리와 같은 kwargs** 로 부른다 — 다르면 없는 실패를 만든다.
        **role_extra_kwargs(config, role),
    )
    try:
        # `run_name` 을 붙인다 — usage tracker 가 이 토큰을 **관측 사각으로 두지 않게**.
        # 1토큰이라도 나간 호출은 집계에 보여야 한다 (`test_usage_tracker` 가 전수로 강제한다).
        await probe_client.ainvoke("ping", config={"run_name": PROBE_RUN_NAME})
    except Exception as exc:  # noqa: BLE001 — 어떤 실패든 사유가 화면에 있어야 한다
        status = getattr(getattr(exc, "response", None), "status_code", None)
        hint = {
            401: "키가 거절됐습니다 — 값이 틀렸거나 만료됐습니다",
            403: "접근이 막혔습니다 — 키 권한이나 IP 허용을 확인하세요",
            404: f"모델을 찾지 못했습니다 — 이름을 확인하세요 (예: {provider.model_example})",
            429: "호출 한도에 걸렸습니다 — 잠시 뒤 다시 시도하세요",
        }.get(status)
        if hint is None and status is not None and status >= 500:
            hint = "제공자 쪽 장애입니다 — 우리 설정 문제가 아닙니다"
        detail = f"{provider.name}: {hint}" if hint else f"{provider.name}: 호출이 실패했습니다 ({type(exc).__name__})"
        logger.warning(f"LLM 확인 호출 실패 — role={role} provider={provider.id} error={type(exc).__name__}")
        return {"role": role, "ok": False, "checked": True, "detail": detail}
    return {"role": role, "ok": True, "checked": True, "detail": f"{provider.name} · {model} 로 확인했습니다"}


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
        except UnknownProvider:
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
        except UnknownProvider as exc:
            # 예외 문구에 입력 값이 없다는 것이 `UnknownProvider` 의 계약이다 — 칸 순서를
            # 바꿔 적으면 첫 칸이 **키**라, 원문을 옮기면 그것이 API 응답에 실린다.
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
            provider, base_url = resolve(provider_id, "")
        except UnknownProvider:
            # **못 쓰는 폴백 하나가 기동을 막지 않는다.** 폴백은 주 경로가 죽었을 때의
            # 보험이라, 그 보험의 오타로 서비스를 못 띄우면 주객이 전도된다.
            # 사유는 `fallback_problems()` 가 내고 `GET /agent/llm` 이 화면에 보인다.
            continue
        if not base_url:
            continue  # custom 은 주소가 없어 폴백으로 못 쓴다
        # 폴백에도 **그 제공자의** compat 를 적용한다 — 주 경로만 맞춰 두면 넘어간 순간
        # 같은 400 으로 죽어, 폴백이 있으나 마나가 된다.
        extra = _vllm_compat_kwargs(config, provider)
        chain.append(ChatOpenAI(base_url=base_url, api_key=api_key, model=model, **kwargs, **extra))
    return primary.with_fallbacks(chain) if chain else primary


def _build(config, role: str, **kwargs) -> ChatOpenAI:
    _, base_url, model, api_key = _role(config, role)
    kwargs.setdefault("max_tokens", 4096)
    return ChatOpenAI(base_url=base_url, api_key=api_key, model=model, **kwargs)


def get_router_llm(config) -> ChatOpenAI:
    return _with_fallbacks(
        _build(config, "router", temperature=0.0, **role_extra_kwargs(config, "router")),
        config,
        temperature=0.0,
        max_tokens=4096,
    )


def get_planner_llm(config) -> ChatOpenAI:
    return _with_fallbacks(
        _build(config, "router", temperature=0.0, **role_extra_kwargs(config, "router")),
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
