#!/usr/bin/env python3
"""포커스 표시를 그리는 자리가 하나인지 검사한다 — fail-closed (stdlib 전용).

## 왜 있나

포커스 표시의 정본은 `frontend/styles/globals.css` 의 `:focus-visible` 한 자리다
(디자인 시스템 §「포커스는 `ring` 이 아니라 `outline` 이다」). 그런데 컴포넌트가
`focus:outline-none` 을 얹으면 **명시도(0,2,0)가 그 정본(0,1,0)을 덮어** 표시를 지우고,
대신 남는 `ring-*` 은 자리마다 색·굵기가 달라 「어디에 있는지 눈으로 쫓기 어렵다」가 된다
(`#443` F36). 실제로 이 레포에서 33개 파일이 그렇게 갈라져 있었다.

지우는 쪽과 대신 그리는 쪽이 **늘 짝으로** 들어오므로, 둘 다 없는 상태를 잠근다.

## 무엇을 막지 못하나

- `style={{ outline: "none" }}` 같은 인라인 스타일·CSS-in-JS. 이 레포는 Tailwind 클래스로만
  쓰고 있어 지금은 새지 않지만, 이 검사는 그 경로를 안 본다.
- 포커스가 **보이는지**는 못 판정한다 — 클래스가 없다는 것만 안다. 실제로 보이는지는
  브라우저로 확인한다(디자인 시스템의 완료 조건: 「표 첫 행에 Tab 으로 진입했을 때 링 4변이
  모두 보인다」).

    python3 scripts/verify_focus_indicator_single_source.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
SCAN_DIRS = ("components", "app")
GLOBALS_CSS = FRONTEND / "styles" / "globals.css"

# 정본을 덮거나 대신 그리는 클래스. `ring-` 은 **포커스 변형이 붙은 것만** 본다 —
# 선택·활성 표시로 쓰는 맨 `ring-1` 은 다른 축이라 정상이다(디자인 시스템: 포커스만 점선).
BANNED = re.compile(
    r"(?<![\w:-])(?:focus|focus-visible):(?:outline-none|ring-(?:inset|offset-[\w./-]+|\d+|[\w./\[\]-]+))(?![\w:/-])"
)
COMMENT_START = ("//", "*", "/*")

# 대상이 이 아래로 내려가면 그물이 죽은 것이다 (경로가 사라져도 「위반 0건」으로 초록이 된다).
MIN_FILES = 100


def scan() -> tuple[int, list[str]]:
    hits: list[str] = []
    files = 0
    for directory in SCAN_DIRS:
        root = FRONTEND / directory
        if not root.is_dir():
            return 0, [f"검사 대상 디렉터리가 없습니다: {root.relative_to(REPO_ROOT)}"]
        for path in sorted(root.rglob("*.tsx")):
            if ".test." in path.name:
                continue
            files += 1
            for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
                if line.lstrip().startswith(COMMENT_START):
                    continue  # 주석은 규칙을 **설명**하는 자리라 인용이 정상이다
                for match in BANNED.finditer(line):
                    hits.append(f"{path.relative_to(REPO_ROOT)}:{number}: {match.group(0)}")
    return files, hits


def main() -> int:
    if not GLOBALS_CSS.is_file():
        print(f"::error::포커스 정본 파일이 없습니다: {GLOBALS_CSS.relative_to(REPO_ROOT)}")
        return 1
    css = GLOBALS_CSS.read_text(encoding="utf-8")

    failures: list[str] = []
    # 정본이 실제로 살아 있는가 — 클래스만 없애고 정본이 사라지면 포커스가 **아무 데도** 없다.
    #
    # **부분 문자열로 찾지 않는다.** `:focus-visible` 을 `:focus-visible-off` 로 바꿔도
    # `in` 검사는 그대로 참이라, 규칙을 죽이는 개명이 통과한다 — 이 그물을 짜면서 실제로
    # 그렇게 통과시켰다. 선택자 형태를 그대로 본다.
    base_rule = re.search(r"^\s*:focus-visible\s*\{(?P<body>[^}]*)\}", css, re.M)
    if base_rule is None or "outline:" not in base_rule["body"]:
        failures.append("globals.css 에 `:focus-visible { outline: … }` 정본이 없다 — 포커스 표시가 어디에도 없다")
    # 자르는 구역 안에서 안쪽으로 그리는 규칙 — 선택자가 `overflow` 유틸리티를 짚는지 본다.
    inset_rule = re.search(r"^\s*:is\([^)]*overflow[^)]*\)\s+:focus-visible[^{]*\{(?P<body>[^}]*)\}", css, re.M)
    if inset_rule is None or "outline-offset:" not in inset_rule["body"]:
        failures.append(
            "globals.css 에 overflow 구역용 `outline-offset` 규칙이 없다 — 자르는 구역 안에서 포커스가 잘린다"
        )

    files, hits = scan()
    print(f"검사한 파일 {files}개 (하한 {MIN_FILES}) · 위반 {len(hits)}건")
    if files < MIN_FILES:
        failures.append(f"검사 대상이 {files}개입니다 (하한 {MIN_FILES}) — fail-closed")
    failures.extend(f"포커스 정본을 덮거나 대신 그린다 — {hit}" for hit in hits)

    for line in failures:
        print(f"::error::{line}")
    if failures:
        print("::error::포커스 표시는 globals.css 의 `:focus-visible` 한 자리가 그린다 (디자인 시스템 · #443 F36)")
        return 1
    print("판정: 포커스 표시를 그리는 자리가 globals.css 한 곳뿐이다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
