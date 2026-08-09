"""required 게이트 판정 — head SHA 의 `test: ` 체크런을 전수로 판다 (stdlib 전용, fail-closed).

## 왜 있나

테스트를 개별로 required 로 걸면 pending 창이 잡 수만큼 생긴다. `review-gate.yml` 머리의
「Orca 판정 규칙」 실측대로 pending 이 하나만 있어도 머지 버튼이 잠기므로, 전부를 대표하는
잡 **하나**만 required 로 건다. `repo-scans.yml` 은 경로 필터가 없어 모든 PR 에서 도므로
그 게이트의 자리다.

## 왜 `needs:` 가 아니라 체크런 조회인가

`needs:` 는 **같은 워크플로 안**만 묶는다. 그러면 게이트는 `repo-scans.yml` 의 3종만 대표하고
`ci.yml` 7종·`frontend-ci.yml` 3종은 대표하지 못한다. 지금 그 열을 보는 것은
`merge-router.yml` 의 전수 초록 게이트인데, 그 파일은 이 재설계(#23 Task 8)가 지운다 —
지운 순간 자동 머지가 backend·frontend 테스트를 안 보고 머지하게 된다. 그래서 판정 근거를
`merge-router` 와 같은 것(head SHA 의 `test: ` 접두 체크런 전수)으로 맞춘다.

## 판정 규칙 (merge-router.yml 의 전수 초록 게이트와 동일)

1. head SHA 의 체크런에서 `test: ` 접두만 고른다
2. **자기 자신(`test: gate`)은 뺀다** — 안 빼면 자기 체크가 `in_progress` 로 잡혀 영영
   초록이 안 된다 (게이트가 스스로를 기다리는 교착)
3. 같은 이름이 여러 번 있으면(재실행) **id 가 가장 큰 것**만 본다
4. 전부 `completed` 이고 conclusion 이 `success` 또는 `skipped` 여야 한다
5. **개수가 하한 이상**이어야 한다 — 0건이 「위반 없음」으로 읽히는 구멍을 막는다.
   조회 실패도 0건으로 떨어져 여기 걸린다 (fail-closed)

## 종료 코드

  · `0` 통과 · `1` 실패 · `2` 아직 미완 (호출자가 다시 조회해야 한다)

`--final` 을 주면 미완도 실패로 판정한다 — 대기 한도를 넘긴 호출자가 쓴다.

    gh api "repos/$REPO/commits/$SHA/check-runs?per_page=100" --paginate \
      --jq '.check_runs[] | {id, name, status, conclusion}' | python3 scripts/verify_upstream_gate.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
GATE_WORKFLOW = WORKFLOW_DIR / "repo-scans.yml"

# 게이트 잡의 id 와 체크 이름. 이름은 워크플로의 `name:` 과 **글자 그대로** 같아야 한다 —
# 어긋나면 게이트가 자기 자신을 못 걸러 스스로를 기다린다. 아래 check_structure 가 대조한다.
GATE_JOB_ID = "gate"
SELF_CHECK_NAME = "test: gate"
CHECK_NAME_PREFIX = "test: "

# 통과로 세는 conclusion. `neutral` 은 GitHub 이 required check 통과로 세지만 여기서는
# 빼 둔다 — merge-router.yml 의 전수 초록 게이트와 같은 기준을 쓴다.
PASSING_CONCLUSIONS = ("success", "skipped")

# 게이트가 대표해야 하는 `test: ` 체크의 하한 (자기 자신 제외).
# 2026-08-09 실측: main 커밋의 체크런 13개 = ci.yml 7 + frontend-ci.yml 3 + repo-scans.yml 3.
# 세 워크플로 모두 `pull_request: {}` 와 `push: [main]` 에서 돌고 경로 필터는 잡 레벨이라
# (#23 Task 4) 건너뛴 잡도 `skipped` 체크런을 남긴다 — 즉 이 수는 이벤트에 안 흔들린다.
# 잡을 정당하게 지웠다면 이 하한도 함께 내린다. 조용히 넘어가는 대신 시끄럽게 실패하는 것이
# 의도다 (verify_ci_check_coverage.py 의 축별 하한과 같은 규율).
MIN_TEST_CHECKS = 13

# 워크플로 파싱에 쓰는 최소 문법 — verify_ci_check_coverage.py 와 같은 들여쓰기 규약.
TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):")
JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_][A-Za-z0-9_-]*):\s*$")
JOB_ATTR = re.compile(r"^    ([A-Za-z0-9_-]+):\s*(.*)$")


def _fail(msg: str) -> None:
    print(f"::error::{msg}")


# ── 입력 파싱 ────────────────────────────────────────────────────────────────


def parse_check_runs(text: str) -> list[dict]:
    """체크런 JSON 을 레코드 목록으로 읽는다.

    받는 모양 셋을 전부 받는다 — API 응답 원문(`{"check_runs": [...]}`) · 배열 ·
    `gh --jq` 가 내는 줄 단위 JSON. 읽지 못하면 **빈 목록**이다: 조회 실패를 0건으로
    떨어뜨려 하한 검사에 걸리게 하는 것이 fail-closed 다.
    """
    text = (text or "").strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        # API 응답 원문이면 `check_runs`, 줄이 하나뿐인 gh --jq 출력이면 그 자체가 레코드다.
        # 둘 다 아니면(예: `{"message": "Not Found"}`) 0건 — 조회 실패 취급이다.
        runs = parsed.get("check_runs")
        if isinstance(runs, list):
            return [r for r in runs if isinstance(r, dict)]
        return [parsed] if "name" in parsed else []
    if isinstance(parsed, list):
        return [r for r in parsed if isinstance(r, dict)]
    if parsed is not None:
        return []

    records: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _run_id(record: dict) -> int:
    try:
        return int(record.get("id") or 0)
    except (TypeError, ValueError):
        return 0


def latest_by_name(records: list[dict]) -> dict[str, dict]:
    """`test: ` 접두 체크런을 이름별로 모으되 **id 가 가장 큰 것**만 남긴다 (재실행 대비)."""
    latest: dict[str, dict] = {}
    for record in records:
        name = record.get("name")
        if not isinstance(name, str) or not name.startswith(CHECK_NAME_PREFIX):
            continue
        if name not in latest or _run_id(record) >= _run_id(latest[name]):
            latest[name] = record
    return latest


# ── 판정 ─────────────────────────────────────────────────────────────────────


def judge(
    records: list[dict],
    *,
    self_name: str = SELF_CHECK_NAME,
    minimum: int = MIN_TEST_CHECKS,
    final: bool = False,
) -> tuple[str, list[str], list[str]]:
    """(상태, 사람이 읽을 줄, 문제 목록) 을 낸다. 상태는 pass·fail·wait 중 하나.

    `final` 이면 미완(wait)도 실패로 접는다 — 대기 한도를 넘긴 호출자용.
    """
    latest = latest_by_name(records)
    self_seen = self_name in latest
    latest.pop(self_name, None)

    lines = [
        f"체크런 {len(records)}건 수집 · `{CHECK_NAME_PREFIX}` 접두 {len(latest)}건 "
        f"(자기 자신 `{self_name}` 제외 {'1' if self_seen else '0'}건, 하한 {minimum})"
    ]
    for name in sorted(latest):
        record = latest[name]
        lines.append(
            f"  · {name}: {record.get('status')}/{record.get('conclusion') or '-'}"
        )

    problems: list[str] = []
    pending = [n for n, r in latest.items() if r.get("status") != "completed"]
    bad = [
        n
        for n, r in latest.items()
        if r.get("status") == "completed"
        and r.get("conclusion") not in PASSING_CONCLUSIONS
    ]

    # 실패는 기다려도 안 바뀐다 — 미완이 남아 있어도 즉시 빨간불로 접는다.
    for name in sorted(bad):
        record = latest[name]
        problems.append(
            f"테스트 체크 `{name}` 의 conclusion 이 `{record.get('conclusion') or '-'}` 입니다 — "
            f"통과는 {' 또는 '.join(f'`{c}`' for c in PASSING_CONCLUSIONS)} 뿐입니다"
        )
    if problems:
        return "fail", lines, problems

    if pending:
        detail = ", ".join(f"`{n}`" for n in sorted(pending))
        if not final:
            return (
                "wait",
                lines,
                [f"아직 끝나지 않은 테스트 체크 {len(pending)}건: {detail}"],
            )
        problems.append(
            f"대기 한도 안에 끝나지 않은 테스트 체크 {len(pending)}건: {detail}"
        )

    if len(latest) < minimum:
        message = (
            f"테스트 체크가 {len(latest)}건 — 하한 {minimum}건 미만입니다. "
            "검사가 아예 안 돌았거나(워크플로 미트리거·조회 실패) 잡이 사라졌습니다. "
            "정당한 삭제라면 MIN_TEST_CHECKS 도 함께 내리세요"
        )
        if not problems and not final:
            return "wait", lines, [message]
        problems.append(message)

    if problems:
        return "fail", lines, problems
    return "pass", lines, problems


# ── 구조 대조 — 자기 제외 이름과 하한이 워크플로와 어긋나지 않는지 ──────────────


def parse_jobs(text: str) -> dict[str, dict]:
    """워크플로 YAML 에서 `jobs:` 아래 잡의 `name` 을 읽는다.

    러너·루트에 PyYAML 이 없어 들여쓰기 규약만으로 읽는다. 형식이 깨지면 잡 0건이 되어
    아래 fail-closed 검사에 걸린다.
    """
    jobs: dict[str, dict] = {}
    top: str | None = None
    job: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m = TOP_KEY.match(line)
        if m:
            top, job = m.group(1), None
            continue
        if top != "jobs":
            continue

        m = JOB_HEADER.match(line)
        if m:
            job = m.group(1)
            jobs[job] = {"name": None}
            continue
        if job is None:
            continue

        m = JOB_ATTR.match(line)
        if m and m.group(1) == "name":
            jobs[job]["name"] = m.group(2).strip().strip("'\"")
    return jobs


def collect_test_job_names(workflow_dir: Path) -> dict[str, str]:
    """레포 워크플로에 선언된 `test: ` 잡의 체크 이름 → 워크플로 파일명."""
    found: dict[str, str] = {}
    for wf in sorted(workflow_dir.glob("*.yml")):
        for spec in parse_jobs(wf.read_text(encoding="utf-8")).values():
            name = spec.get("name") or ""
            if name.startswith(CHECK_NAME_PREFIX):
                found[name] = wf.name
    return found


def check_structure(
    gate_jobs: dict[str, dict],
    test_job_names: dict[str, str],
    *,
    minimum: int = MIN_TEST_CHECKS,
) -> list[str]:
    """게이트가 자기를 걸러낼 이름과 대표할 개수를 워크플로와 대조한다.

    런타임 판정만 두면 두 가지가 조용히 어긋난다: ① 게이트 잡 이름을 바꾸면 자기 제외가
    빗나가 게이트가 스스로를 기다린다(대기 한도까지 갔다가 빨간불 — 원인은 안 보인다),
    ② 테스트 잡을 지우면 하한 미만이 되는데 그 사실을 **PR 이 돌기 전엔** 모른다.
    """
    if not gate_jobs:
        return [
            "워크플로에서 잡을 0건 읽었습니다 — 파싱이 깨졌거나 파일이 사라졌습니다"
        ]

    problems: list[str] = []
    gate = gate_jobs.get(GATE_JOB_ID)
    if gate is None:
        problems.append(
            f"게이트 잡 `{GATE_JOB_ID}` 이 없습니다 — 읽은 잡: {', '.join(sorted(gate_jobs))}"
        )
    elif gate["name"] != SELF_CHECK_NAME:
        problems.append(
            f"게이트의 체크 이름이 {gate['name']!r} 인데 판정부는 {SELF_CHECK_NAME!r} 를 "
            "제외합니다 — 어긋나면 게이트가 자기 자신을 기다립니다"
        )

    if not SELF_CHECK_NAME.startswith(CHECK_NAME_PREFIX):
        problems.append(
            f"게이트 이름 {SELF_CHECK_NAME!r} 이 `{CHECK_NAME_PREFIX}` 접두가 아닙니다 — "
            "merge-router.yml 의 전수 초록 게이트가 그 접두로 판정 잡을 고릅니다"
        )

    represented = {n: wf for n, wf in test_job_names.items() if n != SELF_CHECK_NAME}
    if len(represented) < minimum:
        problems.append(
            f"워크플로에 선언된 `{CHECK_NAME_PREFIX}` 잡이 {len(represented)}개 "
            f"(자기 자신 제외) — 하한 {minimum}개 미만입니다. 잡을 지웠다면 "
            "MIN_TEST_CHECKS 도 함께 내리세요"
        )
    for name in sorted(n for n in represented if "${{" in n):
        problems.append(
            f"테스트 잡 이름 {name!r} 이 식을 담고 있습니다 — 매트릭스 잡은 체크 이름이 "
            "실행 시점에 갈라져 선언 수와 체크런 수가 어긋납니다"
        )
    return problems


def main(argv: list[str]) -> int:
    final = "--final" in argv[1:]

    gate_jobs = (
        parse_jobs(GATE_WORKFLOW.read_text(encoding="utf-8"))
        if GATE_WORKFLOW.is_file()
        else {}
    )
    test_job_names = (
        collect_test_job_names(WORKFLOW_DIR) if WORKFLOW_DIR.is_dir() else {}
    )
    structure_problems = check_structure(gate_jobs, test_job_names)

    print(
        f"구조: 워크플로에 선언된 `{CHECK_NAME_PREFIX}` 잡 {len(test_job_names)}개 "
        f"(게이트 포함) · 하한 {MIN_TEST_CHECKS}개"
    )
    for name in sorted(test_job_names):
        mark = " (게이트 — 자기 제외)" if name == SELF_CHECK_NAME else ""
        print(f"  · {name} — {test_job_names[name]}{mark}")
    for problem in structure_problems:
        _fail(problem)

    records = parse_check_runs(sys.stdin.read() if not sys.stdin.isatty() else "")
    state, lines, problems = judge(records, final=final)
    print()
    for line in lines:
        print(line)

    if structure_problems:
        for problem in problems:
            _fail(problem)
        print(
            f"판정: 게이트 실패 — 구조 {len(structure_problems)}건 · 결과 {len(problems)}건"
        )
        return 1

    if state == "wait":
        for problem in problems:
            print(f"::notice::{problem}")
        print(f"판정: 대기 — {problems[0] if problems else '미완'}")
        return 2

    for problem in problems:
        _fail(problem)
    if state == "pass":
        represented = latest_by_name(records)
        represented.pop(SELF_CHECK_NAME, None)
        print(f"판정: 테스트 체크 {len(represented)}개 전수 초록 — 게이트 초록")
        return 0
    print(f"판정: 게이트 실패 — 결과 {len(problems)}건")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
