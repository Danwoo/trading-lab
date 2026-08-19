#!/usr/bin/env python3
"""실패 사유가 **화면으로 나가는 모든 자리**에서 가림을 지나는가 (fail-closed, stdlib 전용).

## 왜 루트 `scripts/` 에 있나

이 그물이 지키는 것은 `frontend/` 다. `backend-service/scripts/` 에 두면 `ci.yml` 의 경로
필터(`FILTER_PATTERNS`)에 `frontend/**` 가 없어 **프론트만 바꾼 PR 에서 조용히 skip** 된다 —
지켜야 할 바로 그 PR 클래스에서 안 도는 그물이다. 이 레포가 같은 클래스를 이미 겪고
`repo-scans.yml` 주석에 적어 두었다. 그래서 경로 필터가 없는 `repo-scan` 잡에서 돈다
(`scripts/verify_color_token_usage.py` 가 같은 선례다).

## 왜 있나

저장 시점 방어(#251)는 「앞으로」만 덮고 **소급되지 않는다.** 이미 저장된 행이 화면에
원문을 내보내고 있었다:

    HTTPStatusError: Client error '403 Forbidden' for url 'https://openapi.tossinvest.com/oauth2/token'

**data.go.kr 은 인증키를 쿼리 파라미터로 받는다.** 그 소스의 실패였다면 그 자리에 키가 있다.

## 무엇을 보나

`failed_reason`·`absent_reason` 을 **읽는** 자리가 전부 `redactReason(...)` **안에** 있는가.

세 가지를 앞선 판에서 놓쳤고, 그것이 이 그물이 지금 이 모양인 이유다:

1. **`components/` 만 봤다** — 유출은 `hooks/`(`.ts`)에서 `failedReason` 으로 **개명**되어 나갔다.
   이제 `frontend/**` 의 `.ts`·`.tsx` 를 다 보고, 개명 자리도 별칭 분해로 잡는다
2. **±60자 안에 문자열이 있으면 통과였다** — 이웃의 가림을 자기 것으로 셌다.
   이제 **감싸는 호출인지**를 괄호 대응으로 확인한다
3. **줄 단위로 셌다** — 포매터가 감싸는 순간 자리가 검사에서 사라졌다. 전체 텍스트를 본다

**fail-closed**: 자리를 0건 찾거나 기대보다 적으면 실패한다. 자리가 **줄어드는 방식**의 우회도
막아야 한다 — 실제로 그렇게 초록이 난 적이 있다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONT = REPO_ROOT / "frontend"

#: 사유 필드 — 원 이름과, 화면 계층에서 흔히 쓰는 개명형.
FIELD = re.compile(r"\b(failed_reason|absent_reason|failedReason)\b")
GUARD = "redactReason"
#: fail-closed 핀 — 검사한 자리가 조용히 줄지 않게 박는다.
#: 이 스크립트를 그냥 돌려 나온 수다 (손으로 세면 계층을 빠뜨린다 — 실제로 hooks 2곳을 빠뜨려
#: 8 로 박혔고, 그동안 자리 2곳이 사라져도 초록이었다).
EXPECTED_SITES = 10
SKIP_DIRS = {"node_modules", ".next", "dist", "build"}


def _blank_comments(text: str) -> str:
    """주석을 공백으로 바꾼다(줄 번호 보존). 설계 의도를 적으며 필드를 언급하는 것은 위반이 아니다."""

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return re.sub(
        r"//[^\n]*", blank, re.sub(r"/\*.*?\*/", blank, text, flags=re.DOTALL)
    )


def _guarded(code: str, at: int) -> bool:
    """이 자리가 `redactReason(...)` **안**에 있는가 — 괄호 대응으로 확인한다.

    둘레에 문자열이 있기만 하면 통과시키면, 바로 옆 줄에서 가린 것을 자기 것으로 센다:

        {redactReason(run.failed_reason) && <span>{run.failed_reason}</span>}
                                                       ^^^ 이 자리는 안 가려졌다
    """
    depth = 0
    index = at
    while index > 0:
        index -= 1
        char = code[index]
        if char == ")":
            depth += 1
        elif char == "(":
            if depth == 0:
                return code[max(0, index - len(GUARD)) : index].endswith(GUARD)
            depth -= 1
        elif char in ";\n" and depth == 0:
            return False
    return False


def _alias_binding(code: str, end: int) -> bool:
    """`const { failed_reason: reason } = run` 인가 — **읽는 자리**다.

    타입 선언(`{ failed_reason: string }`)과 글자 모양이 같아 tail 만으로는 못 가른다. 가르는
    것은 **바인딩 키워드와 `=`** 다 — 타입에는 둘 다 없다. 개명해서 내보내는 이 패턴이 앞선
    판에서 그물을 통째로 우회했다.
    """
    open_brace = code.rfind("{", max(0, end - 300), end)
    if open_brace == -1:
        return False
    if not re.search(
        r"\b(const|let|var)\s*$", code[max(0, open_brace - 30) : open_brace]
    ):
        return False
    close = code.find("}", end)
    return (
        close != -1 and re.match(r"\s*=[^=]", code[close + 1 : close + 4]) is not None
    )


def sites(text: str) -> list[tuple[int, bool, str]]:
    """`(줄, 가려졌나, 둘레)` — 타입 선언은 뺀다. **별칭 분해는 읽는 자리로 센다.**"""
    code = _blank_comments(text)
    out: list[tuple[int, bool, str]] = []
    for match in FIELD.finditer(code):
        tail = code[match.end() : match.end() + 4]
        # 타입 선언(`x: T` · `x?: T`)만 제외한다. `??` 는 읽는 자리다.
        if (
            re.match(r"\s*\?\s*:", tail) or re.match(r"\s*:(?!\s*\w+\s*[,}])", tail)
        ) and not _alias_binding(code, match.end()):
            continue
        line = code.count("\n", 0, match.start()) + 1
        around = code[max(0, match.start() - 70) : match.end() + 70]
        out.append((line, _guarded(code, match.start()), " ".join(around.split())))
    return out


def main() -> int:
    if not FRONT.is_dir():
        print(f"::error::필수 경로가 없습니다: {FRONT} — fail-closed 종료")
        return 1

    found: list[str] = []
    unguarded: list[str] = []
    for path in sorted(FRONT.rglob("*.ts*")):
        if any(part in SKIP_DIRS for part in path.parts) or path.suffix not in (
            ".ts",
            ".tsx",
        ):
            continue
        # 테스트는 일부러 원문을 다룬다 — 화면으로 나가는 자리가 아니다.
        if (
            "tests" in path.parts
            or path.name.endswith(".test.ts")
            or path.name.endswith(".test.tsx")
        ):
            continue
        for line, guarded, around in sites(path.read_text(encoding="utf-8")):
            where = f"{path.relative_to(REPO_ROOT)}:{line}"
            found.append(where)
            if not guarded:
                unguarded.append(f"{where}: {around[:110]}")

    print(f"사유를 읽는 자리 {len(found)}곳 검사 (frontend/**/*.ts·tsx, 테스트 제외)")
    if not found:
        print(
            "::error::자리를 0건 찾았습니다 — 필드 이름이 바뀌었을 수 있습니다 (fail-closed)"
        )
        return 1
    if len(found) < EXPECTED_SITES:
        print(
            f"::error::자리가 {len(found)}곳뿐입니다 (기대 {EXPECTED_SITES}곳) — 검사가 줄었습니다"
        )
        for where in found:
            print(f"::error::  본 자리: {where}")
        return 1
    if unguarded:
        print(f"::error::가림을 안 지나는 자리 {len(unguarded)}곳")
        for line in unguarded:
            print(f"::error::  {line}")
        print(
            "::error::저장 시점 방어는 소급되지 않는다 — 읽는 자리마다 redactReason 안에 있어야 한다."
        )
        return 1

    print("위반 0건 — 사유를 읽는 자리가 전부 가림 안에 있다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
