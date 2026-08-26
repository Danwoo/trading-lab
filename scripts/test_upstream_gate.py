"""머지 게이트 판정 회귀 그물 (#23 Task 5) — fail-closed, stdlib 전용.

게이트는 **초록일 때 아무 일도 안 하는 검사**라 죽어도 티가 안 난다. 통과 집합에 한 줄만
더하면(`failure` 를 통과로 세거나, 0건을 통과로 세거나) 그 뒤로는 영영 초록이다.
그래서 판정의 축을 케이스로 못박는다:

  · **자기 제외** — `self_name` 을 준 호출자에서만 쓴다. 판정 자신이 `test: ` 체크로 뜨면
    안 빼는 순간 스스로를 기다린다. 지금 호출자 둘은 체크런을 안 만들어 기본값이 `None` 이다.
  · **결과** — `success`·`skipped` 만 통과. 미완은 대기(재조회), `--final` 이면 실패.
  · **하한** — 0건·조회 실패·잡 삭제는 전부 실패. 이 자리가 「검사 0건 = 통과」를 막는다.
  · **재실행** — 같은 이름이 여러 번이면 id 가 가장 큰 것만 본다.
  · **구조** — 선언된 `test: ` 잡 수 ↔ 하한, 없앤 대표자 잡(`test: gate`)의 부활, 이름에
    섞인 식(매트릭스). 실제 워크플로로도 한 번 돌린다 (합성 픽스처만 보면 배선이 끊겨도 초록이다).
  · **대기 루프** — 자동 머지 arm 스텝이 상류를 기다리는 계약. 잡이 아니라 **스텝** 하나를
    잘라 본다 — 그 잡에는 리뷰 폴링용 루프·DEADLINE 이 여럿이라 잡째로 보면 엉뚱한 루프를
    보고 초록이 된다.

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
MIN_JUDGE_CASES = 20
MIN_PARSE_CASES = 6
MIN_STRUCTURE_CASES = 6
MIN_LIVE_CASES = 3
MIN_LOOP_CASES = 7

# 판정이 자기 자신을 빼야 하는 호출자를 흉내 내는 이름 (지금 호출자 둘은 체크런을 안 만든다).
SELF = "test: self"
# 없앤 대표자 잡 — 되살아나면 구조 검사가 막는다.
RETIRED = gate.RETIRED_GATE_CHECK_NAME

failures: list[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        failures.append(f"{label}{(' — ' + detail) if detail else ''}")


def _run(name: str, conclusion: str | None, *, run_id: int = 1, status: str = "completed") -> dict:
    return {"id": run_id, "name": name, "status": status, "conclusion": conclusion}


def _green(count: int, *, start: int = 0) -> list[dict]:
    """통과하는 `test: ` 체크런을 count 개 만든다."""
    return [_run(f"test: job{i}", "success", run_id=100 + i) for i in range(start, start + count)]


FULL = _green(gate.MIN_TEST_CHECKS)
SHORT = _green(gate.MIN_TEST_CHECKS - 1)

# (라벨, 체크런 목록, final 여부, 기대 상태)
JUDGE_CASES: list[tuple[str, list[dict], bool, str]] = [
    ("하한만큼 전부 success", FULL, False, "pass"),
    (
        "자기 제외를 안 주면 그 체크도 세어 실패한다 (기본값 None)",
        FULL + [_run(SELF, "failure")],
        False,
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
    # 개시 직후가 실제로 가장 흔한 상태다 — cross-review 와 ci 는 같은
    # pull_request 이벤트로 동시에 시작하므로, 게이트가 처음 조회할 때 상류는 대개 아직 돈다.
    # 이 상태를 통과로 접으면 게이트는 아무것도 안 보고 초록이 된다.
    (
        "개시 직후 — 상류가 전부 미완",
        [_run(f"test: job{i}", None, run_id=200 + i, status="in_progress") for i in range(gate.MIN_TEST_CHECKS)],
        False,
        "wait",
    ),
    (
        "개시 직후 상태로 대기 상한 초과",
        [_run(f"test: job{i}", None, run_id=200 + i, status="in_progress") for i in range(gate.MIN_TEST_CHECKS)],
        True,
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


def _names(count: int) -> dict[str, str]:
    return {f"test: job{i}": "ci.yml" for i in range(count)}


ENOUGH = _names(gate.MIN_TEST_CHECKS)

# (라벨, 선언된 test: 잡 목록, 문제가 있어야 하는가, 사유 조각)
STRUCTURE_CASES: list[tuple[str, dict[str, str], bool, str]] = [
    ("하한만큼 선언돼 있음", ENOUGH, False, ""),
    ("`test: ` 잡을 0건 읽음", {}, True, "0건"),
    ("테스트 잡이 하한 미만", _names(gate.MIN_TEST_CHECKS - 1), True, "하한"),
    (
        "없앤 대표자 잡이 되살아남",
        {**ENOUGH, RETIRED: "ci.yml"},
        True,
        "되살아났습니다",
    ),
    (
        "매트릭스로 갈리는 이름",
        {**ENOUGH, "test: mcp ${{ matrix.svc }}": "ci.yml"},
        True,
        "매트릭스",
    ),
    (
        "대표자 부활 + 하한 미만 — 둘 다 사유로 남는다",
        {**_names(gate.MIN_TEST_CHECKS - 2), RETIRED: "ci.yml"},
        True,
        "하한",
    ),
]


_LOOP_OK = """    timeout-minutes: 25
      - name: 판정 → 네이티브 리뷰 + 자동 머지 arm
        run: |
          DEADLINE=$(( $(date +%s) + 1200 ))
          while :; do
            FINAL=""
            [ "$(date +%s)" -ge "$DEADLINE" ] && FINAL="--final"
            OUT=$(gh api ... | python3 scripts/verify_upstream_gate.py $FINAL)
            RC=$?
            if [ "$RC" -ne 2 ]; then exit "$RC"; fi
            sleep 15
          done
