#!/usr/bin/env python3
"""비텍스트 토큰이 글자에 쓰이는 것을 막는다 — fail-closed (stdlib 전용).

**두 그물 사이에 난 구멍을 메운다.** `verify_token_contrast.py` 는 토큰을 역할로 분류하고
「비텍스트」로 찍힌 것을 **텍스트 대비 곱집합에서 뺀다**(리드 결정 ㉡ — `--ink-faint` 는 선·아이콘
전용). `verify_color_token_usage.py` 는 **토큰 밖의 색**(팔레트 기본색·hex 리터럴)만 잡는다.

그래서 등록된 비텍스트 토큰을 `text-…` 로 쓰면 **양쪽 다 통과한다** — 대비 검사는 "비텍스트니
검사 안 함"으로 넘기고, 색 사용 검사는 "등록된 토큰이니 위반 아님"으로 넘긴다. 실제로는 규격상
못 읽는 값(`--ink-faint` 는 다크 2.74:1 · 라이트 2.91:1)이 화면에 글자로 상시 노출된다.
실측으로 그렇게 새어 나간 적이 있다(PR #161 리뷰).

**분류의 정본은 `verify_token_contrast.py` 다** — 여기서 목록을 복제하지 않고 그 모듈에서
읽어 온다. 두 벌이 되면 갈린다.

standalone 실행:
    python3 scripts/verify_non_text_token_usage.py
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND = REPO_ROOT / "frontend"
SCAN_DIRS = ("components", "app")

# **글자색**을 정하는 유틸리티 접두만. `border-`·`bg-`·`ring-`·`fill-`·`stroke-` 는 비텍스트라 정상이고,
# `decoration-` 도 밑줄「선」의 색이라 비텍스트 토큰이 오히려 맞다 (첫 판이 그것을 오탐했다).
TEXT_PREFIXES = ("text-", "placeholder-")

# 대상이 이 아래로 내려가면 그물이 죽은 것이다.
MIN_FILES = 100


def non_text_tokens() -> list[str]:
    """`verify_token_contrast.py` 가 「비텍스트」로 분류한 토큰 — 정본에서 읽는다."""
    path = REPO_ROOT / "scripts" / "verify_token_contrast.py"
    spec = importlib.util.spec_from_file_location("verify_token_contrast", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"분류 정본을 읽지 못했습니다: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    exact = [
        name for name, role in module.EXACT_ROLES.items() if role == module.NON_TEXT
    ]
    prefixes = [p for p, role in module.PREFIX_ROLES if role == module.NON_TEXT]
    return sorted(set(exact)), sorted(set(prefixes))


def tailwind_names(
    tokens: list[str], prefixes: list[str]
) -> tuple[set[str], list[str]]:
    """CSS 변수명(`--ink-faint`) → Tailwind 유틸 조각(`ink-faint`)."""
    return {t.lstrip("-") for t in tokens}, [p.lstrip("-") for p in prefixes]


def scan() -> tuple[int, list[str], set[str], list[str], re.Pattern[str]]:
    exact_vars, prefix_vars = non_text_tokens()
    names, prefixes = tailwind_names(exact_vars, prefix_vars)

    # `text-ink-faint` · `text-ink-faint/60` · `hover:text-line-strong` ·
    # **`!text-ink-faint`** · **`placeholder:!text-ink-faint`** · `dark:hover:!text-ink-faint` 를 다 잡는다.
    #
    # `!`(important 수식자)를 빼먹으면 그물이 조용히 새어 나간다 — 첫 판이 정확히 그랬고,
    # 그 상태로 로그인 화면의 `placeholder:!text-ink-faint` 2곳이 통과했다(리뷰가 잡았다).
    # 변형 체인의 **각 마디 앞**과 유틸리티 앞 **양쪽**에 `!` 가 올 수 있다.
    pattern = re.compile(
        r"(?:^|[\s\"'`])(?:!?[a-z0-9-]+:)*!?("
        + "|".join(TEXT_PREFIXES)
        + r")([a-z0-9-]+)"
    )

    problems: list[str] = []
    checked = 0
    for directory in SCAN_DIRS:
        for path in sorted((FRONTEND / directory).rglob("*.tsx")):
            checked += 1
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                for _prefix, name in pattern.findall(line):
                    base = name.split("/")[0]
                    hit = base in names or any(base.startswith(p) for p in prefixes)
                    if hit:
                        rel = path.relative_to(FRONTEND)
                        problems.append(
                            f"{rel}:{lineno} — 비텍스트 토큰을 글자에 썼습니다: --{base}"
                        )
    return checked, problems, names, prefixes, pattern


# 스캐너 자신의 자기검사 — **이 목록이 그물의 구멍을 막는다.**
# 첫 판은 `!`(important 수식자)를 못 잡아 실제 위반 2건이 통과했다. 파손 주입은
# 수식자 없는 형태만 시도해 그 구멍을 못 봤다 — 그래서 형태를 목록으로 못박는다.
SELF_CHECK_HITS = (
    'className="text-ink-faint"',
    'className="!text-ink-faint"',
    'className="placeholder:!text-ink-faint"',
    'className="dark:hover:!text-ink-faint"',
    'className="text-ink-faint/60"',
    'className="hover:text-line-strong"',
)
SELF_CHECK_MISSES = (
    'className="border-line-strong"',  # 선 — 비텍스트 토큰의 제 자리다
    'className="decoration-line-strong"',  # 밑줄도 선이다
    'className="bg-ink-faint/10"',  # 바탕
    'className="text-ink-muted"',  # 텍스트 토큰
)


def self_check(
    names: set[str], prefixes: list[str], pattern: re.Pattern[str]
) -> list[str]:
    """그물이 잡아야 할 형태를 실제로 잡는지 — 그물의 그물."""
    failures = []
    for sample in SELF_CHECK_HITS:
        if not any(
            m[1].split("/")[0] in names
            or any(m[1].split("/")[0].startswith(p) for p in prefixes)
            for m in pattern.findall(sample)
        ):
            failures.append(f"잡아야 하는데 놓쳤다: {sample}")
    for sample in SELF_CHECK_MISSES:
        if any(
            m[1].split("/")[0] in names
            or any(m[1].split("/")[0].startswith(p) for p in prefixes)
            for m in pattern.findall(sample)
        ):
            failures.append(f"잡으면 안 되는데 잡았다: {sample}")
    return failures


def main() -> int:
    checked, problems, names, prefixes, pattern = scan()

    # **그물의 그물부터 돌린다.** 스캐너가 잡아야 할 형태를 못 잡으면 아래 「위반 0건」은
    # 「위반이 없다」가 아니라 「아무것도 못 봤다」다 — 실제로 그렇게 새어 나갔다.
    self_failures = self_check(names, prefixes, pattern)
    for failure in self_failures:
        print(f"::error::스캐너 자기검사 실패 — {failure}", file=sys.stderr)

    print(
        f"`.tsx` {checked}건 검사 ({' · '.join(f'frontend/{d}' for d in SCAN_DIRS)}) · "
        f"위반 {len(problems)}건 · 자기검사 {len(SELF_CHECK_HITS) + len(SELF_CHECK_MISSES)}건 "
        f"중 실패 {len(self_failures)}건"
    )

    if self_failures:
        return 1

    if checked < MIN_FILES:
        print(
            f"::error::검사 대상이 {checked}건뿐이다 — 그물이 죽어 있다 (하한 {MIN_FILES}). "
            "스캔 경로가 바뀌었는지 보라.",
            file=sys.stderr,
        )
        return 1

    if problems:
        for line in problems:
            print(f"::error::{line}", file=sys.stderr)
        print(
            "\n비텍스트 토큰은 선·아이콘 전용입니다 (리드 결정 ㉡). "
            "라벨·표 헤더는 `--ink-muted` 가 받습니다.",
            file=sys.stderr,
        )
        return 1

    print("판정: 비텍스트 토큰을 글자에 쓴 자리 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
