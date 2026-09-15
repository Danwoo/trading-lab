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

import re
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


def arm_in(**over):
    """`review_record.decide_arm` 이 **arm 이라고 답하는** 입력. 기본값이 통과 케이스다."""
    base = {
        "head_sha": HEAD,
        "marker_sha": HEAD,
        "marker_model": "kimi",
        "marker_tier": None,
        "verdict": "merge_ok",
        "manual": False,
        "reviews": [{"user_login": "github-actions[bot]", "state": "APPROVED", "commit_id": HEAD}],
        "pr_author_login": "Danwoo",
        "pr_author_is_bot": False,
        "pr_title": "fix: 무언가 고친다 — #1",
        "head_ref": "fix-1-claude",
        "issue_refs": [{"number": 1, "is_pr": False, "labels": ["risk: low"]}],
        "dropped_refs": [],
        "commit_author_emails": ["claude-opus-agent@noreply.local"],
    }
    base.update(over)
    return base


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
        "arm_input": arm_in(),
    }
    base.update(over)
    return base


# ── arm 입력이 판정부가 요구하는 **전부**인가 ────────────────────────────────
#
# 일부만 모으면 판정부는 빠진 축을 「없음」으로 읽고 늘 같은 쪽으로 기운다. 실측(리뷰 지적):
# `author: human` 라벨 입력 셋을 빠뜨렸더니 사람이 연 PR 은 라벨이 붙어 있어도 영영 `rearm` 이
# 안 나고 사유는 「라벨 없음」이라는 거짓이었다. 케이스로는 안 잡힌다 — **키 집합**을 본다.
WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/cross-review.yml"


def workflow_arm_keys() -> set[str]:
    """워크플로의 arm 스텝이 판정부에 넘기는 jq 객체의 키 — 그것이 계약이다."""
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("ARM=$(jq -n")
    end = text.index('review_record.py" arm)', start)
    return set(re.findall(r"(\w+):\s*[\$(]", text[start:end]))


def fake_gh(args):
    """`arm_input` 이 부르는 조회를 전부 성공으로 흉내 낸다 — 모양만 본다."""
    path = args[1] if len(args) > 1 else ""
    if "/reviews" in path:
        return 0, "[]"
    if "/commits" in path:
        return 0, '["a@example.com"]'
    if "/timeline" in path:
        return 0, "[]"
    if "/permission" in path:
        return 0, "admin"
    if "/issues/" in path:
        return 0, '{"number": 1, "is_pr": false, "labels": []}'
    return 1, ""


def arm_input_keys() -> set[str]:
    real_gh = sweep._gh
    sweep._gh = fake_gh
    try:
        built = sweep.arm_input(
            "owner/repo",
            {
                "number": 1,
                "headRefOid": HEAD,
                "title": "fix: x — #1",
                "body": "closes #1",
                "author": {"login": "someone", "is_bot": False},
                "headRefName": "fix-1-claude",
                "labels": [{"name": sweep.HUMAN_LABEL}],
            },
            [],
            {"sha": HEAD, "verdict": "merge_ok", "model": "kimi", "tier": None, "manual": False},
        )
    finally:
        sweep._gh = real_gh
    return set(built)


