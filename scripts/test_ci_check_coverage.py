"""verify_ci_check_coverage 의 pre-commit 대조 회귀 그물 — 관대해지는 방향을 못박는다.

이 대조는 **초록일 때 아무 일도 안 하는** 검사라 죽어도 티가 안 난다. 그리고 이 그물이
막으려는 결함은 정확히 「검사가 있는데 안 돈다」이므로, 관대해지는 방향(새 훅을 모른 척 ·
사라진 대응을 배선된 것으로 셈 · 훅을 0건 읽고 통과)이 최악이다.

케이스를 0건 수집하면 실패한다 (fail-closed).
"""

from __future__ import annotations

import sys

import verify_ci_check_coverage as cov

LOCAL_ONLY = cov.LOCAL_ONLY

# 표를 케이스마다 새로 만든다 — 실제 PRECOMMIT_PARITY 를 쓰면 그 표가 바뀔 때 케이스가
# 같이 흔들려, 무엇을 못박은 것인지 사라진다.
TABLE = {
    "hook-file": ("scripts/verify_x.py", "파일 대응"),
    "hook-cmd": ("npm test", "명령 대응"),
    "hook-local": (LOCAL_ONLY, "CI 대응 없음이 옳다"),
}
FILES = {"scripts/verify_x.py"}
COMMANDS = "npm test\nnpx tsc --noEmit"

# (설명, 훅 목록, cov 파일 집합, 명령 원문, 하한, 문제 있어야 하나)
CASES = [
    ("전부 배선된 상태", ["hook-file", "hook-cmd", "hook-local"], FILES, COMMANDS, 3, False),
    ("표에 없는 새 훅", ["hook-file", "hook-cmd", "hook-local", "hook-new"], FILES, COMMANDS, 3, True),
    ("파일 대응이 CI 에서 사라짐", ["hook-file", "hook-cmd", "hook-local"], set(), COMMANDS, 3, True),
    ("명령 대응이 CI 에서 사라짐", ["hook-file", "hook-cmd", "hook-local"], FILES, "", 3, True),
    ("훅이 사라졌는데 표에 남음", ["hook-file"], FILES, COMMANDS, 1, True),
    ("훅 0건 — 파싱이 깨졌거나 파일이 사라짐", [], FILES, COMMANDS, 3, True),
    ("훅 수가 하한 미만", ["hook-file", "hook-cmd"], FILES, COMMANDS, 3, True),
    # 부분 문자열이 아니라 **정확한 조각**이 있어야 한다 — 명령을 줄여 적어 통과시키는 길을 막는다
    ("명령이 비슷하지만 다름", ["hook-cmd"], FILES, "npm run test:db", 1, True),
]

# pre-commit 설정 파싱 — `- id:` 만 훅이다.
PARSE_CASES = [
    (
        "훅 세 개",
        "repos:\n  - repo: x\n    hooks:\n      - id: a\n      - id: b\n  - repo: y\n    hooks:\n      - id: c\n",
        ["a", "b", "c"],
    ),
    ("빈 설정", "repos: []\n", []),
    ("id 가 값의 일부인 줄은 훅이 아니다", "        entry: bash -c 'echo - id: nope'\n", []),
]


def _check_parity(failures: list[str]) -> None:
    for desc, hooks, files, commands, minimum, want_problems in CASES:
        _lines, problems = cov.check_precommit_parity(hooks, set(files), commands, table=dict(TABLE), minimum=minimum)
        if bool(problems) != want_problems:
            failures.append(f"{desc}: 문제 {len(problems)}건 (기대 {'있음' if want_problems else '없음'}) — {problems}")


def _check_parse(failures: list[str]) -> None:
    for desc, text, want in PARSE_CASES:
        got = cov.parse_precommit_hooks(text)
        if got != want:
            failures.append(f"{desc}: {got} (기대 {want})")


def _check_live(failures: list[str]) -> None:
    """실물 설정 ↔ 실물 표 — 표가 낡거나 훅이 늘어난 것을 여기서도 본다."""
    config = cov.PRECOMMIT_CONFIG
    if not config.is_file():
        failures.append(f"실물 설정이 없습니다: {config}")
        return
    hooks = cov.parse_precommit_hooks(config.read_text(encoding="utf-8"))
    if len(hooks) < cov.PRECOMMIT_HOOK_MINIMUM:
        failures.append(f"실물 훅 {len(hooks)}건 — 하한 {cov.PRECOMMIT_HOOK_MINIMUM} 미만")
    unknown = [h for h in hooks if h not in cov.PRECOMMIT_PARITY]
    stale = sorted(set(cov.PRECOMMIT_PARITY) - set(hooks))
    if unknown:
        failures.append(f"실물 훅 중 표에 없는 것: {unknown}")
    if stale:
        failures.append(f"표에만 있고 실물에 없는 훅: {stale}")


def main() -> int:
    if not CASES or not PARSE_CASES:
        print("::error::케이스 0건 — 그물이 비었다 (fail-closed)")
        return 1
    failures: list[str] = []
    _check_parity(failures)
    _check_parse(failures)
    _check_live(failures)
    total = len(CASES) + len(PARSE_CASES) + 1
    print(
        f"pre-commit 대조 케이스 {total}건 검사 (판정 {len(CASES)} · 파싱 {len(PARSE_CASES)} · 실물 1) · 실패 {len(failures)}건"
    )
    for f in failures:
        print(f"::error::{f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
