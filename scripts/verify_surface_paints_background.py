#!/usr/bin/env python3
"""**바탕을 안 칠한 자리와 자기 모드를 안 밝힌 자리** (#281).

이 그물이 존재하는 이유는 대비 검사가 **원리적으로 못 잡는** 결함이 있기 때문이다.

`FIELD_INPUT_CLASS` 에는 배경 클래스가 **아예 없었다**. 그래서 입력칸이 브라우저 기본(흰색)으로
떨어졌고, 다크 보드 위에서 흰 상자가 됐다. 그런데 흰 바탕에 다크 잉크는 대비가 **높아서**
`verify_token_contrast.py` 도 렌더 대비 측정도 통과한다 — 대비는 멀쩡하고 **바탕이 틀린** 것이다.

같은 결함의 뒷면이 하나 더 있다. 토큰은 `:root` 가 다크 기본이고 `[data-theme="light"]` 가
라이트다. **밝은 자리가 그 선언을 빠뜨리면** 그 안의 프리미티브가 다크로 풀려, 이번엔 밝은 카드
위에 검은 상자가 놓인다. 실제로 이 PR 의 첫 판이 `/admin` 은 선언하고 회원가입 카드는 빠뜨려
그 반례를 만들었다.

**검사 축 셋**:

  ① 공용 입력 프리미티브(`components/shared/ui/**`)의 텍스트 입력 — 배경 토큰이 있어야 한다
  ② 전면을 덮는 자리(`h-screen`·`min-h-svh`·`h-[100dvh]` …) — 배경 토큰이 있어야 한다
  ③ 어두운 `.auth-backdrop` 안의 **밝은 카드** — `data-theme="light"` 를 선언해야 한다

축마다 검사 대상이 0건이면 실패한다. 면제는 **쓰이지 않으면 실패한다** — 낡은 예외가 조용히
남아 있으면 그물이 무엇을 봐주는지 아무도 못 본다.

**못 막는 것**: 축 ③ 은 밝은 카드를 `LIGHT_CARD_BG` 의 클래스로 알아본다. 다른 밝은 색을
새로 쓰면 표식에 안 걸린다. 축 ② 도 표식(높이 클래스) 기반이라 JS 로 높이를 주면 안 걸린다.

    python3 scripts/verify_surface_paints_background.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONT = REPO_ROOT / "frontend"

#: 배경을 주는 토큰 클래스. `bg-white` 같은 원시 색은 `verify_color_token_usage.py` 가 따로 막는다.
#:
#: **변형 접두사가 붙은 것은 안 센다** — `read-only:bg-bg-raised` 는 그 상태에서만 칠하므로
#: 기본 상태는 여전히 브라우저 기본으로 떨어진다. 실제로 이 구분이 없을 때 그물이 조용히
#: 통과했다(돌연변이 ①이 안 잡혔다).
BG_TOKEN = re.compile(r"(?<![:\w-])bg-(?:bg-base|bg-panel|bg-raised|transparent|inherit)\b")

#: 전면을 덮는 자리의 표식 — 이 높이를 쓰면 그 아래가 전부 그 자리다.
#: 뷰포트 단위 넷(`vh`·`dvh`·`svh`·`lvh`)을 임의값 대괄호까지 함께 받는다. 종전에는
#: `min-h-svh|min-h-screen|h-screen` 만 봐서 이 레포가 실제로 쓰는 `h-[100dvh]` 를 통째로
#: 놓쳤고, 그 자리에 걸어 둔 면제 2건도 아무 일을 하지 않았다.
FULL_SURFACE = re.compile(r"(?<![\w-])(?:min-)?h-(?:screen|svh|dvh|lvh|\[100(?:d|s|l)?vh\])(?![\w-])")

#: 공용 입력이 공유하는 클래스 상수 — 하나가 비면 그것을 쓰는 모든 입력이 함께 샌다.
SHARED_FIELD_CONSTANTS: dict[str, tuple[str, ...]] = {
    "components/shared/ui/primitives/FieldShell.tsx": ("FIELD_INPUT_CLASS",),
}

#: 축 ① 이 훑는 자리. 이 PR 이 토큰으로 옮긴 공용 프리미티브의 집이다.
#: DataTable 은 아직 원시 팔레트 단계(#73 S3)라 여기 없다 — 옮겨질 때 이 경로를 늘린다.
FIELD_ROOTS: tuple[str, ...] = ("components/shared/ui",)

#: 바탕을 칠하지 않아도 되는 입력 종류. 체크박스·라디오는 네이티브 그림이고(`color-scheme` 이
#: 테마를 고른다), `type="file"` 은 `sr-only` 로 숨는다.
UNPAINTED_INPUT = re.compile(r'type="(?:checkbox|radio|file)"')

#: 어두운 `.auth-backdrop` 안의 밝은 카드 색. 축 ③ 의 표식이다.
LIGHT_CARD_BG = re.compile(r"(?<![:\w-])bg-(?:white|\[#F0F1F2\])(?![\w-])", re.IGNORECASE)

#: 바탕을 안 칠해도 되는 자리와 그 이유. **쓰이지 않는 항목은 실패한다** — 낡은 면제는
#: 「대상 0건이라 통과」와 같은 얼굴이다.
ALLOWED: dict[str, str] = {
    "components/features/Common/Auth/Login.tsx": "`.auth-backdrop` 이 globals.css 에서 칠한다",
}

SKIP_DIRS = {"node_modules", ".next", "dist", "build", "tests"}

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?<![:\"'])//[^\n]*")


def _blank(match: re.Match[str]) -> str:
    """주석을 같은 길이의 공백으로 바꾼다 — 줄 번호와 오프셋이 원본과 어긋나지 않게."""
    return "".join("\n" if ch == "\n" else " " for ch in match.group(0))


def strip_comments(text: str) -> str:
    """주석을 걷는다 — 주석에 적힌 예시 클래스가 오탐을 내지 않게. 길이는 보존한다."""
    return LINE_COMMENT.sub(_blank, BLOCK_COMMENT.sub(_blank, text))


def _files(root: Path) -> list[Path]:
    out = []
    for path in sorted(root.rglob("*.tsx")):
        if any(part in SKIP_DIRS for part in path.parts) or path.name.endswith(".test.tsx"):
            continue
        out.append(path)
    return out


def _class_strings(text: str) -> list[tuple[int, str]]:
    """클래스가 실릴 만한 문자열 리터럴들 — 줄 번호와 함께 (주석은 이미 걷힌 텍스트)."""
    out: list[tuple[int, str]] = []
    for match in re.finditer(r'"([^"\n]{4,400})"', text):
        line = text.count("\n", 0, match.start()) + 1
        out.append((line, match.group(1)))
    return out


def _jsx_elements(text: str, tag: str) -> list[tuple[int, str]]:
    """`<tag …>` 여는 태그 하나치 — 줄 번호와 함께.

    끝나는 `>` 를 단순히 `find` 로 잡으면 **화살표 함수(`(e) => …`)의 `>`** 에서 잘린다.
    실제로 그렇게 잘려 `className` 이 슬라이스 밖으로 나가 오탐이 났다. 중괄호 깊이를 세고
    문자열 리터럴을 건너뛰어, 깊이 0 의 `>` 에서만 닫는다.
    """
    out: list[tuple[int, str]] = []
    for match in re.finditer(rf"<{tag}\b", text):
        depth = 0
        quote: str | None = None
        index = match.end()
        while index < len(text):
            char = text[index]
            if quote is not None:
                if char == quote:
                    quote = None
            elif char in "\"'`":
                quote = char
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif char == ">" and depth == 0:
                break
            index += 1
        out.append((text.count("\n", 0, match.start()) + 1, text[match.start() : index + 1]))
    return out


def main() -> int:
    if not FRONT.is_dir():
        print(f"::error::필수 경로가 없습니다: {FRONT} — fail-closed 종료", file=sys.stderr)
        return 1

    violations: list[str] = []
    shared_checked = 0
    input_checked = 0
    surface_checked = 0
    card_checked = 0
    allowed_used: set[str] = set()

    # ① 공용 입력 클래스 상수
    for rel, names in SHARED_FIELD_CONSTANTS.items():
        path = FRONT / rel
        if not path.is_file():
            violations.append(f"{rel}: 파일이 없습니다 — 상수가 옮겨졌다면 이 그물도 따라가야 합니다")
            continue
        text = path.read_text(encoding="utf-8")
        for name in names:
            block = re.search(rf"{re.escape(name)}\s*=\s*(.+?);", text, re.DOTALL)
            if block is None:
                violations.append(f"{rel}: 상수 {name} 을 찾지 못했습니다 — 이름이 바뀌었을 수 있습니다")
                continue
            shared_checked += 1
            if not BG_TOKEN.search(block.group(1)):
                violations.append(
                    f"{rel}: {name} 에 배경 토큰이 없습니다 — 입력칸이 브라우저 기본(흰색)으로 떨어집니다"
                )

    # ① 공용 프리미티브의 텍스트 입력 — 상수를 쓰든 직접 쓰든 바탕이 있어야 한다.
    #    상수만 보면 사본을 든 프리미티브가 사각지대로 남는다(실제로 TextBox 가 그랬다).
    for rel_root in FIELD_ROOTS:
        root = FRONT / rel_root
        if not root.is_dir():
            violations.append(f"{rel_root}: 경로가 없습니다 — 프리미티브가 옮겨졌다면 FIELD_ROOTS 도 따라가야 합니다")
            continue
        for path in _files(root):
            rel = str(path.relative_to(FRONT))
            text = strip_comments(path.read_text(encoding="utf-8"))
            uses_shared = any(name in text for names in SHARED_FIELD_CONSTANTS.values() for name in names)
            for tag in ("input", "textarea"):
                for line, element in _jsx_elements(text, tag):
                    if UNPAINTED_INPUT.search(element) or "sr-only" in element:
                        continue
                    input_checked += 1
                    if BG_TOKEN.search(element):
                        continue
                    if uses_shared and "FIELD_INPUT_CLASS" in element:
                        continue
                    violations.append(
                        f"{rel}:{line}: <{tag}> 가 자기 바탕을 안 칠합니다 — 브라우저 기본으로 떨어집니다"
                    )

    # ② 전면을 덮는 자리
    for path in _files(FRONT):
        rel = str(path.relative_to(FRONT))
        text = strip_comments(path.read_text(encoding="utf-8"))
        for line, literal in _class_strings(text):
            if not FULL_SURFACE.search(literal):
                continue
            surface_checked += 1
            if BG_TOKEN.search(literal):
                continue
            if rel in ALLOWED:
                allowed_used.add(rel)
                continue
            violations.append(f"{rel}:{line}: 전면을 덮는데 배경 토큰이 없습니다 — {literal[:70]}")

    # ③ 어두운 인증 배경 안의 밝은 카드 — 자기 모드를 선언해야 한다.
    #    대상은 목록이 아니라 **발견**으로 잡는다: `.auth-backdrop` 을 쓰는 파일 전수.
    for path in _files(FRONT):
        rel = str(path.relative_to(FRONT))
        text = strip_comments(path.read_text(encoding="utf-8"))
        if "auth-backdrop" not in text:
            continue
        for line, element in _jsx_elements(text, "div"):
            if not LIGHT_CARD_BG.search(element):
                continue
            card_checked += 1
            if 'data-theme="light"' not in element:
                violations.append(
                    f'{rel}:{line}: 어두운 인증 배경 안의 밝은 카드가 `data-theme="light"` 를 안 답니다'
                    " — 그 안의 공용 입력이 다크로 풀려 검은 상자가 됩니다"
                )

    print(
        f"공유 입력 클래스 {shared_checked}건 · 공용 입력 요소 {input_checked}건 · "
        f"전면 서피스 {surface_checked}건 · 인증 라이트 카드 {card_checked}건 검사"
        f" (frontend/**/*.tsx, 테스트·주석 제외 · 면제 {len(ALLOWED)}건)"
    )

    empty_axes = [
        name
        for name, count in (
            ("공유 입력 클래스", shared_checked),
            ("공용 입력 요소", input_checked),
            ("전면 서피스", surface_checked),
            ("인증 라이트 카드", card_checked),
        )
        if count == 0
    ]
    if empty_axes:
        print(
            f"::error::검사 대상이 0건인 축이 있습니다({' · '.join(empty_axes)}) — 표식이 바뀌었을 수 있습니다 (fail-closed)",
            file=sys.stderr,
        )
        return 1

    for rel in sorted(set(ALLOWED) - allowed_used):
        violations.append(
            f"{rel}: 면제가 낡았습니다 — 이 파일은 이제 검사에 안 걸립니다. 면제를 지우세요 ({ALLOWED[rel]})"
        )

    for line in violations:
        print(f"::error::{line}", file=sys.stderr)
    if violations:
        print(
            "::error::대비 검사는 이것을 못 잡습니다 — 흰 바탕에 다크 잉크는 대비가 높습니다."
            " 바탕을 안 칠했거나 모드를 안 밝힌 것이 결함입니다.",
            file=sys.stderr,
        )
        return 1
    print("위반 0건 — 전면 서피스·공용 입력이 자기 바탕을 칠하고, 밝은 카드가 자기 모드를 밝힙니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
