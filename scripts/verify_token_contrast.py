"""색 토큰 조합 전수의 WCAG 대비를 계산해 AA 미달을 보고한다 — fail-closed (stdlib 전용).

## 왜 있나

디자인 시스템(`.docs/4-아키텍처/디자인-시스템.md` §7.1)이 **손계산으로** 대비 미달을 짚어 뒀다.
손계산은 두 가지를 못 한다 — 조합을 빠뜨리지 않는 것과, 값이 바뀌었을 때 다시 도는 것이다.
토큰을 하나 손보면 그 토큰이 얹히는 **모든** 바탕과의 조합이 같이 움직이는데, 사람이 그
곱집합을 매번 다시 재지는 않는다. 그래서 조용히 미달인 조합이 남는다.

이 스크립트가 그 자리를 메운다: `globals.css` 의 색 토큰을 읽어 **글자색 × 바탕색 전수**의
대비를 계산하고, 검사한 조합 수를 출력한다.

## 무엇을 검사하나

1. **고정 기준 케이스** — WCAG 명세가 값을 못박은 두 점(검정↔흰색 = 21:1, 같은 색 = 1:1)과
   디자인 시스템 §7.1 이 손계산으로 적어 둔 세 조합. 계산식이 틀어지면 여기가 먼저 빨개진다.
   **문서의 손계산을 코드가 재현하는지**를 고정해 두는 자리이므로, 문서 값이 바뀌면 여기도
   같이 바꾼다. 케이스를 0건 모으면 실패한다.
2. **토큰 전수 조합** — `:root` 의 색 토큰을 분류해(글자색·바탕색·비텍스트) 글자색 × 바탕색을
   전부 계산한다.

## 분류를 강제하는 이유

토큰을 분류표에 없는 이름으로 새로 만들면 **실패한다.** 분류가 없으면 그 토큰은 곱집합에서
조용히 빠지고, 빠진 것은 아무도 못 본다 — 이 레포가 반복해서 데인 「대상이 0건이라 통과」의
축소판이다. 새 토큰을 들이면 분류도 같이 적어야 한다.

## 지금은 보고만 한다 (미달이 있어도 종료코드 0)

`--ink-faint` 의 값 방향은 **리드 판단 대기**이고(디자인 시스템 §7.1 의 ㉠/㉡), 현행
`--ink-muted` 도 이미 AA 에 못 미친다(아래 실측). 지금 미달을 실패로 만들면 **색 결정을 하기도
전에 CI 가 빨간불로 고정**되어, 빨간불이 일상이 되면 그물로서 죽는다.

그래서 이 단계에서는 **재고 보고**가 목적이다 — 무엇이 몇 대 몇인지 매 PR 출력에 남긴다.

**나중에 조이는 방법**: 색 값이 확정되고 미달 조합이 0건이 되면 아래 `FAIL_ON_AA_VIOLATION`
을 `True` 로 바꾼다. 그 한 줄이 이 스크립트를 보고자에서 게이트로 바꾼다. 미리 확인하려면
`--strict` 로 돌려 보면 된다(종료코드만 달라지고 출력은 같다).

실행: `python3 scripts/verify_token_contrast.py [--strict]` (cwd 무관).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GLOBALS_CSS = REPO_ROOT / "frontend" / "styles" / "globals.css"

# WCAG 2.1 1.4.3 / 1.4.6 임계.
AA_TEXT = 4.5
AA_LARGE_TEXT = 3.0
AAA_TEXT = 7.0

# 미달을 실패로 접을지. 머리 주석 「지금은 보고만 한다」 참조 — 색 확정 뒤 True 로 바꾼다.
FAIL_ON_AA_VIOLATION = False

# 토큰·조합이 통째로 사라지면(경로 변경·리네임) 조용히 초록이 되지 않게 하는 하한.
# 정당하게 줄였다면 하한도 함께 내린다 — 조용히 넘어가는 대신 시끄럽게 실패하는 것이 의도다.
MIN_COLOR_TOKENS = 8
MIN_COMBINATIONS = 10

FOREGROUND = "글자색"
SURFACE = "바탕색"
NON_TEXT = "비텍스트"

# 토큰 분류. **정확 이름**이 먼저, 없으면 **접두**로 판정한다. 둘 다 못 맞히면 실패한다
# (머리 주석 「분류를 강제하는 이유」).
EXACT_ROLES: dict[str, str] = {
    # 스크롤바 전용(파일 상단 `:root`). 글자가 얹히지 않으므로 텍스트 대비 대상이 아니다.
    "--primary": NON_TEXT,
    "--secondary": NON_TEXT,
    "--tertiary": NON_TEXT,
    "--slate-void": SURFACE,
    "--slate-panel": SURFACE,
    "--slate-line": NON_TEXT,
    "--hairline": NON_TEXT,
    "--line": NON_TEXT,
    "--line-strong": NON_TEXT,
    "--ink": FOREGROUND,
    "--danger": FOREGROUND,
    "--success": FOREGROUND,
}

# 접두 규칙 — 디자인 시스템 §1 의 이름 규약을 그대로 따른다.
PREFIX_ROLES: list[tuple[str, str]] = [
    ("--bg-", SURFACE),
    ("--btn-line", NON_TEXT),
    ("--btn-", SURFACE),
    ("--ink-", FOREGROUND),
    ("--signal-", FOREGROUND),
    ("--market-", FOREGROUND),
    ("--line-", NON_TEXT),
]

# WCAG 명세가 못박은 두 점 + 디자인 시스템 §7.1 의 손계산 세 조합.
# `expected` 는 소수 둘째 자리까지 일치해야 한다.
REFERENCE_CASES: list[tuple[str, str, str, float]] = [
    ("WCAG 최대 — 검정 on 흰색", "#000000", "#FFFFFF", 21.00),
    ("WCAG 최소 — 같은 색", "#16191C", "#16191C", 1.00),
    ("§7.1 다크 --ink-faint on --bg-panel", "#625E58", "#16191C", 2.74),
    ("§7.1 라이트 --ink-faint on --bg-panel", "#94908A", "#F4F5F6", 2.91),
    ("§7.1 다크 --ink-muted on --bg-raised", "#8B877F", "#1C2126", 4.53),
]

# `:root { ... }` 블록 안의 `--name: value;` 만 읽는다. 다른 선택자의 변수(`.auth-backdrop` 의
# `--auth-layers` 등)는 색 토큰이 아니라 합성 값이라 대상이 아니다.
ROOT_BLOCK = re.compile(r":root\s*\{(.*?)\}", re.S)
DECLARATION = re.compile(r"(--[A-Za-z0-9-]+)\s*:\s*([^;]+);")
CHANNELS = re.compile(r"^(\d{1,3})\s+(\d{1,3})\s+(\d{1,3})$")
HEX_VALUE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

Rgb = tuple[int, int, int]


def _fail(message: str) -> None:
    print(f"::error::{message}")


def relative_luminance(rgb: Rgb) -> float:
    """WCAG 2.1 relative luminance."""

    def channel(value: int) -> float:
        srgb = value / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(c) for c in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: Rgb, second: Rgb) -> float:
    lighter = max(relative_luminance(first), relative_luminance(second))
    darker = min(relative_luminance(first), relative_luminance(second))
    return (lighter + 0.05) / (darker + 0.05)


def parse_hex(value: str) -> Rgb | None:
    match = HEX_VALUE.match(value.strip())
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def parse_color(value: str) -> Rgb | None:
    """토큰 값을 RGB 로 푼다. `"R G B"` 채널 문자열이 정본이고 hex 도 읽는다."""
    value = value.strip()
    match = CHANNELS.match(value)
    if match:
        channels = tuple(int(g) for g in match.groups())
        if all(0 <= c <= 255 for c in channels):
            return channels  # type: ignore[return-value]
        return None
    return parse_hex(value)


def role_of(name: str) -> str | None:
    if name in EXACT_ROLES:
        return EXACT_ROLES[name]
    for prefix, role in PREFIX_ROLES:
        if name.startswith(prefix):
            return role
    return None


def verdict(ratio: float) -> str:
    if ratio >= AAA_TEXT:
        return "AAA"
    if ratio >= AA_TEXT:
        return "AA"
    if ratio >= AA_LARGE_TEXT:
        return "큰 글씨만(3:1)"
    return "미달"


def collect_tokens(css: str) -> dict[str, str]:
    """`:root` 블록 전부에서 커스텀 프로퍼티를 모은다 (뒤 블록이 앞을 덮는 CSS 규칙 그대로)."""
    tokens: dict[str, str] = {}
    for block in ROOT_BLOCK.findall(css):
        for name, value in DECLARATION.findall(block):
            tokens[name] = value.strip()
    return tokens


def run_reference_cases() -> bool:
    """계산식이 문서·명세의 값을 재현하는지. 케이스 0건이면 실패한다."""
    print("── 고정 기준 케이스 (WCAG 명세 2점 + 디자인 시스템 §7.1 손계산 3점) ──")
    if not REFERENCE_CASES:
        _fail("고정 기준 케이스를 0건 수집했습니다 — 계산식을 검증할 근거가 없습니다")
        return False

    ok = True
    for label, foreground, background, expected in REFERENCE_CASES:
        fg, bg = parse_hex(foreground), parse_hex(background)
        if fg is None or bg is None:
            _fail(
                f"기준 케이스의 색을 읽지 못했습니다: {label} ({foreground} / {background})"
            )
            ok = False
            continue
        actual = contrast_ratio(fg, bg)
        agrees = abs(actual - expected) < 0.005
        print(
            f"  {'OK ' if agrees else '불일치'} {label}: 계산 {actual:.2f}:1 / 기대 {expected:.2f}:1"
        )
        if not agrees:
            _fail(
                f"기준 케이스 불일치 — {label}: 계산 {actual:.4f}:1 이 기대 {expected:.2f}:1 과 다릅니다. "
                "계산식이 바뀌었거나 디자인 시스템 §7.1 의 값이 갱신된 것입니다."
            )
            ok = False
    print(f"  기준 케이스 {len(REFERENCE_CASES)}건 검사")
    print()
    return ok


def main(argv: list[str]) -> int:
    strict = "--strict" in argv[1:]

    if not GLOBALS_CSS.is_file():
        _fail(f"토큰 정의 파일이 없습니다: {GLOBALS_CSS.relative_to(REPO_ROOT)}")
        _fail(
            "경로가 바뀌었을 수 있습니다 — 이 스크립트의 GLOBALS_CSS 를 함께 고치세요."
        )
        return 1

    ok = run_reference_cases()

    tokens = collect_tokens(GLOBALS_CSS.read_text(encoding="utf-8"))
    if not tokens:
        _fail(
            f"{GLOBALS_CSS.relative_to(REPO_ROOT)} 의 :root 에서 커스텀 프로퍼티를 0건 읽었습니다 "
            "— 파서가 형식 변화를 못 따라간 것입니다"
        )
        return 1

    colors: dict[str, Rgb] = {}
    roles: dict[str, str] = {}
    unclassified: list[str] = []
    unreadable: list[str] = []

    for name, raw in sorted(tokens.items()):
        rgb = parse_color(raw)
        if rgb is None:
            # 색이 아닌 값(합성 그라디언트 등)은 대상이 아니다. `:root` 에 있는 색이 형식
            # 위반으로 안 읽히는 경우와 구분되지 않으므로 목록으로 남긴다.
            unreadable.append(f"{name}: {raw}")
            continue
        role = role_of(name)
        if role is None:
            unclassified.append(name)
            continue
        colors[name] = rgb
        roles[name] = role

    if unclassified:
        _fail(
            f"분류표에 없는 색 토큰 {len(unclassified)}건 — 곱집합에서 조용히 빠집니다:"
        )
        for name in unclassified:
            _fail(f"  · {name}")
        _fail(
            "이 스크립트의 EXACT_ROLES 또는 PREFIX_ROLES 에 역할"
            f"({FOREGROUND}·{SURFACE}·{NON_TEXT})을 적으세요."
        )
        ok = False

    foregrounds = sorted(n for n in colors if roles[n] == FOREGROUND)
    surfaces = sorted(n for n in colors if roles[n] == SURFACE)
    non_text = sorted(n for n in colors if roles[n] == NON_TEXT)

    print("── 토큰 재고 ──")
    print(f"  {FOREGROUND} {len(foregrounds)}건: {', '.join(foregrounds) or '없음'}")
    print(f"  {SURFACE} {len(surfaces)}건: {', '.join(surfaces) or '없음'}")
    print(
        f"  {NON_TEXT} {len(non_text)}건 (텍스트 대비 대상 아님): {', '.join(non_text) or '없음'}"
    )
    if unreadable:
        print(f"  색으로 안 읽힌 값 {len(unreadable)}건: {', '.join(unreadable)}")
    print()

    if len(colors) < MIN_COLOR_TOKENS:
        _fail(
            f"색 토큰을 {len(colors)}건 수집했습니다 (하한 {MIN_COLOR_TOKENS}) — fail-closed 종료"
        )
        _fail(
            "토큰이 이동·삭제됐거나 값 형식이 바뀌었을 수 있습니다. "
            "정당한 삭제라면 MIN_COLOR_TOKENS 도 함께 내리세요."
        )
        return 1

    combinations = [(f, s) for f in foregrounds for s in surfaces]
    if len(combinations) < MIN_COMBINATIONS:
        _fail(
            f"검사할 조합이 {len(combinations)}건입니다 (하한 {MIN_COMBINATIONS}) — fail-closed 종료"
        )
        _fail(
            f"{FOREGROUND} {len(foregrounds)}건 × {SURFACE} {len(surfaces)}건. "
            "분류가 한쪽으로 쏠렸는지 확인하세요."
        )
        return 1

    print(
        f"── 조합 전수 대비 ({FOREGROUND} {len(foregrounds)} × {SURFACE} {len(surfaces)}) ──"
    )
    violations: list[tuple[str, str, float]] = []
    for fg_name, bg_name in combinations:
        ratio = contrast_ratio(colors[fg_name], colors[bg_name])
        label = verdict(ratio)
        print(f"  {ratio:6.2f}:1  {label:<14} {fg_name} on {bg_name}")
        if ratio < AA_TEXT:
            violations.append((fg_name, bg_name, ratio))
    print()

    print(
        f"검사한 조합 {len(combinations)}건 · AA({AA_TEXT}:1) 미달 {len(violations)}건"
    )

    if violations:
        print(f"::warning::AA({AA_TEXT}:1) 미달 조합 {len(violations)}건:")
        for fg_name, bg_name, ratio in violations:
            large_ok = (
                "큰 글씨(3:1)는 통과"
                if ratio >= AA_LARGE_TEXT
                else "큰 글씨(3:1)도 미달"
            )
            print(f"::warning::  {fg_name} on {bg_name} — {ratio:.2f}:1 ({large_ok})")

    if violations and (strict or FAIL_ON_AA_VIOLATION):
        _fail(f"AA 미달 조합 {len(violations)}건 — 토큰 값을 고치세요")
        return 1

    if violations:
        print(
            "판정: 보고만 하고 통과합니다 — 색 값이 리드 판단 대기라 지금은 게이트가 아닙니다. "
            "조이는 방법은 이 파일 머리의 「나중에 조이는 방법」 참조."
        )
    else:
        print("판정: AA 미달 조합 0건")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
