"""운영 정보 raw 메시지 정규식 redaction (순수함수).

외부 도구(DART/시세/뉴스/Web) 응답·sub-agent 결과·예외 메시지가 LLM context 나 답변에
들어가기 직전 결정론적으로 차단한다 (프롬프트의 LLM 자율 보호와 2중 방어).

차단 대상: API 쿼터/키 미등록 코드, IP 인증 메시지, API 키 패턴, IPv4 주소,
permanent_failure_reason JSON 키, faultstring XML, 영문 quota/rate-limit 메시지.
"""

from __future__ import annotations

import re

# 운영 코드 패턴 (DART/EDGAR/KRX/etc 영문 대문자 코드)
_OP_CODE_PATTERN = re.compile(r"\b(?:DART|EDGAR|KRX|FSS|FNGUIDE|KOSCOM)_[A-Z_]{3,40}\b")

# 한국어 IP 인증·접근 차단 메시지
_KR_ACCESS_DENIED_PATTERN = re.compile(
    r"(?:접근\s*허용\s*IP가\s*아닙니다|허용되지\s*않은\s*IP|"
    r"인증\s*실패\s*\(IP\)|API\s*키.*?(?:미등록|불일치|만료))"
)

# permanent_failure_reason JSON 키와 그 값
_FAILURE_REASON_PATTERN = re.compile(r'"permanent_failure_reason"\s*:\s*"[^"]*"')

# faultstring XML
_FAULTSTRING_PATTERN = re.compile(r"<faultstring>.*?</faultstring>", flags=re.DOTALL)

# IPv4 주소 (한글 환경에서 \b 미작동 → lookbehind/lookahead 로 자릿수 boundary 강제)
_IPV4_PATTERN = re.compile(r"(?<!\d)(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)){3}(?!\d)")

# API key 패턴 — 명시적 prefix 함께 매칭 (false positive 회피). prefix 를 그룹으로 잡아
# 구분자(공백·따옴표 포함)와 무관하게 키 전체를 치환한다.
_API_KEY_PATTERN = re.compile(
    r"(apprvKey|api[_-]?key|access[_-]?token|bearer|Authorization\s*:\s*Bearer)"
    r"[\s=:\"']{1,4}[A-Za-z0-9_\-]{16,}",
    flags=re.IGNORECASE,
)

# API quota / 사용량 초과 영문 패턴
_QUOTA_EN_PATTERN = re.compile(
    r"\b(?:quota\s*exceeded|rate\s*limit\s*exceeded|usage\s*limit|"
    r"daily\s*limit|api\s*key\s*not\s*registered|invalid\s*api\s*key)\b",
    flags=re.IGNORECASE,
)

_REDACTED_GENERIC = "해당 도메인 데이터 수집 불가"
_REDACTED_API_KEY = "***"
_REDACTED_IP = "***.***.***.***"
_REDACTED_FAULT = "[운영 메시지 제거]"


def redact_operational_info(text: str | None) -> str:
    """입력 텍스트에서 운영 정보 raw 메시지를 일반화·치환해 반환. None/빈 문자열은 그대로."""
    if not text:
        return text or ""

    out = text
    out = _KR_ACCESS_DENIED_PATTERN.sub(_REDACTED_GENERIC, out)
    out = _FAILURE_REASON_PATTERN.sub('"permanent_failure_reason": "data_unavailable"', out)
    out = _OP_CODE_PATTERN.sub(_REDACTED_GENERIC, out)
    out = _FAULTSTRING_PATTERN.sub(_REDACTED_FAULT, out)
    out = _API_KEY_PATTERN.sub(lambda m: m.group(1) + "=" + _REDACTED_API_KEY, out)
    out = _IPV4_PATTERN.sub(_REDACTED_IP, out)
    out = _QUOTA_EN_PATTERN.sub(_REDACTED_GENERIC, out)
    return out
