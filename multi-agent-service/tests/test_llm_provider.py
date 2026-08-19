"""LLM 제공자 축이 **가진 키가 달라도 쓸 수 있게** 하는가 (네트워크 없음).

설정에 `BASE_URL`·`API_KEY`·`MODEL` 셋뿐이라 제공자 축이 없었다 — 받는 사람은 자기 키가 어느
제공자 것인지에 따라 무엇을 어떻게 적어야 하는지 알 길이 없었고, 잘못 적으면 기동은 되고
질문할 때 터졌다 (#226).

이 그물이 잠그는 것:

  ① 표에 아는 제공자가 있고, 각 항목이 쓰는 데 필요한 것을 다 갖는다
  ② **설정의 BASE_URL 이 표를 이긴다** — 사내 게이트웨이로 우회하는 구성이 실재한다
  ③ 못 부르는 이유가 **다음 행동**을 말하고 키를 담지 않는다
  ④ 모르는 제공자를 조용히 기본값으로 떨어뜨리지 않는다
  ⑤ 폴백 설정의 모양이 어긋나면 사유를 낸다 — 조용히 무시하면 「적었는데 안 도는」 상태가 된다
  ⑥ 상태 표에 키가 안 실린다
  ⑦ **폴백 사유에도** 키가 안 실린다 — 칸 순서를 바꿔 적으면 첫 칸이 키다
  ⑧ 제공자가 vLLM 토글을 이긴다 — Groq 를 고른 사람이 400 으로 죽지 않게
  ⑨ 고른 제공자와 실제 주소가 어긋나면 조용하지 않다
  ⑩ **상태·probe 가 팩토리와 같은 것을 말한다** — generator 는 extra_body 를 안 싣는다

standalone 실행 겸용:
    cd multi-agent-service && uv run python tests/test_llm_provider.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "llm-provider-test")
os.environ.setdefault("JWT_SECRET", "test-secret")

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from clients.llm.llm_client import describe_roles, fallback_count, fallback_problems  # noqa: E402
from clients.llm.providers import (  # noqa: E402
    PROVIDERS,
    address_mismatch,
    resolve,
    sends_vllm_extra_body,
    unavailable_reason,
)

FAILURES: list[str] = []
CHECKED = 0

SECRET = "gsk_CANARY_DO_NOT_USE_0123456789"


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


class Config:
    ROUTER_LLM_PROVIDER = "groq"
    ROUTER_LLM_BASE_URL = ""
    ROUTER_LLM_MODEL = "llama-3.3-70b-versatile"
    ROUTER_LLM_API_KEY = SECRET
    GENERATOR_LLM_PROVIDER = "openai"
    GENERATOR_LLM_BASE_URL = ""
    GENERATOR_LLM_MODEL = ""
    GENERATOR_LLM_API_KEY = ""
    LLM_FALLBACKS = ""
    ROUTER_LLM_VLLM_COMPAT = False


def main() -> int:
    # ① 표가 쓸 만한가
    check("제공자가 여럿 있다", len(PROVIDERS) >= 4, True)
    for provider in PROVIDERS:
        check(f"{provider.id}: 이름이 있다", bool(provider.name), True)
        check(f"{provider.id}: 모델 예시가 있다", bool(provider.model_example), True)
        check(f"{provider.id}: 키 안내가 있다", bool(provider.key_hint), True)
        if provider.id != "custom":
            check(f"{provider.id}: 주소가 있다", provider.base_url.startswith("http"), True)

    # ② 설정이 표를 이긴다 (사내 게이트웨이)
    _, from_table = resolve("groq", "")
    check("표의 주소를 쓴다", from_table, "https://api.groq.com/openai/v1")
    _, overridden = resolve("groq", "https://gw.internal/v1")
    check("설정이 이긴다", overridden, "https://gw.internal/v1")
    _, empty_custom = resolve("", "")
    check("안 고르면 custom — 주소 없음", empty_custom, "")

    # ③ 못 부르는 이유가 다음 행동을 말한다
    groq, url = resolve("groq", "")
    check("모델 없음 사유", "모델명이 없습니다" in (unavailable_reason(groq, url, "", SECRET) or ""), True)
    check("모델 없음 사유에 예시", groq.model_example in (unavailable_reason(groq, url, "", SECRET) or ""), True)
    no_key = unavailable_reason(groq, url, "m", "") or ""
    check("키 없음 사유", "키가 없습니다" in no_key, True)
    check("키 없음 사유가 발급처를 말한다", groq.key_hint in no_key, True)
    check("다 있으면 사유 없음", unavailable_reason(groq, url, "m", SECRET), None)

    # ④ 모르는 제공자는 조용히 넘어가지 않는다
    try:
        resolve("gorq", "")
        check("오타를 거절한다", "통과함", "거절")
    except ValueError as exc:
        check("오타를 거절한다", "모르는 LLM 제공자" in str(exc), True)
        check("아는 것을 알려 준다", "groq" in str(exc), True)

    # ⑤ 폴백 형식
    check("빈 폴백은 0개", fallback_count(""), 0)
    check("빈 폴백은 사유도 없음", fallback_problems(""), [])
    check("정상 2개", fallback_count(f"groq|m1|{SECRET},openai|m2|{SECRET}"), 2)
    check("칸이 모자라면 사유", len(fallback_problems("groq|m1")), 1)
    check("모르는 제공자면 사유", len(fallback_problems(f"gorq|m1|{SECRET}")), 1)
    check("모양이 틀리면 세지 않는다", fallback_count("groq|m1"), 0)
    # 못 쓰는 폴백이 섞여도 **기동을 막지 않는다** — 보험의 오타로 서비스를 못 띄우면 주객전도다.
    check("모르는 제공자는 안 센다", fallback_count(f"groq|m1|{SECRET},bogus|m2|{SECRET}"), 1)
    check("주소 없는 custom 은 안 센다", fallback_count(f"custom|m1|{SECRET}"), 0)

    class WithBadFallback(Config):
        LLM_FALLBACKS = f"groq|m1|{SECRET},bogus|m2|{SECRET}"

    from clients.llm.llm_client import get_router_llm  # noqa: PLC0415

    try:
        get_router_llm(WithBadFallback())
        check("못 쓰는 폴백이 있어도 만들어진다", True, True)
    except Exception as exc:  # noqa: BLE001
        check("못 쓰는 폴백이 있어도 만들어진다", f"{type(exc).__name__}: {exc}", True)

    # ⑥ 상태 표에 키가 없다
    rows = describe_roles(Config())
    check("역할이 둘", len(rows), 2)
    check("표에 키가 없다", SECRET in repr(rows), False)
    by_role = {row["role"]: row for row in rows}
    check("router 는 부를 수 있다", by_role["router"]["reason"], None)
    check("router 제공자", by_role["router"]["provider"], "groq")
    check("generator 는 사유가 있다", by_role["generator"]["reason"] is not None, True)
    check("답한 모델을 알려 준다", by_role["router"]["model"], "llama-3.3-70b-versatile")

    # ⑦ **폴백 사유에 값이 실리지 않는다** — 칸 순서를 바꿔 적으면 첫 칸이 키다.
    #    리뷰가 지목한 그 공격을 그대로 건다.
    leaked = fallback_problems(f"{SECRET}|groq|llama-3.3-70b-versatile")
    check("칸 순서를 바꿔도 사유가 난다", len(leaked), 1)
    check("사유에 키가 안 실린다", any(SECRET in problem for problem in leaked), False)
    check("사유가 아는 것을 알려 준다", "groq" in leaked[0], True)
    try:
        resolve(SECRET, "")
        check("모르는 제공자를 거절한다", "통과함", "거절")
    except Exception as exc:  # noqa: BLE001
        check("예외 문구에도 키가 없다", SECRET in str(exc), False)

    # ⑧ **제공자가 vLLM 토글을 이긴다** — Groq 를 고른 사람이 400 으로 죽지 않게
    groq_provider, _ = resolve("groq", "")
    vllm_provider, _ = resolve("vllm", "")
    custom_provider, _ = resolve("custom", "")
    check("Groq 는 토글이 켜져도 안 보낸다", sends_vllm_extra_body(groq_provider, True), False)
    check("자체 vLLM 은 보낸다", sends_vllm_extra_body(vllm_provider, True), True)
    check("custom 은 토글을 따른다 (켬)", sends_vllm_extra_body(custom_provider, True), True)
    check("custom 은 토글을 따른다 (끔)", sends_vllm_extra_body(custom_provider, False), False)

    class GroqWithToggleOn(Config):
        ROUTER_LLM_VLLM_COMPAT = True

    from clients.llm.llm_client import _vllm_compat_kwargs  # noqa: PLC0415

    check("팩토리가 Groq 에 extra_body 를 안 싣는다", _vllm_compat_kwargs(GroqWithToggleOn(), groq_provider), {})

    # ⑩ **상태·probe 가 팩토리와 같은 것을 말한다.** generator 계열은 extra_body 를 아예 안
    #    싣는데 상태가 「보낸다」고 하면, reasoning 을 디버깅하는 사람이 그 칸을 보고 「이미
    #    억제돼 있다」고 결론낸다. probe 도 같은 이유로 없는 실패를 만든다.
    from clients.llm.llm_client import role_extra_kwargs  # noqa: PLC0415

    class CustomWithToggleOn(Config):
        ROUTER_LLM_PROVIDER = ""  # custom — 토글을 따른다
        GENERATOR_LLM_PROVIDER = ""
        ROUTER_LLM_VLLM_COMPAT = True

    custom_config = CustomWithToggleOn()
    check("router 는 토글대로 싣는다", "extra_body" in role_extra_kwargs(custom_config, "router"), True)
    check("generator 는 절대 안 싣는다", role_extra_kwargs(custom_config, "generator"), {})
    rows_custom = describe_roles(custom_config)
    by_role_custom = {row["role"]: row for row in rows_custom}
    check("상태가 generator 에 대해 거짓말하지 않는다", by_role_custom["generator"]["sends_vllm_extra_body"], False)
    check("상태가 router 에 대해서는 참을 말한다", by_role_custom["router"]["sends_vllm_extra_body"], True)

    # ⑨ **주소가 어긋나면 조용하지 않다** — 제공자만 고르고 BASE_URL 을 안 비운 상태
    check("표의 주소면 경고 없음", address_mismatch(groq_provider, "https://api.groq.com/openai/v1"), None)
    mismatch = address_mismatch(groq_provider, "http://198.51.100.35:18080/router/v1")
    check("다른 주소면 경고", mismatch is not None, True)
    check("경고가 무엇을 하면 되는지 말한다", "BASE_URL 을 비우세요" in (mismatch or ""), True)
    check("custom 은 경고 없음", address_mismatch(custom_provider, "http://gw.internal/v1"), None)

    rows = describe_roles(Config())
    check("상태에 실제 주소가 실린다", all("base_url" in row for row in rows), True)
    check("상태에 경고 칸이 있다", all("warning" in row for row in rows), True)

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과 (제공자 {len(PROVIDERS)}종)")
    if CHECKED < 66:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 제공자를 고를 수 있고, 못 부르면 다음 행동을 말하며, 키는 안 나온다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
