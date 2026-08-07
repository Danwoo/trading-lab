"""스택 PR 이 위로 합쳐진 뒤 아래 브랜치에 커밋이 착륙해 조용히 고립되는 사례를 찾는다 (#330).

## 무엇을 잡는가

PR A(head=`branch`)가 어딘가(main 또는 다른 브랜치)로 머지된 **뒤에**, 바로 그 `branch` 에 커밋이
더 들어오면 — `branch` 는 이미 위로 합쳐졌으므로 그 새 커밋은 다시 올라갈 자리가 없다. squash 머지
라 `git log main..branch` 로는 이걸 못 가린다(머지된 브랜치도 전부 "main 에 없는 커밋 N개"로
보인다 — 신호 대 잡음이 0에 가깝다). 정확한 신호는 **"자기 PR 이 머지된 시각 이후, 그 head 브랜치
자체에 커밋이 더 들어왔는가"** 뿐이다.

## 오탐이 있다 — 이것은 사람이 판정하는 후보 뽑기 도구다

같은 변경이 나중에 다른 제목의 squash 커밋으로 `main` 에 별도로 착륙했다면(설계 문서 PR 등에서
실측됨 — #237·#239) 이 스캔은 여전히 후보로 잡는다(브랜치 자체에는 머지 후 커밋이 있으므로).
**이 스크립트는 그 브랜치의 커밋들이 다른 경로로 이미 착륙했는지 판별하지 않는다** — 그건 사람이
`git log main --grep=...` 등으로 내용을 대조해 확인할 몫이다. 그래서 자동으로 브랜치를 삭제하거나
PR·머지를 막지 않는다 — 후보만 낸다.

## 사용

    python3 scripts/detect_orphaned_merged_branches.py [--repo OWNER/NAME] [--limit N]

`gh`(인증됨) · `git`(origin 리모트, 전체 브랜치 fetch 필요) 가 PATH 에 있어야 한다. `--repo` 를
생략하면 `gh repo view` 로 현재 디렉터리 기준 레포를 추론한다.

fail-closed: 살펴본 머지 PR 이 0건이면(gh 조회 실패·레포에 머지 PR 이 아예 없음) 통과가 아니라
실패다 — "후보 0건"이 "전부 정상"인지 "아무것도 안 봤음"인지 출력에서 구분한다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field


@dataclass
class Candidate:
    pr_number: int
    head_ref: str
    base_ref: str
    merged_at: str
    orphan_commits: list[tuple[str, str]] = field(
        default_factory=list
    )  # (sha, subject)


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"명령 실패({result.returncode}): {' '.join(cmd)}\n{result.stderr}"
        )
    return result.stdout


def _infer_repo() -> str:
    out = _run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
    )
    return out.strip()


def _fetch_all_branches() -> None:
    # 얕은/부분 체크아웃(CI actions/checkout 기본값)에는 origin 의 다른 브랜치가 없다 —
    # 브랜치별 커밋 이력을 보려면 전부 끌어와야 한다.
    subprocess.run(
        ["git", "fetch", "origin", "+refs/heads/*:refs/remotes/origin/*", "--prune"],
        check=True,
        capture_output=True,
        text=True,
    )


def _list_merged_prs(repo: str, limit: int) -> list[dict]:
    out = _run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "merged",
            "--limit",
            str(limit),
            "--json",
            "number,headRefName,baseRefName,mergedAt",
        ]
    )
    return json.loads(out)


def _branch_exists(ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "-q", f"origin/{ref}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _commits_since(ref: str, since_iso: str) -> list[tuple[str, str]]:
    out = _run(
        [
            "git",
            "log",
            f"origin/{ref}",
            f"--since={since_iso}",
            "--format=%H%x09%s",
        ]
    )
    commits = []
    for line in out.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        commits.append((sha, subject))
    return commits


def find_candidates(repo: str, limit: int) -> tuple[list[dict], list[Candidate]]:
    prs = _list_merged_prs(repo, limit)
    candidates: list[Candidate] = []
    for pr in prs:
        head = pr["headRefName"]
        if not _branch_exists(head):
            continue  # 이미 정리됨(삭제됨) — 고립될 자리가 없다
        commits = _commits_since(head, pr["mergedAt"])
        if commits:
            candidates.append(
                Candidate(
                    pr_number=pr["number"],
                    head_ref=head,
                    base_ref=pr["baseRefName"],
                    merged_at=pr["mergedAt"],
                    orphan_commits=commits,
                )
            )
    return prs, candidates


def _format_report(repo: str, examined: int, candidates: list[Candidate]) -> str:
    lines = [f"검사한 머지 PR: {examined}건 (레포: {repo})"]
    if not candidates:
        lines.append(
            "후보 0건 — 위 {}건을 전부 살펴봤고 고립 신호가 없었다.".format(examined)
        )
        return "\n".join(lines)
    lines.append(
        f"후보 {len(candidates)}건 — 브랜치 내용이 다른 경로로 이미 착륙했는지는 사람이 확인해야 한다:"
    )
    for c in candidates:
        lines.append(
            f"\n  PR #{c.pr_number} — head={c.head_ref} (base={c.base_ref}, merged={c.merged_at})"
        )
        lines.append(f"    머지 후 이 브랜치에 커밋 {len(c.orphan_commits)}개:")
        for sha, subject in c.orphan_commits:
            lines.append(f"      {sha[:9]}  {subject}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--repo", default=None, help="OWNER/NAME (생략 시 gh repo view 로 추론)"
    )
    parser.add_argument(
        "--limit", type=int, default=300, help="조회할 머지 PR 최대 개수 (기본 300)"
    )
    args = parser.parse_args()

    repo = args.repo or _infer_repo()
    _fetch_all_branches()
    prs, candidates = find_candidates(repo, args.limit)

    print(_format_report(repo, len(prs), candidates))

    if not prs:
        print(
            "\n✗ 머지 PR 을 0건 조회했다 — gh 인증·레포 지정을 확인하라 (0건은 '이상 없음'이 아니라 '아무것도 안 봄'이다)"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