"""

# (라벨, 게이트 잡 본문, 문제가 있어야 하는가, 사유 조각)
LOOP_CASES: list[tuple[str, str, bool, str]] = [
    ("대기 루프가 서 있음", _LOOP_OK, False, ""),
    ("본문을 못 읽음", "", True, "본문을 못 읽었습니다"),
    (
        "루프 없이 한 번만 조회",
        _LOOP_OK.replace("while :; do", "if :; then"),
        True,
        "재조회 루프",
    ),
    (
        "종료코드 2 처리를 지움",
        _LOOP_OK.replace('"$RC" -ne 2', '"$RC" -ne 9'),
        True,
        "종료코드 2",
    ),
    (
        "--final 을 지움",
        _LOOP_OK.replace('FINAL="--final"', 'FINAL=""'),
        True,
        "--final",
    ),
    (
        "--final 이 주석에만 남음",
        _LOOP_OK.replace('FINAL="--final"', 'FINAL=""   # 종전엔 --final 을 넣었다'),
        True,
        "--final",
    ),
    (
        "대기 상한을 지움",
        _LOOP_OK.replace("DEADLINE=$(( $(date +%s) + 1200 ))", "DEADLINE=0"),
        True,
        "대기 상한",
    ),
    (
        "timeout-minutes 를 지움",
        _LOOP_OK.replace("    timeout-minutes: 25\n", ""),
        True,
        "timeout-minutes",
    ),
    (
        "잡 타임아웃이 대기 상한보다 짧다",
        _LOOP_OK.replace("timeout-minutes: 25", "timeout-minutes: 15"),
        True,
        "먼저 잡을",
    ),
]


def main() -> int:
    for label, cases, minimum in (
        ("판정", JUDGE_CASES, MIN_JUDGE_CASES),
        ("파싱", PARSE_CASES, MIN_PARSE_CASES),
        ("구조", STRUCTURE_CASES, MIN_STRUCTURE_CASES),
        ("대기", LOOP_CASES, MIN_LOOP_CASES),
    ):
        if len(cases) < minimum:
            print(f"::error::{label} 케이스를 {len(cases)}건만 모았습니다 (하한 {minimum})")
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

    for label, names, should_fail, fragment in STRUCTURE_CASES:
        problems = gate.check_structure(names)
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

    for label, block, should_fail, fragment in LOOP_CASES:
        problems = gate.check_wait_loop(block)
        joined = " / ".join(problems)
        _check(
            f"[대기] {label}",
            bool(problems) == should_fail,
            f"기대 {'문제 있음' if should_fail else '문제 없음'} · 실제 {joined or '문제 없음'}",
        )
        if should_fail and problems:
            _check(
                f"[대기] {label} — 사유에 {fragment!r}",
                fragment in joined,
                f"실제 사유: {joined}",
            )

    # 합성 픽스처만 보면 실제 배선이 끊겨도 초록이다 — 살아 있는 워크플로로도 한 번 판다.
    live_text = gate.WAIT_LOOP_WORKFLOW.read_text(encoding="utf-8")
    live_names = gate.collect_test_job_names(gate.WORKFLOW_DIR)
    live_problems = gate.check_structure(live_names)
    _check("[실물] 게이트 구조", not live_problems, " / ".join(live_problems))
    live_loop = gate.check_wait_loop(gate.wait_loop_block(live_text))
    _check("[실물] 대기 루프", not live_loop, " / ".join(live_loop))
    # 스텝을 실제로 잘라냈는지 — 빈 블록이면 위 검사가 「본문 못 읽음」으로 빨개지지만,
    # 잘라낸 블록이 잡 전체만큼 크면(스텝 좁힘 실패) 엉뚱한 루프를 보고 초록이 될 수 있다.
    _check(
        "[실물] 대기 루프 블록이 스텝 하나로 좁혀졌다",
        0 < len(gate.wait_loop_block(live_text).splitlines()) < len(live_text.splitlines()) // 4,
        f"블록 {len(gate.wait_loop_block(live_text).splitlines())}줄 / 파일 {len(live_text.splitlines())}줄",
    )

    total = len(JUDGE_CASES) + len(PARSE_CASES) + len(STRUCTURE_CASES) + len(LOOP_CASES) + MIN_LIVE_CASES
    print(
        f"케이스 {total}건 (판정 {len(JUDGE_CASES)} · 파싱 {len(PARSE_CASES)} · "
        f"구조 {len(STRUCTURE_CASES)} · 대기 {len(LOOP_CASES)} · 실물 {MIN_LIVE_CASES}) · 실패 {len(failures)}건"
    )
    print(
        f"실물: 선언된 `{gate.CHECK_NAME_PREFIX}` 잡 {len(live_names)}개 · "
        f"하한 {gate.MIN_TEST_CHECKS}개 · 대기 루프 {gate.WAIT_LOOP_WORKFLOW.name}"
    )
    for f in failures:
        print(f"::error::{f}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
