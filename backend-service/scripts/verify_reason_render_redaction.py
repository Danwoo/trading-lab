#!/usr/bin/env python3
"""실패 사유를 그리는 자리가 **전부** 가림을 지나는가 (fail-closed, stdlib 전용).

## 왜 있나

저장 시점 방어(#251)는 「앞으로」만 덮는다. 이미 저장된 행·다른 경로로 들어온 행·다른 서비스가
쓴 행은 그대로 화면에 나간다 — 실제로 그런 행이 DB 에 있었고 화면에 이렇게 보였다:

    HTTPStatusError: Client error '403 Forbidden' for url 'https://openapi.tossinvest.com/oauth2/token'

**data.go.kr 은 인증키를 쿼리 파라미터로 받는다.** 그 소스의 실패였다면 그 자리에 키가 있다.
화면은 어디서 왔든 그리는 자리라 마지막 관문이 여기이고, **관문이 하나라도 비면 그 하나로 샌다.**

## 무엇을 보나

프론트에서 `failed_reason`·`absent_reason` 을 **그리는** 자리(JSX 표현식·title 속성)가 전부
`redactReason(...)` 을 지나는가. 그리지 않고 넘기기만 하는 자리(props 전달)는 대상이 아니다.

**fail-closed**: 그리는 자리를 0건 찾으면 실패한다 — 이름이 바뀌어 검사가 죽은 것이다.

실행: `cd backend-service && python3 scripts/verify_reason_render_redaction.py`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONT = REPO_ROOT / "frontend" / "components"

#: 사유를 **그리는** 자리 — 필드 이름이 나오는 곳을 전부 잡고, 그 둘레에서 가림을 찾는다.
#:
#: **줄 단위로 보지 않는다.** JSX 는 포매터가 한 줄을 여러 줄로 쪼개므로, 줄 정규식으로 세면
#: 감싸는 순간 그 자리가 **검사에서 사라진다**(실측: 4곳이 3곳으로 줄었다). 그러면 그물이
#: 「고쳤더니 검사 대상이 없어졌다」는 최악의 초록을 낸다.
FIELD = re.compile(r"\b(failed_reason|absent_reason)\b")
#: 필드 앞뒤로 이만큼을 한 덩어리로 본다 — 감싼 호출이 다른 줄에 있어도 잡힌다.
CONTEXT_CHARS = 60
GUARD = "redactReason"
#: fail-closed 핀 — 검사한 자리가 조용히 줄지 않게 박는다.
EXPECTED_RENDER_SITES = 5


def _strip_comments(text: str) -> str:
    """주석을 **공백으로 바꾼다**(지우지 않는다) — 줄 번호가 어긋나지 않게.

    주석은 「그리는 자리」가 아니다. 설계 의도를 적으며 필드 이름을 언급하는 것까지 위반으로
    세면 그물이 문서를 못 쓰게 만든다.
    """

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", blank, text)


def render_sites(text: str) -> list[tuple[int, str]]:
    """`(줄 번호, 둘레 문자열)` — 코드에서 필드를 **읽는** 자리만."""
    code = _strip_comments(text)
    out: list[tuple[int, str]] = []
    for match in FIELD.finditer(code):
        # 타입 선언(`failed_reason: string | null` · `failed_reason?: string`)은 그리는 자리가
        # 아니다. **`??` 를 여기서 걸러선 안 된다** — `cell.failed_reason ?? undefined` 는
        # 그리는 자리인데, 그것을 선언으로 오인하면 **가림을 뺀 자리가 목록에서 사라져**
        # 위반이 초록으로 지나간다(실측: 뮤테이션에서 5곳이 4곳이 되며 통과했다).
        tail = code[match.end() : match.end() + 4]
        if re.match(r"\s*\?\s*:", tail) or re.match(r"\s*:", tail):
            continue
        start = max(0, match.start() - CONTEXT_CHARS)
        out.append((code.count("\n", 0, match.start()) + 1, code[start : match.end() + CONTEXT_CHARS]))
    return out


def main() -> int:
    if not FRONT.is_dir():
        print(f"::error::필수 경로가 없습니다: {FRONT} — fail-closed 종료")
        return 1

    sites: list[str] = []
    unguarded: list[str] = []
    for path in sorted(FRONT.rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        for lineno, around in render_sites(text):
            where = f"{path.relative_to(REPO_ROOT)}:{lineno}"
            sites.append(where)
            if GUARD not in around:
                unguarded.append(f"{where}: {' '.join(around.split())[:100]}")

    if not sites:
        print("::error::사유를 그리는 자리를 0건 찾았습니다 — 필드 이름이 바뀌었을 수 있습니다 (fail-closed)")
        return 1
    # **개수가 줄어드는 것도 실패다.** 자리가 사라지는 방식으로 검사를 빠져나가면 위반이
    # 초록으로 지나간다 — 그것이 실제로 한 번 일어났다. 자리를 줄였으면 이 수를 함께 내려라.
    if len(sites) < EXPECTED_RENDER_SITES:
        print(f"::error::그리는 자리가 {len(sites)}곳뿐입니다 (기대 {EXPECTED_RENDER_SITES}곳) — 검사가 줄었습니다")
        for where in sites:
            print(f"::error::  본 자리: {where}")
        return 1

    print(f"사유를 그리는 자리 {len(sites)}곳 검사 (components/**/*.tsx)")
    if unguarded:
        print(f"::error::가림을 안 지나는 자리 {len(unguarded)}곳")
        for line in unguarded:
            print(f"::error::  {line}")
        print("::error::저장 시점 방어는 소급되지 않는다 — 그리는 자리마다 redactReason 을 지나야 한다.")
        return 1

    print("위반 0건 — 사유를 그리는 자리가 전부 가림을 지난다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
