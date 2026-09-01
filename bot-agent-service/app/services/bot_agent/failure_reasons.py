"""대화 실패를 **사유 코드**로 옮긴다 (#423).

봉투를 건너는 것은 이 닫힌 집합의 코드뿐이고, 화면 문구는 받는 쪽이 자기 언어 표
(`frontend/utils/common/locale/*/apierrors.ts` 의 `STREAM_FAILURE_MESSAGES`)에서 고른다 —
SDK·CLI 원문과 내부 경로는 여기서 버려지고 서버 로그에만 남는다. 프론트의
`utils/common/errors/streamFailure.ts` 와 **같은 문자열**이 계약이다(lockstep).

**왜 텍스트까지 보나.** CLI 는 인증 실패를 구조화된 오류가 아니라 **일반 `text` 블록**으로 흘리고
(`Invalid API key · Fix external API key`), 그 턴의 `result.subtype` 은 `success` 로 끝낸다
(실측 SSE, Cycle 6 F5). subtype 이나 예외만 보면 「키가 무효다」를 영영 못 가른다.
"""

from __future__ import annotations

# 프론트 `STREAM_FAILURE_CODES` 와 같은 값이어야 한다 — 한쪽만 바꾸면 화면이 문구를 못 고른다.
FAILURE_INVALID_API_KEY = "botAgent.invalid_api_key"
FAILURE_TURN_FAILED = "botAgent.turn_failed"

# CLI 가 인증 실패에서 실제로 내는 문구들. 좁게 잡는다 — 넓히면 사용자가 그 단어를 말하기만 해도
# 「키가 무효다」로 오진한다.
_AUTH_FAILURE_MARKERS = (
    "invalid api key",
    "fix external api key",
    "invalid x-api-key",
    "authentication_error",
    "oauth token has expired",
    "credit balance is too low",
)


def looks_like_auth_failure(text: str) -> bool:
    """이 문구가 「자격증명이 거부됐다」를 말하는가."""
    lowered = text.lower()
    return any(marker in lowered for marker in _AUTH_FAILURE_MARKERS)


def failure_event(*, auth_failure: bool) -> dict:
    """실패 이벤트 하나 — `code` 가 정본이고 `message` 는 코드를 모르는 소비자용 폴백이다."""
    if auth_failure:
        return {
            "type": "error",
            "code": FAILURE_INVALID_API_KEY,
            "message": "봇 대화의 API 키 인증이 거부됐습니다.",
        }
    return {
        "type": "error",
        "code": FAILURE_TURN_FAILED,
        "message": "대화가 끝까지 가지 못했습니다.",
    }
