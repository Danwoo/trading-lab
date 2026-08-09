"""required 게이트 판정 회귀 그물 (#23 Task 5) — fail-closed, stdlib 전용.

게이트는 **초록일 때 아무 일도 안 하는 검사**라 죽어도 티가 안 난다. 통과 집합에 한 줄만
더하면(`failure` 를 통과로 세거나, 상류 0건을 통과로 세거나) 그 뒤로는 영영 초록이다.
그래서 판정의 축을 케이스로 못박는다:

  · **구조** — 게이트의 `needs` 가 같은 워크플로의 나머지 잡을 전부 담는가. 실제
    `repo-scans.yml` 로도 한 번 돌린다 (합성 픽스처만 보면 배선이 끊겨도 초록이다).
  · **결과** — `success`·`skipped` 만 통과. 상류 0건·JSON 파손·`result` 부재는 전부 실패.

**fail-closed**: 케이스를 하한보다 적게 모으면 실패한다.

    python3 scripts/test_upstream_gate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_upstream_gate as gate  # noqa: E402

# 케이스가 이보다 적으면 수집이 깨진 것이다 (「0건 통과」 방지).
MIN_STRUCTURE_CASES = 9
MIN_RESULT_CASES = 12

failures: list[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        failures.append(f"{label}{(' — ' + detail) if detail else ''}")


def _workflow(gate_block: str, upstream: tuple[str, ...] = ("alpha", "beta")) -> str:
    """게이트 + 상류 잡으로 이뤄진 최소 워크플로를 만든다."""
    body = "".join(
        f'  {job}:\n    name: "test: {job}"\n    runs-on: ubuntu-latest\n'
        for job in upstream
    )
    return "on:\n  pull_request: {}\n\njobs:\n" + gate_block + body


GATE_OK = (
    '  gate:\n    name: "test: gate"\n'
    "    needs: [alpha, beta]\n    runs-on: ubuntu-latest\n"
)

# (라벨, 워크플로 YAML, 문제가 있어야 하는가, 문제 문자열에 있어야 할 조각)
STRUCTURE_CASES: list[tuple[str, str, bool, str]] = [
    ("needs 가 상류 전부를 담음", _workflow(GATE_OK), False, ""),
    (
        "needs 블록 리스트 형식",
        _workflow(
            '  gate:\n    name: "test: gate"\n'
            "    needs:\n      - alpha\n      - beta\n    runs-on: ubuntu-latest\n"
        ),
        False,
        "",
    ),
    (
        "상류가 하나뿐일 때 스칼라 needs",
        _workflow(
            '  gate:\n    name: "test: gate"\n'
            "    needs: alpha\n    runs-on: ubuntu-latest\n",
            upstream=("alpha",),
        ),
        False,
        "",
    ),
    (
        "잡을 더하고 needs 를 안 고침",
        _workflow(
            '  gate:\n    name: "test: gate"\n'
            "    needs: [alpha]\n    runs-on: ubuntu-latest\n"
        ),
        True,
        "beta",
    ),
    (
        "needs 가 통째로 없음",
        _workflow('  gate:\n    name: "test: gate"\n    runs-on: ubuntu-latest\n'),
        True,
        "alpha",
    ),
    (
        "없는 잡을 needs 에 적음",
        _workflow(
            '  gate:\n    name: "test: gate"\n'
            "    needs: [alpha, beta, ghost]\n    runs-on: ubuntu-latest\n"
        ),
        True,
        "ghost",
    ),
    ("게이트 잡 자체가 없음", _workflow(""), True, "gate"),
    (
        "게이트 체크 이름이 `test: ` 접두가 아님",
        _workflow(
            '  gate:\n    name: "chore: gate"\n'
            "    needs: [alpha, beta]\n    runs-on: ubuntu-latest\n"
        ),
        True,
        "접두",
    ),
    (
        "상류 잡이 0건",
        _workflow(
            '  gate:\n    name: "test: gate"\n    runs-on: ubuntu-latest\n',
            upstream=(),
        ),
        True,
        "상류 잡이 0건",
    ),
    ("잡을 0건 읽음", "on:\n  pull_request: {}\n", True, "0건"),
    (
        "on: 아래 키를 잡으로 오독하지 않음",
        "on:\n  push:\n    branches: [main]\n  pull_request: {}\n\njobs:\n"
        + GATE_OK
        + '  alpha:\n    name: "test: alpha"\n    runs-on: ubuntu-latest\n'
        + '  beta:\n    name: "test: beta"\n    runs-on: ubuntu-latest\n',
        False,
        "",
    ),
]

# (라벨, NEEDS_JSON 원문, 통과해야 하는가)
RESULT_CASES: list[tuple[str, str, bool]] = [
    (
        "상류 전부 success",
        '{"a": {"result": "success"}, "b": {"result": "success"}}',
        True,
    ),
    (
        "success + skipped",
        '{"a": {"result": "success"}, "b": {"result": "skipped"}}',
        True,
    ),
    ("전부 skipped", '{"a": {"result": "skipped"}}', True),
    (
        "outputs 가 붙어 있어도 무관",
        '{"a": {"result": "success", "outputs": {}}}',
        True,
    ),
    (
        "하나가 failure",
        '{"a": {"result": "success"}, "b": {"result": "failure"}}',
        False,
    ),
    ("하나가 cancelled", '{"a": {"result": "cancelled"}}', False),
    ("모르는 결과값", '{"a": {"result": "neutral"}}', False),
    ("needs 가 빈 객체", "{}", False),
    ("NEEDS_JSON 미설정", "", False),
    ("공백만", "   \n  ", False),
    ("JSON 파손", '{"a": {"result": "success"', False),
    ("객체가 아닌 JSON", '["a", "b"]', False),
    ("result 키 부재", '{"a": {"outputs": {}}}', False),
    ("result 가 빈 문자열", '{"a": {"result": ""}}', False),
    ("엔트리가 객체가 아님", '{"a": "success"}', False),
    ("null 결과", '{"a": null}', False),
]


def main() -> int:
    if len(STRUCTURE_CASES) < MIN_STRUCTURE_CASES:
        print(
            f"::error::구조 케이스를 {len(STRUCTURE_CASES)}건만 모았습니다 "
            f"(하한 {MIN_STRUCTURE_CASES})"
        )
        return 1
    if len(RESULT_CASES) < MIN_RESULT_CASES:
        print(
            f"::error::결과 케이스를 {len(RESULT_CASES)}건만 모았습니다 "
            f"(하한 {MIN_RESULT_CASES})"
        )
        return 1

    for label, text, should_fail, fragment in STRUCTURE_CASES:
        problems = gate.check_structure(gate.parse_jobs(text))
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

    for label, raw, should_pass in RESULT_CASES:
        _, problems = gate.judge_results(raw)
        _check(
            f"[결과] {label}",
            (not problems) == should_pass,
            f"기대 {'통과' if should_pass else '실패'} · 실제 {' / '.join(problems) or '통과'}",
        )

    # 합성 픽스처만 보면 실제 배선이 끊겨도 초록이다 — 살아 있는 워크플로로도 한 번 판다.
    live = gate.parse_jobs(gate.GATE_WORKFLOW.read_text(encoding="utf-8"))
    live_problems = gate.check_structure(live)
    _check(
        "[실물] repo-scans.yml 의 게이트가 상류를 전부 담음",
        not live_problems,
        " / ".join(live_problems),
    )
    _check(
        "[실물] 상류 잡이 1건 이상",
        len(live) >= 2,
        f"읽은 잡 {len(live)}개: {', '.join(sorted(live))}",
    )

    total = len(STRUCTURE_CASES) + len(RESULT_CASES) + 2
    print(
        f"케이스 {total}건 (구조 {len(STRUCTURE_CASES)} · 결과 {len(RESULT_CASES)} · 실물 2) "
        f"· 실패 {len(failures)}건"
    )
    print(
        f"실물 repo-scans.yml: 잡 {len(live)}개 "
        f"(게이트 `{gate.GATE_JOB_ID}` + 상류 {len(live) - 1})"
    )
    for f in failures:
        print(f"::error::{f}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
