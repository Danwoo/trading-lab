"""SSE 이벤트 스키마 (순수함수).

stream_query() 가 yield 하는 이벤트 dict 빌더. 라우터가 그대로 SSE data 프레임으로 감싼다.

이벤트 종류:
    step          : 실행 진행 표시 (phase: plan/execute/map_answer/answer/guardrail/cache/tool_call)
    text          : 최종 답변 본문 ({"content": ...})
    trace         : 응답 신뢰도·출처 metadata 요약 (스트림 종료 직전 1건)
    error         : 장애 안내
    clarification : 명확화 질문 (clarify 노드 발화)

frontend 참고: step 은 진행 스피너·chip 용으로 무시해도 답변 수신엔 지장 없음.
"""

from __future__ import annotations

from typing import Any


def step_event(
    phase: str,
    status: str,
    *,
    domain: str | None = None,
    message: str | None = None,
    elapsed_s: float | None = None,
    **extra: Any,
) -> dict:
    payload: dict[str, Any] = {"type": "step", "phase": phase, "status": status}
    if domain is not None:
        payload["domain"] = domain
    if message is not None:
        payload["message"] = message
    if elapsed_s is not None:
        payload["elapsed_s"] = round(elapsed_s, 2)
    payload.update(extra)
    return payload


def text_event(content: str) -> dict:
    return {"type": "text", "content": content}


def trace_event(metadata: dict[str, Any]) -> dict:
    return {"type": "trace", "metadata": metadata}


def error_event(content: str) -> dict:
    return {"type": "error", "content": content}


def clarification_event(question: str) -> dict:
    return {"type": "clarification", "question": question, "content": question}


# 표준 메시지 상수 (한국어) — UX 일관성 위해 중앙화
MSG_PLAN_STARTED = "질문을 분석하고 있습니다..."
MSG_PLAN_COMPLETED = "조회 계획 수립 완료"
MSG_EXECUTE_STARTED = "도메인 에이전트를 호출하고 있습니다..."
MSG_EXECUTE_COMPLETED = "도메인 조회 완료"
MSG_ANSWER_STARTED = "결과를 종합하여 답변을 생성합니다..."
MSG_GUARDRAIL_BLOCKED = "안전 검사에서 이 질문은 처리할 수 없습니다."
MSG_CACHE_HIT = "이전 동일 질문의 결과를 재사용합니다."
MSG_CLARIFY_REQUESTED = "질문을 더 구체적으로 좁혀주시면 더 정확히 답변할 수 있어요."
MSG_REFUSE_OUT_OF_DOMAIN = "이 질문은 금융·투자 리서치 도메인 외 영역입니다."

# 도메인 키 → 한국어 라벨 (사용자 노출용)
DOMAIN_KO_LABEL = {
    "instrument_domain": "종목·시세",
    "financials_domain": "재무·공시",
    "risk_domain": "리스크·밸류",
    "market_domain": "시장·뉴스",
}


def domain_label(domain_key: str) -> str:
    """도메인 내부 키를 사용자 친화적 한국어로 변환."""
    return DOMAIN_KO_LABEL.get(domain_key, domain_key)
