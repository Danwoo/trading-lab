"""리뷰 룰의 Detection pathspec 이 대상을 다 보는지 — fail-closed (stdlib 전용).

## 왜 있나

`.claude/docs/anti-patterns-*.md` 는 `review-backend`/`review-frontend` 의 SoT 다. 에이전트는
Detection 박스의 명령을 **재작성하지 않고 그대로** 실행하므로, pathspec 의 결함이 그대로
전파된다. 그리고 후처리 안내가 「0 hit → 통과」라 **안 본 범위가 「위반 없음」으로 보고된다.**

실제로 그랬다 (https://github.com/Danwoo/trading-lab/issues/330): pathspec 이 `'{backend}/app/**/*.py'` 였는데, git **기본** 매직에서 `*` 는
`/` 를 넘고 `**/` 는 「디렉터리가 한 단계 이상」이 되어 **깊이 1 파일이 통째로 빠진다.**

    git ls-files 'backend-service/app/**/*.py'        -> 127
    git ls-files ':(glob)backend-service/app/**/*.py' -> 129   # main.py · modules.py

11개 서비스의 `app/main.py` 와 `backend-service/app/modules.py` — lifespan·매니저 배선·컨테이너가
사는 가장 위험한 자리 12개 파일이 룰 5개의 사정권 밖에 있었다. 위반이 없던 것은 운이지 그물이
아니다.

`':(glob)'` 매직 아래에서만 `*` 가 한 세그먼트 안에 머물고 `/**/` 가 「0개 이상의 디렉터리」로
읽힌다 — **문서에 이미 적혀 있던 뜻대로** 동작한다. 그래서 처방은 글롭을 다시 쓰는 것이 아니라
매직을 선언하는 것이다. 글롭을 손으로 고치는 쪽은 자리마다 다르게 틀린다:
`'frontend/app/api/**/route.ts'` 에서 `**/` 를 빼면 67개가 아니라 0개를 본다.

## 무엇을 검사하나

1. **`:(glob)` 선언** — 대상 문서의 git 명령에 등장하는 모든 pathspec 이 `:(glob)` 로 시작해야
   한다. 접두가 없으면 그 글롭은 「사람이 읽는 뜻」과 「git 이 읽는 뜻」이 갈릴 수 있고, 갈린
   쪽으로 조용히 통과한다.
2. **한 파일이라도 맞히는가** — pathspec 이 한 파일도 안 맞히면 실패한다. 디렉터리를 옮기거나
   지웠는데 문서의 좌표가 안 따라오면 그 룰은 「대상 없음 = 위반 없음」으로 영원히 초록이 된다.
   0건이 정답인 자리(「금지된 위치」 룰)는 `EXPECT_EMPTY` 에 이유와 함께 선언한다.

fail-closed — 뽑아낸 pathspec 수가 하한 미만이면 실패하고, 검사 건수를 출력에 남긴다. 통과가
"위반 없음"인지 "아무것도 안 봤음"인지 읽는 사람이 구분할 수 있어야 한다.

실행: `python3 scripts/verify_detection_pathspec.py` (cwd 무관).
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 검사 대상 — 리뷰 에이전트가 명령을 그대로 실행하는 문서들.
TARGET_DOCS = [
    ".claude/docs/anti-patterns-backend.md",
    ".claude/docs/anti-patterns-frontend.md",
    ".claude/agents/review-backend.md",
    ".claude/agents/review-frontend.md",
]

# pathspec 을 인자로 받는 git 하위명령. `grep`/`diff` 는 `--` 뒤만 pathspec 이고, 앞은 패턴·리비전이다.
SUBCOMMANDS_AFTER_DASHDASH = {"grep", "diff", "log"}
SUBCOMMANDS_TRAILING_ARGS = {"ls-files"}

# 파이프라인·목록 구분자 — 여기서 명령이 끊긴다.
SEPARATORS = {"|", "||", "&&", ";", "{", "}", "(", ")"}

# 「접두를 떼면 이렇게 된다」를 보여주는 반례 줄. 문서가 자기 규칙을 설명하려면 깨진 형태를
# 한 번은 적어야 한다. 남용을 막으려고 상한을 둔다.
OPTOUT_MARKER = "pathspec-check: 반례"
MAX_OPTOUTS = 2

# 0건이 정답인 pathspec — (pathspec, 사유). 등록했는데 실제로 0건이 아니면 실패한다.
EXPECT_EMPTY: list[tuple[str, str]] = [
    (
        ":(glob)frontend/app/**/_components/**/*.tsx",
        "「컴포넌트 위치 위반」 룰의 금지된 위치 — 파일이 있으면 그 자체가 위반이라 0건이 정상이다.",
    ),
]

# `{backend}` 치환 대상 — `app/main.py` 가 있는 폴더를 스스로 찾는다.
BACKEND_PLACEHOLDER = "{backend}"

# 하한은 현재 실측치다 (2026-08-23 기준 49건 / 4문서). 정당하게 줄었다면 여기도 함께 내린다.
MIN_PATHSPECS = 45
MIN_DOCS_WITH_PATHSPECS = 4


def _discover_backends() -> list[str]:
    return sorted(p.parents[1].name for p in REPO_ROOT.glob("*/app/main.py"))


_INLINE_CODE = re.compile(r"`([^`\n]+)`")


def _command_lines(text: str) -> tuple[list[tuple[int, str]], int]:
    """명령이 실제로 적히는 두 자리만 읽는다 — 코드 펜스 안, 그리고 인라인 코드 스팬.

    산문을 그대로 토큰화하면 명령 뒤에 붙은 한국어 설명까지 pathspec 으로 읽힌다.
    반환값의 둘째는 반례 마커로 건너뛴 줄 수다.
    """
    out: list[tuple[int, str]] = []
    skipped = 0
    in_fence = False
    buf = ""
    start = 0
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            if not buf:
                start = lineno
            if line.endswith("\\"):
                buf += line[:-1] + " "
                continue
            buf += line
            if OPTOUT_MARKER in buf:
                skipped += 1
            else:
                out.append((start, buf))
            buf = ""
        else:
            for span in _INLINE_CODE.findall(line):
                if OPTOUT_MARKER in span:
                    skipped += 1
                else:
                    out.append((lineno, span))
    if buf:
        out.append((start, buf))
    return out, skipped


def _tokenize(line: str) -> list[str] | None:
    try:
        tokens = shlex.split(line, posix=True)
    except ValueError:
        return None
    # `--flag=x;` 처럼 구분자가 토큰에 붙어 오는 경우를 떼어 낸다.
    split_out: list[str] = []
    for tok in tokens:
        while tok and tok[-1] in ";|&":
            split_out.append(tok[:-1])
            split_out.append(tok[-1])
            tok = ""
        if tok:
            split_out.append(tok)
    return [t for t in split_out if t]


def _pathspecs_in(line: str) -> list[str]:
    """한 논리 줄에서 git 하위명령별 pathspec 자리를 뽑는다."""
    tokens = _tokenize(line)
    if not tokens:
        return []
    found: list[str] = []
    i = 0
    while i < len(tokens):
        if tokens[i] != "git":
            i += 1
            continue
        sub = tokens[i + 1] if i + 1 < len(tokens) else ""
        j = i + 2
        args: list[str] = []
        while j < len(tokens) and tokens[j] not in SEPARATORS:
            args.append(tokens[j])
            j += 1
        if sub in SUBCOMMANDS_AFTER_DASHDASH:
            if "--" in args:
                found.extend(a for a in args[args.index("--") + 1 :] if a)
        elif sub in SUBCOMMANDS_TRAILING_ARGS:
            rest = args[args.index("--") + 1 :] if "--" in args else args
            found.extend(a for a in rest if not a.startswith("-"))
        i = j
    return found


def _collect() -> tuple[list[tuple[str, int, str]], int]:
    out: list[tuple[str, int, str]] = []
    optouts = 0
    for rel in TARGET_DOCS:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue  # 실재 확인은 호출자가 한다
        lines, skipped = _command_lines(path.read_text(encoding="utf-8"))
        optouts += skipped
        for lineno, line in lines:
            for spec in _pathspecs_in(line):
                out.append((rel, lineno, spec))
    return out, optouts


def _match_count(spec: str, backends: list[str]) -> int:
    specs = [spec.replace(BACKEND_PLACEHOLDER, b) for b in backends] if BACKEND_PLACEHOLDER in spec else [spec]
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", *specs],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return -1
    return len({line for line in result.stdout.splitlines() if line})


def main() -> None:
    violations: list[str] = []

    missing_docs = [rel for rel in TARGET_DOCS if not (REPO_ROOT / rel).is_file()]
    for rel in missing_docs:
        violations.append(f"{rel} 가 없다 — 검사 대상 목록이 현실과 어긋났다.")

    backends = _discover_backends()
    if not backends:
        violations.append("`*/app/main.py` 를 하나도 못 찾았다 — {backend} 치환 대상이 없다.")

    collected, optouts = _collect()
    entries = [e for e in collected if e[2]]
    docs_seen = {rel for rel, _, _ in entries}
    unique_specs = sorted({spec for _, _, spec in entries})

    expect_empty = {spec for spec, _ in EXPECT_EMPTY}
    seen_expect_empty: set[str] = set()

    for spec in unique_specs:
        where = ", ".join(f"{rel}:{ln}" for rel, ln, s in entries if s == spec)
        if not spec.startswith(":(glob)"):
            violations.append(
                f"{where} — pathspec '{spec}' 에 `:(glob)` 접두가 없다. "
                f"기본 매직에서는 `*` 가 `/` 를 넘고 `**/` 가 깊이 1 을 뺀다."
            )
            continue
        count = _match_count(spec, backends)
        if count < 0:
            violations.append(f"{where} — pathspec '{spec}' 를 git 이 거부했다.")
            continue
        if spec in expect_empty:
            seen_expect_empty.add(spec)
            if count != 0:
                violations.append(
                    f"{where} — '{spec}' 는 0건이 정답으로 선언돼 있는데 {count}건이다. "
                    f"룰 위반이거나 EXPECT_EMPTY 선언이 낡았다."
                )
        elif count == 0:
            violations.append(
                f"{where} — '{spec}' 가 한 파일도 안 맞힌다. 대상이 옮겨졌거나 사라졌다면 "
                f"pathspec 을 고치고, 0건이 정답이면 EXPECT_EMPTY 에 사유와 함께 등록하라."
            )

    for spec, _ in EXPECT_EMPTY:
        if spec not in seen_expect_empty:
            violations.append(f"EXPECT_EMPTY 의 '{spec}' 가 문서에 더는 없다 — 예외를 지워라.")

    print(
        f"[Detection pathspec] 문서 {len(docs_seen)}/{len(TARGET_DOCS)}개 / "
        f"등장 {len(entries)}건 / 고유 {len(unique_specs)}종 "
        f"(backend {len(backends)}개 치환, 0건 예외 {len(EXPECT_EMPTY)}종, 반례 제외 {optouts}줄)"
    )

    if optouts > MAX_OPTOUTS:
        violations.append(
            f"반례 마커(`{OPTOUT_MARKER}`) 가 {optouts}줄로 상한 {MAX_OPTOUTS} 초과 — 검사를 끄는 데 쓰이고 있다."
        )

    if len(entries) < MIN_PATHSPECS:
        violations.append(
            f"뽑아낸 pathspec 이 {len(entries)}건으로 하한 {MIN_PATHSPECS} 미만 — "
            f"추출이 깨졌거나 대상 지정이 현실과 어긋났다."
        )
    if len(docs_seen) < MIN_DOCS_WITH_PATHSPECS:
        violations.append(
            f"pathspec 이 발견된 문서가 {len(docs_seen)}개로 하한 {MIN_DOCS_WITH_PATHSPECS} 미만 — "
            f"문서 하나가 통째로 안 읽혔다."
        )

    if violations:
        print(f"\n위반 {len(violations)}건:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    print("위반 없음")


if __name__ == "__main__":
    main()
