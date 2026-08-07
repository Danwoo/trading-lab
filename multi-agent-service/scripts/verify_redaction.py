"""운영정보 redaction 회귀 검증 — redactor 계약 + Writer evidence 경로 적용.

계약:
  (1) API 키는 구분자(=, :, 공백, 따옴표)와 무관하게 키 원문이 출력에 남지 않는다
  (2) IP·한국어 접근차단·quota·faultstring·운영코드·permanent_failure_reason 치환 유지
  (3) Writer-as-Map evidence 경로(_map_domain_answer)가 tool 출력을 redaction 후 LLM 에 전달
      — tool_calls sink 는 raw 저장(grounding 파싱용)이라 소비 지점 redaction 이 유일한 방어

import 체인이 Settings() 를 인스턴스화하므로 env 없는 실행(CI)용 placeholder 를 setdefault.
`uv run python scripts/verify_redaction.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from graphs.plan_execute.map_reduce import _map_domain_answer  # noqa: E402
from utils.redaction.redactor import redact_operational_info  # noqa: E402

_SECRET = "SECRETKEY1234567890"


def _check_redactor(problems: list[str]) -> None:
    key_cases = [
        f"apprvKey={_SECRET}",
        f"api-key: {_SECRET}",
        f"bearer {_SECRET}",
        f"Authorization: Bearer {_SECRET}",
        f"access_token '{_SECRET}'",
    ]
    for c in key_cases:
        if _SECRET in redact_operational_info(c):
            problems.append(f"API 키 잔존: {c!r}")

    fixed_cases = [
        ("접근 허용 IP가 아닙니다", "해당 도메인 데이터 수집 불가"),
        ("서버 192.168.0.17 응답", "***.***.***.***"),
        ("quota exceeded for key", "해당 도메인 데이터 수집 불가"),
        ("<faultstring>DART_OPEN_API_KEY 오류</faultstring>", "[운영 메시지 제거]"),
        ('"permanent_failure_reason": "IP 미등록"', '"permanent_failure_reason": "data_unavailable"'),
        ("code=DART_QUOTA_EXCEEDED", "해당 도메인 데이터 수집 불가"),
    ]
    for raw, want in fixed_cases:
        got = redact_operational_info(raw)
        if want not in got:
            problems.append(f"패턴 치환 실패: {raw!r} → {got!r} (기대 포함: {want!r})")


class _CaptureLLM:
    """ainvoke 로 받은 messages 를 캡처하고 고정 답변을 반환하는 mock."""

    def __init__(self) -> None:
        self.captured: list = []

    async def ainvoke(self, messages, config=None):
        self.captured.append(messages)
        import types

        return types.SimpleNamespace(content="mock narrative")


def _check_writer_evidence_path(problems: list[str]) -> None:
    from graphs.plan_execute.deps import _GraphDeps

    writer = _CaptureLLM()
    deps = _GraphDeps(
        planner=None,
        clarifier=None,
        replanner=None,
        generator_llm=None,
        guardrail_llm=None,
        guardrail_fn=None,
        writer_llm=writer,
        agents={},
        agent_timeout=1.0,
        agent_max_retries=0,
        agent_retry_delay=0.0,
        react_recursion_limit=1,
        plan_system="",
        replan_system="",
        plan_timeout_s=1.0,
        answer_timeout_s=1.0,
        clarify_timeout_s=1.0,
        guardrail_timeout_s=1.0,
        map_timeout_s=5.0,
        history_max_chars=8000,
        enable_clarify=False,
        enable_guardrail=False,
        max_replan=0,
        map_reduce_domain_threshold=3,
        map_concurrency=1,
        reduce_mode="full",
    )
    tool_calls = [{"tool": "get_quote", "input": "삼성전자", "output": f"bearer {_SECRET} 인증 실패", "agent": "x"}]
    items = [{"agent": "instrument_domain", "status": "ok", "output": "시세 결과"}]
    result = asyncio.run(
        _map_domain_answer(
            deps, "instrument", items, "질문", {}, asyncio.Semaphore(1), None, tool_calls_for_domain=tool_calls
        )
    )
    if result.get("status") != "OK":
        problems.append(f"writer 경로 mock 호출 실패: {result}")
        return
    prompt_text = str(writer.captured)
    if _SECRET in prompt_text:
        problems.append("writer evidence 에 API 키 원문 잔존 (redaction 미적용)")
    if "***" not in prompt_text:
        problems.append("writer evidence 에 redaction 흔적(***) 없음")


def main() -> int:
    problems: list[str] = []
    _check_redactor(problems)
    _check_writer_evidence_path(problems)

    if problems:
        print("redaction 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("redaction OK — 구분자 무관 API 키 치환 + 패턴 6종 + Writer evidence 경로 적용")
    return 0


if __name__ == "__main__":
    sys.exit(main())