# (설명, PR, 기대 kind, 기대 frozen 또는 None)
CASES: list[tuple[str, dict, str, bool | None]] = [
    ("마커 있음 + 라벨 맞음 + arm 됨 → 무행동", pr(auto_merge=True), "none", None),
    ("마커 merge_ok + 판정부도 arm 인데 안 걸림 → rearm", pr(), "rearm", None),
    # 실물(PR #492 — dependabot 의 nodemailer major)에서 이 파일이 `rearm` 을 내고 있었다.
    # 손으로 따르면 사람 대기열을 건너뛰고 major 가 자동 머지된다.
    (
        "판정부가 거부한다(봇 major 상승) → rearm 을 내지 않는다",
        pr(
            arm_input=arm_in(
                pr_author_login="app/dependabot",
                pr_author_is_bot=True,
                pr_title="build(deps): bump nodemailer from 9.1.1 to 10.0.3 in /frontend",
                issue_refs=[],
            )
        ),
        "none",
        None,
    ),
    (
        "판정부가 거부한다(현재 head 봇 승인 없음) → rearm 을 내지 않는다",
        pr(arm_input=arm_in(reviews=[])),
        "none",
        None,
    ),
    (
        "arm 판정 입력을 못 모았다 → rearm 을 내지 않는다 (fail-closed)",
        pr(arm_input=None),
        "none",
        None,
    ),
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


# ── 수집부의 fail-closed — 「조회 실패」와 「진짜 0건」이 갈리는가 ────────────────
# 이 자리가 실제로 뚫려 있었다 (2026-08-25 리뷰 차단급): `_gh` 가 종료코드를 버려서
# `gh api` 실패의 빈 stdout 이 `[]` 로 파싱됐고, 멀쩡한 PR 이 「마커 없음 → rerun」이 됐다.
# (라벨, rc, stdout, 기대값 또는 sentinel)
_SENTINEL = object()
COLLECT_CASES = [
    ("종료코드 0 + 페이지 하나 → 그 목록", 0, '[{"body":"x"}]', [{"body": "x"}]),
    (
        "종료코드 0 + 페이지 둘 → 이어 붙인다 (--paginate)",
        0,
        '[{"body":"a"}]\n[{"body":"b"}]',
        [{"body": "a"}, {"body": "b"}],
    ),
    ("종료코드 0 + 빈 출력 → 진짜 0건", 0, "", []),
    ("**종료코드 비0 + 빈 출력 → None** (조회 실패)", 1, "", None),
    ("종료코드 비0 + 그럴듯한 출력이어도 None", 1, '[{"body":"x"}]', None),
    ("종료코드 0 + 깨진 JSON → None", 0, "{not json", None),
    ("종료코드 0 + 배열이 아닌 JSON → None", 0, '{"body":"x"}', None),
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

    for label, rc, raw, want in COLLECT_CASES:
        got = sweep.parse_comments(rc, raw)
        if got != want:
            failures.append(f"[수집] {label}: 기대 {want!r} ≠ 실제 {got!r}")

    # 수집부 실패가 판정부의 fail-closed 계약과 실제로 맞물리는가 — 두 층을 이어서 본다
    broken = sweep.decide_pr(pr(comments=sweep.parse_comments(1, "")))
    if broken["kind"] != "none":
        failures.append(f"[수집→판정] 조회 실패가 무행동으로 안 접힌다: {broken}")
    if sweep.parse_json_list(1, "") is not None:
        failures.append("[수집] parse_json_list 가 실패를 빈 목록으로 삼킨다")

    # 묶음 판정 — 빈 입력은 처분이 아니라 오류다
    empty = sweep.decide_sweep({})
    if not empty.get("error"):
        failures.append("PR 목록 부재를 오류로 안 낸다 (fail-closed 위반)")
    batch = sweep.decide_sweep({"prs": [pr(), pr(number=2, auto_merge=True)]})
    if batch["scanned"] != 2 or batch["counts"].get("rearm") != 1:
        failures.append(f"묶음 판정이 어긋난다: {batch['counts']}")

    # arm 판정을 **정말 판정부에 묻는지** — 거부 사유가 그대로 실려 나와야 한다.
    refused = sweep.decide_pr(
        pr(
            arm_input=arm_in(
                pr_author_login="app/dependabot",
                pr_author_is_bot=True,
                pr_title="build(deps): bump nodemailer from 9.1.1 to 10.0.3 in /frontend",
                issue_refs=[],
            )
        )
    )
    if "major" not in (refused.get("reason") or ""):
        failures.append(f"거부 사유가 판정부의 말이 아니다: {refused.get('reason')!r}")

    # arm 입력 키가 워크플로의 계약과 같아야 한다 — 빠진 키는 판정부에서 「없음」이 된다
    wanted = workflow_arm_keys()
    built = arm_input_keys()
    if not wanted:
        failures.append("워크플로에서 arm 입력 키를 못 읽었다 — 대조할 것이 없다 (fail-closed)")
    elif not wanted <= built:
        failures.append(f"arm 입력에 빠진 키: {sorted(wanted - built)}")

    # 라벨 표는 cross-review 의 라벨 스텝과 같아야 한다 — 갈리면 쓸어담기가 매번 relabel 한다
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/cross-review.yml").read_text(encoding="utf-8")
    for verdict, label in sweep.VERDICT_LABEL.items():
        if f'"{label}"' not in workflow:
            failures.append(f"라벨 표 불일치: {verdict} → {label!r} 이 cross-review.yml 에 없다")

    print(
        f"쓸어담기 케이스 {len(CASES)}건 + 수집 {len(COLLECT_CASES)}건 + 이음 2건 "
        f"+ 묶음 3건 + arm 입력 키 {len(workflow_arm_keys())}건 + 라벨 표 {len(sweep.VERDICT_LABEL)}건 검사"
    )
    for line in failures:
        print(f"::error::{line}")
    if failures:
        print(f"판정: 실패 {len(failures)}건")
        return 1
    print("판정: 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
