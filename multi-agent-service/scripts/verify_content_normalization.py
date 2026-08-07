"""멀티모달 list content 정규화 회귀 검증 — LLM/메시지 응답 `.content` str 가정 방어 (#30).

계약 (graphs/plan_execute/context.py `_message_text` SoT):
  (1) 메시지 `.content` 가 멀티모달 list([{text},{image}]) 여도 소비처는 항상 str 을 받는다 — payload 저장·
      narrative join·final_answer(str 연산)에 list 가 새어들어 TypeError 를 내지 않는다.
  (2) 텍스트 파트 없는 image-only 응답은 빈 텍스트로 정규화 → invocation 은 `empty` 로 정직 처리
      (str content 를 truthy list 로 오판해 image dict 를 payload 로 저장하던 잠복 교정).
  (3) 회귀 감지: 현 스택의 str content 경로 동작은 불변 (payload/narrative == 원본 str).

#21 이 `_extract_query` 에서 확립한 `.text` property 패턴을 SoT 로, 남은 소비처(invocation·map_reduce·
nodes·history_ctx)를 이 헬퍼로 수렴했다. 실제 `_invoke_agent_safe`·`_map_domain_answer` 를 멀티모달
list content 라는 **새 입력**으로 end-to-end 구동한다 (남이 준 케이스 재실행 아님).

import 체인이 Settings() 를 인스턴스화하므로 env 없는 실행(CI)용 placeholder 를 setdefault.
`uv run python scripts/verify_content_normalization.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from graphs.plan_execute.context import _build_history_ctx, _message_text  # noqa: E402
from graphs.plan_execute.invocation import _invoke_agent_safe  # noqa: E402
from graphs.plan_execute.map_reduce import _build_sub_answers_section, _map_domain_answer  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

_MULTIMODAL = [
    {"type": "text", "text": "삼성전자 요약 "},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
    {"type": "text", "text": "실적 견조."},
]
_MULTIMODAL_TEXT = "삼성전자 요약 실적 견조."
_IMAGE_ONLY = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")
    raise SystemExit(1)


class _FakeAgent:
    """agent.ainvoke 대역 — 지정 content 의 AIMessage 를 messages 로 반환."""

    def __init__(self, content) -> None:
        self._content = content

    async def ainvoke(self, inp, config=None):
        return {"messages": [HumanMessage(content="q"), AIMessage(content=self._content)]}


class _FakeLLM:
    """generator_llm 대역 — ainvoke 마다 지정 content 의 AIMessage 반환."""

    def __init__(self, content) -> None:
        self._content = content

    async def ainvoke(self, messages, config=None):
        return AIMessage(content=self._content)


def check_message_text_helper() -> None:
    """(1)(2) SoT 헬퍼: 멀티모달·str·image-only·비메시지 정규화."""
    ai = AIMessage(content=_MULTIMODAL)
    if _message_text(ai) != _MULTIMODAL_TEXT:
        _fail(f"멀티모달 list → 텍스트 병합 실패: {_message_text(ai)!r}")

    ai_str = AIMessage(content="평범한 문자열 답변")
    if _message_text(ai_str) != "평범한 문자열 답변":
        _fail("str content 정규화가 원본을 바꿈 (회귀)")

    ai_img = AIMessage(content=_IMAGE_ONLY)
    if _message_text(ai_img) != "":
        _fail(f"image-only 는 빈 텍스트여야 함: {_message_text(ai_img)!r}")

    non_msg = SimpleNamespace()  # .text/.content 없음
    if _message_text(non_msg) != str(non_msg):
        _fail("비메시지 객체 str 폴백 실패")

    print("  ✓ (1)(2) _message_text: 멀티모달 병합·str 불변·image-only 빈값·비메시지 폴백")


async def check_invocation_payload() -> None:
    """(1)(2)(3) _invoke_agent_safe: payload 항상 str, image-only→empty, str 경로 불변."""
    r = await _invoke_agent_safe(_FakeAgent(_MULTIMODAL), task="t", agent_name="a", timeout=5.0)
    if r.status != "ok":
        _fail(f"멀티모달 응답 status 기대 ok, 실제 {r.status}")
    if not isinstance(r.payload, str) or r.payload != _MULTIMODAL_TEXT:
        _fail(f"payload 가 str 아님/불일치: {type(r.payload).__name__} {r.payload!r}")
    # downstream _format_prior_stage_results 의 str(output) join 무크래시 확인
    _ = f"[a 종합]\n{r.payload}".join(["", ""])

    r_img = await _invoke_agent_safe(_FakeAgent(_IMAGE_ONLY), task="t", agent_name="a", timeout=5.0)
    if r_img.status != "empty":
        _fail(f"image-only 응답 status 기대 empty, 실제 {r_img.status} (payload={r_img.payload!r})")

    r_str = await _invoke_agent_safe(_FakeAgent("직접 문자열"), task="t", agent_name="a", timeout=5.0)
    if r_str.status != "ok" or r_str.payload != "직접 문자열":
        _fail(f"str content 경로 회귀: status={r_str.status} payload={r_str.payload!r}")

    print("  ✓ (1)(2)(3) _invoke_agent_safe: 멀티모달 payload str·image-only empty·str 경로 불변")


async def check_map_narrative_and_join() -> None:
    """(1)(3) _map_domain_answer narrative str → _build_sub_answers_section join 무TypeError."""
    deps = SimpleNamespace(writer_llm=None, generator_llm=_FakeLLM(_MULTIMODAL), map_timeout_s=5.0)
    sem = asyncio.Semaphore(1)
    result = await _map_domain_answer(deps, "instrument", [{"agent": "x", "output": "o"}], "질문", {}, sem)
    if not isinstance(result["narrative"], str) or result["narrative"] != _MULTIMODAL_TEXT:
        _fail(f"map narrative str 아님/불일치: {result['narrative']!r}")
    # list 였다면 "\n\n".join(...) 에서 TypeError — join 이 str 을 반환해야 계약 성립
    joined = _build_sub_answers_section({"instrument": result})
    if not isinstance(joined, str) or _MULTIMODAL_TEXT not in joined:
        _fail(f"_build_sub_answers_section join 실패: {joined!r}")

    deps_str = SimpleNamespace(writer_llm=None, generator_llm=_FakeLLM("문자열 narrative"), map_timeout_s=5.0)
    result_str = await _map_domain_answer(deps_str, "instrument", [{"agent": "x", "output": "o"}], "질문", {}, sem)
    if result_str["narrative"] != "문자열 narrative":
        _fail(f"str content map 경로 회귀: {result_str['narrative']!r}")

    print("  ✓ (1)(3) _map_domain_answer → _build_sub_answers_section: 멀티모달 narrative join 무TypeError")


def check_history_ctx() -> None:
    """(1) _build_history_ctx: 멀티모달 human content 도 repr 아닌 텍스트로."""
    msgs = [HumanMessage(content=_MULTIMODAL), AIMessage(content="답"), HumanMessage(content="현재턴")]
    ctx = _build_history_ctx(msgs, k=20)
    if "image_url" in ctx or "'type'" in ctx:
        _fail(f"history 에 멀티모달 dict repr 누출: {ctx!r}")
    if _MULTIMODAL_TEXT not in ctx:
        _fail(f"history 에 텍스트 파트 누락: {ctx!r}")
    print("  ✓ (1) _build_history_ctx: 멀티모달 human content → 텍스트 (dict repr 미누출)")


async def main() -> None:
    print("멀티모달 content 정규화 회귀 검증 (#30)")
    check_message_text_helper()
    await check_invocation_payload()
    await check_map_narrative_and_join()
    check_history_ctx()
    print("\n✅ 전체 통과 — 멀티모달 list content 소비처가 str 로 수렴, str 경로 불변")


if __name__ == "__main__":
    asyncio.run(main())
