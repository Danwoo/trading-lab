"""아이콘 조작부가 공용 표적 클래스를 쓰는지 검사한다 — fail-closed (stdlib 전용).

## 왜 있나

`frontend/tests/a11y/touchTargets.test.tsx` 는 표적을 **진짜 픽셀로** 잰다(헤드리스 크롬).
그 그물이 재는 대상은 그 파일이 손으로 고른 픽스처뿐이다 — 새 아이콘 버튼을 만들고 픽스처를
안 더하면 그 자리는 **조용히 초록**이다. 실측으로 그 구멍이 열렸다: #289 최초 구현이
아이콘 조작부 11 자리를 고쳤는데, 같은 모양의 `×` 두 자리(`FileUploader` 파일 목록 ·
`SelectMenu` 다중선택 태그)가 목록에서 빠졌고 픽스처에도 없어 그물이 못 잡았다.

이 스크립트는 그 축을 메운다. **크기를 재지 않는다** — 정적으로는 못 잰다(`p-1` 이 24 를
만드는지 22 를 만드는지는 안쪽 아이콘 크기에 달렸다). 대신 **「아이콘 조작부인데 공용 클래스
`ICON_HIT_AREA` 를 안 쓰는 자리」를 센다.** 둘은 다른 문제다:

- 크기가 24 인가 → 크롬이 잰다 (`touchTargets.test.tsx`).
- 크기를 보증하는 클래스를 붙였나 → 여기서 센다.

## 무엇을 아이콘 조작부로 보나

`<button>` · `<a>` · `<summary>` · `DialogPrimitive.Close` 중, 자식이

1. **아이콘 하나뿐**(`<Icon …>` · `<svg>` · 이름이 `Icon` 으로 끝나는 컴포넌트)이고 글자가 없거나,
2. **기호 한두 글자**(`×` · `‹` · `⋮` — 영문·숫자·한글이 아닌 문자 3자 이하)

인 것. 라벨이 글자인 버튼은 글자가 상자를 키우므로 이 클래스가 아니다.

**자식에 중괄호 식이 섞이면 후보에서 뺀다** — `{text}` 가 무엇을 그릴지 정적으로는 모른다
(`Button.tsx` 의 `{icon && <Icon/>}{text}` 는 아이콘 전용 버튼이 아니다). 그 자리의 크기는
크롬이 재는 그물의 몫이다. 여기서 세는 것은 「소스만 보고 아이콘 전용이라고 단정할 수 있는
자리」이고, #289 가 놓친 두 자리가 정확히 그 모양이었다(자식이 `×` 한 글자).

`className` 이 상수를 가리키면(`className={NAV_BUTTON_CLASS}`) 그 상수 정의까지 따라간다 —
**다른 파일에 있어도** 따라가고, 상수가 상수를 물면 사슬 끝까지 간다. 안 그러면 공용 클래스로
묶은 자리가 통째로 위반으로 잡힌다.

## allowlist — 이미 24 이상인 자리

`ICON_HIT_AREA` 없이도 24 를 넘는 자리가 있다(자기 크기를 직접 정하는 `h-8 w-8`,
16px 아이콘 + `p-1` 인 다이얼로그 닫기). 그 자리는 **이유와 함께 등록**한다. 등록은 늘지 못한다:

- **낡은 항목은 실패한다** — 등록한 자리가 사라졌거나 이제 `ICON_HIT_AREA` 를 쓰면 실패한다.
  낡은 예외가 남아 새 위반을 덮는 것이 이 그물의 유일한 우회로다.
- **늘어나면 실패한다** — `ALLOWLIST_CAP` 이 상한이다. 새 예외를 등록하려면 상한도 같이
  올려야 하고, 그 한 줄이 리뷰에 보인다.
- **후보가 0건이면 실패한다** — 경로가 바뀌어 아무것도 안 훑고도 「위반 0건」으로 초록이
  되는 것을 막는다.

실행: `python3 scripts/verify_icon_hit_area.py` (cwd 무관).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
SCAN_ROOTS = ("components", "app")
# 자식이 아이콘·기호뿐일 수 있는 조작부. 이름이 곧 표적이다.
CONTROL_TAGS = ("button", "a", "summary", "DialogPrimitive.Close")
# 후보가 이보다 적으면 훑은 자리가 잘못된 것이다 — 「위반 0건」과 구분한다.
MIN_CANDIDATES = 15

HIT_AREA_CLASS = "ICON_HIT_AREA"
# `display` 를 구간별로 갈라야 하는 자리가 쓰는 변형 — 크기·정렬은 같다.
HIT_AREA_BOX_CLASS = "ICON_HIT_AREA_BOX"

# 「자리 → 왜 ICON_HIT_AREA 없이도 24 이상인가」. 키는 `파일::식별자`(aria-label 또는 기호).
ALLOWLIST: dict[str, str] = {
    "components/shared/ui/primitives/dialog.tsx::닫기": "p-1(4px) + 16px 아이콘 = 24×24",
    "components/features/ResearchChat/ConversationPanel.tsx::생성 중지": "h-8 w-8 — 자기 크기를 직접 정한다",
    "components/features/ResearchChat/ConversationPanel.tsx::전송": "h-8 w-8 — 자기 크기를 직접 정한다",
}
ALLOWLIST_CAP = 3


def strip_comments(src: str) -> str:
    """문자열을 보호하면서 `//` · `/* */` · `{/* */}` 를 걷는다."""
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch in "\"'`":
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                if src[i] == "\\":
                    out.append(src[i : i + 2])
                    i += 2
                    continue
                out.append(src[i])
                if src[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if src.startswith("{/*", i):
            end = src.find("*/}", i)
            i = n if end < 0 else end + 3
            continue
        if src.startswith("//", i):
            while i < n and src[i] != "\n":
                i += 1
            continue
        if src.startswith("/*", i):
            end = src.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def find_tag_end(src: str, start: int) -> tuple[int, bool]:
    """여는 태그의 `>` 위치와 self-closing 여부. 중괄호·문자열 안의 `>` 는 건너뛴다."""
    i, n, depth = start, len(src), 0
    while i < n:
        ch = src[i]
        if ch in "\"'`":
            quote = ch
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == ">" and depth == 0:
            return i, src[i - 1] == "/"
        i += 1
    return -1, False


def find_close(src: str, tag: str, after: int) -> int:
    """같은 태그의 중첩을 세어 짝이 맞는 닫는 태그를 찾는다."""
    open_re = re.compile("<" + re.escape(tag) + r"(?=[\s/>])")
    close = f"</{tag}>"
    i, depth = after, 1
    while True:
        pos = src.find(close, i)
        if pos < 0:
            return -1
        nested = open_re.search(src, i, pos)
        while nested:
            depth += 1
            nested = open_re.search(src, nested.end(), pos)
        depth -= 1
        if depth == 0:
            return pos
        i = pos + len(close)


def literal_text(inner: str) -> str:
    """자식에서 **소스에 그대로 적힌 글자**만 남긴다 (태그·중괄호 식은 뺀다)."""
    without_tags = re.sub(r"<[^>]*>", "", inner)
    out: list[str] = []
    depth = 0
    for ch in without_tags:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out).strip()


def identifier(open_tag: str, text: str) -> str:
    label = re.search(r'aria-label=(?:"([^"]*)"|\{`([^`]*)`\})', open_tag)
    if label:
        return (label.group(1) or label.group(2)).strip()
    return text or "icon"


def covering_names(sources: list[str]) -> set[str]:
    """표적 클래스를 실어 나르는 이름들 — 상수를 거쳐 전달되는 사슬을 끝까지 따라간다.

    `FIELD_ICON_BUTTON_CLASS = `${ICON_HIT_AREA} …`` 처럼 **다른 파일의 상수**로 묶인 자리가
    있어서 파일 안만 보면 그 자리가 통째로 위반으로 잡힌다.
    """
    names = {HIT_AREA_CLASS, HIT_AREA_BOX_CLASS}
    definitions: list[tuple[str, str]] = []
    for src in sources:
        for match in re.finditer(r"const\s+([A-Za-z_$][\w$]*)\s*=", src):
            end = src.find(";", match.end())
            definitions.append((match.group(1), src[match.end() : end if end > 0 else len(src)]))

    grew = True
    while grew:
        grew = False
        for name, body in definitions:
            if name in names:
                continue
            if any(re.search(rf"\b{re.escape(known)}\b", body) for known in names):
                names.add(name)
                grew = True
    return names


def scan_file(path: Path, covering: set[str]) -> list[tuple[str, bool]]:
    """(식별자, 표적 클래스가 걸렸는가) 목록."""
    src = strip_comments(path.read_text(encoding="utf-8"))
    found: list[tuple[str, bool]] = []
    for tag in CONTROL_TAGS:
        for match in re.finditer("<" + re.escape(tag) + r"(?=[\s/>])", src):
            end, self_closing = find_tag_end(src, match.end())
            if end < 0 or self_closing:
                continue
            close = find_close(src, tag, end + 1)
            if close < 0:
                continue
            open_tag = src[match.start() : end + 1]
            inner = src[end + 1 : close]
            # 자식에 중괄호 식이 남아 있으면 무엇이 그려질지 모른다 — 후보에서 뺀다.
            if "{" in re.sub(r"<[^>]*>", "", inner):
                continue
            text = literal_text(inner)
            has_icon = bool(re.search(r"<(svg|Icon|[A-Z][A-Za-z]*Icon)(?=[\s/>])", inner))
            symbol_only = 0 < len(text) <= 3 and not re.search(r"[0-9A-Za-z가-힣]", text)
            if not ((has_icon and text == "") or symbol_only):
                continue
            covered = any(re.search(rf"\b{re.escape(name)}\b", open_tag) for name in covering)
            found.append((identifier(open_tag, text), covered))
    return found


def _fail(message: str) -> None:
    print(f"::error::{message}" if "CI" in os.environ else f"[실패] {message}")


def main() -> int:
    files = sorted(p for root in SCAN_ROOTS for p in (FRONTEND / root).rglob("*.tsx"))
    if not files:
        _fail(f"훑을 `.tsx` 가 없습니다 — 경로가 바뀌었습니까? ({', '.join(SCAN_ROOTS)})")
        return 1

    # 클래스 상수는 `.ts` 에도 산다(`hitArea.ts`) — 이름 수집은 확장자를 넓혀서 한다.
    sources = [
        strip_comments(p.read_text(encoding="utf-8"))
        for root in SCAN_ROOTS
        for suffix in ("*.ts", "*.tsx")
        for p in (FRONTEND / root).rglob(suffix)
    ]
    covering = covering_names(sources)

    covered: list[str] = []
    uncovered: list[str] = []
    for path in files:
        rel = path.relative_to(FRONTEND).as_posix()
        for ident, has_hit in scan_file(path, covering):
            key = f"{rel}::{ident}"
            (covered if has_hit else uncovered).append(key)

    total = len(covered) + len(uncovered)
    print(
        f"`.tsx` {len(files)}건 검사 (frontend/{', frontend/'.join(SCAN_ROOTS)}) · "
        f"아이콘 조작부 후보 {total}건 · {HIT_AREA_CLASS} 적용 {len(covered)}건 · "
        f"allowlist {len(ALLOWLIST)}건 (상한 {ALLOWLIST_CAP})"
    )
    print()

    ok = True

    if total < MIN_CANDIDATES:
        _fail(
            f"아이콘 조작부 후보가 {total}건뿐입니다 (하한 {MIN_CANDIDATES}) — "
            "검출이 죽었을 수 있습니다. 「위반 0건」과 「아무것도 안 봤음」은 다릅니다."
        )
        ok = False

    if len(ALLOWLIST) > ALLOWLIST_CAP:
        _fail(
            f"allowlist 가 {len(ALLOWLIST)}건으로 상한 {ALLOWLIST_CAP}건을 넘었습니다 — "
            "등록을 늘리려면 상한도 같이 올려야 하고, 그 판단은 사람이 합니다."
        )
        ok = False

    stale = sorted(set(ALLOWLIST) - set(uncovered))
    if stale:
        _fail(f"allowlist 에 적힌 자리가 사라졌거나 이제 {HIT_AREA_CLASS} 를 씁니다 {len(stale)}건 — 항목을 지우세요:")
        for key in stale:
            _fail(f"  · {key}")
        ok = False

    unexpected = sorted(set(uncovered) - set(ALLOWLIST))
    if unexpected:
        _fail(f"아이콘 조작부인데 {HIT_AREA_CLASS} 를 안 씁니다 {len(unexpected)}건:")
        for key in unexpected:
            _fail(f"  · {key}")
        _fail(
            f"`components/shared/ui/primitives/hitArea.ts` 의 {HIT_AREA_CLASS} 를 붙이고, "
            "그 자리를 `frontend/tests/a11y/touchTargets.test.tsx` 픽스처에도 더하세요 "
            "(크기를 실제로 재는 것은 그 그물입니다). 이미 24 이상인 자리면 "
            "이유와 함께 이 스크립트의 ALLOWLIST 에 등록하세요."
        )
        ok = False

    if ok:
        print(f"판정: {HIT_AREA_CLASS} 를 안 쓰는 아이콘 조작부 0건 (allowlist {len(ALLOWLIST)}건 제외)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
