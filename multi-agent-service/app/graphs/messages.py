"""wrap_agent_as_tool 이 반환하는 한국어 상태 메시지 중앙 관리 (톤·로케일 일괄 교체 지점)."""

from __future__ import annotations

LIMIT_SOFT_TEMPLATE = (
    "[{name}_호출한도도달: 추가 수집 한도({max_calls}회) 도달. "
    "일반 지식 추론 금지. 아래 기수집 데이터를 사용하여 답변하세요.]\n\n"
    "{prior_content}"
)

LIMIT_HARD_TEMPLATE = (
    "[{name}_데이터수집실패: 최대 호출 횟수({max_calls}회) 초과로 "
    "실제 데이터를 수집하지 못했습니다. "
    "이 도메인 정보를 일반 지식으로 추론하거나 대체하지 마세요.]"
)

TIMEOUT_TEMPLATE = "(타임아웃 — {timeout:.0f}초 초과)"

RECURSION_TEMPLATE = "(재귀 오류 — recursion_limit={recursion_limit} 도달)"

EXCEPTION_TEMPLATE = "(오류: {error_type}: {error_msg})"


def format_limit_soft(name: str, max_calls: int, prior_content: str) -> str:
    return LIMIT_SOFT_TEMPLATE.format(name=name, max_calls=max_calls, prior_content=prior_content)


def format_limit_hard(name: str, max_calls: int) -> str:
    return LIMIT_HARD_TEMPLATE.format(name=name, max_calls=max_calls)


def format_timeout(timeout: float) -> str:
    return TIMEOUT_TEMPLATE.format(timeout=timeout)


def format_recursion(recursion_limit: int) -> str:
    return RECURSION_TEMPLATE.format(recursion_limit=recursion_limit)


def format_exception(error_type: str, error_msg: str) -> str:
    return EXCEPTION_TEMPLATE.format(error_type=error_type, error_msg=error_msg)
