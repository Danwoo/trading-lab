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
   `--ink-faint` 결정(#73 S1 ㉡)의 전후 값. 계산식이 틀어지면 여기가 먼저 빨개진다.
   케이스를 0건 모으면 실패한다.
2. **네 벌 전수 조합** — 화면이 실제로 띄우는 조합은 모드(다크·라이트) × 등락 프리셋(kr·us)
   네 벌이고, 각 벌은 `:root` 위에 자기 선택자를 겹쳐 만들어진다. 네 벌을 각각 따로 조립해
   벌마다 글자색 × 바탕색을 전부 계산한다. **한 벌이라도 조립에 실패하면 종료한다** —
   라이트만 미달인 상태가 다크만 보고 통과하던 구멍이 이 스크립트의 첫 판(#145)에 있었다.

## 바탕을 둘로 가르는 이유

바탕은 **본문 바탕**(`--bg-*`·레거시 `--slate-*`)과 **컨트롤 바탕**(`--btn-*` 계조 서피스)으로
갈린다. 본문 바탕에는 어떤 글자색이든 얹힐 수 있지만, 컨트롤 바탕에 얹히는 글자는 **버튼
라벨뿐**이다 — 라벨·표 헤더(`--ink-faint`)와 데이터색(등락·상태)은 버튼 위에 오지 않는다
(디자인 시스템 §1.4·§2.3). 그래서 곱집합을 둘로 나눠 각각 전수로 돌리고, **양쪽 건수를 모두
출력한다.** 나누지 않고 한 판으로 돌리면, 일어나지 않는 조합(버튼 위의 오류색) 때문에 잉크와
데이터색을 실제 필요보다 밝혀야 하고 그것은 화면을 위한 값이 아니라 스크립트를 위한 값이다.

## 분류를 강제하는 이유

토큰을 분류표에 없는 이름으로 새로 만들면 **실패한다.** 분류가 없으면 그 토큰은 곱집합에서
조용히 빠지고, 빠진 것은 아무도 못 본다 — 이 레포가 반복해서 데인 「대상이 0건이라 통과」의
축소판이다. 새 토큰을 들이면 분류도 같이 적어야 한다. 색이 아닌 토큰(치수·굵기·자간)도
접두로 선언해야 하며, 선언 없이 채널 형식이 아닌 값은 **오식으로 보고 실패한다.**

실행: `python3 scripts/verify_token_contrast.py [--report-only]` (cwd 무관).
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

# 색 값이 확정된 뒤(#73 S1) 게이트로 조였다. `--report-only` 로 종료코드만 눌러 볼 수 있다.
FAIL_ON_AA_VIOLATION = True

# 토큰·조합이 통째로 사라지면(경로 변경·리네임) 조용히 초록이 되지 않게 하는 하한.
# 정당하게 줄였다면 하한도 함께 내린다 — 조용히 넘어가는 대신 시끄럽게 실패하는 것이 의도다.
MIN_COLOR_TOKENS = 20
MIN_COMBINATIONS_PER_SET = 20

INK_ANY = "전역 잉크"
INK_CONTENT = "본문 잉크"
SURFACE = "본문 바탕"
CONTROL_SURFACE = "컨트롤 바탕"
NON_TEXT = "비텍스트"

INK_ROLES = (INK_ANY, INK_CONTENT)

# 토큰 분류. **정확 이름**이 먼저, 없으면 **접두**로 판정한다. 둘 다 못 맞히면 실패한다
# (머리 주석 「분류를 강제하는 이유」).
EXACT_ROLES: dict[str, str] = {
    # 스크롤바 전용(파일 상단 `:root`). 글자가 얹히지 않으므로 텍스트 대비 대상이 아니다.
    "--primary": NON_TEXT,
    "--secondary": NON_TEXT,
    "--tertiary": NON_TEXT,
    # 레거시 토큰(#242 O3) — #73 S5 가 Tailwind 팔레트에서 내렸고, 값은 `.auth-backdrop`
    # (인증 배경)이 아직 소비해 남아 있다. 그 배경 위에 글자가 얹히므로 계속 검사한다.
    "--slate-void": SURFACE,
    "--slate-panel": SURFACE,
    "--slate-line": NON_TEXT,
    "--hairline": NON_TEXT,
    "--line": NON_TEXT,
    "--line-strong": NON_TEXT,
    # 버튼 계조 서피스의 두 정지점. 그 위에 얹히는 글자는 버튼 라벨뿐이다.
    "--btn-from": CONTROL_SURFACE,
    "--btn-to": CONTROL_SURFACE,
    "--btn-line": NON_TEXT,
    # 버튼 윗변 1px 하이라이트 — 선이지 바탕이 아니다.
    "--btn-inset": NON_TEXT,
    "--ink": INK_ANY,
    "--ink-strong": INK_ANY,
    # 라벨·표 헤더가 여기로 강등됐다(리드 결정 ㉡). 버튼 라벨은 --ink 계열이 받는다(§1.4).
    "--ink-muted": INK_CONTENT,
    # **비텍스트 전용** — 선·아이콘에만 쓴다. 글자에 쓰지 않기로 한 값이라 텍스트 대비
    # 곱집합에서 뺀다. 이 분류가 ㉡ 결정을 코드로 강제하는 자리다.
    "--ink-faint": NON_TEXT,
    # 상태색은 메시지·배지·테두리에만 온다 — 버튼 채움이 되지 않는다(§2.3).
    "--danger": INK_CONTENT,
    "--success": INK_CONTENT,
}

# 접두 규칙 — 디자인 시스템 §1 의 이름 규약을 그대로 따른다.
PREFIX_ROLES: list[tuple[str, str]] = [
    ("--bg-", SURFACE),
    ("--ink-", INK_ANY),
    ("--signal-", INK_ANY),
    # 등락색은 숫자·표에만 온다.
    ("--market-", INK_CONTENT),
    ("--line-", NON_TEXT),
]

# 색이 아닌 토큰(치수·굵기·자간·그림자). 채널 형식이 아니어도 오식이 아니라는 선언이며,
# 여기 없는 이름이 채널로 안 읽히면 실패한다.
NON_COLOR_PREFIXES = (
    "--text-",
    "--weight-",
    "--tracking-",
    "--leading-",
    "--space-",
    "--size-",
    "--shell-",
    "--radius-",
    "--focus-",
    "--btn-inset-alpha",
    "--e1",
)

# 레거시 토큰(#242 O3). **다크 한 벌만 있다** — 라이트 값이 없고, 이것을 쓰는 화면
# (`.auth-backdrop` 인증 배경)은 모드와 무관하게 어두운 팔레트로 그려진다. 그래서 라이트 벌의
# 곱집합에서는 뺀다. 빼는 것을 조용히 하지 않으려고 벌마다 제외 건수를 출력한다.
# `--ink-primary` 는 소비자가 사라져 #73 S5 가 지웠다 — 남은 셋은 그 배경이 아직 쓴다.
LEGACY_TOKENS = frozenset(
    {"--slate-void", "--slate-panel", "--slate-line", "--signal-warn"}
)

# 화면이 실제로 띄우는 네 벌. 각 벌은 `:root` 위에 뒤 선택자를 순서대로 겹쳐 만든다
# (CSS 캐스케이드 그대로 — globals.css 의 선택자 순서와 같아야 한다).
# 셋째 항목은 레거시 토큰이 그 벌에 실제로 뜨는지.
TOKEN_SETS: list[tuple[str, tuple[str, ...], bool]] = [
    ("다크 · 한국식", (":root",), True),
    ("다크 · 미국식", (":root", '[data-market-preset="us"]'), True),
    ("라이트 · 한국식", (":root", '[data-theme="light"]'), False),
    (
        "라이트 · 미국식",
        (
            ":root",
            '[data-theme="light"]',
            '[data-theme="light"][data-market-preset="us"]',
        ),
        False,
    ),
]

# WCAG 명세가 못박은 두 점 + `--ink-faint` 결정(㉡)의 전후 값.
# 앞 세 줄은 디자인 시스템 §7.1 이 손계산으로 적은 값이고(그중 `--ink-faint` 두 줄이 ㉡ 으로
# 텍스트에서 내려온 값이다), 뒤 두 줄은 라벨·표 헤더를 새로 받는 `--ink-muted` 자리다.
# **문서 값이 바뀌면 여기도 같이 바꾼다.** `expected` 는 소수 둘째 자리까지 일치해야 한다.
REFERENCE_CASES: list[tuple[str, str, str, float]] = [
    ("WCAG 최대 — 검정 on 흰색", "#000000", "#FFFFFF", 21.00),
    ("WCAG 최소 — 같은 색", "#16191C", "#16191C", 1.00),
    ("§7.1 옛 다크 --ink-faint on --bg-panel", "#625E58", "#16191C", 2.74),
    ("§7.1 옛 라이트 --ink-faint on --bg-panel", "#94908A", "#F4F5F6", 2.91),
    ("§7.1 다크 --ink-muted on --bg-raised", "#8B877F", "#1C2126", 4.53),
    ("㉡ 라벨 자리 다크 --ink-muted on --bg-panel", "#8B877F", "#16191C", 4.93),
    ("㉡ 라벨 자리 라이트 --ink-muted on --bg-panel", "#67635D", "#F4F5F6", 5.47),
]

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


def is_non_color(name: str) -> bool:
    return name.startswith(NON_COLOR_PREFIXES)


def verdict(ratio: float) -> str:
    if ratio >= AAA_TEXT:
        return "AAA"
    if ratio >= AA_TEXT:
        return "AA"
    if ratio >= AA_LARGE_TEXT:
        return "큰 글씨만(3:1)"
    return "미달"


# `선택자목록 { 선언 }` 한 덩어리. 중첩 규칙(@media 등)은 이 파일에 없으므로 평면 파싱으로 충분하다.
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)


def block_bodies(css: str, selector: str) -> list[str]:
    """`selector` 가 **선택자 목록의 한 항목**인 규칙들의 본문 (등장 순서대로).

    쉼표로 나눠 정확히 대조하는 이유가 둘 있다.
    - 부분 문자열로 찾으면 `[data-market-preset="us"]` 가
      `[data-theme="light"][data-market-preset="us"]` 안에서도 걸려 다크 벌이 라이트 값을
      집어온다. 실제로 그렇게 잘못 조립됐고 미달 10건으로 드러났다.
    - `:root, [data-theme="dark"], .auth-backdrop` 처럼 한 규칙이 여러 선택자를 가질 때
      `:root` 만 보고도 그 본문을 찾을 수 있어야 한다.
    """
    bodies: list[str] = []
    for prelude, body in RULE.findall(css):
        # 주석은 선택자 목록 앞뒤에만 오므로 통째로 걷어낸다.
        cleaned = re.sub(r"/\*.*?\*/", " ", prelude, flags=re.S)
        # 앞선 문장(`@tailwind utilities;` 등)이 붙어 오므로 마지막 `;` 뒤만 남긴다.
        # 선택자에는 `;` 가 올 수 없어 안전하다.
        cleaned = cleaned.rsplit(";", 1)[-1]
        parts = [part.strip() for part in cleaned.split(",")]
        if selector in parts:
            bodies.append(body)
    return bodies


def declarations_of(css: str, selector: str) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for body in block_bodies(css, selector):
        for name, value in DECLARATION.findall(body):
            tokens[name] = value.strip()
    return tokens


def run_reference_cases() -> bool:
    """계산식이 문서·결정의 값을 재현하는지. 케이스 0건이면 실패한다."""
    print("── 고정 기준 케이스 (WCAG 명세 2점 + `--ink-faint` 결정 전후 5점) ──")
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


def classify(tokens: dict[str, str]) -> tuple[dict[str, Rgb], dict[str, str], bool]:
    """토큰을 색·역할로 가른다. 분류 누락·채널 오식은 실패로 돌려준다."""
    colors: dict[str, Rgb] = {}
    roles: dict[str, str] = {}
    unclassified: list[str] = []
    malformed: list[str] = []
    ok = True

    for name, raw in sorted(tokens.items()):
        if is_non_color(name):
            continue
        rgb = parse_color(raw)
        if rgb is None:
            malformed.append(f"{name}: {raw}")
            continue
        role = role_of(name)
        if role is None:
            unclassified.append(name)
            continue
        colors[name] = rgb
        roles[name] = role

    if malformed:
        _fail(f'채널 형식("R G B")으로 안 읽히는 색 토큰 {len(malformed)}건:')
        for entry in malformed:
            _fail(f"  · {entry}")
        _fail(
            "색이 아닌 토큰이라면 이 스크립트의 NON_COLOR_PREFIXES 에 접두를 적으세요. "
            "색이라면 값을 채널 문자열로 고치세요 — hex 는 Tailwind 의 opacity modifier 를 깹니다(#313)."
        )
        ok = False

    if unclassified:
        _fail(
            f"분류표에 없는 색 토큰 {len(unclassified)}건 — 곱집합에서 조용히 빠집니다:"
        )
        for name in unclassified:
            _fail(f"  · {name}")
        _fail(
            "이 스크립트의 EXACT_ROLES 또는 PREFIX_ROLES 에 역할"
            f"({INK_ANY}·{INK_CONTENT}·{SURFACE}·{CONTROL_SURFACE}·{NON_TEXT})을 적으세요."
        )
        ok = False

    return colors, roles, ok


def check_set(
    label: str, tokens: dict[str, str], include_legacy: bool
) -> tuple[int, list[tuple[str, str, float]], bool]:
    """한 벌의 곱집합 두 판을 돌린다. (검사 조합 수, 미달 목록, 성공 여부)"""
    colors, roles, ok = classify(tokens)

    if not include_legacy:
        dropped = sorted(n for n in colors if n in LEGACY_TOKENS)
        for name in dropped:
            del colors[name]
        print(
            f"── {label} · 레거시 토큰 {len(dropped)}건 제외 "
            f"(다크 전용, #73 S5 삭제 예정): {', '.join(dropped) or '없음'}"
        )

    names_by_role = {
        role: sorted(n for n in colors if roles[n] == role)
        for role in (INK_ANY, INK_CONTENT, SURFACE, CONTROL_SURFACE, NON_TEXT)
    }

    print(f"── {label} · 토큰 재고 ──")
    for role in (INK_ANY, INK_CONTENT, SURFACE, CONTROL_SURFACE, NON_TEXT):
        names = names_by_role[role]
        suffix = " (텍스트 대비 대상 아님)" if role == NON_TEXT else ""
        print(f"  {role} {len(names)}건{suffix}: {', '.join(names) or '없음'}")

    if len(colors) < MIN_COLOR_TOKENS:
        _fail(
            f"{label}: 색 토큰을 {len(colors)}건 수집했습니다 (하한 {MIN_COLOR_TOKENS}) — fail-closed 종료"
        )
        _fail(
            "토큰이 이동·삭제됐거나 값 형식이 바뀌었을 수 있습니다. "
            "정당한 삭제라면 MIN_COLOR_TOKENS 도 함께 내리세요."
        )
        return 0, [], False

    combinations: list[tuple[str, str]] = [
        (fg, bg)
        for role in INK_ROLES
        for fg in names_by_role[role]
        for bg in names_by_role[SURFACE]
    ]
    combinations += [
        (fg, bg)
        for fg in names_by_role[INK_ANY]
        for bg in names_by_role[CONTROL_SURFACE]
    ]

    if len(combinations) < MIN_COMBINATIONS_PER_SET:
        _fail(
            f"{label}: 검사할 조합이 {len(combinations)}건입니다 "
            f"(하한 {MIN_COMBINATIONS_PER_SET}) — fail-closed 종료"
        )
        _fail("분류가 한쪽으로 쏠렸는지 확인하세요.")
        return len(combinations), [], False

    print(
        f"── {label} · 조합 전수 "
        f"(({INK_ANY} {len(names_by_role[INK_ANY])} + {INK_CONTENT} {len(names_by_role[INK_CONTENT])})"
        f" × {SURFACE} {len(names_by_role[SURFACE])}"
        f" + {INK_ANY} × {CONTROL_SURFACE} {len(names_by_role[CONTROL_SURFACE])}"
        f" = {len(combinations)}) ──"
    )
    violations: list[tuple[str, str, float]] = []
    for fg_name, bg_name in combinations:
        ratio = contrast_ratio(colors[fg_name], colors[bg_name])
        print(f"  {ratio:6.2f}:1  {verdict(ratio):<14} {fg_name} on {bg_name}")
        if ratio < AA_TEXT:
            violations.append((fg_name, bg_name, ratio))
    print(f"  {label}: 조합 {len(combinations)}건 · AA 미달 {len(violations)}건")
    print()
    return len(combinations), violations, ok


def print_ink_ladder(sets: dict[str, dict[str, str]]) -> None:
    """텍스트 잉크 3단이 서로 얼마나 갈리는지 — 위계가 색만으로 서는지 수치로 남긴다.

    `--ink-faint` 는 여기 없다. ㉡ 이 그 값을 비텍스트로 내렸고, 텍스트 위계는 3단이다.
    """
    print("── 텍스트 잉크 사다리 인접 단 대비 (색만으로 위계가 서는지) ──")
    ladder = ["--ink-strong", "--ink", "--ink-muted"]
    for label in ("다크 · 한국식", "라이트 · 한국식"):
        tokens = sets[label]
        values = [parse_color(tokens[name]) for name in ladder]
        if any(v is None for v in values):
            _fail(f"{label}: 잉크 4단을 다 읽지 못했습니다 — {ladder}")
            continue
        pairs = [
            f"{a} ↔ {b}: {contrast_ratio(x, y):.2f}:1"  # type: ignore[arg-type]
            for (a, x), (b, y) in zip(
                list(zip(ladder, values))[:-1], list(zip(ladder, values))[1:]
            )
        ]
        print(f"  {label}: " + " · ".join(pairs))
    print(
        "  라벨·표 헤더는 --ink-muted 가 받는다(리드 결정 ㉡). --ink-faint 는 비텍스트 전용이라 "
        "이 사다리에 없다."
    )
    print()


def main(argv: list[str]) -> int:
    report_only = "--report-only" in argv[1:]

    if not GLOBALS_CSS.is_file():
        _fail(f"토큰 정의 파일이 없습니다: {GLOBALS_CSS.relative_to(REPO_ROOT)}")
        _fail(
            "경로가 바뀌었을 수 있습니다 — 이 스크립트의 GLOBALS_CSS 를 함께 고치세요."
        )
        return 1

    css = GLOBALS_CSS.read_text(encoding="utf-8")
    ok = run_reference_cases()

    # 네 벌을 각각 조립한다. 겹칠 선택자가 하나라도 비면 그 벌은 존재하지 않는 것이므로 실패한다.
    sets: dict[str, dict[str, str]] = {}
    include_legacy_by_label: dict[str, bool] = {}
    for label, selectors, include_legacy in TOKEN_SETS:
        include_legacy_by_label[label] = include_legacy
        merged: dict[str, str] = {}
        for selector in selectors:
            declarations = declarations_of(css, selector)
            if not declarations:
                _fail(
                    f"{label}: 선택자 `{selector}` 의 선언을 0건 읽었습니다 — "
                    "선택자가 사라졌거나 파서가 형식 변화를 못 따라간 것입니다"
                )
                return 1
            merged.update(declarations)
        sets[label] = merged

    # 네 벌이 같은 토큰 이름을 갖는지 — 한 모드에만 추가된 토큰은 다른 모드에서 조용히 빈다.
    base_names = set(sets[TOKEN_SETS[0][0]])
    for label, tokens in sets.items():
        missing = base_names - set(tokens)
        if missing:
            _fail(f"{label}: 다크 기본 벌에 있는 토큰이 없습니다 — {sorted(missing)}")
            ok = False

    print(f"── 벌 {len(sets)}개 조립 (모드 2 × 등락 프리셋 2) ──")
    for label, tokens in sets.items():
        print(f"  {label}: 커스텀 프로퍼티 {len(tokens)}건")
    print()

    print_ink_ladder(sets)

    total_combinations = 0
    all_violations: list[tuple[str, str, str, float]] = []
    for label, tokens in sets.items():
        count, violations, set_ok = check_set(
            label, tokens, include_legacy_by_label[label]
        )
        total_combinations += count
        all_violations += [(label, fg, bg, r) for fg, bg, r in violations]
        ok = ok and set_ok

    print(
        f"검사한 조합 {total_combinations}건 (벌 {len(sets)}개 합) · "
        f"AA({AA_TEXT}:1) 미달 {len(all_violations)}건"
    )

    if all_violations:
        print(f"::warning::AA({AA_TEXT}:1) 미달 조합 {len(all_violations)}건:")
        for label, fg_name, bg_name, ratio in all_violations:
            large_ok = (
                "큰 글씨(3:1)는 통과"
                if ratio >= AA_LARGE_TEXT
                else "큰 글씨(3:1)도 미달"
            )
            print(
                f"::warning::  [{label}] {fg_name} on {bg_name} — {ratio:.2f}:1 ({large_ok})"
            )

    if all_violations and FAIL_ON_AA_VIOLATION and not report_only:
        _fail(f"AA 미달 조합 {len(all_violations)}건 — 토큰 값을 고치세요")
        return 1

    if all_violations:
        print("판정: 보고만 하고 통과합니다 (--report-only)")
    else:
        print("판정: AA 미달 조합 0건")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
