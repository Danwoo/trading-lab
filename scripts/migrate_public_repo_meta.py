"""공개 레포 이사 — 파일이 아닌 것을 옮긴다 (라벨·마일스톤·열린 이슈) (#360).

`scripts/release_public.py` 는 **트리만** 옮긴다. 완전 이사는 그 밖의 것이 남는다.
이 스크립트는 그중 **자동화되는 세 가지**를 옮긴다 — 라벨·마일스톤·열린 이슈.

    python3 scripts/migrate_public_repo_meta.py --target <owner/repo>            # 드라이런
    python3 scripts/migrate_public_repo_meta.py --target <owner/repo> --execute  # 실제 생성

기본은 **드라이런**이다. 이슈 생성은 GitHub 에 남는 되돌릴 수 없는 외부 작용이고
(닫을 수는 있어도 번호는 회수되지 않는다), 아무 인자도 안 준 실행이 사고가 되지 않게 한다.

──────────────────────────────────────────────────────────────────────────────
## 무엇을 옮기고 무엇을 안 옮기나

**옮긴다**

  · **라벨** — 이름·색·설명. 대상에 없으면 만들고, 있는데 색·설명이 다르면 갱신한다.
    라벨은 워크플로가 **이름으로** 읽는다(`review: passed`·`human: merge`·`risk: low` …).
    이름이 하나라도 빠지면 그 라벨을 붙이는 워크플로 단계가 조용히 실패한다.
  · **마일스톤** — 제목·설명·상태·마감일. 이슈의 소속을 복원하려면 먼저 있어야 한다.
  · **열린 이슈** — 본문·라벨·마일스톤. 각 이슈 본문 맨 위에 출처 표시 주석을 박는다
    (아래 「멱등」).

**안 옮긴다 (구조적으로 못 옮기거나, 사람이 정할 것)**

  · **닫힌 이슈** — 이 레포에 229건 있다 (2026-08-07 측정). 리드 결정으로 개발 레포는
    **보관용으로 남으므로** 이력은 거기 그대로 있다. 옮기면 공개본에 「이미 끝난 일」이
    번호만 새로 붙어 쌓인다. 필요하면 `--include-closed` 로 켠다 (기본 꺼짐).
  · **PR** — 못 옮긴다. PR 은 브랜치·커밋에 묶여 있고, 공개본에는 그 커밋이 하나도 없다
    (이관 커밋은 개발 히스토리를 조상으로 갖지 않는다). 열린 PR 은 **이사 전에 개발
    레포에서 머지하거나 닫는다** — 런북의 사전 조건이다.
  · **이슈 코멘트** — 옮기지 않는다. 코멘트까지 옮기면 작성자가 전부 이사 실행자 명의가 되어
    누가 무엇을 말했는지가 **거짓이 된다.** 본문의 출처 링크로 원본을 가리키는 편이 정직하다.
  · **프로젝트 보드** — 옮길 필요가 없다. 실측: `BOARD_PROJECT_ID` 는 **사용자 레벨**
    프로젝트(`https://github.com/users/<user>/projects/2`)이고, 레포에 묶여 있지 않다
    (`projectV2.repositories` 가 빈 목록). 새 레포에서도 **같은 ID 를 그대로** 쓰면 된다.

──────────────────────────────────────────────────────────────────────────────
## 이슈 번호는 보존되지 않는다 — 그래서 본문의 `#N` 은 옛 번호다

새 레포의 이슈 번호는 1부터 다시 붙는다. GitHub 에는 번호를 지정해 이슈를 만드는 API 가
없다. 그래서 **본문 안의 `#N` 표기는 건드리지 않는다** — 자동 치환은 코드 블록·커밋 메시지
인용·「#1 번 항목」 같은 산문까지 함께 망가뜨리고, 그 손상은 조용하다.

대신 두 가지를 한다:

  · 본문 맨 위에 **출처 한 줄**을 붙인다 (`옮겨온 이슈: <source>#414`).
  · 실행이 끝나면 **옛 번호 → 새 번호 대조표**를 출력한다. 사람이 그 표를 보고 필요한
    본문만 고친다.

옛 개발 레포가 **보관용으로 비공개로 남으므로** 출처 링크는 리드에게만 열린다. 공개본을 읽는
제3자에게는 404 다 — 이것은 「히스토리를 안 내보낸다」는 리드 결정(#360 ㉡)의 필연적 대가이지
결함이 아니다. **이사 이후의 이슈는 공개 레포에서 새로 열리므로 이 제약을 받지 않는다.**

## 멱등 — 두 번 돌려도 이슈가 두 벌 생기지 않는다

이슈 생성은 되돌릴 수 없으므로 재실행 안전성이 필수다. 만드는 이슈 본문에

    <!-- migrated-from: <owner/repo>#<번호> -->

주석을 박고, 만들기 **전에** 대상 레포에서 같은 마커를 찾는다. 이미 있으면 건너뛴다.
라벨·마일스톤도 이름·제목으로 대조해 있으면 안 만든다.

**마커 조회는 GitHub 검색이 아니라 이슈 전수 조회로 한다** — 검색 인덱스는 방금 만든 이슈를
바로 반영하지 않아(비동기), 같은 실행 안에서도 중복을 낼 수 있다.

## fail-closed

  · 대상 레포에 접근할 수 없으면 시작하지 않는다.
  · **옮길 대상이 0건인 범주가 있으면 실패한다.** 라벨 0·마일스톤 0 은 이 레포에서 일어날 수
    없고, 일어났다면 조회가 깨진 것이다. 열린 이슈 0 은 있을 수 있으나 「조용히 아무것도
    안 옮김」이 가장 나쁜 결과이므로 기본은 실패이고 `--allow-no-issues` 로만 넘어간다.
  · 범주별로 **조회 몇 건 · 생성 몇 건 · 건너뜀 몇 건**을 항상 출력한다 — 초록이
    「다 옮겼다」인지 「아무것도 안 봤다」인지 읽는 사람이 구분할 수 있어야 한다.

## 이 스크립트가 못 하는 것

  · **대상 레포를 만들지 않는다.** 레포 생성·공개 전환은 리드가 직접 한다.
  · **출처 이슈를 닫지 않는다.** 개발 레포의 상태를 바꾸는 것은 별개 판단이라
    `--close-source` 를 명시했을 때만 한다 (기본 꺼짐).
  · **라벨을 지우지 않는다.** 대상에만 있는 라벨은 그대로 둔다 — 새 레포의 기본 라벨을
    이사가 임의로 치우면 되돌릴 근거가 없다.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

MARKER = "<!-- migrated-from: {source}#{number} -->"
MARKER_PATTERN = re.compile(r"<!--\s*migrated-from:\s*(\S+)#(\d+)\s*-->")


class GhError(RuntimeError):
    """`gh` 호출이 실패했다 — 조용히 빈 목록으로 떨어지지 않게 예외로 올린다."""


def gh(*args: str, check: bool = True) -> str:
    result = subprocess.run(["gh", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if check and result.returncode != 0:
        raise GhError(f"gh {' '.join(args)} 실패: {result.stderr.strip()}")
    return result.stdout


def gh_json(*args: str) -> object:
    text = gh(*args).strip()
    if not text:
        raise GhError(f"gh {' '.join(args)} 가 빈 응답을 돌려줬다 — 조회가 깨졌다")
    return json.loads(text)


def fail(message: str) -> int:
    print(f"\n중단: {message}")
    return 1


# ── 조회 ─────────────────────────────────────────────────────────────────────
def source_labels(source: str) -> list[dict]:
    return gh_json(
        "api",
        f"repos/{source}/labels",
        "--paginate",
        "-q",
        "[.[] | {name,color,description}]",
    )  # type: ignore[return-value]


def source_milestones(source: str) -> list[dict]:
    return gh_json(
        "api",
        f"repos/{source}/milestones?state=all",
        "--paginate",
        "-q",
        "[.[] | {number,title,description,state,due_on}]",
    )  # type: ignore[return-value]


def source_issues(source: str, include_closed: bool) -> list[dict]:
    state = "all" if include_closed else "open"
    raw = gh_json(
        "issue",
        "list",
        "--repo",
        source,
        "--state",
        state,
        "--limit",
        "1000",
        "--json",
        "number,title,body,state,labels,milestone",
    )
    # `gh issue list` 는 PR 을 섞지 않는다 (이슈 전용 명령) — 별도 필터 불필요.
    return sorted(raw, key=lambda issue: issue["number"])  # type: ignore[arg-type,index]


def target_labels(target: str) -> dict[str, dict]:
    rows = gh_json(
        "api",
        f"repos/{target}/labels",
        "--paginate",
        "-q",
        "[.[] | {name,color,description}]",
    )
    return {row["name"]: row for row in rows}  # type: ignore[index,union-attr]


def target_milestones(target: str) -> dict[str, dict]:
    rows = gh_json(
        "api",
        f"repos/{target}/milestones?state=all",
        "--paginate",
        "-q",
        "[.[] | {number,title,state}]",
    )
    return {row["title"]: row for row in rows}  # type: ignore[index,union-attr]


def target_migrated_markers(target: str) -> dict[str, int]:
    """대상 레포에 이미 옮겨진 이슈: `"<source>#<옛번호>" → 새 번호`.

    **검색 API 를 쓰지 않는다** — 인덱스가 비동기라 방금 만든 이슈를 못 찾고, 그러면 같은
    실행 안에서도 중복이 난다. 이슈 전수 조회는 느리지만 바로 정확하다.
    """
    rows = gh_json(
        "issue",
        "list",
        "--repo",
        target,
        "--state",
        "all",
        "--limit",
        "1000",
        "--json",
        "number,body",
    )
    found: dict[str, int] = {}
    for row in rows:  # type: ignore[union-attr]
        match = MARKER_PATTERN.search(row.get("body") or "")
        if match:
            found[f"{match.group(1)}#{match.group(2)}"] = row["number"]
    return found


# ── 이관 ─────────────────────────────────────────────────────────────────────
def migrate_labels(source: str, target: str, execute: bool) -> tuple[int, int, int, int]:
    """(조회, 생성, 갱신, 그대로)."""
    wanted = source_labels(source)
    existing = target_labels(target)
    created = updated = same = 0
    for label in wanted:
        name = label["name"]
        color = label["color"]
        description = label.get("description") or ""
        current = existing.get(name)
        if current is None:
            print(f"  + 라벨 생성  {name}  #{color}")
            created += 1
            if execute:
                gh(
                    "api",
                    "--method",
                    "POST",
                    f"repos/{target}/labels",
                    "-f",
                    f"name={name}",
                    "-f",
                    f"color={color}",
                    "-f",
                    f"description={description}",
                )
        elif current["color"] != color or (current.get("description") or "") != description:
            print(f"  ~ 라벨 갱신  {name}  #{current['color']} → #{color}")
            updated += 1
            if execute:
                gh(
                    "api",
                    "--method",
                    "PATCH",
                    f"repos/{target}/labels/{name}",
                    "-f",
                    f"new_name={name}",
                    "-f",
                    f"color={color}",
                    "-f",
                    f"description={description}",
                )
        else:
            same += 1
    return len(wanted), created, updated, same


def migrate_milestones(source: str, target: str, execute: bool) -> tuple[int, int, int, dict[str, int]]:
    """(조회, 생성, 그대로, 제목→대상 번호 대조표).

    드라이런에서는 새로 만들 마일스톤의 대상 번호를 알 수 없다. 그 자리는 대조표에서 빼고
    이슈 단계가 「드라이런이라 미정」으로 출력한다 — 없는 번호를 지어내지 않는다.
    """
    wanted = source_milestones(source)
    existing = target_milestones(target)
    created = same = 0
    mapping: dict[str, int] = {title: row["number"] for title, row in existing.items()}
    for milestone in wanted:
        title = milestone["title"]
        if title in existing:
            same += 1
            continue
        print(f"  + 마일스톤 생성  {title}  ({milestone['state']})")
        created += 1
        if execute:
            args = [
                "api",
                "--method",
                "POST",
                f"repos/{target}/milestones",
                "-f",
                f"title={title}",
                "-f",
                f"state={milestone['state']}",
                "-f",
                f"description={milestone.get('description') or ''}",
            ]
            if milestone.get("due_on"):
                args += ["-f", f"due_on={milestone['due_on']}"]
            response = json.loads(gh(*args))
            mapping[title] = response["number"]
    return len(wanted), created, same, mapping


def migrate_issues(
    source: str,
    target: str,
    issues: list[dict],
    milestone_numbers: dict[str, int],
    execute: bool,
) -> tuple[int, int, int, list[tuple[int, str]]]:
    """(조회, 생성, 건너뜀, [(옛 번호, 새 번호 또는 '드라이런')])."""
    already = target_migrated_markers(target)
    created = skipped = 0
    mapping: list[tuple[int, str]] = []
    for issue in issues:
        number = issue["number"]
        key = f"{source}#{number}"
        if key in already:
            print(f"  · 이슈 건너뜀 #{number} — 대상에 이미 있다 (#{already[key]})")
            skipped += 1
            mapping.append((number, f"#{already[key]} (기존)"))
            continue

        labels = [label["name"] for label in issue.get("labels") or []]
        milestone = (issue.get("milestone") or {}).get("title")
        body = (
            f"{MARKER.format(source=source, number=number)}\n"
            f"> 옮겨온 이슈: `{source}#{number}` — 본문 안의 `#N` 은 **옛 레포의 번호**다.\n\n"
            f"{issue.get('body') or ''}"
        )
        target_milestone = milestone_numbers.get(milestone) if milestone else None
        shown = (
            f"마일스톤 {milestone}"
            if milestone and target_milestone
            else (f"마일스톤 {milestone} (드라이런 — 대상 번호 미정)" if milestone else "마일스톤 없음")
        )
        print(f"  + 이슈 생성  #{number} {issue['title'][:60]}")
        print(f"      라벨 {len(labels)}개 · {shown}")
        created += 1
        if not execute:
            mapping.append((number, "드라이런"))
            continue

        args = [
            "issue",
            "create",
            "--repo",
            target,
            "--title",
            issue["title"],
            "--body",
            body,
        ]
        for label in labels:
            args += ["--label", label]
        if milestone:
            # 대상 마일스톤은 **제목으로** 붙인다 — 번호는 레포마다 다르고, 제목은 방금
            # 마일스톤 단계가 존재를 보장했다.
            args += ["--milestone", milestone]
        url = gh(*args).strip().splitlines()[-1]
        new_number = url.rsplit("/", 1)[-1]
        print(f"      → {url}")
        mapping.append((number, f"#{new_number}"))
    return len(issues), created, skipped, mapping


def close_source_issues(source: str, issues: list[dict], target: str, execute: bool) -> int:
    closed = 0
    for issue in issues:
        number = issue["number"]
        print(f"  × 출처 이슈 닫기 {source}#{number}")
        closed += 1
        if execute:
            gh(
                "issue",
                "close",
                str(number),
                "--repo",
                source,
                "--comment",
                f"공개 레포 이사로 `{target}` 으로 옮겼다 (#360). 후속은 그쪽에서 진행한다.",
            )
    return closed


# ── 본체 ─────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="공개 레포 이사 — 라벨·마일스톤·열린 이슈를 옮긴다")
    parser.add_argument("--target", required=True, help="대상 레포 `owner/repo` (필수)")
    parser.add_argument("--source", default=None, help="출처 레포 `owner/repo` (기본: 이 레포)")
    parser.add_argument("--execute", action="store_true", help="실제로 만든다 (기본은 드라이런)")
    parser.add_argument("--include-closed", action="store_true", help="닫힌 이슈도 옮긴다 (기본 꺼짐)")
    parser.add_argument(
        "--allow-no-issues",
        action="store_true",
        help="옮길 이슈가 0건이어도 실패로 보지 않는다",
    )
    parser.add_argument(
        "--close-source",
        action="store_true",
        help="옮긴 뒤 출처 이슈를 닫는다 (기본 꺼짐 — 개발 레포 상태 변경은 별개 판단)",
    )
    args = parser.parse_args(argv)

    source = args.source or gh("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
    if not source:
        return fail("출처 레포를 판정할 수 없다 — `--source owner/repo` 로 명시하라")
    if source == args.target:
        return fail(f"출처와 대상이 같다 ({source}) — 자기 자신으로 이사할 수 없다")

    mode = "실행 (실제로 만든다)" if args.execute else "드라이런 (아무것도 만들지 않는다)"
    print(f"== 공개 레포 이사: {source} → {args.target} ==")
    print(f"  · 모드: {mode}")

    try:
        gh("api", f"repos/{args.target}", "-q", ".full_name")
    except GhError as error:
        return fail(f"대상 레포에 접근할 수 없다 ({args.target}) — 먼저 리드가 레포를 만들어야 한다. {error}")

    try:
        print("\n-- 1. 라벨 --")
        label_seen, label_new, label_upd, label_same = migrate_labels(source, args.target, args.execute)
        print(f"  · 출처 라벨 {label_seen}개 — 생성 {label_new} · 갱신 {label_upd} · 그대로 {label_same}")
        if label_seen == 0:
            return fail("출처 라벨 0건 — 조회가 깨졌다 (fail-closed)")

        print("\n-- 2. 마일스톤 --")
        ms_seen, ms_new, ms_same, ms_numbers = migrate_milestones(source, args.target, args.execute)
        print(f"  · 출처 마일스톤 {ms_seen}개 — 생성 {ms_new} · 그대로 {ms_same}")
        if ms_seen == 0:
            return fail("출처 마일스톤 0건 — 조회가 깨졌다 (fail-closed)")

        print(f"\n-- 3. 이슈 ({'열림+닫힘' if args.include_closed else '열린 것만'}) --")
        issues = source_issues(source, args.include_closed)
        if not issues and not args.allow_no_issues:
            return fail(
                "옮길 이슈 0건 — 조회가 깨졌을 수 있다. 정말 0건이면 `--allow-no-issues` 로 명시하라 (fail-closed)"
            )
        issue_seen, issue_new, issue_skip, mapping = migrate_issues(
            source, args.target, issues, ms_numbers, args.execute
        )
        print(f"  · 출처 이슈 {issue_seen}건 — 생성 {issue_new} · 건너뜀 {issue_skip}")

        closed = 0
        if args.close_source:
            print("\n-- 4. 출처 이슈 닫기 --")
            movable = [i for i in issues if i["state"].lower() == "open"]
            closed = close_source_issues(source, movable, args.target, args.execute)
            print(f"  · 닫은 이슈 {closed}건")
    except GhError as error:
        return fail(str(error))

    print("\n-- 이슈 번호 대조표 (본문의 `#N` 은 옛 번호다) --")
    if mapping:
        for old, new in mapping:
            print(f"  {source}#{old}  →  {args.target} {new}")
    else:
        print("  (없음)")

    print(f"\n== 집계: 라벨 {label_seen} · 마일스톤 {ms_seen} · 이슈 {issue_seen} 을 검사했다 ==")
    if not args.execute:
        print(
            "== 드라이런 종료 — 아무것도 만들지 않았다 ==\n"
            "  실제로 옮기려면: --execute 를 붙여 다시 실행하라.\n"
            "  두 번 돌려도 안전하다 — 옮긴 이슈는 본문 마커로 알아보고 건너뛴다."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
