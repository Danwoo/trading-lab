"""멀티턴 히스토리 인젝션 무력화 (순수함수).

가드레일(_guardrail_node)은 의도적으로 **현재 질문만** 검사한다(멀티턴 사회공학 방어 불변).
그 결과 차단된 질문이라도 프론트가 히스토리에 기록하면 다음 턴에 `[이전 대화]` 로 무검사
재주입되어, 인젝션 페이로드를 턴을 나눠 넣는 방식으로 가드레일을 구조적으로 우회할 수 있다.

히스토리는 LLM 재판정(비용) 대신 소비 직전(_build_history_ctx) 결정론적 소독으로 방어한다:
과거 발화 텍스트에서 지시성(instruction-directed) 시그니처를 `_NEUTRALIZED` 로 치환해 무력화한다.

⚠️ 경계: 이것은 **알려진 시그니처의 심층방어**이지 완전한 인젝션 분류기가 아니다(정규식 arms-race).
미매칭 텍스트의 blast radius 는 _build_history_ctx 의 신뢰경계 envelope 가 1차로 줄인다.
금융 도메인 정상어(규제·방산·공매도·레버리지 등) 오탐을 피하려 **다단어 지시성 패턴만** 타겟한다.
"""

from __future__ import annotations

import re

_NEUTRALIZED = "[제거된 지시성 문구]"

# 각 패턴은 "AI 를 향한 지시" 로만 성립하는 다단어 구조를 잡는다 (단일 도메인 키워드 회피).
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # 이전 지시/규칙/프롬프트 무시·해제 (EN)
    re.compile(
        r"(?:ignore|disregard|forget|override|bypass)\s+"
        r"(?:all\s+|any\s+|the\s+|your\s+|previous\s+|above\s+|prior\s+|earlier\s+|these\s+){0,3}"
        r"(?:instruction|instructions|rule|rules|prompt|prompts|system\s*prompt|guardrail|guardrails|"
        r"guideline|guidelines|restriction|restrictions|filter|filters)",
        re.IGNORECASE,
    ),
    # 이전 지시/규칙/프롬프트/제약 … 무시·잊·해제·무효 (KO)
    re.compile(
        r"(?:이전|앞|위|기존|모든|위의|앞의)\s*"
        r"(?:지시|지시사항|규칙|지침|프롬프트|시스템\s*프롬프트|가이드라인|제약|제한|필터)"
        r"(?:사항|들)?\s*[은는을를]?\s*(?:상관없이\s*)?"
        r"(?:무시|잊|해제|무효화|무력화|풀)"
    ),
    # 지금부터 제한/제약/규칙/필터/검열 없이·해제 (KO)
    re.compile(
        r"(?:지금부터|이제부터|앞으로|여기서부터)?\s*"
        r"(?:제한|제약|규칙|필터|검열|가드레일)\s*(?:을|를|은|는)?\s*"
        r"(?:없이|없는|해제|풀고|풀어|무시|끄고|꺼)"
    ),
    # no/without restrictions|rules|filters|guardrails (EN)
    re.compile(
        r"(?:no|without|free\s+of|unrestricted|unfiltered)\s+"
        r"(?:restriction|restrictions|rule|rules|filter|filters|limit|limits|guardrail|guardrails|censorship)",
        re.IGNORECASE,
    ),
    # system prompt / 내부 지시 노출 요청 (KO/EN 기술 위장 포함).
    # 대상 명사와 노출 동사 사이 필러(조사·"그대로" 등)를 최대 15자 허용.
    re.compile(
        r"(?:system\s*prompt|시스템\s*프롬프트|내부\s*지시|내부\s*지침|internal\s+instruction|"
        r"\$?SYSTEM_PROMPT|instruction\s+field)s?[^\n]{0,15}?"
        r"(?:출력|보여|알려|공개|반환|노출|덤프|echo|print|show|reveal|dump)",
        re.IGNORECASE,
    ),
    # 페르소나/역할 전환 (KO)
    re.compile(r"(?:지금부터|이제)?\s*너는\s*이제\s*[^\n。.]{0,24}(?:이야|다|persona|역할|모드)"),
    # act as / you are now / pretend / roleplay / DAN·developer mode (EN)
    re.compile(
        r"\b(?:act\s+as|you\s+are\s+now|pretend\s+to\s+be|roleplay\s+as|new\s+persona|"
        r"DAN\s+mode|developer\s+mode|jailbreak)\b",
        re.IGNORECASE,
    ),
    # 개발자/관리자 승인·예외 위장 (KO)
    re.compile(r"(?:개발(?:자|팀)|관리자|운영자|admin|developer)\s*(?:가|이)?\s*(?:승인|허락|허가|예외)"),
    # 이 대화는 예외 / this conversation is an exception (KO/EN)
    re.compile(r"(?:이\s*(?:대화|질문|요청)|this\s+(?:conversation|chat|request))\s*(?:는|은)?\s*예외", re.IGNORECASE),
    # 아까/이전에 허락·허용했잖아 (KO — 멀티턴 사회공학)
    re.compile(r"(?:아까|이전에|앞에서|먼저)\s*[^\n。.]{0,12}(?:허락|허용|승인)했"),
)


def neutralize_injection(text: str | None) -> str:
    """히스토리 발화 텍스트에서 지시성 인젝션 시그니처를 치환해 무력화한다. None/빈 문자열은 그대로."""
    if not text:
        return text or ""
    out = text
    for pattern in _INJECTION_PATTERNS:
        out = pattern.sub(_NEUTRALIZED, out)
    return out
