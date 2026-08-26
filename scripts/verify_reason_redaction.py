#!/usr/bin/env python3
"""실패 사유가 **화면으로 나가는 모든 자리**에서 가림을 지나는가 (fail-closed, stdlib 전용).

## 왜 루트 `scripts/` 에 있나

이 그물이 지키는 것은 `frontend/` 다. `backend-service/scripts/` 에 두면 `ci.yml` 의 경로
필터(`FILTER_PATTERNS`)에 `frontend/**` 가 없어 **프론트만 바꾼 PR 에서 조용히 skip** 된다 —
지켜야 할 바로 그 PR 클래스에서 안 도는 그물이다. 이 레포가 같은 클래스를 이미 겪고
`ci.yml` 주석에 적어 두었다. 그래서 경로 필터가 없는 `repo-scan` 잡에서 돈다
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
EXPECTED_SITES = 11
SKIP_DIRS = {"node_modules", ".next", "dist", "build"}


def _blank_noncode(text: str) -> str:
    """문자열과 주석을 공백으로 눕힌다(줄 번호 보존).

    **한 번에 훑어야 한다.** 주석만 먼저 지우면 `href="https://…"` 안의 `//` 를 주석 시작으로
    읽어 그 줄의 나머지가 통째로 사라진다 — 링크가 있는 줄에서 사유를 그리면 그 자리가 검사에서
    빠졌다. 문자열만 먼저 지우면 주석 안의 따옴표가 문자열을 연다.

    따옴표는 **같은 줄에서 닫힐 때만** 문자열로 본다. JSX 본문의 아포스트로피가 뒤 코드를
    삼키지 않게 하는 안전장치다 (역따옴표는 여러 줄이 정상이라 예외).
    """
    out = list(text)
    index, size = 0, len(text)
    while index < size:
        char = text[index]
        if char in "'\"`":
            end = _string_end(text, index)
            if end is None:
                index += 1
                continue
            for pos in range(index + 1, end):
                if out[pos] != "\n":
                    out[pos] = " "
            index = end + 1
        elif text.startswith("//", index):
            stop = text.find("\n", index)
            stop = size if stop == -1 else stop
            out[index:stop] = " " * (stop - index)
            index = stop
        elif text.startswith("/*", index):
            stop = text.find("*/", index + 2)
            stop = size if stop == -1 else stop + 2
            for pos in range(index, stop):
                if out[pos] != "\n":
                    out[pos] = " "
            index = stop
        else:
            index += 1
    return "".join(out)


def _string_end(text: str, start: int) -> int | None:
    """여는 따옴표 위치를 받아 닫는 위치를 준다. 못 닫으면 문자열이 아니다."""
    quote = text[start]
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == quote:
            return index
        if char == "\n" and quote != "`":
            return None
        index += 1
    return None


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
        elif char == ";" and depth == 0:
            # 개행에서 멈추면 포매터가 인자를 줄바꿈한 **정상 코드**가 빨강이 된다
            # (`redactReason(\n  run.failed_reason,\n)`). 문장 끝에서만 멈춘다.
            return False
    return False


def _alias_binding(code: str, end: int) -> bool:
    """`{ failed_reason: reason }` 이 **바인딩**인가 — 그렇다면 읽는 자리다.

    타입 선언(`{ failed_reason: string }`)과 글자 모양이 같아 tail 만으로는 못 가른다. 가르는
    것은 **바깥에 무엇이 있는가**다. 중첩·매개변수 분해까지 잡으려면 안쪽 중괄호가 아니라
    **가장 바깥 중괄호**를 보고 판정해야 한다:

        const { run: { failed_reason: reason } } = props   ← 앞이 `const`
        function Cell({ failed_reason: reason }: Props)    ← 앞이 `(`

    안쪽 중괄호 바로 앞만 보면 각각 `run: ` · `(` 라 둘 다 타입으로 오분류된다.
    """
    brace = _pattern_root(code, end)
    if brace is None:
        return False
    before = code[max(0, brace - 40) : brace].rstrip()
    if before.endswith(("(", ",")):
        return True
    if not re.search(r"\b(const|let|var)$", before):
        return False
    close = _matching_brace(code, brace)
    return close is not None and re.match(r"\s*=[^=]", code[close + 1 : close + 4]) is not None


def _pattern_root(code: str, at: int) -> int | None:
    """`at` 을 감싸는 **분해 패턴의 뿌리** 중괄호.

    중첩 분해(`const { run: { … } }`)의 안쪽에서 시작해 바깥으로 오르되, **`:` 로 이어질 때만**
    오른다 — 그것이 패턴 안쪽이라는 표시다. 함수 본문·JSX 블록까지 오르면 뿌리를 지나쳐
    `const` 를 못 보게 된다.
    """
    brace = _enclosing_brace(code, at)
    while brace is not None and code[max(0, brace - 40) : brace].rstrip().endswith(":"):
        outer = _enclosing_brace(code, brace)
        if outer is None:
            break
        brace = outer
    return brace


def _enclosing_brace(code: str, at: int) -> int | None:
    """`at` 을 바로 감싸는 여는 중괄호."""
    depth = 0
    index = at
    while index > 0:
        index -= 1
        char = code[index]
        if char == "}":
            depth += 1
        elif char == "{":
            if depth == 0:
                return index
            depth -= 1
        elif char == ";" and depth == 0:
            return None
    return None


def _matching_brace(code: str, opening: int) -> int | None:
    """여는 중괄호와 짝이 되는 닫는 위치."""
    depth = 0
    for index in range(opening, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def sites(text: str) -> list[tuple[int, bool, str]]:
    """`(줄, 가려졌나, 둘레)` — 타입 선언은 뺀다. **별칭 분해는 읽는 자리로 센다.**"""
    code = _blank_noncode(text)
    out: list[tuple[int, bool, str]] = []
    for match in FIELD.finditer(code):
        tail = code[match.end() : match.end() + 4]
        # 타입 선언(`x: T` · `x?: T`)만 제외한다. `??` 는 읽는 자리다.
        if (re.match(r"\s*\?\s*:", tail) or re.match(r"\s*:(?!\s*\w+\s*[,}])", tail)) and not _alias_binding(
            code, match.end()
        ):
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
        if "tests" in path.parts or path.name.endswith(".test.ts") or path.name.endswith(".test.tsx"):
            continue
        for line, guarded, around in sites(path.read_text(encoding="utf-8")):
            where = f"{path.relative_to(REPO_ROOT)}:{line}"
            found.append(where)
            if not guarded:
                unguarded.append(f"{where}: {around[:110]}")

    print(f"사유를 읽는 자리 {len(found)}곳 검사 (frontend/**/*.ts·tsx, 테스트 제외)")
    if not found:
        print("::error::자리를 0건 찾았습니다 — 필드 이름이 바뀌었을 수 있습니다 (fail-closed)")
        return 1
    if len(found) < EXPECTED_SITES:
        print(f"::error::자리가 {len(found)}곳뿐입니다 (기대 {EXPECTED_SITES}곳) — 검사가 줄었습니다")
        for where in found:
            print(f"::error::  본 자리: {where}")
        return 1
    if unguarded:
        print(f"::error::가림을 안 지나는 자리 {len(unguarded)}곳")
        for line in unguarded:
            print(f"::error::  {line}")
        print("::error::저장 시점 방어는 소급되지 않는다 — 읽는 자리마다 redactReason 안에 있어야 한다.")
        return 1

    print("위반 0건 — 사유를 읽는 자리가 전부 가림 안에 있다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
