"""챗 유틸 — 상대기간 계산·대화 이력 변환·검색 범위 라벨.

IO/외부상태 없는 순수 함수.
"""

import calendar
from datetime import timedelta

from langchain_core.messages import AIMessage, HumanMessage, trim_messages

# character 수로 token 수 근사(한글 ≈ 3자/token). 4096 token ≈ 12288 자
_TRIM_MAX_CHARS = 4096 * 3


def _strlist(v) -> list[str]:
    return [str(x) for x in v] if isinstance(v, list) else []


def date_context(now) -> str:
    """상대 기간을 코드로 미리 계산해 프롬프트에 주입."""
    d = now.date()
    mon = d - timedelta(days=d.weekday())
    last_mon = mon - timedelta(days=7)
    m_start = d.replace(day=1)
    last_m_end = m_start - timedelta(days=1)
    last_m_start = last_m_end.replace(day=1)
    m_end = d.replace(day=calendar.monthrange(d.year, d.month)[1])
    wd = "월화수목금토일"[d.weekday()]

    def r(a, b) -> str:
        return f"{a:%Y-%m-%d} ~ {b:%Y-%m-%d}"

    return (
        f"오늘: {d:%Y-%m-%d} ({wd})\n"
        f"- 이번 주: {r(mon, mon + timedelta(days=6))}\n"
        f"- 지난 주: {r(last_mon, last_mon + timedelta(days=6))}\n"
        f"- 이번 달: {r(m_start, m_end)}\n"
        f"- 지난 달: {r(last_m_start, last_m_end)}\n"
        f"- 최근 7일: {r(d - timedelta(days=6), d)}\n"
        f"- 최근 30일: {r(d - timedelta(days=29), d)}"
    )


def lc_history(history) -> list:
    """프론트 전송 대화 이력 [{role, content}] → LangChain 메시지 + token 기반 truncation."""
    if not isinstance(history, list):
        return []
    out = []
    for m in history:
        if not (isinstance(m, dict) and isinstance(m.get("content"), str) and m["content"].strip()):
            continue
        if m.get("role") == "user":
            out.append(HumanMessage(content=m["content"]))
        elif m.get("role") == "assistant":
            out.append(AIMessage(content=m["content"]))

    def _char_token_counter(messages) -> int:
        return sum(len(msg.content) for msg in messages if isinstance(msg.content, str))

    return list(
        trim_messages(
            out,
            max_tokens=_TRIM_MAX_CHARS,
            token_counter=_char_token_counter,
            strategy="last",
            allow_partial=False,
        )
    )


def scope_note(account, since, until, kind, symbols, holders) -> str:
    """UI 지정 조회 범위 → 프롬프트 힌트 문자열."""
    parts = []
    if account:
        parts.append(f"계좌 {account}")
    elif kind:
        parts.append(f"계좌유형 {kind}")
    if since or until:
        parts.append(f"기간 {since or '…'}~{until or '…'}")
    if symbols:
        parts.append(f"종목 {','.join(_strlist(symbols))}")
    if holders:
        parts.append(f"계좌주 {','.join(_strlist(holders))}")
    return " · ".join(parts)
