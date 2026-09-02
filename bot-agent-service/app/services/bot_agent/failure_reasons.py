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

import re

# 프론트 `STREAM_FAILURE_CODES` 와 같은 값이어야 한다 — 한쪽만 바꾸면 화면이 문구를 못 고른다.
FAILURE_INVALID_API_KEY = "botAgent.invalid_api_key"
FAILURE_TURN_FAILED = "botAgent.turn_failed"

# CLI 가 인증 실패에서 실제로 내는 문구들. 목록만으로는 좁지 않다 — 이 문구가 텍스트의 **주된
# 내용**인지까지 봐야 인용과 갈린다 (`looks_like_auth_failure`).
_AUTH_FAILURE_MARKERS = (
    "invalid api key",
    "fix external api key",
    "invalid x-api-key",
    "authentication_error",
    "oauth token has expired",
    "credit balance is too low",
)


_AUTH_MARKER_PATTERN = re.compile("|".join(re.escape(marker) for marker in _AUTH_FAILURE_MARKERS), re.IGNORECASE)

# 마커를 지우고 남아도 되는 길이. 실제 CLI 출력은 마커가 사실상 전부이고, 앞에 붙어야 라벨 한 토막
# (`API Error:` 10자)이다. 그보다 길게 남으면 그건 문장이다 — 마커가 아니라 그 문장이 주된 내용이다.
_AUTH_RESIDUAL_MAX_CHARS = 16


def looks_like_auth_failure(text: str) -> bool:
    """이 문구가 「자격증명이 거부됐다」를 말하는가 — **마커가 주된 내용일 때만** 참이다.

    포함 여부로 가르면 안 된다: 사용자가 인증 오류를 붙여넣고 봇이 그것을 인용해 설명하는
    **정상 턴**까지 「키가 무효다」로 닫힌다. 이 PR 의 주제가 그 오류라 그런 문의는 실현 가능한
    입력이고, 오진하면 멀쩡한 키에 「키를 교체하라」는 거짓 처방이 붙는다.

    그래서 마커를 지우고 남는 것이 라벨 정도로 짧을 때만 참으로 본다. 마커가 긴 봉투 안에
    묻혀 있으면 일반 코드(`turn_failed`)로 떨어진다 — **틀린 처방보다 덜 구체적인 문구가 낫다.**
    """
    residual, hits = _AUTH_MARKER_PATTERN.subn("", text.strip())
    if not hits:
        return False
    return len(residual.strip()) <= _AUTH_RESIDUAL_MAX_CHARS


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
