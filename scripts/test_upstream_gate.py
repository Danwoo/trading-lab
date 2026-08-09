"""required 게이트 판정 회귀 그물 (#23 Task 5) — fail-closed, stdlib 전용.

게이트는 **초록일 때 아무 일도 안 하는 검사**라 죽어도 티가 안 난다. 통과 집합에 한 줄만
더하면(`failure` 를 통과로 세거나, 0건을 통과로 세거나) 그 뒤로는 영영 초록이다.
그래서 판정의 축을 케이스로 못박는다:

  · **자기 제외** — 게이트 자신도 `test: ` 접두 체크다. 안 빼면 자기 체크가 `in_progress`
    로 잡혀 영영 초록이 안 된다. 자기 자신이 섞인 입력에서 판정이 나오는지 판다.
  · **결과** — `success`·`skipped` 만 통과. 미완은 대기(재조회), `--final` 이면 실패.
  · **하한** — 0건·조회 실패·잡 삭제는 전부 실패. 이 자리가 「검사 0건 = 통과」를 막는다.
  · **재실행** — 같은 이름이 여러 번이면 id 가 가장 큰 것만 본다.
  · **구조** — 게이트 잡 이름 ↔ 판정부가 빼는 이름, 선언된 `test: ` 잡 수 ↔ 하한.
    실제 워크플로로도 한 번 돌린다 (합성 픽스처만 보면 배선이 끊겨도 초록이다).

**fail-closed**: 케이스를 하한보다 적게 모으면 실패한다.

    python3 scripts/test_upstream_gate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_upstream_gate as gate  # noqa: E402

# 케이스가 이보다 적으면 수집이 깨진 것이다 (「0건 통과」 방지).
MIN_JUDGE_CASES = 18
MIN_PARSE_CASES = 6
MIN_STRUCTURE_CASES = 6

SELF = gate.SELF_CHECK_NAME

failures: list[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        failures.append(f"{label}{(' — ' + detail) if detail else ''}")


def _run(
    name: str, conclusion: str | None, *, run_id: int = 1, status: str = "completed"
) -> dict:
    return {"id": run_id, "name": name, "status": status, "conclusion": conclusion}


def _green(count: int, *, start: int = 0) -> list[dict]:
    """통과하는 `test: ` 체크런을 count 개 만든다."""
    return [
        _run(f"test: job{i}", "success", run_id=100 + i)
        for i in range(start, start + count)
    ]


FULL = _green(gate.MIN_TEST_CHECKS)
SHORT = _green(gate.MIN_TEST_CHECKS - 1)

# (라벨, 체크런 목록, final 여부, 기대 상태)
JUDGE_CASES: list[tuple[str, list[dict], bool, str]] = [
    ("하한만큼 전부 success", FULL, False, "pass"),
    (
        "자기 자신이 in_progress 로 섞여 있어도 통과",
        FULL + [_run(SELF, None, status="in_progress")],
        False,
        "pass",
    ),
    (
        "자기 자신이 실패로 남아 있어도 통과",
        FULL + [_run(SELF, "failure")],
        False,
        "pass",
    ),
    (
        "자기 자신만 있고 나머지 0건",
        [_run(SELF, None, status="in_progress")],
        False,
        "wait",
    ),
    (
        "자기 자신만 있고 나머지 0건 (final)",
        [_run(SELF, None, status="in_progress")],
        True,
        "fail",
    ),
    (
        "skipped 는 통과",
        _green(gate.MIN_TEST_CHECKS - 1) + [_run("test: skipme", "skipped", run_id=9)],
        False,
        "pass",
    ),
    ("하나가 failure", SHORT + [_run("test: bad", "failure", run_id=9)], False, "fail"),
    (
        "하나가 cancelled",
        SHORT + [_run("test: bad", "cancelled", run_id=9)],
        False,
        "fail",
    ),
    (
        "하나가 timed_out",
        SHORT + [_run("test: bad", "timed_out", run_id=9)],
        False,
        "fail",
    ),
    (
        "neutral 은 통과가 아니다",
        SHORT + [_run("test: bad", "neutral", run_id=9)],
        False,
        "fail",
    ),
    (
        "conclusion 이 null 인데 completed",
        SHORT + [_run("test: bad", None, run_id=9)],
        False,
        "fail",
    ),
    (
        "미완이 있으면 대기",
        SHORT + [_run("test: slow", None, run_id=9, status="in_progress")],
        False,
        "wait",
    ),
    (
        "queued 도 미완",
        SHORT + [_run("test: slow", None, run_id=9, status="queued")],
        False,
        "wait",
    ),
    (
        "미완 + final 이면 실패",
        SHORT + [_run("test: slow", None, run_id=9, status="in_progress")],
        True,
        "fail",
    ),
    (
        "실패는 미완이 남아 있어도 즉시 실패",
        SHORT
        + [
            _run("test: slow", None, run_id=9, status="queued"),
            _run("test: bad", "failure", run_id=8),
        ],
        False,
        "fail",
    ),
    ("하한 미만이면 대기", SHORT, False, "wait"),
    ("하한 미만 + final 이면 실패", SHORT, True, "fail"),
    ("입력 0건", [], False, "wait"),
    ("입력 0건 + final (조회 실패 경로)", [], True, "fail"),
    (
        "test: 접두 아닌 체크는 안 센다",
        FULL[:-1] + [_run("chore: plan-check", "success", run_id=7)],
        False,
        "wait",
    ),
    (
        "실패한 비-test 체크는 게이트를 안 막는다",
        FULL + [_run("Analyze (python)", "failure", run_id=7)],
        False,
        "pass",
    ),
    (
        "재실행 — id 가 큰 성공이 이긴다",
        SHORT
        + [
            _run("test: retry", "failure", run_id=1),
            _run("test: retry", "success", run_id=2),
        ],
        False,
        "pass",
    ),
    (
        "재실행 — id 가 큰 실패가 이긴다",
        SHORT
        + [
            _run("test: retry", "success", run_id=1),
            _run("test: retry", "failure", run_id=2),
        ],
        False,
        "fail",
    ),
]

# (라벨, 원문, 기대 레코드 수)
PARSE_CASES: list[tuple[str, str, int]] = [
    (
        "gh --jq 의 줄 단위 JSON",
        '{"id":1,"name":"test: a","status":"completed","conclusion":"success"}\n{"id":2,"name":"test: b","status":"completed","conclusion":"success"}',
        2,
    ),
    (
        "API 응답 원문",
        json.dumps({"total_count": 1, "check_runs": [{"id": 1, "name": "test: a"}]}),
        1,
    ),
    ("JSON 배열", '[{"id":1,"name":"test: a"}]', 1),
    ("빈 문자열 (조회 실패)", "", 0),
    ("공백만", "  \n  ", 0),
    ("파손된 JSON", '{"id":1,"name":', 0),
    ("객체가 아닌 줄은 버린다", '"just a string"\n{"id":1,"name":"test: a"}', 1),
    ("check_runs 가 없는 객체", '{"message":"Not Found"}', 0),
    (
        "체크런이 하나뿐이면 줄 하나가 곧 객체다",
        '{"id":1,"name":"test: a","status":"completed","conclusion":"success"}',
        1,
    ),
    ("문자열 JSON", '"nope"', 0),
]

_GATE_JOB = f'  gate:\n    name: "{SELF}"\n    runs-on: ubuntu-latest\n'


def _workflow(job_block: str) -> str:
    return "on:\n  pull_request: {}\n\njobs:\n" + job_block


def _names(count: int, *, include_self: bool = True) -> dict[str, str]:
    found = {f"test: job{i}": "ci.yml" for i in range(count)}
    if include_self:
        found[SELF] = "repo-scans.yml"
    return found


ENOUGH = _names(gate.MIN_TEST_CHECKS)

# (라벨, 게이트 워크플로 YAML, 선언된 test: 잡 목록, 문제가 있어야 하는가, 사유 조각)
STRUCTURE_CASES: list[tuple[str, str, dict[str, str], bool, str]] = [
    ("게이트 이름이 판정부와 일치", _workflow(_GATE_JOB), ENOUGH, False, ""),
    (
        "게이트 이름을 바꾸고 판정부를 안 고침",
        _workflow(
            '  gate:\n    name: "test: gatekeeper"\n    runs-on: ubuntu-latest\n'
        ),
        ENOUGH,
        True,
        "자기 자신을 기다립니다",
    ),
    (
        "게이트 잡이 없음",
        _workflow('  other:\n    name: "test: other"\n'),
        ENOUGH,
        True,
        "게이트 잡",
    ),
    ("잡을 0건 읽음", "on:\n  pull_request: {}\n", ENOUGH, True, "0건"),
    (
        "테스트 잡이 하한 미만",
        _workflow(_GATE_JOB),
        _names(gate.MIN_TEST_CHECKS - 1),
        True,
        "하한",
    ),
    (
        "게이트만 선언돼 있고 대표할 잡이 0건",
        _workflow(_GATE_JOB),
        {SELF: "repo-scans.yml"},
        True,
        "자기 자신 제외",
    ),
    (
        "매트릭스로 갈리는 이름",
        _workflow(_GATE_JOB),
        {**ENOUGH, "test: mcp ${{ matrix.svc }}": "ci.yml"},
        True,
        "매트릭스",
    ),
]


def main() -> int:
    for label, cases, minimum in (
        ("판정", JUDGE_CASES, MIN_JUDGE_CASES),
        ("파싱", PARSE_CASES, MIN_PARSE_CASES),
        ("구조", STRUCTURE_CASES, MIN_STRUCTURE_CASES),
    ):
        if len(cases) < minimum:
            print(
                f"::error::{label} 케이스를 {len(cases)}건만 모았습니다 (하한 {minimum})"
            )
            return 1

    for label, records, final, expected in JUDGE_CASES:
        state, _lines, problems = gate.judge(records, final=final)
        _check(
            f"[판정] {label}",
            state == expected,
            f"기대 {expected} · 실제 {state} ({' / '.join(problems) or '문제 없음'})",
        )

    for label, raw, expected in PARSE_CASES:
        got = gate.parse_check_runs(raw)
        _check(
            f"[파싱] {label}",
            len(got) == expected,
            f"기대 {expected}건 · 실제 {len(got)}건",
        )

    for label, text, names, should_fail, fragment in STRUCTURE_CASES:
        problems = gate.check_structure(gate.parse_jobs(text), names)
        joined = " / ".join(problems)
        _check(
            f"[구조] {label}",
            bool(problems) == should_fail,
            f"기대 {'문제 있음' if should_fail else '문제 없음'} · 실제 {joined or '문제 없음'}",
        )
        if should_fail and problems:
            _check(
                f"[구조] {label} — 사유에 {fragment!r}",
                fragment in joined,
                f"실제 사유: {joined}",
            )

    # 합성 픽스처만 보면 실제 배선이 끊겨도 초록이다 — 살아 있는 워크플로로도 한 번 판다.
    live_jobs = gate.parse_jobs(gate.GATE_WORKFLOW.read_text(encoding="utf-8"))
    live_names = gate.collect_test_job_names(gate.WORKFLOW_DIR)
    live_problems = gate.check_structure(live_jobs, live_names)
    _check("[실물] 게이트 구조", not live_problems, " / ".join(live_problems))

    total = len(JUDGE_CASES) + len(PARSE_CASES) + len(STRUCTURE_CASES) + 1
    print(
        f"케이스 {total}건 (판정 {len(JUDGE_CASES)} · 파싱 {len(PARSE_CASES)} · "
        f"구조 {len(STRUCTURE_CASES)} · 실물 1) · 실패 {len(failures)}건"
    )
    print(
        f"실물: 선언된 `{gate.CHECK_NAME_PREFIX}` 잡 {len(live_names)}개 (게이트 포함) · "
        f"하한 {gate.MIN_TEST_CHECKS}개 · 자기 제외 이름 {SELF!r}"
    )
    for f in failures:
        print(f"::error::{f}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
