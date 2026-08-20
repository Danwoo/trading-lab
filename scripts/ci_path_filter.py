r"""경로 필터 판정 — 변경 파일 목록이 글롭 하나라도 무는지 (stdlib 전용, I/O 없는 순수 판정).

## 왜 있나

워크플로 레벨 `on.paths` 로 건너뛴 체크는 **체크런이 아예 생기지 않는다** — required 로 걸면
영영 pending 이라 그 PR 이 머지 불가로 막힌다. 잡 레벨 `if:` 로 건너뛴 잡은 `skipped` 를
보고하고 GitHub 은 `success`·`skipped`·`neutral` 을 통과로 센다. 그래서 `ci.yml`·
`frontend-ci.yml` 은 `on.paths` 대신 **판정 잡 하나**가 이 스크립트로 boolean 을 내고
나머지 잡이 `if: needs.changes.outputs.run == 'true'` 로 그것을 읽는다 (#23 Task 4).

판정부를 워크플로 안 bash 가 아니라 이 파일에 두는 이유는 **로컬에서 돌려 볼 수 있어야**
하기 때문이다 — YAML 안 판정은 러너 위에서만 실행돼 회귀 그물을 못 건다.

## 글롭 문법

GitHub 의 `on.paths` 문법 중 이 레포가 실제로 쓰는 둘만 구현한다:

  · `*`  — `/` 를 제외한 0자 이상
  · `**` — `/` 포함 0자 이상

`?`·`+`·`[]`·`!`·`\` 는 **구현하지 않고 거부한다**. GitHub 의 `?`·`+` 는 셸 글롭이 아니라
"앞 문자의 0~1회·1회 이상" 이라 직관과 어긋나는데, 조용히 셸 글롭으로 해석하면 판정이
GitHub 과 갈린다. 쓰려면 여기 문법을 먼저 맞춰라 — 거부는 그 강제 장치다.

## fail-closed

- 패턴 목록이 비면 실패한다 (종료코드 1). "패턴 0건 = 아무것도 안 무는다 = 전부 skip" 은
  검사가 통째로 사라졌는데 초록인 상태다.
- 변경 파일 목록을 **모르면 `run=true`** 다 (`--unknown`). 얕은 클론·force push·base 삭제로
  diff 를 못 구했을 때 건너뛰면 검사 없이 머지된다. 모르면 돌린다.
- 변경 파일이 **0건이면 모른다로 친다.** PR·push 는 무언가를 바꾸므로 빈 목록은 정상 상태가
  아니라 diff 가 헛돈 신호다.

실행:
    printf '%s\n' "$CHANGED" | FILTER_PATTERNS="$(cat patterns.txt)" python3 scripts/ci_path_filter.py
    FILTER_PATTERNS=... python3 scripts/ci_path_filter.py --unknown

stdout 에는 `run=true|false` 한 줄만 낸다 (`>> "$GITHUB_OUTPUT"` 로 흘려보낼 수 있게).
사람이 읽을 근거는 stderr 로 낸다.
"""

from __future__ import annotations

import os
import re
import sys

UNSUPPORTED = "?+[]!\\"


class PatternError(ValueError):
    """지원하지 않는 글롭 문법."""


def glob_to_regex(pattern: str) -> str:
    """GitHub `on.paths` 글롭을 완전 일치 정규식 문자열로 바꾼다."""
    if not pattern:
        raise PatternError("빈 패턴")
    bad = sorted({c for c in pattern if c in UNSUPPORTED})
    if bad:
        raise PatternError(
            f"지원하지 않는 글롭 문자 {bad} — 패턴 {pattern!r}. "
            "구현된 것은 `*` 와 `**` 뿐이다 (머리 주석 「글롭 문법」)"
        )
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern[i] == "*":
            if pattern[i + 1 : i + 2] == "*":
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return "^" + "".join(out) + "$"


def parse_patterns(text: str) -> list[str]:
    """패턴 블록을 목록으로 판다. 빈 줄·`#` 주석 줄·따옴표는 버린다.

    워크플로의 YAML 블록 스칼라(`|`)를 그대로 받으므로 주석을 패턴 옆에 둘 수 있다.
    """
    patterns: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if len(line) >= 2 and line[0] == line[-1] and line[0] in "\"'":
            line = line[1:-1]
        patterns.append(line)
    return patterns


def decide(patterns: list[str], changed: list[str] | None) -> tuple[bool, list[tuple[str, str]]]:
    """(돌릴지, 무는 (패턴, 파일) 목록) 을 낸다. `changed` 가 None 이면 모르는 것 → 돌린다."""
    if not patterns:
        raise PatternError("패턴이 0건 — 그대로 두면 전 잡이 조용히 skip 된다")
    if changed is None:
        return True, []
    hits: list[tuple[str, str]] = []
    for pattern in patterns:
        matcher = re.compile(glob_to_regex(pattern))
        for path in changed:
            if matcher.match(path):
                hits.append((pattern, path))
                break
    return bool(hits), hits


def main(argv: list[str]) -> int:
    unknown = "--unknown" in argv[1:]
    for arg in argv[1:]:
        if arg != "--unknown":
            print(f"::error::알 수 없는 인자: {arg}", file=sys.stderr)
            return 1

    patterns = parse_patterns(os.environ.get("FILTER_PATTERNS", ""))
    changed: list[str] | None = None
    if not unknown:
        changed = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
        if not changed:
            print(
                "::warning::변경 파일 0건 — 판정 불가로 보고 전 잡을 돌린다 (fail-closed)",
                file=sys.stderr,
            )
            changed = None

    try:
        run, hits = decide(patterns, changed)
    except PatternError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    print(
        f"패턴 {len(patterns)}건 · 변경 파일 {'모름' if changed is None else len(changed)}건",
        file=sys.stderr,
    )
    if changed is None:
        print("판정: run=true (변경 파일을 모른다 — 건너뛰지 않는다)", file=sys.stderr)
    elif run:
        for pattern, path in hits:
            print(f"  · {pattern} ← {path}", file=sys.stderr)
        print(f"판정: run=true ({len(hits)}개 패턴이 물었다)", file=sys.stderr)
    else:
        print("판정: run=false (무는 패턴 없음)", file=sys.stderr)

    print(f"run={'true' if run else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
