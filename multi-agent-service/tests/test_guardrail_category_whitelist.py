"""#195 회귀 방지 — 가드레일 category 화이트리스트 강제.

LLM 이 is_safe=false 를 내면서 프롬프트에 정의된 적 없는 category(발명 `copyright`,
빈 문자열 등)를 붙이면, 프롬프트의 "불명확한 경우 기본값 SAFE" 원칙대로 통과시켜야 한다.
정의된 category(injection/harmful)의 차단·fail-closed 예외 처리는 그대로 유지된다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_guardrail_category_whitelist.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다 (LLM 은 mock — 네트워크 호출 없음).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# app 소스 루트(절대 import)와 dev 설정을 app 모듈 import 전에 준비한다.
os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from services.agent.guardrail import (  # noqa: E402
    GuardrailVerdict,
    _GuardrailOutput,
    check_guardrail,
)


class _FakeStructuredLLM:
    """with_structured_output(...).ainvoke(...) 가 고정 _GuardrailOutput 을 반환하는 더블."""

    def __init__(self, output: _GuardrailOutput) -> None:
        self._output = output

    def with_structured_output(self, schema: type) -> _FakeStructuredLLM:
        assert schema is _GuardrailOutput, f"예상 밖 스키마: {schema!r}"
        return self

    async def ainvoke(self, messages: list, config: dict | None = None) -> _GuardrailOutput:
        return self._output


def _run(output: _GuardrailOutput) -> GuardrailVerdict:
    return asyncio.run(
        check_guardrail("한빛반도체 2026Q2 리서치 노트의 목표주가와 투자의견을 알려줘", _FakeStructuredLLM(output))
    )


def test_invented_category_passes() -> str:
    """is_safe=false + 발명 category(copyright) → 화이트리스트 밖이므로 SAFE 통과."""
    verdict = _run(_GuardrailOutput(is_safe=False, category="copyright"))
    assert verdict.is_safe is True, f"발명 카테고리는 통과여야 함: {verdict!r}"
    assert "copyright" in verdict.reason, f"reason 에 원문 카테고리 기록: {verdict.reason!r}"
    return "test_invented_category_passes"


def test_empty_category_passes() -> str:
    """is_safe=false + category='' (2026-07-28 실측 오탐) → SAFE 통과."""
    verdict = _run(_GuardrailOutput(is_safe=False, category=""))
    assert verdict.is_safe is True, f"빈 카테고리는 통과여야 함: {verdict!r}"
    return "test_empty_category_passes"


def test_injection_still_blocked() -> str:
    """is_safe=false + category=injection (정의됨) → 차단·refusal 유지."""
    verdict = _run(_GuardrailOutput(is_safe=False, category="injection"))
    assert verdict.is_safe is False, f"injection 은 차단 유지여야 함: {verdict!r}"
    assert verdict.category == "injection"
    assert "내부 지시" in verdict.refusal_message
    return "test_injection_still_blocked"


def test_harmful_still_blocked() -> str:
    """is_safe=false + category=harmful (정의됨) → 차단·refusal 유지."""
    verdict = _run(_GuardrailOutput(is_safe=False, category="harmful"))
    assert verdict.is_safe is False, f"harmful 은 차단 유지여야 함: {verdict!r}"
    assert verdict.category == "harmful"
    assert "유해" in verdict.refusal_message
    return "test_harmful_still_blocked"


def test_case_whitespace_variants_still_blocked() -> str:
    """정의 카테고리의 대소문자·둘레 공백 변형 → 정규화 후 차단 유지 (PR #206 리뷰 지적).

    exact-match 였다면 "Injection" 등이 미정의로 새어 SAFE 통과 — 새 우회 경로가 된다.
    """
    for raw in ("Injection", "INJECTION", "injection ", "harmful\n"):
        verdict = _run(_GuardrailOutput(is_safe=False, category=raw))
        assert verdict.is_safe is False, f"변형 {raw!r} 은 차단 유지여야 함: {verdict!r}"
        normalized = raw.strip().lower()
        assert verdict.category == normalized, f"category 는 정규화 값이어야 함: {verdict.category!r}"
        # refusal_message 분기도 정규화 값 기준으로 카테고리별 메시지가 나와야 한다.
        expected_phrase = "내부 지시" if normalized == "injection" else "유해"
        assert expected_phrase in verdict.refusal_message, f"{raw!r}: {verdict.refusal_message!r}"
    return "test_case_whitespace_variants_still_blocked"


def test_safe_passes() -> str:
    """is_safe=true → 통과 (기존 동작 불변)."""
    verdict = _run(_GuardrailOutput(is_safe=True))
    assert verdict.is_safe is True, f"SAFE 판정은 통과여야 함: {verdict!r}"
    return "test_safe_passes"


class _RaisingLLM:
    """with_structured_output(...).ainvoke(...) 가 항상 예외를 내는 더블 — 프로바이더 호출 실패 재현."""

    def with_structured_output(self, schema: type) -> _RaisingLLM:
        return self

    async def ainvoke(self, messages: list, config: dict | None = None) -> _GuardrailOutput:
        raise RuntimeError("provider unavailable")


def test_provider_exception_failcloses() -> str:
    """LLM 호출 자체가 예외를 내면(429·연결 끊김 등) fail-closed 차단 — #338.

    판정 불가는 안전 판정이 아니다. category="unavailable"·안내 문구가 사용자에게 도달해야 한다.
    """
    verdict = asyncio.run(check_guardrail("아무 질문이나", _RaisingLLM()))
    assert verdict.is_safe is False, f"프로바이더 예외는 차단(fail-closed)이어야 함: {verdict!r}"
    assert verdict.category == "unavailable", f"category=unavailable 이어야 함: {verdict!r}"
    assert "다시 시도" in verdict.refusal_message, (
        f"사용자에게 무엇이 일어났는지·무엇을 하면 되는지 안내해야 함: {verdict.refusal_message!r}"
    )
    return "test_provider_exception_failcloses"


def _main() -> int:
    tests = [
        test_invented_category_passes,
        test_empty_category_passes,
        test_injection_still_blocked,
        test_harmful_still_blocked,
        test_case_whitespace_variants_still_blocked,
        test_safe_passes,
        test_provider_exception_failcloses,
    ]
    passed = 0
    for tc in tests:
        name = tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
