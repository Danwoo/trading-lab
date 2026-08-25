"""CI 가 레포의 검증 단위를 하나도 빠뜨리지 않는지 대조한다 — fail-closed (stdlib 전용).

## 왜 있나

이 레포는 "검증은 있는데 CI 가 안 돌린다"로 반복해서 데었다 (#241 · #252 · #269 · #290 ·
#302 · #335 — 전부 같은 부류다: **대상을 손으로 적은 목록·경로로 지정했는데 그 지정이
현실과 어긋나도 아무 신호가 없다**). 종전 처방은 매번 "빠진 것을 찾아 잡을 하나 더 추가"
였고, 그래서 잡이 36개까지 늘었다. 인스턴스만 고치고 클래스를 남긴 것이다.

이 스크립트가 클래스를 닫는다: **레포에 실재하는 검증 단위 목록(파일시스템 글롭)** 과
**워크플로가 실제로 실행하는 것(YAML 의 run 명령 파싱)** 을 대조해, 안 도는 것이 하나라도
있으면 실패한다. 새 `verify_*.py`·`tests/test_*.py` 를 추가하면 배선 없이는 CI 가 빨개진다.

## 무엇을 대조하나

1. **글롭 단위** — 파일시스템에서 찾는다. 전부 실행돼야 한다. 축은 `INVENTORY_AXES` 참조
   (`*/scripts/verify_*.py` · 루트 `scripts/verify_*.{py,mjs}` · `*/tests/test_*.py` ·
   `frontend/scripts/check-*.js`). **축마다 개별 하한**이 걸려 있다 — 아래 「축별 fail-closed」.
2. **명명 명령** — 파일 하나로 환원되지 않는 검사(린터·타입체커·npm 스크립트·alembic).
   글롭이 불가능하므로 이름 목록으로 두되, **하나라도 워크플로에서 사라지면 실패**한다.

## 축별 fail-closed (#402)

인벤토리는 **글롭 목록**으로 대상을 잡는다. fail-closed 를 합계 0건에만 걸면 **목록의 축 하나가
통째로 사라져도 나머지가 0이 아니라 조용히 초록**이다 — 그리고 그 순간 이 스크립트는 자기가
막으려던 바로 그 클래스("검사가 있는데 안 돈다")를 스스로 저지른다.

실증(2026-08-06): `*/tests` 축을 없는 경로로 바꾸고 **동시에** ci.yml 에서 multi-agent 의
`run_standalone_tests.py tests` 스텝을 지웠다 — 테스트 15개가 CI 에서 통째로 빠진 진짜 위반인데
`미배선 0건 / EXIT=0` 으로 통과했다(인벤토리만 75 → 40 으로 줄었다).

그래서 축마다 **기대 하한**을 선언하고 실제 수를 출력에 남긴다. 파일을 정당하게 지웠다면 하한도
같이 내린다 — 조용히 넘어가는 대신 시끄럽게 실패하는 것이 의도다.

## 커버리지 판정

워크플로의 `run:` 블록을 읽어 다음을 커버로 친다:
  · `run_verify_scripts.py <dir> [--skip N]`  → `<cwd>/<dir>/verify_*.py` 전부 (skip 제외)
  · `run_standalone_tests.py <dir>`           → `<cwd>/<dir>/test_*.py` 전부
  · 명령줄에 등장하는 실재 파일 경로          → 그 파일
`working-directory:`(스텝 우선, 없으면 잡 defaults)로 상대 경로를 푼다.

`--skip` 된 파일은 **다른 잡에서 실행돼야** 커버로 인정된다 — 제외했는데 아무도 안 돌리면
그대로 미배선이다.

## pre-commit 훅 ↔ CI 대조 (#331 계열의 같은 클래스)

위 두 축은 **파일과 명명 명령**만 본다. 그래서 `.pre-commit-config.yaml` 이 거는 검사가
CI 에 통째로 없어도 조용히 초록이었다 — 실측: `ruff format` 은 워크플로 어디에도 없었고,
`ruff check` 는 두 서비스의 `app/` 만 봤다. 그 사이로 `scripts/verify_stage_claims.py` 의
포맷 드리프트가 main 에 앉아 있었다.

`PRECOMMIT_PARITY` 가 훅 하나하나에 CI 대응을 못박는다. 훅을 새로 추가하면 이 표에도
적어야 하고(안 적으면 실패), 표에만 있고 훅이 사라져도 실패한다(낡은 표 차단).
CI 대응이 **없는 것이 옳은** 훅은 `LOCAL_ONLY` 로 이유와 함께 선언한다 — 빠뜨린 것과
일부러 안 건 것이 코드에서 갈린다.

## 예외 (라이브러리 — 검사 단위가 아님)

`EXEMPT` 에 이유와 함께 명시한다. 예외 항목이 실재하지 않으면 실패한다(낡은 예외 차단).

실행: `python3 scripts/verify_ci_check_coverage.py`
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
PRECOMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"

# 검사 단위가 아닌 것 — 이유를 적는다. 실재하지 않으면 실패한다.
EXEMPT: dict[str, str] = {
    "scripts/verify_alembic_head_freshness.py": (
        "판정 함수를 제공하는 라이브러리 — 실행 주체는 backend-service/tests/test_alembic_head_freshness.py 다 (#387)."
    ),
    "frontend/scripts/check-deps-sync.js": (
        "frontend/package.json 의 pretest·predev 훅이 부른다 — `npm test` 스텝이 돌 때 "
        "함께 실행되므로 워크플로에 따로 적지 않는다."
    ),
}

# 인벤토리 축 — (부모 디렉터리 글롭, 그 안의 파일 글롭, 기대 하한).
# **축마다 개별 fail-closed** 다 (#402 — 머리 주석 「축별 fail-closed」). 합계 하나로 묶으면
# 축이 통째로 사라져도 조용하다. 하한은 현재 실측치이며, 파일을 정당하게 지웠다면 함께 내린다.
INVENTORY_AXES: list[tuple[str, str, int]] = [
    ("*/scripts", "verify_*.py", 26),  # 서비스별 계약 검증
    ("scripts", "verify_*.py", 29),  # 루트 계약 검증
    ("scripts", "verify_*.mjs", 2),  # 루트 계약 검증 (node)
    # 루트 실행형 테스트. 이 축이 없던 동안 `scripts/test_public_release_gate.py` 는 배선돼
    # 있었지만 **인벤토리에는 없었다** — 배선을 지워도 이 검사가 초록이었다는 뜻이다. 서비스
    # 쪽 `*/tests` 축이 있는데 루트만 비어 있던 자리이고, 이 스크립트가 막으려는 바로 그
    # 클래스라 채운다 (#23 Task 2).
    ("scripts", "test_*.py", 14),
    ("*/tests", "test_*.py", 35),  # 서비스별 standalone 테스트 (#335)
    ("frontend/scripts", "check-*.js", 5),  # frontend 정적 스캔
    ("frontend/scripts", "generate-*.js", 1),  # 생성물 재현 대조 (--check 모드, #361)
    ("scripts", "generate_*.py", 1),  # 루트 생성물 재현 대조 (--check 모드)
    # 주입 프로브 — 「그 검사가 무엇을 막는지」를 증명하는 자리다. 이 축이 없던 동안
    # `frontend/scripts/injection-probe-devextreme.sh` 는 배선돼 있었지만 **인벤토리에도
    # 인식에도 없었다** — 그 스텝을 `echo skip` 으로 바꿔도 이 검사가 초록이었다(재현함).
    ("frontend/scripts", "injection-probe-*.sh", 1),
]

# 파일 하나로 환원되지 않는 검사. 워크플로 어딘가에 이 문자열이 있어야 한다.
# `ruff check app/` 은 여기 없다 (2026-08-25). 서비스 잡의 그 스텝은 `test: repo` 의
# `verify_python_format.py` 가 `git ls-files` 의 `*.py` **전수**에 같은 검사를 거는 것의
# 진부분집합이었다 — ruff 는 파일마다 최근접 `pyproject.toml` 을 읽으므로 서비스 설정이
# 그대로 적용된다. 유일하게 남던 차이(훅 rev 0.15.13 vs 서비스 잠금 0.16.x)는 훅 rev 를
# 0.16.4 로 올려 없앴고, 레포 전체가 그 판에서 `All checks passed!` 다.
NAMED_COMMANDS: dict[str, str] = {
    "alembic check": "모델 ↔ 마이그레이션 드리프트 (#185)",
    "npm test": "frontend vitest 단위 테스트",
    "npm run test:api-regressions": "frontend 실제 라우트 핸들러 회귀 (#337)",
    "npm run test:db": "deleteUserCascade 실 DB 통합 (#363)",
    "npx eslint .": "frontend 린트 (--fix 없이, #265)",
    "npx tsc --noEmit": "frontend 타입체크 (#265)",
}

# ── pre-commit 훅 ↔ CI 대조표 ────────────────────────────────────────────────
# 값은 (대응, 근거) 다. 대응이 파일 경로면 그 파일이 어느 워크플로에서든 실행돼야 하고,
# 그 밖의 문자열이면 워크플로 run 블록 원문에 그대로 있어야 한다.
# `LOCAL_ONLY` 는 CI 대응이 **없는 것이 옳은** 훅이다 — 이유를 반드시 적는다.
LOCAL_ONLY = "LOCAL_ONLY"

PRECOMMIT_PARITY: dict[str, tuple[str, str]] = {
    "no-commit-to-branch": (
        LOCAL_ONLY,
        "main 직접 커밋 차단은 서버 ruleset `main protection` 이 한다 — CI 는 이미 PR 만 본다.",
    ),
    "gitleaks": (
        "detect --no-git --redact --source .",
        "repo-scans.yml `test: repo-lint` 이 훅과 같은 버전으로 트리 전수를 스캔한다.",
    ),
    "ruff-check": (
        "scripts/verify_python_format.py",
        "ci.yml 의 `ruff check app/` 은 두 서비스만 본다 — 레포 전수는 이 스크립트가 본다.",
    ),
    "ruff-format": (
        "scripts/verify_python_format.py",
        "CI 에 `ruff format` 이 아예 없던 자리 — 이 스크립트가 레포 전수로 본다.",
    ),
    "eslint": ("npx eslint .", "frontend-ci.yml `test: frontend` (--fix 없이, #265)."),
    "tsc": ("npx tsc --noEmit", "frontend-ci.yml `test: frontend` (#265)."),
    "backend-claude-md": (
        "scripts/verify_backend_claude_md.py",
        "ci.yml `test: repo-contracts`.",
    ),
    "vitest": ("npm test", "frontend-ci.yml `test: frontend`."),
    "mcp-lockstep": (
        "multi-agent-service/scripts/verify_mcp_lockstep.py",
        "ci.yml `test: multi-agent` 의 run_verify_scripts.py 스위트에 포함된다.",
    ),
}

# 훅을 0건 읽으면 대조가 통째로 사라진다 — 하한을 걸고 실측 수를 출력에 남긴다.
PRECOMMIT_HOOK_MINIMUM = 9

# 대응 문자열이 「파일 경로」인지 「명령 조각」인지 가르는 기준. 파일시스템을 안 보므로
# 테스트에서도 같은 판정이 나온다.
_PATH_SUFFIXES = (".py", ".mjs", ".js", ".sh")


# 워크플로 파싱에 쓰는 최소 문법 — 잡 헤더는 들여쓰기 2, 스텝은 '- ' 로 시작한다.
JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_][A-Za-z0-9_-]*):\s*$")
STEP_START = re.compile(r"^(\s*)- ")
WORKDIR = re.compile(r"^\s*working-directory:\s*(\S+)\s*$")


def _fail(msg: str) -> None:
    print(f"::error::{msg}")


class Coverage:
    """워크플로가 실행하는 파일·명령의 집합."""

    def __init__(self) -> None:
        self.files: set[str] = set()  # REPO_ROOT 상대 posix 경로
        self.commands: list[str] = []  # run 블록 원문 (명명 명령 검색용)


def _iter_run_blocks(text: str):
    """(cwd, run 명령 원문) 을 순서대로 낸다.

    cwd 는 스텝의 working-directory, 없으면 잡 defaults.run.working-directory, 없으면 ''.
    YAML 파서 없이(러너·루트에 PyYAML 이 없다) 들여쓰기 규약만으로 읽는다 — 이 레포
    워크플로가 모두 같은 형식을 쓰므로 충분하고, 형식이 깨지면 파싱이 대상 0건이 되어
    아래 fail-closed 검사에 걸린다.
    """
    lines = text.splitlines()
    job_workdir = ""
    step_workdir: str | None = None
    in_defaults = False
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        if JOB_HEADER.match(line):
            job_workdir = ""
            step_workdir = None
            in_defaults = False
            i += 1
            continue

        if re.match(r"^    defaults:\s*$", line):
            in_defaults = True
            i += 1
            continue

        m = WORKDIR.match(line)
        if m:
            if in_defaults:
                job_workdir = m.group(1)
            else:
                step_workdir = m.group(1)
            i += 1
            continue

        sm = STEP_START.match(line)
        if sm and len(sm.group(1)) <= 6:
            # 새 스텝 — 스텝 로컬 working-directory 초기화. defaults 블록도 여기서 끝난다.
            step_workdir = None
            in_defaults = False

        # `defaults: / run: / working-directory:` 안의 `run:` 은 명령이 아니다 — 이것을
        # 명령으로 잘못 읽으면 뒤따르는 working-directory 줄을 삼켜 잡의 cwd 가 통째로
        # 유실된다 (실측: 스위트 잡 7개의 cwd 가 빈 문자열이 됐다).
        rm = None if in_defaults else re.match(r"^(\s*)run:\s*(.*)$", line)
        if rm:
            indent = len(rm.group(1))
            rest = rm.group(2).strip()
            body: list[str] = []
            if rest and rest not in {"|", ">", "|-", ">-", "|+"}:
                body.append(rest)
            else:
                j = i + 1
                while j < n:
                    nxt = lines[j]
                    if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= indent:
                        break
                    body.append(nxt)
                    j += 1
                i = j - 1
            yield (
                (step_workdir if step_workdir is not None else job_workdir),
                "\n".join(body),
            )

        i += 1


def _resolve(cwd: str, token: str) -> Path | None:
    """run 명령의 토큰을 REPO_ROOT 기준 실재 파일로 푼다 (없으면 None)."""
    if not token or token.startswith("-"):
        return None
    for base in ((REPO_ROOT / cwd) if cwd else REPO_ROOT, REPO_ROOT):
        try:
            candidate = (base / token).resolve()
        except (OSError, ValueError):
            continue
        if candidate.is_file() and REPO_ROOT in candidate.parents:
            return candidate
    return None


def collect_coverage() -> tuple[Coverage, int]:
    cov = Coverage()
    workflows = sorted(WORKFLOW_DIR.glob("*.yml"))
    for wf in workflows:
        text = wf.read_text(encoding="utf-8")
        for cwd, block in _iter_run_blocks(text):
            cov.commands.append(block)
            for raw_line in block.splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                try:
                    tokens = shlex.split(stripped, comments=True)
                except ValueError:
                    tokens = stripped.split()

                # 스위트 러너 — 글롭을 그대로 커버로 편다
                for runner, pattern in (
                    ("run_verify_scripts.py", "verify_*.py"),
                    ("run_standalone_tests.py", "test_*.py"),
                ):
                    if not any(t.endswith(runner) for t in tokens):
                        continue
                    idx = next(i for i, t in enumerate(tokens) if t.endswith(runner))
                    args = tokens[idx + 1 :]
                    positional = [a for a in args if not a.startswith("-")]
                    skips = {args[i + 1] for i, a in enumerate(args) if a == "--skip" and i + 1 < len(args)}
                    if not positional:
                        continue
                    target = (REPO_ROOT / cwd / positional[0]) if cwd else (REPO_ROOT / positional[0])
                    for f in sorted(target.glob(pattern)):
                        if f.name in skips:
                            continue
                        cov.files.add(f.resolve().relative_to(REPO_ROOT).as_posix())

                # 직접 호출 — 실재하는 파일 경로 토큰
                for t in tokens:
                    if not t.endswith((".py", ".mjs", ".js", ".sh")):
                        continue
                    resolved = _resolve(cwd, t)
                    if resolved is not None:
                        cov.files.add(resolved.relative_to(REPO_ROOT).as_posix())
    return cov, len(workflows)


def parse_precommit_hooks(text: str) -> list[str]:
    """`.pre-commit-config.yaml` 의 훅 id 를 선언 순서대로 낸다."""
    return [m.group(1) for m in re.finditer(r"^\s*-\s*id:\s*(\S+)\s*$", text, re.M)]


def check_precommit_parity(
    hook_ids: list[str],
    cov_files: set[str],
    joined_commands: str,
    *,
    table: dict[str, tuple[str, str]] | None = None,
    minimum: int = PRECOMMIT_HOOK_MINIMUM,
) -> tuple[list[str], list[str]]:
    """훅 전수 ↔ CI 대응을 대조한다. (사람이 읽을 줄, 문제 목록) 을 낸다.

    fail-closed 는 세 겹이다: 훅을 0건(또는 하한 미만) 읽으면 실패 · 표에 없는 훅이 있으면
    실패 · 표에만 있고 훅이 사라졌으면 실패. 그리고 대응이 워크플로에 실재하지 않으면 실패다.
    """
    table = PRECOMMIT_PARITY if table is None else table
    lines = [f"pre-commit 훅 {len(hook_ids)}개 (하한 {minimum}) ↔ CI 대조표 {len(table)}개"]
    problems: list[str] = []

    if len(hook_ids) < minimum:
        problems.append(
            f"pre-commit 훅을 {len(hook_ids)}개 읽었습니다 — 하한 {minimum}개 미만입니다. "
            "설정 파일이 사라졌거나 파싱이 깨졌습니다. 훅을 정당하게 지웠다면 "
            "PRECOMMIT_HOOK_MINIMUM 과 PRECOMMIT_PARITY 도 함께 줄이세요."
        )

    for hook in hook_ids:
        entry = table.get(hook)
        if entry is None:
            problems.append(
                f"pre-commit 훅 {hook!r} 이 CI 대조표에 없습니다 — 로컬에서만 도는 검사는 "
                "그 훅을 안 거치는 경로(다른 워커·CI)를 통과시킵니다. "
                "PRECOMMIT_PARITY 에 CI 대응을 적거나, 대응이 없는 것이 옳다면 "
                "LOCAL_ONLY 로 이유와 함께 선언하세요."
            )
            continue
        target, reason = entry
        if target == LOCAL_ONLY:
            lines.append(f"  · {hook}: CI 대응 없음(선언됨) — {reason}")
            continue
        if target.endswith(_PATH_SUFFIXES) and "/" in target:
            covered = target in cov_files
            kind = "파일"
        else:
            covered = target in joined_commands
            kind = "명령"
        lines.append(f"  · {hook}: {kind} {target!r} — {'배선됨' if covered else '미배선'}")
        if not covered:
            problems.append(f"pre-commit 훅 {hook!r} 의 CI 대응({kind} {target!r})이 워크플로에 없습니다 — {reason}")

    for hook in sorted(set(table) - set(hook_ids)):
        problems.append(f"CI 대조표에 있는 훅 {hook!r} 이 .pre-commit-config.yaml 에 없습니다 — 표가 낡았습니다")

    return lines, problems


def axis_label(parent_glob: str, child_glob: str) -> str:
    return f"{parent_glob}/{child_glob}"


def collect_inventory() -> dict[str, list[str]]:
    """레포에 실재하는 검증 단위를 **축별로** 낸다 (REPO_ROOT 상대 posix 경로).

    축을 합쳐서 돌려주지 않는 것이 핵심이다 — 합치면 축 하나가 0건이 돼도 총합에 묻힌다
    (#402). 호출자가 축별 하한을 검사한 뒤 합집합을 만든다.
    """
    per_axis: dict[str, list[str]] = {}
    for parent_glob, child_glob, _minimum in INVENTORY_AXES:
        found: set[str] = set()
        for parent in sorted(REPO_ROOT.glob(parent_glob)):
            if not parent.is_dir():
                continue
            for f in parent.glob(child_glob):
                if f.is_file():
                    found.add(f.relative_to(REPO_ROOT).as_posix())
        per_axis[axis_label(parent_glob, child_glob)] = sorted(found)
    return per_axis


def main() -> int:
    if not WORKFLOW_DIR.is_dir():
        _fail(f"워크플로 디렉터리가 없습니다: {WORKFLOW_DIR}")
        return 1

    cov, workflow_count = collect_coverage()
    inventory_by_axis = collect_inventory()
    inventory = sorted({u for files in inventory_by_axis.values() for u in files})

    print(f"워크플로 {workflow_count}개 파싱 · run 블록 {len(cov.commands)}개")
    print(f"레포의 검증 단위 {len(inventory)}개 · CI 가 실행하는 파일 {len(cov.files)}개")
    print("인벤토리 축별 수집 (축마다 하한 — #402):")
    for parent_glob, child_glob, minimum in INVENTORY_AXES:
        label = axis_label(parent_glob, child_glob)
        print(f"  · {label}: {len(inventory_by_axis[label])}건 (하한 {minimum})")
    print()

    # fail-closed: 아무것도 안 봤으면 통과가 아니다.
    if workflow_count == 0 or not cov.commands:
        _fail("워크플로 또는 run 블록을 0건 수집했습니다 — 파싱이 깨졌거나 파일이 사라졌습니다")
        return 1
    if not inventory:
        _fail("검증 단위를 0건 수집했습니다 — 글롭이 현실과 어긋났습니다")
        return 1

    ok = True

    # 축별 fail-closed — 축 하나가 통째로 사라지면 그 축의 미배선이 전부 안 보인다 (#402).
    # 합계 0건 검사는 이 구멍을 못 막는다: 나머지 축이 살아 있으면 총합은 0이 아니다.
    for parent_glob, child_glob, minimum in INVENTORY_AXES:
        label = axis_label(parent_glob, child_glob)
        actual = len(inventory_by_axis[label])
        if actual < minimum:
            _fail(
                f"인벤토리 축 {label} 가 {actual}건 — 기대 하한 {minimum}건 미만입니다. "
                "글롭이 현실과 어긋났거나(디렉터리 이동·리네임) 검증 단위가 사라졌습니다. "
                "정당한 삭제라면 INVENTORY_AXES 의 하한도 함께 내리세요."
            )
            ok = False

    # 예외 목록이 낡지 않았는지 (지정한 파일이 실재해야 한다)
    for path, reason in sorted(EXEMPT.items()):
        if not (REPO_ROOT / path).is_file():
            _fail(f"EXEMPT 에 적힌 파일이 없습니다: {path} — 예외 목록이 낡았습니다 ({reason})")
            ok = False

    missing = [u for u in inventory if u not in cov.files and u not in EXEMPT]
    if missing:
        _fail(f"어느 워크플로에서도 실행되지 않는 검증 단위 {len(missing)}건:")
        for u in missing:
            _fail(f"  · {u}")
        _fail("스위트 잡에 배선하거나, 검사 단위가 아니라면 EXEMPT 에 이유와 함께 적으세요.")
        ok = False

    joined = "\n".join(cov.commands)
    missing_cmds = [c for c in NAMED_COMMANDS if c not in joined]
    if missing_cmds:
        _fail(f"워크플로에서 사라진 명명 검사 {len(missing_cmds)}건:")
        for c in missing_cmds:
            _fail(f"  · {c!r} — {NAMED_COMMANDS[c]}")
        ok = False

    # pre-commit 훅 ↔ CI 대조 — 파일·명명 명령 두 축이 못 보던 자리다.
    if not PRECOMMIT_CONFIG.is_file():
        _fail(f"훅 설정이 없습니다: {PRECOMMIT_CONFIG} — 대조할 목록이 사라졌습니다")
        ok = False
        hook_ids: list[str] = []
    else:
        hook_ids = parse_precommit_hooks(PRECOMMIT_CONFIG.read_text(encoding="utf-8"))
    parity_lines, parity_problems = check_precommit_parity(hook_ids, cov.files, joined)
    print()
    for line in parity_lines:
        print(line)
    for problem in parity_problems:
        _fail(problem)
    if parity_problems:
        ok = False
    print()

    exempt_count = sum(1 for u in inventory if u in EXEMPT)
    print(
        f"판정: 검증 단위 {len(inventory)}건 중 배선 {len(inventory) - len(missing) - exempt_count}건 · "
        f"예외 {exempt_count}건 · 미배선 {len(missing)}건"
    )
    print(f"판정: 명명 검사 {len(NAMED_COMMANDS)}건 중 배선 {len(NAMED_COMMANDS) - len(missing_cmds)}건")
    if ok:
        print("모든 검증 단위가 CI 에 배선돼 있습니다.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
