"""runner_freeze_rerun.decide 회귀 그물 — 동결 재실행이 진짜 실패를 덮지 않는지 못박는다.

케이스의 뼈대는 실제 API 응답 픽스처(scripts/fixtures/runner_freeze_annotations.json —
2026-08-11 동결 run 31456676162 attempt 1 에서 뜬 원형)다. 동결 실측 3건 모두
「cross 동결 + verdict unable 여파」 모양이었으므로 그 모양이 rerun 의 기준 케이스이고,
가장 중요한 케이스는 반대쪽 — **동결과 진짜 실패가 섞이면 재실행하지 않는다** 다.

lockstep 검사 둘:
  · FREEZE_SIGNATURE ↔ 픽스처의 실제 GitHub 문자열 (서명 상수가 현실과 어긋나면 실패)
  · UNABLE_PREFIX ↔ review_verdict.judge("unable") 의 문구 (그쪽 문구가 바뀌면 여파
    분류가 조용히 죽는다 — 여기서 시끄럽게 잡는다)
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_verdict as rv  # noqa: E402
import runner_freeze_rerun as rfr  # noqa: E402

FIXTURE = json.loads(
    (
        Path(__file__).resolve().parent / "fixtures" / "runner_freeze_annotations.json"
    ).read_text(encoding="utf-8")
)

FREEZE_ANN = FIXTURE["freeze"]  # cross 잡 — 동결 서명 1건
UNABLE_ANN = FIXTURE["verdict_unable"]  # verdict 잡 — warning + exit1 + unable
NEEDS_ANN = FIXTURE["verdict_needs_changes"]  # verdict 잡 — 진짜 실패


def job(name, conclusion, annotations):
    return {"name": name, "conclusion": conclusion, "annotations": annotations}


# 실측 동결 run 의 잡 구성 그대로 (route·publish 성공, cross 동결, verdict 여파)
OBSERVED_FREEZE_JOBS = [
    job("review: route (비게이트)", "success", []),
    job("review: cross (비게이트)", "failure", FREEZE_ANN),
    job("review: publish (비게이트)", "success", []),
    job("review: verdict (비게이트)", "failure", UNABLE_ANN),
]

# (설명, run_attempt, jobs, 기대 판정, 출력에 있어야 하는 조각들)
CASES = [
    (
        "동결 서명만 (실측 픽스처 모양) → 재실행",
        1,
        OBSERVED_FREEZE_JOBS,
        "rerun",
        ["동결 서명 정확 일치", "동결의 여파"],
    ),
    (
        "동결 + 진짜 실패(needs_changes) 혼재 → 재실행 안 함 (가장 중요한 케이스)",
        1,
        [
            job("review: cross (비게이트)", "failure", FREEZE_ANN),
            job("review: verdict (비게이트)", "failure", NEEDS_ANN),
        ],
        "skip",
        ["동결 서명 밖의 실패"],
    ),
    (
        "동결 서명 없음 (진짜 실패만) → 재실행 안 함",
        1,
        [job("review: verdict (비게이트)", "failure", NEEDS_ANN)],
        "skip",
        [],
    ),
    (
        "annotation 조회 실패 → 재실행 안 함 (fail-closed)",
        1,
        [job("review: cross (비게이트)", "failure", None)],
        "skip",
        ["조회 실패"],
    ),
    (
        "동결인데 attempt 상한 이상 → 상한 초과 (재실행 안 함)",
        3,
        OBSERVED_FREEZE_JOBS,
        "cap_exceeded",
        ["상한", "사람에게"],
    ),
    (
        "여파(verdict unable)만 있고 동결 없음 → 재실행 안 함",
        1,
        [job("review: verdict (비게이트)", "failure", UNABLE_ANN)],
        "skip",
        ["여파만으로는 재실행하지 않는다"],
    ),
    (
        "exit code 1 단독 (unable 없는 잡) → 재실행 안 함",
        1,
        [
            job("review: cross (비게이트)", "failure", FREEZE_ANN),
            job(
                "review: route (비게이트)",
                "failure",
                [{"annotation_level": "failure", "message": rfr.GENERIC_EXIT}],
            ),
        ],
        "skip",
        ["동결 서명 밖의 실패"],
    ),
    (
        "failure annotation 0건인 실패 잡 → 재실행 안 함 (fail-closed)",
        1,
        [job("review: cross (비게이트)", "failure", [])],
        "skip",
        ["증명할 수 없다"],
    ),
    (
        "잡 목록 0건 → 재실행 안 함 (fail-closed)",
        1,
        [],
        "skip",
        ["잡 목록 0건"],
    ),
    (
        "미지 잡 상태(cancelled) 혼재 → 재실행 안 함 (fail-closed)",
        1,
        [
            job("review: cross (비게이트)", "failure", FREEZE_ANN),
            job("review: publish (비게이트)", "cancelled", []),
        ],
        "skip",
        ["미지 상태"],
    ),
    (
        "run_attempt 비정상 값 → 재실행 안 함 (fail-closed)",
        None,
        OBSERVED_FREEZE_JOBS,
        "skip",
        ["비정상 값"],
    ),
    (
        "동결 서명 부분 일치(잘린 문자열)는 동결이 아니다",
        1,
        [
            job(
                "review: cross (비게이트)",
                "failure",
                [
                    {
                        "annotation_level": "failure",
                        "message": rfr.FREEZE_SIGNATURE[:80],
                    }
                ],
            )
        ],
        "skip",
        ["동결 서명 밖의 실패"],
    ),
]


def run_cases():
    failures = 0
    for desc, attempt, jobs, want, want_bits in CASES:
        action, lines = rfr.decide(attempt, jobs)
        out = "\n".join(lines)
        if action != want:
            print(f"FAIL [{desc}] 판정: got {action!r}, want {want!r}")
            failures += 1
        for bit in want_bits:
            if bit not in out:
                print(f"FAIL [{desc}] 출력에 {bit!r} 없음")
                failures += 1
    return failures


def run_lockstep_checks():
    failures = 0
    # 서명 상수 ↔ 실제 GitHub 문자열 (픽스처가 API 원형이다)
    fixture_msg = FREEZE_ANN[0]["message"]
    if rfr.FREEZE_SIGNATURE != fixture_msg:
        print("FAIL FREEZE_SIGNATURE 가 픽스처(실제 API 응답)와 다르다")
        failures += 1
    # UNABLE_PREFIX ↔ review_verdict 의 unable 문구 (annotation 은 ::error:: 줄에서 나온다)
    _, verdict_lines = rv.judge("unable")
    error_lines = [ln for ln in verdict_lines if ln.startswith("::error::")]
    if not error_lines or not error_lines[0].removeprefix("::error::").startswith(
        rfr.UNABLE_PREFIX
    ):
        print("FAIL UNABLE_PREFIX 가 review_verdict.judge('unable') 문구와 어긋난다")
        failures += 1
    # 픽스처의 여파 annotation 도 같은 prefix 인지 (실환경 대조)
    unable_msgs = [
        a["message"]
        for a in UNABLE_ANN
        if a["annotation_level"] == "failure" and a["message"] != rfr.GENERIC_EXIT
    ]
    if not unable_msgs or not all(m.startswith(rfr.UNABLE_PREFIX) for m in unable_msgs):
        print("FAIL 픽스처의 verdict unable annotation 이 UNABLE_PREFIX 와 어긋난다")
        failures += 1
    return failures


def run_cli_check():
    """워크플로가 쓰는 CLI 계약 — stdin JSON, 마지막 줄 action=<판정>, 종료코드 0."""
    failures = 0
    payload = json.dumps({"run_attempt": 1, "jobs": OBSERVED_FREEZE_JOBS})
    proc = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "runner_freeze_rerun.py"),
        ],
        input=payload,
        capture_output=True,
        text=True,
    )
    last = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    if proc.returncode != 0 or last != "action=rerun":
        print(f"FAIL CLI 계약: rc={proc.returncode}, 마지막 줄 {last!r}")
        failures += 1
    proc = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent / "runner_freeze_rerun.py"),
        ],
        input="깨진 JSON",
        capture_output=True,
        text=True,
    )
    last = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    if proc.returncode != 0 or last != "action=skip":
        print(
            f"FAIL CLI 계약(파싱 실패 fail-closed): rc={proc.returncode}, 마지막 줄 {last!r}"
        )
        failures += 1
    return failures


def main() -> int:
    failures = run_cases() + run_lockstep_checks() + run_cli_check()
    total = len(CASES) + 3 + 2
    print(f"runner_freeze_rerun 케이스 {total}건 검사 · 실패 {failures}건")
    if not CASES:
        print("FAIL 검사 대상 0건")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
