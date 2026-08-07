"""미근거 수치 검출 — 최종 답변의 금융 수치를 도구 출력과 대조 (결정론적·오프라인).

LLM 이 tool 출력에 없는 가격·비율·금액을 지어내는 것(hallucinated figures)을 잡기 위해,
답변에서 '금융 수치'로 보이는 토큰을 추출해 tool_calls 출력의 숫자 집합에 없으면 '미근거'로 표기한다.
LLM·네트워크 의존 없는 순수함수 — 오프라인 단위 테스트 가능.
"""

from __future__ import annotations

import re

# 금융 단위(있으면 무조건 수치 주장으로 간주)
_UNIT = r"%|％|퍼센트|원|달러|엔|위안|억|조|만|배|bp|bps|pt|포인트|p"
# 숫자 코어: 1,234.56 / 12.3 / 005930 등 (천단위 콤마·소수 허용)
_NUM_CORE = r"\d[\d,]*(?:\.\d+)?"
# 답변에서 '단위가 붙었거나 콤마/소수가 있는' 수치 + 순수 4자리+ 정수까지 후보로
_CLAIM_RE = re.compile(rf"({_NUM_CORE})\s*(?:{_UNIT})?")
# tool 출력에서 숫자 코어 전부
_ANY_NUM_RE = re.compile(_NUM_CORE)
# 연도(1900~2099) 단독 정수는 오탐이 잦아 제외
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")


def _norm(token: str) -> str:
    """콤마 제거 + 소수 뒤 무의미한 0 정리로 비교용 정규화 (예: '1,234.50' → '1234.5')."""
    core = token.replace(",", "").strip()
    if "." in core:
        core = core.rstrip("0").rstrip(".")
    return core


def _collect_tool_numbers(tool_calls: list[dict]) -> set[str]:
    """tool_calls 출력 텍스트의 모든 숫자 코어를 정규화 집합으로."""
    nums: set[str] = set()
    for tc in tool_calls or []:
        out = tc.get("output")
        if not out:
            continue
        text = out if isinstance(out, str) else str(out)
        for m in _ANY_NUM_RE.findall(text):
            n = _norm(m)
            if n:
                nums.add(n)
    return nums


def _is_financial_claim(token: str, has_unit: bool) -> bool:
    """수치 주장으로 검사할 가치가 있는 토큰인지 — 오탐(연도·한자리 등) 억제."""
    core = token.replace(",", "").strip()
    if not core or core in (".",):
        return False
    if _YEAR_RE.match(core):
        return False  # 단독 연도 제외
    if has_unit or ("," in token) or ("." in core):
        return True
    digits = core.replace(".", "")
    return len(digits) >= 4  # 콤마·소수·단위 없으면 4자리 이상만 (종목코드·큰 금액)


def find_ungrounded_numbers(answer: str, tool_calls: list[dict]) -> list[str]:
    """답변의 금융 수치 중 어떤 tool 출력에도 없는 것을 원문 표기 그대로 반환 (등장 순·중복 제거)."""
    if not answer:
        return []
    tool_numbers = _collect_tool_numbers(tool_calls)
    ungrounded: list[str] = []
    seen: set[str] = set()
    for m in _CLAIM_RE.finditer(answer):
        token = m.group(1)
        matched = m.group(0)
        has_unit = matched.rstrip() != token.rstrip()  # 단위가 뒤에 붙었는지
        if not _is_financial_claim(token, has_unit):
            continue
        norm = _norm(token)
        if not norm or norm in tool_numbers or norm in seen:
            continue
        seen.add(norm)
        ungrounded.append(token.strip())
    return ungrounded


def build_ungrounded_annotation(numbers: list[str], limit: int = 12) -> str:
    """미근거 수치 목록 → 사용자 표기 1줄 (없으면 빈 문자열)."""
    if not numbers:
        return ""
    shown = numbers[:limit]
    suffix = " 등" if len(numbers) > limit else ""
    return "⚠️ 미근거 수치(도구 출처 미확인, 참고만): " + ", ".join(shown) + suffix


def annotate_ungrounded_numbers(answer: str, tool_calls: list[dict]) -> tuple[str, list[str]]:
    """(annotation_text, ungrounded_numbers) 반환. annotation 은 미근거 수치 있을 때만 비어있지 않음."""
    nums = find_ungrounded_numbers(answer, tool_calls)
    return build_ungrounded_annotation(nums), nums
