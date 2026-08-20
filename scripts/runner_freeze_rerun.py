"""러너 동결로 버려진 cross-review 를 재실행할지 판정한다 (순수 판정, stdlib 전용).

`runner-freeze-rerun.yml` 이 부른다. self-hosted 러너가 WSL 위에 있어 호스트가 절전에
들면 러너가 얼고, GitHub 은 심장박동이 끊긴 잡을 ~10분 뒤 버린다 — 리뷰는 실제로 돌았는데
결과를 올릴 자리가 사라진다 (실측 2026-08-11: 최근 30 run 중 3건, 전부 수동 재실행으로 해소).
호스트 절전 자체는 막을 수 없다는 것이 리드 판단이라, 얼었을 때 밖(GitHub-hosted)에서
자동 재실행한다.

## 판정 규칙 — 무조건 재시도는 진짜 결함을 「몇 번 돌리면 초록」으로 덮는다

입력: stdin JSON `{"run_attempt": N, "jobs": [{"name", "conclusion", "annotations"}]}`.
`annotations` 는 그 잡의 annotation 목록(GitHub API 원형)이고, 조회에 실패했으면 null.

  rerun         — 실패 잡 전부가 「동결」 또는 「동결의 여파」로 분류되고, 동결이 ≥1
  skip          — 그 밖의 전부 (fail-closed: 분류 불가·조회 실패·실패 잡 0건 포함)
  cap_exceeded  — 동결이라 재실행했을 텐데 run_attempt 가 상한 이상 — 사람에게 넘긴다

잡 분류 (failure 레벨 annotation 만 본다 — warning/notice 는 실패 근거가 아니다.
실측: 동결 run 에도 Node.js deprecation warning 이 붙어 있었다):

  동결(frozen)   — failure annotation 전부가 러너 동결 서명(FREEZE_SIGNATURE)과 정확 일치.
                   GitHub 이 생성하는 고정 문자열이라 정확 일치만 받는다 — 다듬는 관대함은
                   비슷한 다른 실패를 동결로 삼킨다.
  여파(shadow)   — verdict 잡의 fail-closed 그림자. 동결 실측 3건 모두에서 cross 동결과
                   함께 verdict 잡이 「리뷰 판정 unable」 + 「Process completed with exit
                   code 1.」 로 실패했다 (publish 가 산출물 부재를 unable 처리 → 판정 체크
                   빨강). 이것을 「그 밖의 실패」로 치면 실사례 전부에서 재실행이 막힌다 —
                   그래서 이 조합만 허용 목록으로 명시한다. UNABLE_PREFIX 로 시작하는
                   annotation 이 ≥1 이고, 나머지가 전부 GENERIC_EXIT 일 때만.
  그 밖          — 하나라도 있으면 재실행하지 않는다. 동결과 진짜 실패가 섞여 있으면
                   재실행이 진짜를 덮는다 — 이 조건이 이 설계의 핵심 안전장치다.

## 재시도 상한 (MAX_ATTEMPTS = 3)

`run_attempt` 로 센다 — 동결한 attempt 가 상한 이상이면 재실행하지 않는다 (자동 재실행
최대 2회). 근거: 실측 3건 모두 재실행 1회로 해소됐고, 상한 3은 재실행 중 또 절전에 드는
이중 동결까지 흡수한다. 그 이상 얼면 호스트가 장기 수면 중일 공산이 커서 재실행은 러너 큐
정체만 만든다 — 사람에게 넘긴다. 러너가 계속 자면 무한 재실행이 되므로 상한은 필수다.

판정 근거는 lines 로 전부 남긴다 — 무엇을 보고 재실행했는지/안 했는지가 run 로그에서
읽혀야 한다.
"""

import json
import sys

# GitHub 이 러너 통신 두절 시 실패 잡에 다는 고정 문자열 —
# scripts/fixtures/runner_freeze_annotations.json (실제 API 응답) 과 정확 일치.
FREEZE_SIGNATURE = (
    "The self-hosted runner lost communication with the server. Verify the machine "
    "is running and has a healthy network connection. Anything in your workflow that "
    "terminates the runner process, starves it for CPU/Memory, or blocks its network "
    "access can cause this error."
)

# verdict 잡(scripts/review_verdict.py)의 unable 문구 — 그쪽 문구가 바뀌면 이 분류가
# 깨져 재실행이 멎는다 (안전한 방향의 고장). test_runner_freeze_rerun.py 가 두 파일의
# lockstep 을 검사한다.
UNABLE_PREFIX = "리뷰 판정 unable"

