"""컴플라이언스 고지 상수 + 결정론적 부착 백스톱.

노드 프롬프트가 soft 로 지시하는 면책을 LLM 이 흘려도, 최종 답변 직전 이 함수가 hard 로 보강한다.
"""

from __future__ import annotations

# 컴플라이언스 고지 — 모든 최종 답변 말미에 부착 (LLM 미부착 시 결정론적 폴백 보강)
COMPLIANCE_DISCLAIMER = "ⓘ 정보 제공 목적이며 투자 조언이 아닙니다"


def _ensure_disclaimer(text: str) -> str:
    """답변 말미에 컴플라이언스 고지 1줄 보장 (LLM 이 이미 넣었으면 중복 추가하지 않음)."""
    body = (text or "").rstrip()
    if not body:
        return body
    if "투자 조언이 아닙니다" in body:
        return body
    return f"{body}\n\n{COMPLIANCE_DISCLAIMER}"
