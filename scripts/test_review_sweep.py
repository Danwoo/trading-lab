"""쓸어담기 판정 회귀 그물 — fail-closed, stdlib 전용.

쓸어담기는 **아무 일도 안 할 때가 정상**이라 죽어도 티가 안 난다. 그리고 이것이 종전
`runner-freeze-rerun.yml` 의 자리를 물려받았는데, **그 워크플로가 정확히 그렇게 죽어 있었다** —
365번 깨어나 재실행 0건, 진짜 동결 4건에는 한 번도 안 깨어났다(감사 §1-4). 원인은 판정 근거를
run conclusion 에 둔 것이었다. 그래서 여기서 축을 못박는다:

  · **동결은 잡 annotation 으로 본다** — run conclusion 이 `success` 여도 동결이다 (실측 4/4)
  · **서명은 정확 일치** — 다듬으면 비슷한 다른 실패를 동결로 삼킨다
  · **failure 레벨만** — 동결 run 에도 warning annotation 이 붙어 있었다
  · **마커가 있으면 재실행하지 않는다** — 리뷰는 돌았다
  · **끝나지 않은 run 은 기다린다** — 도는 중을 유실로 오판하면 매 주기 재실행이 쌓인다
  · **상한** — 계속 얼면 무한 재실행이 되므로 사람에게 넘긴다
  · **입력 결손은 무행동** — 조회 실패를 「할 일 없음」으로 삼키지 않는다

**fail-closed**: 케이스를 하한보다 적게 모으면 실패한다.

    python3 scripts/test_review_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_sweep as sweep  # noqa: E402

MIN_CASES = 16

HEAD = "a" * 40
OLD = "b" * 40
FREEZE = sweep.FREEZE_SIGNATURE

failures: list[str] = []


def marker(sha=HEAD, verdict="merge_ok", model="kimi"):
    return f"독립 리뷰\n\n<!-- cross-review v1 model={model} verdict={verdict} sha={sha} -->"


def comment(body, association="OWNER"):
    return {
        "body": body,
        "author_association": association,
        "html_url": "https://example.invalid/c/1",
        "user_login": "Danwoo",
        "user_type": "User",
    }


def run(status="completed", conclusion="success", attempt=1, annotations=None, level="failure"):
    job = {"name": "review: cross (비게이트)", "conclusion": conclusion}
    if annotations is not None:
        job["annotations"] = [{"annotation_level": level, "message": m} for m in annotations]
    return {"id": 1, "status": status, "conclusion": conclusion, "run_attempt": attempt, "jobs": [job]}


def pr(**over):
    base = {
        "number": 1,
        "head_sha": HEAD,
        "draft": False,
        "merged": False,
        "auto_merge": False,
        "labels": ["review: passed"],
        "comments": [comment(marker())],
        "review_runs": [run()],
    }
    base.update(over)
    return base


# (설명, PR, 기대 kind, 기대 frozen 또는 None)
CASES: list[tuple[str, dict, str, bool | None]] = [
    ("마커 있음 + 라벨 맞음 + arm 됨 → 무행동", pr(auto_merge=True), "none", None),
    ("마커 merge_ok 인데 arm 안 됨 → rearm", pr(), "rearm", None),
    (
        "마커 needs_changes 인데 라벨이 passed → relabel",
        pr(comments=[comment(marker(verdict="needs_changes"))]),
        "relabel",
        None,
    ),
    (
        "마커 merge_ok 인데 라벨이 없다 → relabel",
        pr(labels=[]),
        "relabel",
        None,
    ),
    (
        "낡은 판정 라벨이 함께 남아 있다 → relabel",
        pr(labels=["review: passed", "review: needs-work"], auto_merge=True),
        "relabel",
        None,
    ),
    (
        "마커 unable + 라벨 unable → 무행동 (판정은 났다)",
        pr(comments=[comment(marker(verdict="unable"))], labels=["review: unable"]),
        "none",
        None,
    ),
    # ── 동결 축 — run conclusion 이 success 여도 잡 annotation 이 동결이면 동결이다
    (
        "마커 없음 + run success 인데 잡 annotation 이 동결 서명 → rerun(frozen)",
        pr(comments=[], review_runs=[run(conclusion="success", annotations=[FREEZE])]),
        "rerun",
        True,
    ),
    (
        "마커 없음 + run failure + 동결 서명 → rerun(frozen)",
        pr(comments=[], review_runs=[run(conclusion="failure", annotations=[FREEZE])]),
        "rerun",
        True,
    ),
    (
        "마커 없음 + annotation 없음 → rerun(frozen=false, 원인 미상)",
        pr(comments=[], review_runs=[run(conclusion="cancelled")]),
        "rerun",
        False,
    ),
    (
        "동결 서명이 warning 레벨이면 동결로 안 센다",
        pr(comments=[], review_runs=[run(annotations=[FREEZE], level="warning")]),
        "rerun",
        False,
    ),
    (
        "서명을 한 글자 다듬으면 동결로 안 센다 (정확 일치)",
        pr(comments=[], review_runs=[run(annotations=[FREEZE.replace("runner", "runner ")])]),
        "rerun",
        False,
    ),
    (
        "서명을 **품고 있는** 더 긴 메시지는 동결이 아니다 (부분 일치로 느슨해지면 여기서 걸린다)",
        pr(comments=[], review_runs=[run(annotations=[FREEZE + " (see job log for details)"])]),
        "rerun",
        False,
    ),
    (
        "동결 서명과 진짜 실패가 섞여 있으면 동결로 안 센다 — 재실행이 진짜를 덮는다",
        pr(
            comments=[],
            review_runs=[
                {
                    "id": 1,
                    "status": "completed",
                    "conclusion": "failure",
                    "run_attempt": 1,
                    "jobs": [
                        {
                            "name": "review: cross (비게이트)",
                            "conclusion": "failure",
                            "annotations": [
                                {"annotation_level": "failure", "message": FREEZE},
                                {"annotation_level": "failure", "message": "판정부 취득 실패"},
                            ],
                        }
                    ],
                }
            ],
        ),
        "rerun",
        False,
    ),
    # ── 기다림·상한·결손
    (
        "run 이 아직 도는 중 → wait (유실로 오판하지 않는다)",
        pr(comments=[], review_runs=[run(status="in_progress", conclusion=None)]),
        "wait",
        None,
    ),
    ("리뷰 run 이 아예 없다 → wait", pr(comments=[], review_runs=[]), "wait", None),
    (
        "동결인데 재시도 상한 도달 → escalate",
        pr(comments=[], review_runs=[run(annotations=[FREEZE], attempt=sweep.MAX_ATTEMPTS)]),
        "escalate",
        True,
    ),
    ("코멘트 조회 실패 → 무행동 (fail-closed)", pr(comments=None), "none", None),
    ("초안은 훑지 않는다", pr(draft=True), "none", None),
    ("머지된 PR 은 훑지 않는다", pr(merged=True), "none", None),
    (
        "낡은 head 의 마커는 마커가 아니다 → rerun",
        pr(comments=[comment(marker(sha=OLD))], review_runs=[run()]),
        "rerun",
        False,
    ),
    (
        "비-멤버가 올린 마커는 안 읽는다 → rerun  (위조 방어는 review_record 한 곳)",
        pr(
            comments=[{**comment(marker()), "author_association": "NONE", "user_login": "stranger"}],
            review_runs=[run()],
        ),
        "rerun",
        False,
    ),
]


def main() -> int:
    if len(CASES) < MIN_CASES:
        print(f"::error::케이스를 {len(CASES)}건만 모았습니다 (하한 {MIN_CASES}) — fail-closed")
        return 1

    for label, payload, want_kind, want_frozen in CASES:
        got = sweep.decide_pr(payload)
        if got["kind"] != want_kind:
            failures.append(f"{label}: kind 기대 {want_kind!r} ≠ 실제 {got['kind']!r} ({got.get('reason')})")
        if want_frozen is not None and got.get("frozen") != want_frozen:
            failures.append(f"{label}: frozen 기대 {want_frozen} ≠ 실제 {got.get('frozen')}")

    # 묶음 판정 — 빈 입력은 처분이 아니라 오류다
    empty = sweep.decide_sweep({})
    if not empty.get("error"):
        failures.append("PR 목록 부재를 오류로 안 낸다 (fail-closed 위반)")
    batch = sweep.decide_sweep({"prs": [pr(), pr(number=2, auto_merge=True)]})
    if batch["scanned"] != 2 or batch["counts"].get("rearm") != 1:
        failures.append(f"묶음 판정이 어긋난다: {batch['counts']}")

    # 라벨 표는 cross-review 의 라벨 스텝과 같아야 한다 — 갈리면 쓸어담기가 매번 relabel 한다
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/cross-review.yml").read_text(encoding="utf-8")
    for verdict, label in sweep.VERDICT_LABEL.items():
        if f'"{label}"' not in workflow:
            failures.append(f"라벨 표 불일치: {verdict} → {label!r} 이 cross-review.yml 에 없다")

    print(f"쓸어담기 케이스 {len(CASES)}건 + 묶음 2건 + 라벨 표 {len(sweep.VERDICT_LABEL)}건 검사")
    for line in failures:
        print(f"::error::{line}")
    if failures:
        print(f"판정: 실패 {len(failures)}건")
        return 1
    print("판정: 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
