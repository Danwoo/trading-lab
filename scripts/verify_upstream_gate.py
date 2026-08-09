"""required 게이트 판정 — 상류 잡을 체크 하나로 대표한다 (stdlib 전용, fail-closed).

## 왜 있나

테스트를 개별로 required 로 걸면 pending 창이 잡 수만큼 생긴다. `review-gate.yml` 머리의
「Orca 판정 규칙」이 실측한 대로 `status != completed` 는 전부 pending 이고, pending 이 하나만
있어도 머지 버튼이 잠긴다. 그래서 상류 잡 전부를 대표하는 잡 **하나**만 required 로 건다.
`repo-scans.yml` 은 경로 필터가 없어 모든 PR 에서 도므로 게이트의 자리다.

## 무엇을 판정하나

1. **구조** — 게이트 잡의 `needs` 가 같은 워크플로의 나머지 잡을 **전부** 담는가.
   담지 못하면 게이트는 안 담긴 잡을 대표하지 않으면서 대표하는 얼굴로 초록이 된다.
   잡을 하나 더 넣고 `needs` 를 안 고치는 것이 이 구멍의 유일한 입구라 여기서 막는다.
   게이트의 체크 이름이 `test: ` 접두인지도 같이 본다 — `merge-router.yml` 의 전수 초록
   게이트가 그 접두로 판정 잡을 고른다.
2. **결과** — `needs` 컨텍스트의 잡 결과가 전부 `success` 또는 `skipped` 인가.
   GitHub 은 required check 판정에서 `skipped` 를 통과로 세므로(경로 필터를 잡 레벨로
   내린 근거) 게이트도 같은 기준을 쓴다.

**상류 0건은 통과가 아니다.** `needs` 가 비면 판정할 대상이 없어 조용히 초록이 되는데,
이 레포가 반복해서 데인 클래스가 정확히 그것이다.

실행 (워크플로): `NEEDS_JSON` 에 `${{ toJSON(needs) }}` 를 넣고 부른다.
실행 (로컬): `python3 scripts/verify_upstream_gate.py` — 상류 0건이라 **실패하는 것이 정상**이다.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "repo-scans.yml"

# 게이트 잡의 id 와 체크 이름 접두. 접두는 merge-router.yml 과의 lockstep 이다.
GATE_JOB_ID = "gate"
CHECK_NAME_PREFIX = "test: "

# GitHub 이 required check 통과로 세는 결과. `neutral` 도 통과로 세지만 잡 결과에는
# 나타나지 않는 값이라(잡은 success·failure·cancelled·skipped 만 낸다) 넣지 않는다.
PASSING_RESULTS = ("success", "skipped")

# 워크플로 파싱에 쓰는 최소 문법 — verify_ci_check_coverage.py 와 같은 들여쓰기 규약.
TOP_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):")
JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_][A-Za-z0-9_-]*):\s*$")
JOB_ATTR = re.compile(r"^    ([A-Za-z0-9_-]+):\s*(.*)$")
LIST_ITEM = re.compile(r"^      -\s*(\S+)\s*$")


def _fail(msg: str) -> None:
    print(f"::error::{msg}")


def parse_jobs(text: str) -> dict[str, dict]:
    """워크플로 YAML 에서 `jobs:` 아래 잡의 `name`·`needs` 를 읽는다.

    러너·루트에 PyYAML 이 없어 들여쓰기 규약만으로 읽는다. 형식이 깨지면 잡 0건이 되어
    아래 fail-closed 검사에 걸린다.
    """
    jobs: dict[str, dict] = {}
    top: str | None = None
    job: str | None = None
    attr: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m = TOP_KEY.match(line)
        if m:
            top, job, attr = m.group(1), None, None
            continue
        if top != "jobs":
            continue

        m = JOB_HEADER.match(line)
        if m:
            job, attr = m.group(1), None
            jobs[job] = {"name": None, "needs": []}
            continue
        if job is None:
            continue

        m = LIST_ITEM.match(line)
        if m and attr == "needs":
            jobs[job]["needs"].append(m.group(1).strip("'\""))
            continue

        m = JOB_ATTR.match(line)
        if m:
            attr, value = m.group(1), m.group(2).strip()
            if attr == "name":
                jobs[job]["name"] = value.strip("'\"")
            elif attr == "needs" and value:
                jobs[job]["needs"] = [
                    t.strip(" '\"") for t in value.strip("[]").split(",") if t.strip()
                ]
    return jobs


def check_structure(jobs: dict[str, dict]) -> list[str]:
    """게이트가 같은 워크플로의 상류 잡을 빠짐없이 대표하는지 본다."""
    if not jobs:
        return [
            "워크플로에서 잡을 0건 읽었습니다 — 파싱이 깨졌거나 파일이 사라졌습니다"
        ]

    problems: list[str] = []
    gate = jobs.get(GATE_JOB_ID)
    if gate is None:
        return [
            f"게이트 잡 `{GATE_JOB_ID}` 이 없습니다 — 읽은 잡: {', '.join(sorted(jobs))}"
        ]

    name = gate["name"] or ""
    if not name.startswith(CHECK_NAME_PREFIX):
        problems.append(
            f"게이트 체크 이름이 {name!r} 입니다 — `{CHECK_NAME_PREFIX}` 접두여야 합니다. "
            "merge-router.yml 의 전수 초록 게이트가 그 접두로 판정 잡을 고릅니다"
        )

    upstream = set(jobs) - {GATE_JOB_ID}
    if not upstream:
        problems.append(
            "같은 워크플로에 상류 잡이 0건입니다 — 게이트가 대표할 것이 없습니다"
        )
        return problems

    declared = set(gate["needs"])
    for missing in sorted(upstream - declared):
        problems.append(
            f"잡 `{missing}` 이 게이트의 `needs` 에 없습니다 — "
            "게이트가 그 잡을 대표하지 않으면서 초록이 됩니다"
        )
    for stale in sorted(declared - upstream):
        problems.append(
            f"게이트의 `needs` 에 있는 `{stale}` 이 이 워크플로의 잡이 아닙니다"
        )
    return problems


def judge_results(raw: str) -> tuple[list[tuple[str, str]], list[str]]:
    """`needs` 컨텍스트 JSON 을 읽어 (잡별 결과, 문제 목록) 을 낸다."""
    text = (raw or "").strip()
    if not text:
        return [], ["상류 잡 결과를 0건 받았습니다 (`NEEDS_JSON` 이 비었습니다)"]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return [], [f"`NEEDS_JSON` 을 JSON 으로 읽지 못했습니다: {exc}"]

    if not isinstance(parsed, dict):
        return [], [
            f"`NEEDS_JSON` 이 객체가 아닙니다 ({type(parsed).__name__}) — "
            "`toJSON(needs)` 의 산출물이 아닙니다"
        ]
    if not parsed:
        return [], [
            "상류 잡 결과가 0건입니다 — `needs` 가 비었습니다. "
            "검사할 것이 없어서 초록이 되는 것은 통과가 아닙니다"
        ]

    results: list[tuple[str, str]] = []
    problems: list[str] = []
    for job in sorted(parsed):
        entry = parsed[job]
        result = entry.get("result") if isinstance(entry, dict) else None
        if not isinstance(result, str) or not result:
            results.append((job, "?"))
            problems.append(f"잡 `{job}` 의 `result` 를 읽지 못했습니다: {entry!r}")
            continue
        results.append((job, result))
        if result not in PASSING_RESULTS:
            problems.append(
                f"상류 잡 `{job}` 의 결과가 `{result}` 입니다 — "
                f"통과는 {' 또는 '.join(f'`{r}`' for r in PASSING_RESULTS)} 뿐입니다"
            )
    return results, problems


def main() -> int:
    ok = True

    if not GATE_WORKFLOW.is_file():
        _fail(f"게이트 워크플로가 없습니다: {GATE_WORKFLOW}")
        return 1

    jobs = parse_jobs(GATE_WORKFLOW.read_text(encoding="utf-8"))
    structure_problems = check_structure(jobs)
    print(
        f"구조: {GATE_WORKFLOW.relative_to(REPO_ROOT)} 에서 잡 {len(jobs)}개 읽음 "
        f"(게이트 1 + 상류 {max(len(jobs) - 1, 0)})"
    )
    for job in sorted(jobs):
        mark = " (게이트)" if job == GATE_JOB_ID else ""
        print(f"  · {job}{mark}")
    if structure_problems:
        ok = False
        for p in structure_problems:
            _fail(p)

    results, result_problems = judge_results(os.environ.get("NEEDS_JSON", ""))
    print(f"\n결과: 상류 잡 {len(results)}개")
    for job, result in results:
        print(f"  · {job}: {result}")
    if result_problems:
        ok = False
        for p in result_problems:
            _fail(p)

    print()
    if ok:
        print(f"판정: 상류 잡 {len(results)}개 전부 통과 — 게이트 초록")
        return 0
    print(
        f"판정: 게이트 실패 — 구조 {len(structure_problems)}건 · 결과 {len(result_problems)}건"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
