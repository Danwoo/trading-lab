"""경로 필터 판정의 회귀 그물 — 글롭 의미 + 워크플로 배선 구조 (stdlib 전용, fail-closed).

## 왜 두 겹인가

`scripts/ci_path_filter.py` 의 단위 케이스만 돌리면 **판정은 맞는데 아무도 안 부르는** 상태가
초록이다. 이 레포가 반복해서 데인 클래스가 정확히 그것이다 (#241 · #252 · #302 — "검사는
실재하는데 CI 가 안 돌린다"). 그래서 배선 구조 자체를 케이스로 못박는다:

  ① 글롭 의미 — `*` 는 `/` 를 안 넘고 `**` 는 넘는다. 미구현 문법은 거부한다
  ② 판정 — 모르면 돌린다 · 무는 게 없으면 안 돌린다 · 패턴 0건은 예외
  ③ 배선 — `ci.yml`·`frontend-ci.yml` 이 `on.paths` 를 다시 갖지 않았는지, 판정 잡이 있는지,
     나머지 잡이 전부 그 출력을 `if:` 로 읽는지
  ④ 죽은 경로 — 패턴 하나하나가 **추적 중인 파일을 실제로 무는지**
  ⑤ 필수 트리거 — 선언한 (워크플로, 입력 파일) 짝에서 그 파일만 바뀐 PR 이 실제로 `run=true`
  ⑥ 필터 밖 그물 — 입력이 서비스 경계를 가로지르는 그물은 **경로 필터 없는 워크플로**에 산다
  ⑦ backend 전수 — `app/main.py` 가 있는 폴더(= 이 레포의 backend 정의, 루트 CLAUDE.md)마다
     그 폴더의 파일만 바뀐 PR 이 `ci.yml` 을 돌린다. 목록은 손으로 적지 않고 폴더를 훑는다

④ 가 이 그물의 핵심이다. 경로 문자열로 대상을 지정하는 필터는 그 경로가 사라져도
"대상 없음 = 트리거 없음" 으로 조용히 초록이 된다 — 시끄럽게 실패하는 그물은 누구든 잡지만,
초록으로 죽은 그물은 아무도 못 본다.

⑦ 은 ⑤ 를 목록 없이 하는 것이다 — backend 는 폴더가 늘어나는 클래스라 짝을 손으로 적으면 새
폴더가 또 빠진다. `single-agent-service` 가 실제로 그 상태였다(#344 리뷰에서 발견).

⑤⑥ 은 ④ 의 반대 방향이다 (#331). ④ 는 「목록의 패턴이 죽었는가」를 보지만, 이 레포가 두 번
당한 것은 **목록에 애초에 없는 입력**이었다 — 그물은 멀쩡히 살아 있고 판정만 `run=false` 라
잡이 `skipped` 로 끝나고 GitHub 은 그것을 통과로 센다. 처방이 둘이라 축도 둘이다: 입력을
목록에 넣거나(⑤), 그물을 필터 없는 워크플로로 옮기거나(⑥).

배선: `.github/workflows/repo-scans.yml` 의 `test: repo-scan` 잡 (경로 필터 없음).

실행: `python3 scripts/test_ci_path_filter.py`
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ci_path_filter import (  # noqa: E402
    PatternError,
    decide,
    glob_to_regex,
    parse_patterns,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# 잡 레벨 필터로 옮긴 워크플로. 여기서 빠지면 그 파일은 이 그물 밖이다.
FILTERED_WORKFLOWS = ["ci.yml", "frontend-ci.yml"]
FILTER_JOB = "changes"
FILTER_IF = "needs.changes.outputs.run == 'true'"

# (패턴, 경로, 무는가)
GLOB_CASES: list[tuple[str, str, bool]] = [
    # `*` 는 `/` 를 넘지 않는다
    ("*/app/core/config.py", "backend-service/app/core/config.py", True),
    ("*/app/core/config.py", "app/core/config.py", False),
    ("*/app/core/config.py", "a/b/app/core/config.py", False),
    ("*-mcp-service/**", "news-mcp-service/app/main.py", True),
    ("*-mcp-service/**", "sub/news-mcp-service/app/main.py", False),
    ("*-service/CLAUDE.md", "backend-service/CLAUDE.md", True),
    ("*-service/CLAUDE.md", "backend-service/app/CLAUDE.md", False),
    # `**` 는 `/` 를 넘는다
    ("frontend/**", "frontend/app/page.tsx", True),
    ("frontend/**", "frontend/a/b/c/d.ts", True),
    ("frontend/**", "frontend-extra/a.ts", False),
    ("backend-service/alembic/**", "backend-service/alembic/versions/0001_x.py", True),
    ("backend-service/alembic/**", "backend-service/app/main.py", False),
    (".github/workflows/**", ".github/workflows/ci.yml", True),
    (".github/workflows/**", ".github/dependabot.yml", False),
    # 리터럴 — 부분 일치로 새지 않는다
    ("THIRD-PARTY-NOTICES.md", "THIRD-PARTY-NOTICES.md", True),
    ("THIRD-PARTY-NOTICES.md", "docs/THIRD-PARTY-NOTICES.md", False),
    ("scripts/verify_notice_counts.py", "scripts/verify_notice_counts.py", True),
    ("scripts/verify_notice_counts.py", "scripts/verify_notice_counts.pyc", False),
    # 정규식 메타문자는 리터럴로 잡힌다
    ("frontend/prisma/init/tables.sql", "frontend/prisma/init/tablesXsql", False),
]

# 구현하지 않은 글롭 문법 — 조용히 셸 글롭으로 해석하면 GitHub 과 판정이 갈린다
REJECTED_PATTERNS = ["src/?.ts", "src/a+.ts", "src/[ab].ts", "!frontend/**", "a\\b"]

# ⑤ (워크플로, 변경 파일) — **그 파일 하나만** 바뀐 PR 에서 그 워크플로가 반드시 돌아야 한다.
# 그 잡이 실제로 그 파일을 입력으로 읽기 때문이다. 목록에서 빠지면 잡이 `skipped` 로 끝나고
# GitHub 은 skipped 를 통과로 센다 — 「검사가 있는데 안 돈다」의 가장 조용한 모양이다.
REQUIRED_TRIGGERS: list[tuple[str, str, str]] = [
    (
        "ci.yml",
        "frontend/prisma/schema.prisma",
        "backend-db 잡이 이 스키마에서 나온 tables.sql 로 scratch DB 를 세운다 (#331)",
    ),
    (
        "ci.yml",
        "frontend/prisma/init/tables.sql",
        "backend-db 잡이 커밋된 이 파일을 그대로 적용한다",
    ),
    (
        "frontend-ci.yml",
        "frontend/prisma/schema.prisma",
        "frontend 잡의 tables.sql 재현 대조가 이 파일을 읽는다 (#331)",
    ),
]

# ⑥ 입력이 서비스 경계를 가로지르는 그물 — 어느 한쪽의 경로 목록으로도 온전히 못 덮는다.
# `ci.yml` 의 backend 스위트에 있던 동안 이 둘은 **프론트만 바뀐 PR 에서 통째로 skipped** 였다:
# 최근 머지 40건 중 8건이 그 경우였고 2건은 그물 글롭에 드는 파일을 고쳤다 (#331 실측).
# 경로 필터 없이 도는 워크플로(repo-scans.yml)에 사는 것이 이 축의 계약이다.
# ⑦ 의 하한 — 폴더 글롭이 헛돌아 0~1개만 찾고 초록이 되는 것을 막는다 (지금 11개).
MIN_BACKEND_DIRS = 8

UNFILTERED_NETS: list[tuple[str, str]] = [
    (
        "scripts/verify_capability_kind_lockstep.py",
        "프론트 schemas/terminal/ingest.ts·components/**·services/**·tests/** 를 읽는다",
    ),
    (
        "scripts/verify_backtest_contract_lockstep.py",
        "프론트 schemas/backtest/backtest.ts 를 읽는다",
    ),
]


def _fail(msg: str) -> None:
    print(f"::error::{msg}")


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def _job_blocks(text: str) -> dict[str, str]:
    """`jobs:` 아래 들여쓰기 2의 잡을 {잡 id: 본문} 으로 판다."""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.rstrip() == "jobs:")
    except StopIteration:
        return {}
    header = re.compile(r"^  ([A-Za-z0-9_][A-Za-z0-9_-]*):\s*$")
    jobs: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[start + 1 :]:
        m = header.match(line)
        if m:
            current = m.group(1)
            jobs[current] = []
        elif current is not None:
            jobs[current].append(line)
    return {name: "\n".join(body) for name, body in jobs.items()}


def _on_block(text: str) -> str:
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.rstrip().startswith("on:"))
    except StopIteration:
        return ""
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line.startswith(" ") and not line.startswith("#"):
            break
        body.append(line)
    return "\n".join(body)


def _filter_patterns(job_body: str) -> list[str]:
    """판정 잡의 `FILTER_PATTERNS: |` 블록 스칼라를 뽑는다."""
    lines = job_body.splitlines()
    for i, line in enumerate(lines):
        if line.strip() != "FILTER_PATTERNS: |":
            continue
        indent = len(line) - len(line.lstrip())
        block: list[str] = []
        for nxt in lines[i + 1 :]:
            if not nxt.strip():
                continue
            if len(nxt) - len(nxt.lstrip()) <= indent:
                break
            block.append(nxt)
        return parse_patterns("\n".join(block))
    return []


def main() -> int:
    checked = 0
    failures: list[str] = []

    # ① 글롭 의미
    for pattern, path, expected in GLOB_CASES:
        checked += 1
        actual = re.match(glob_to_regex(pattern), path) is not None
        if actual != expected:
            failures.append(f"글롭: {pattern!r} ← {path!r} 기대 {expected} 실제 {actual}")

    for pattern in REJECTED_PATTERNS:
        checked += 1
        try:
            glob_to_regex(pattern)
        except PatternError:
            continue
        failures.append(f"글롭: 미구현 문법 {pattern!r} 을 거부하지 않았다")

    # ② 판정
    decision_cases: list[tuple[list[str], list[str] | None, bool]] = [
        (["frontend/**"], None, True),  # 모르면 돌린다
        (["frontend/**"], ["README.md"], False),
        (["frontend/**"], ["README.md", "frontend/app/page.tsx"], True),
        (["a/**", "b/**"], ["b/x"], True),
        (["a/**"], [], False),  # 빈 목록은 CLI 가 None 으로 바꾼다 — 순수 판정은 그대로
    ]
    for patterns, changed, expected in decision_cases:
        checked += 1
        run, _ = decide(patterns, changed)
        if run != expected:
            failures.append(f"판정: {patterns} ← {changed} 기대 {expected} 실제 {run}")

    checked += 1
    try:
        decide([], ["frontend/x"])
        failures.append("판정: 패턴 0건인데 예외가 없다 (fail-closed 위반)")
    except PatternError:
        pass

    # ③·④ 배선 구조 + 죽은 경로
    tracked = _tracked_files()
    if not tracked:
        failures.append("추적 파일 0건 — git ls-files 가 헛돌았다")

    total_patterns = 0
    for name in FILTERED_WORKFLOWS:
        wf = WORKFLOW_DIR / name
        checked += 1
        if not wf.is_file():
            failures.append(f"배선: {name} 이 없다")
            continue
        text = wf.read_text(encoding="utf-8")

        checked += 1
        if re.search(r"^\s*paths(-ignore)?:", _on_block(text), re.MULTILINE):
            failures.append(
                f"배선: {name} 의 on: 에 경로 필터가 다시 생겼다 — 그 잡은 필터 밖 PR 에서 "
                "체크런 자체가 안 생겨 required 로 걸 수 없다 (#23 Task 4)"
            )

        jobs = _job_blocks(text)
        checked += 1
        if FILTER_JOB not in jobs:
            failures.append(f"배선: {name} 에 판정 잡 `{FILTER_JOB}` 이 없다")
            continue

        patterns = _filter_patterns(jobs[FILTER_JOB])
        checked += 1
        if not patterns:
            failures.append(f"배선: {name} 의 FILTER_PATTERNS 가 0건")
        total_patterns += len(patterns)

        for pattern in patterns:
            checked += 1
            try:
                matcher = re.compile(glob_to_regex(pattern))
            except PatternError as exc:
                failures.append(f"죽은 경로: {name} — {exc}")
                continue
            if not any(matcher.match(p) for p in tracked):
                failures.append(
                    f"죽은 경로: {name} 의 {pattern!r} 이 추적 파일을 하나도 물지 않는다 — "
                    "경로가 사라졌으면 목록에서도 빼라 (조용히 안 도는 필터가 된다)"
                )

        for job_id, body in jobs.items():
            if job_id == FILTER_JOB:
                continue
            checked += 1
            if f"needs: {FILTER_JOB}" not in body or FILTER_IF not in body:
                failures.append(
                    f"배선: {name} 의 잡 `{job_id}` 이 판정을 안 읽는다 (`needs: {FILTER_JOB}` + `if: {FILTER_IF}`)"
                )

    # ⑤ 필수 트리거 — 선언한 입력만 바뀐 PR 에서 그 워크플로가 실제로 도는가
    for name, changed_path, reason in REQUIRED_TRIGGERS:
        checked += 1
        wf = WORKFLOW_DIR / name
        if not wf.is_file():
            failures.append(f"필수 트리거: {name} 이 없다")
            continue
        patterns = _filter_patterns(_job_blocks(wf.read_text(encoding="utf-8")).get(FILTER_JOB, ""))
        if not patterns:
            failures.append(f"필수 트리거: {name} 의 FILTER_PATTERNS 를 못 읽었다")
            continue
        if not (REPO_ROOT / changed_path).is_file():
            failures.append(f"필수 트리거: 선언한 입력 {changed_path!r} 이 실재하지 않는다 — 목록이 낡았다 ({reason})")
            continue
        run, _ = decide(patterns, [changed_path])
        if not run:
            failures.append(
                f"필수 트리거: {name} 이 {changed_path!r} 만 바뀐 PR 에서 안 돈다 (run=false) — {reason}. "
                "FILTER_PATTERNS 에 그 입력을 넣어라 (잡이 skipped 로 끝나고 GitHub 은 그것을 통과로 센다)"
            )

    # ⑦ backend 전수 — `app/main.py` 가 있는 폴더마다 그 폴더만 바뀐 PR 에서 ci.yml 이 도는가
    backend_dirs = sorted(p.parent.parent for p in REPO_ROOT.glob("*/app/main.py"))
    checked += 1
    if len(backend_dirs) < MIN_BACKEND_DIRS:
        failures.append(
            f"backend 전수: */app/main.py 로 찾은 폴더가 {len(backend_dirs)}개 — 하한 {MIN_BACKEND_DIRS} 미만이다. "
            "backend 정의(app/main.py 가 있는 폴더)가 바뀌었으면 이 그물부터 고쳐라"
        )
    ci_patterns = _filter_patterns(
        _job_blocks((WORKFLOW_DIR / "ci.yml").read_text(encoding="utf-8")).get(FILTER_JOB, "")
    )
    for backend_dir in backend_dirs:
        checked += 1
        probe = f"{backend_dir.name}/app/main.py"
        run, _ = decide(ci_patterns, [probe]) if ci_patterns else (False, [])
        if not run:
            failures.append(
                f"backend 전수: ci.yml 이 {probe!r} 만 바뀐 PR 에서 안 돈다 (run=false) — "
                f"{backend_dir.name} 은 app/main.py 가 있는 backend 인데 FILTER_PATTERNS 에 없다. "
                "그 서비스만 고친 PR 에서 계약 검증·standalone 테스트가 통째로 skipped 된다"
            )

    # ⑥ 필터 밖 그물 — 경로 필터가 없는 워크플로가 실행해야 한다
    unfiltered_workflows = sorted(wf for wf in WORKFLOW_DIR.glob("*.yml") if wf.name not in FILTERED_WORKFLOWS)
    for script, reason in UNFILTERED_NETS:
        checked += 1
        if not (REPO_ROOT / script).is_file():
            failures.append(f"필터 밖 그물: {script} 가 실재하지 않는다 — 목록이 낡았다 ({reason})")
            continue
        hosts = [wf.name for wf in unfiltered_workflows if script in wf.read_text(encoding="utf-8")]
        if not hosts:
            failures.append(
                f"필터 밖 그물: {script} 를 경로 필터 없는 워크플로가 실행하지 않는다 — {reason}. "
                f"필터가 있는 워크플로({', '.join(FILTERED_WORKFLOWS)})에 두면 그 그물이 지켜야 할 "
                "바로 그 PR 클래스에서 skip 된다 (#331)"
            )

    print(
        f"케이스 {checked}건 검사 · 워크플로 {len(FILTERED_WORKFLOWS)}개 · 패턴 {total_patterns}건 · "
        f"필수 트리거 {len(REQUIRED_TRIGGERS)}건 · 필터 밖 그물 {len(UNFILTERED_NETS)}건 · "
        f"backend 폴더 {len(backend_dirs)}개"
    )
    if checked == 0 or total_patterns == 0:
        _fail("검사 0건 — 통과가 아니라 실패다 (fail-closed)")
        return 1
    if failures:
        for f in failures:
            _fail(f)
        print(f"실패 {len(failures)}건 / {checked}건")
        return 1
    print("모든 케이스 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
