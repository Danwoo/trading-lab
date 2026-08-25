"""열린 PR 을 훑어 「조용히 죽은」 리뷰·머지를 줍는다 — 순수 판정 + 수집 배관 (stdlib 전용).

## 왜 있나

리뷰·판정 게시·라벨·승인·자동 머지 arm 이 **한 self-hosted 잡**의 스텝이 되면서(2026-08-25 통합),
그 잡이 통째로 죽으면 아무것도 안 남는다. 종전에는 두 장치가 그 자리를 받았다:

  · GitHub-hosted `review: publish` 잡 — 리뷰 잡이 죽어도 「판정: 리뷰 불가」를 남겼다
    (PR #340~#383 에서 7번 돌았다 — 판정 코멘트 32건의 22%)
  · `runner-freeze-rerun.yml` — 동결된 run 을 밖에서 재실행했다

둘 다 GitHub-hosted 라 private 전환에서 과금의 몸통이 된다. 이 스크립트가 그 몫을 **결과로**
판정한다 — 트리거 조건을 맞추는 대신 「지금 무엇이 빠져 있나」를 본다. 원인이 동결이든 큐
사망이든 취소든 상관없이 걸린다.

## 왜 run conclusion 이 아니라 **잡 단위 annotation** 인가

옛 `runner-freeze-rerun.yml` 은 `workflow_run.conclusion == 'failure'` 로 깨어났는데,
**실제 동결 4건의 run conclusion 이 전부 `success` 였다** — 그래서 365번 깨어나 재실행 0건이고
진짜 동결에는 한 번도 안 깨어났다 (감사 §1-4, 이 조사의 최대 발견). 동결 서명은 **잡의
failure annotation** 에 붙지 run 결론에 안 붙는다. 그래서 이 판정은 잡 annotation 을 본다.

## 판정 (순수 함수 `decide_sweep`)

입력은 열린 PR 마다 다음을 담은 JSON 이다 — 수집은 아래 「수집」 절의 명령이 한다.

    {"prs": [{"number", "head_sha", "draft", "merged", "auto_merge",
              "labels": [...], "comments": [...], "checks": [...],
              "review_runs": [{"status", "conclusion", "run_attempt",
                               "jobs": [{"name", "conclusion", "annotations": [...]}]}]}]}

처분은 PR 하나에 최대 하나다 (먼저 걸리는 것이 이긴다):

  · `wait`      — 리뷰 run 이 아직 도는 중이거나 아예 없다. 아무것도 안 한다
  · `rerun`     — run 은 끝났는데 현재 head 의 판정 마커가 없다. 리뷰가 유실됐다
                  (`frozen=true` 면 잡 annotation 에서 동결 서명을 봤다는 뜻)
  · `escalate`  — 같은 조건인데 `run_attempt` 가 상한 이상 — 사람에게 넘긴다
  · `relabel`   — 마커는 있는데 판정 라벨이 그 판정과 어긋난다
  · `rearm`     — 마커가 `merge_ok` 인데 자동 머지가 안 걸려 있다
  · `none`      — 할 일 없음. 입력 결손도 여기로 접는다 (fail-closed — 지어내지 않는다)

**판정 마커를 읽는 것은 `review_record.find_marker` 다.** 저자 필터(OWNER·MEMBER·COLLABORATOR
+ 이 레포 봇)와 40자 sha 동등 비교가 거기 한 곳에 있고, 이 스크립트는 그것을 그대로 쓴다 —
위조 마커 방어가 두 벌이 되면 갈린다.

## 신뢰 경계

에이전트가 이 판정부를 부를 때는 **`git show origin/main:scripts/review_sweep.py` 로 꺼내
쓴다** — PR 워크트리의 판본을 쓰면 PR 이 자기 처분을 고칠 수 있다 (설계 ⑦-1).

## 수집 (에이전트가 도는 자리)

    python3 scripts/review_sweep.py collect | python3 scripts/review_sweep.py plan

`collect` 는 `gh` 로 열린 PR 과 그 부속을 모아 위 JSON 을 낸다. `plan` 은 순수 판정만 한다
(stdin JSON → stdout JSON). 처분을 **실행하지는 않는다** — 무엇을 할지 내놓을 뿐이고,
실행은 사람이나 에이전트가 그 목록을 보고 한다. 재실행은 다음 한 줄이다:

    gh run rerun <run_id> --failed

## fail-closed

입력이 비면 처분을 내지 않는다. 「대상 0건」은 통과가 아니라 **검사 건수를 출력에 남기고**
호출자가 판단하게 한다 — `plan` 은 훑은 PR 수와 처분 분포를 항상 낸다.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_record  # noqa: E402

#: GitHub 이 러너 통신 두절 시 실패 잡에 다는 고정 문자열. **정확 일치만** 받는다 —
#: 다듬는 관대함은 비슷한 다른 실패를 동결로 삼킨다 (옛 runner_freeze_rerun.py 승계).
FREEZE_SIGNATURE = (
    "The self-hosted runner lost communication with the server. Verify the machine "
    "is running and has a healthy network connection. Anything in your workflow that "
    "terminates the runner process, starves it for CPU/Memory, or blocks its network "
    "access can cause this error."
)

#: 자동 재실행 상한. 이 이상 얼면 호스트가 장기 수면 중일 공산이 커서 재실행은 큐 정체만
#: 만든다 — 사람에게 넘긴다 (옛 판정부와 같은 값·같은 근거).
MAX_ATTEMPTS = 3

#: 판정 → 사람이 읽는 라벨. cross-review 의 라벨 스텝과 **같은 표**여야 한다.
VERDICT_LABEL = {
    "merge_ok": "review: passed",
    "needs_changes": "review: needs-work",
    "unable": "review: unable",
}
ALL_VERDICT_LABELS = frozenset(VERDICT_LABEL.values())


def _failure_annotations(job) -> list[str]:
    out = []
    for ann in job.get("annotations") or []:
        if not isinstance(ann, dict):
            continue
        if (ann.get("annotation_level") or ann.get("level")) != "failure":
            continue
        message = ann.get("message")
        if isinstance(message, str):
            out.append(message)
    return out


def looks_frozen(review_runs) -> bool:
    """잡 단위 annotation 에서 동결을 본다 (run conclusion 은 보지 않는다).

    **동결과 진짜 실패가 섞여 있으면 동결이 아니다.** 그 잡의 failure annotation 이 전부
    동결 서명일 때만 동결로 센다 — 옛 판정부가 「이 설계의 핵심 안전장치」로 적어 둔 조건이고,
    섞인 것을 동결로 부르면 진짜 실패가 「러너가 얼었다」로 읽혀 원인이 묻힌다.
    """
    for run in review_runs or []:
        if not isinstance(run, dict):
            continue
        for job in run.get("jobs") or []:
            if not isinstance(job, dict):
                continue
            messages = _failure_annotations(job)
            if messages and all(message == FREEZE_SIGNATURE for message in messages):
                return True
    return False


def _runs_finished(review_runs) -> bool:
    """리뷰 run 이 하나 이상 있고 전부 끝났는가 — 없거나 도는 중이면 기다린다."""
    runs = [r for r in (review_runs or []) if isinstance(r, dict)]
    if not runs:
        return False
    return all(r.get("status") == "completed" for r in runs)


def _max_attempt(review_runs) -> int:
    attempts = [
        r.get("run_attempt")
        for r in (review_runs or [])
        if isinstance(r, dict) and isinstance(r.get("run_attempt"), int)
    ]
    return max(attempts) if attempts else 1


def decide_pr(pr) -> dict:
    """PR 하나의 처분. 먼저 걸리는 것이 이긴다."""
    number = pr.get("number")
    base = {"pr": number, "kind": "none", "frozen": False}
    head_sha = pr.get("head_sha") or ""

    if pr.get("merged") or pr.get("draft"):
        return {**base, "reason": "머지됐거나 초안 — 훑지 않는다"}
    comments = pr.get("comments")
    if comments is None:
        return {**base, "reason": "코멘트 조회 실패 — 처분하지 않는다 (fail-closed)"}

    marker = review_record.find_marker(comments, head_sha)
    review_runs = pr.get("review_runs")

    if marker is None:
        if not _runs_finished(review_runs):
            return {**base, "kind": "wait", "reason": "리뷰 run 이 아직 끝나지 않았다 (또는 아직 없다)"}
        frozen = looks_frozen(review_runs)
        attempt = _max_attempt(review_runs)
        why = "러너 동결 서명을 잡 annotation 에서 봤다" if frozen else "원인 미상 (취소·큐 사망·유실)"
        if attempt >= MAX_ATTEMPTS:
            return {
                **base,
                "kind": "escalate",
                "frozen": frozen,
                "reason": f"판정 마커 없음 · 재시도 {attempt}회로 상한({MAX_ATTEMPTS}) 도달 — 사람에게 넘긴다. {why}",
            }
        return {
            **base,
            "kind": "rerun",
            "frozen": frozen,
            "reason": f"리뷰 run 은 끝났는데 head {head_sha[:8]} 의 판정 마커가 없다 — {why}",
        }

    verdict = marker["verdict"]
    want = VERDICT_LABEL.get(verdict)
    labels = set(pr.get("labels") or [])
    stale = (labels & ALL_VERDICT_LABELS) - {want}
    if want and (want not in labels or stale):
        return {
            **base,
            "kind": "relabel",
            "want": want,
            "remove": sorted(stale),
            "reason": f"판정은 {verdict} 인데 라벨이 어긋난다 (현재: {sorted(labels & ALL_VERDICT_LABELS) or '없음'})",
        }

    if verdict == "merge_ok" and not pr.get("auto_merge"):
        return {
            **base,
            "kind": "rearm",
            "reason": "마커가 merge_ok 인데 자동 머지가 안 걸려 있다 — arm 을 다시 시도한다",
        }
    return {**base, "reason": f"처분 없음 (판정 {verdict})"}


def decide_sweep(payload) -> dict:
    prs = payload.get("prs")
    if prs is None:
        return {"actions": [], "counts": {}, "scanned": 0, "error": "PR 목록을 읽지 못했다 (fail-closed)"}
    actions = [decide_pr(pr) for pr in prs if isinstance(pr, dict)]
    counts: dict[str, int] = {}
    for action in actions:
        counts[action["kind"]] = counts.get(action["kind"], 0) + 1
    return {"actions": actions, "counts": counts, "scanned": len(actions)}


# ── 수집 배관 (gh 필요) ──────────────────────────────────────────────────────


def _gh(args: list[str]) -> str:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False).stdout


def collect(repo: str) -> dict:
    prs = []
    listing = _gh(
        ["pr", "list", "--repo", repo, "--state", "open", "--json", "number,headRefOid,isDraft,labels,autoMergeRequest"]
    )
    for item in json.loads(listing or "[]"):
        number, head = item["number"], item["headRefOid"]
        comments_raw = _gh(
            [
                "api",
                f"repos/{repo}/issues/{number}/comments",
                "--paginate",
                "--jq",
                "[.[] | {body, author_association, html_url, user_login: .user.login, user_type: .user.type}]",
            ]
        )
        try:
            comments = [c for page in comments_raw.splitlines() if page for c in json.loads(page)]
        except json.JSONDecodeError:
            comments = None
        runs_raw = _gh(
            [
                "api",
                f"repos/{repo}/actions/workflows/cross-review.yml/runs?head_sha={head}&per_page=20",
                "--jq",
                "[.workflow_runs[] | {id, status, conclusion, run_attempt}]",
            ]
        )
        runs = json.loads(runs_raw or "[]")
        for run in runs:
            jobs_raw = _gh(
                [
                    "api",
                    f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100",
                    "--jq",
                    "[.jobs[] | {id, name, conclusion}]",
                ]
            )
            jobs = json.loads(jobs_raw or "[]")
            for job in jobs:
                ann_raw = _gh(
                    [
                        "api",
                        f"repos/{repo}/check-runs/{job['id']}/annotations",
                        "--jq",
                        "[.[] | {annotation_level, message}]",
                    ]
                )
                job["annotations"] = json.loads(ann_raw or "[]")
            run["jobs"] = jobs
        prs.append(
            {
                "number": number,
                "head_sha": head,
                "draft": item["isDraft"],
                "merged": False,
                "auto_merge": item.get("autoMergeRequest") is not None,
                "labels": [label["name"] for label in item.get("labels") or []],
                "comments": comments,
                "review_runs": runs,
            }
        )
    return {"prs": prs}


def main(argv) -> int:
    command = argv[1] if len(argv) > 1 else ""
    if command == "collect":
        repo = argv[2] if len(argv) > 2 else "Danwoo/trading-lab"
        json.dump(collect(repo), sys.stdout, ensure_ascii=False)
        print()
        return 0
    if command == "plan":
        result = decide_sweep(json.load(sys.stdin))
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
        print(f"훑은 PR {result['scanned']}건 · 처분 {result['counts']}", file=sys.stderr)
        return 1 if result.get("error") else 0
    print(f"::error::알 수 없는 서브커맨드: {command!r} (collect|plan)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