# 스텝이 비정상 종료할 때 GitHub 이 다는 일반 문구 — 단독으로는 아무것도 증명하지 않아
# UNABLE_PREFIX 와 같은 잡에 있을 때만 여파로 허용한다.
GENERIC_EXIT = "Process completed with exit code 1."

MAX_ATTEMPTS = 3

FROZEN = "frozen"
SHADOW = "shadow"
OTHER = "other"


def classify_job(annotations):
    """실패 잡 하나를 (분류, 근거 한 줄) 로 판정한다."""
    failure_msgs = [a.get("message", "") for a in annotations if a.get("annotation_level") == "failure"]
    if not failure_msgs:
        return OTHER, "failure annotation 0건 — 동결을 증명할 수 없다 (fail-closed)"
    if all(m == FREEZE_SIGNATURE for m in failure_msgs):
        return FROZEN, f"동결 서명 정확 일치 ({len(failure_msgs)}건)"
    has_unable = any(m.startswith(UNABLE_PREFIX) for m in failure_msgs)
    rest_ok = all(m == GENERIC_EXIT or m.startswith(UNABLE_PREFIX) for m in failure_msgs)
    if has_unable and rest_ok:
        return SHADOW, "동결의 여파 (verdict unable + exit code 1)"
    unmatched = [
        m for m in failure_msgs if m != FREEZE_SIGNATURE and m != GENERIC_EXIT and not m.startswith(UNABLE_PREFIX)
    ]
    if unmatched:
        return OTHER, f"동결 서명 밖의 failure annotation: {unmatched[0][:120]!r}"
    return OTHER, ("허용 조합 밖 (unable 없는 exit code 1, 또는 동결·일반 종료 혼합) — 동결로 증명되지 않는다")


def decide(run_attempt, jobs):
    """(판정, 사람이 읽을 줄 목록) 을 낸다 — 판정은 rerun/skip/cap_exceeded."""
    lines = [f"입력: run_attempt={run_attempt} · 잡 {len(jobs)}건"]

    if not isinstance(run_attempt, int) or run_attempt < 1:
        lines.append(f"판정: skip — run_attempt 가 비정상 값 {run_attempt!r} (fail-closed)")
        return "skip", lines
    if not jobs:
        lines.append("판정: skip — 잡 목록 0건, 아무것도 못 봤다 (fail-closed)")
        return "skip", lines

    failed = []
    for job in jobs:
        name = job.get("name", "(이름 없음)")
        conclusion = job.get("conclusion")
        if conclusion in ("success", "skipped", "neutral"):
            continue
        if conclusion != "failure":
            lines.append(f"판정: skip — 잡 {name!r} 이 미지 상태 {conclusion!r} (fail-closed)")
            return "skip", lines
        if job.get("annotations") is None:
            lines.append(f"판정: skip — 잡 {name!r} 의 annotation 조회 실패 (fail-closed)")
            return "skip", lines
        failed.append((name, job["annotations"]))

    if not failed:
        lines.append("판정: skip — 실패 잡 0건 (재실행할 대상이 없다)")
        return "skip", lines

    frozen_count = 0
    for name, annotations in failed:
        kind, reason = classify_job(annotations)
        lines.append(f"잡 {name!r}: {kind} — {reason}")
        if kind == OTHER:
            lines.append("판정: skip — 동결 서명 밖의 실패가 섞여 있다. 재실행하면 진짜 실패를 덮는다")
            return "skip", lines
        if kind == FROZEN:
            frozen_count += 1

    if frozen_count == 0:
        lines.append("판정: skip — 동결 서명이 없다 (여파만으로는 재실행하지 않는다)")
        return "skip", lines

    if run_attempt >= MAX_ATTEMPTS:
        lines.append(
            f"판정: cap_exceeded — 동결이지만 attempt {run_attempt} ≥ 상한 {MAX_ATTEMPTS}. "
            "러너가 계속 잔다 — 재실행하지 않고 사람에게 넘긴다"
        )
        return "cap_exceeded", lines

    lines.append(
        f"판정: rerun — 실패 잡 전부가 동결({frozen_count})/여파({len(failed) - frozen_count}), "
        f"attempt {run_attempt} < 상한 {MAX_ATTEMPTS}"
    )
    return "rerun", lines


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"판정: skip — 입력 JSON 파싱 실패: {exc} (fail-closed)")
        print("action=skip")
        return 0
    action, lines = decide(payload.get("run_attempt"), payload.get("jobs") or [])
    for line in lines:
        print(line)
    # 마지막 줄이 기계 판독용 — 워크플로가 tail -1 로 읽는다. 판정 불능도 skip 으로
    # 수렴하므로 종료코드는 항상 0 이다 (비정상 종료는 호출부가 fail-closed 로 skip 처리).
    print(f"action={action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
