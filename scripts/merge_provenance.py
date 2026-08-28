"""머지 커밋에 `작성 · 리뷰 · 머지` 를 남긴다 — 순수 판정, stdlib 전용 (#23 Task 9).

## 왜 있나

이 레포는 squash 머지를 쓴다. squash 는 커밋 author 를 지워 main 의 모든 커밋이
`Danwoo <tjeksdn173@gmail.com>` 이 된다 (실측: `git log origin/main --format=%ae | grep -c
"agent@noreply.local"` → **0**). 저자 축은 GitHub 이 붙이는 `Co-authored-by:` 트레일러가
간신히 남기고 있지만(같은 명령을 `%b` 로 재면 15건), **리뷰어와 머지 주체는 어디에도 없다.**
누가 리뷰했는지는 PR 코멘트에만 있고, 리드가 눌렀는지 워크플로가 밀었는지는 GitHub API 를
따로 물어야 안다. `git log` 만으로는 못 읽는다.

그래서 머지 시점에 한 줄을 남긴다:

    작성: claude(opus) · 리뷰: claude(sonnet) · 머지: 자동

## 왜 본문을 통째로 만들어 넘기나

레포 설정이 `squash_merge_commit_message = COMMIT_MESSAGES` 라(2026-08-09 실측) squash 본문은
**브랜치 커밋 메시지들 + `Co-authored-by:` 트레일러**로 GitHub 이 조립한다. `gh pr merge --body`
는 그것을 **대체**하므로, 한 줄을 더하려고 body 를 넘기면 그 조립분이 통째로 사라진다 —
지금 유일하게 살아 있는 저자 provenance(`Co-authored-by:`)와 커밋 메시지 열 개가 함께.
그래서 GitHub 이 만들 본문을 **똑같이 재현한 뒤 거기에 한 줄을 더한다.** 재현식은 실물
대조로 고정했다 (`test_merge_provenance.py` 가 머지된 PR 전수를 실제 본문과 바이트 대조).

재현식 (머지된 PR 51건 실물 대조로 고정):
  · 머지 커밋(부모 2개 이상)은 메시지 조립에서 **뺀다**
  · 남은 커밋 1개  → 그 메시지에서 **제목 줄과 뒤따르는 빈 줄을 뺀 나머지**
  · 남은 커밋 N개  → `* <커밋 메시지 전문>` 을 빈 줄로 이어 붙이고 `---------` 구분선
  · 그 뒤에 커밋 **저자**(커미터 아님)로 만든 `Co-authored-by:` 트레일러. 본문이 이미
    트레일러로 끝나면(dependabot 의 `Signed-off-by:`) 빈 줄 없이 이어 붙인다

우리 줄은 **트레일러 블록 앞**에 빈 줄을 두고 넣는다 — `Co-authored-by:` 가 본문 마지막
트레일러 블록으로 남아야 git·GitHub 의 트레일러 판독이 그대로 선다.

## 어휘 — 한 곳에서 정의하고 재사용한다

  작성  `claude(opus)` · `claude(티어 미상)` · `claude,kimi` · `봇` · `사람` · `미상`
        (에이전트와 사람이 섞이면 `claude(opus) + 사람`)
  리뷰  `claude(sonnet)` · `kimi` · `미상`
  머지  `사람` · `자동` · `지휘자` · `미상`

**모르는 것은 「미상」이다.** 지어내지 않는다 — 옛 마커(티어 없음)·신원 없는 커밋·읽지 못한
조회가 전부 그렇다. 이 task 전체가 「기록을 믿을 수 있게 만드는」 일이라 거짓 기록은 기록
없음보다 나쁘다.

## 이 줄이 닿지 않는 자리

**리드가 GitHub 버튼으로 직접 머지하면 이 줄은 남지 않는다.** 그때 커밋 메시지를 만드는
것은 GitHub 이고 우리가 끼어들 자리가 없다. 레포 설정(`squash_merge_commit_message`)을
바꾸면 PR 본문 경로가 열리지만 그것은 이 작업의 경계 밖이다(레포 설정 불가침). 그 경우에도
`Co-authored-by:` 는 그대로라 **작성 축은 남고 리뷰·머지 축이 빈다.**

## 서브커맨드 (stdin JSON → stdout JSON)

  line  provenance 한 줄만 만든다
  body  재현한 squash 본문 + provenance 줄을 만든다 (`--no-line` 이면 재현만 — 대조용)
"""

from __future__ import annotations

import json
import re
import sys

import review_route

# `Token: value` — git 이 트레일러로 읽는 꼴. 이어 붙일 때 빈 줄을 넣을지 가른다.
_TRAILER_LINE = re.compile(r"^[A-Za-z][A-Za-z-]*:\s")

# 머지 주체 어휘 — 워크플로가 이 키로 넘긴다. 값은 사람이 `git log` 에서 읽는 말이다.
MERGED_BY = {
    "human": "사람",  # 리드가 버튼을 눌렀다 (이 경로는 아래 「닿지 않는 자리」)
    "auto": "자동",  # 판정·게이트가 서서 자동 머지가 arm 됐다
    "delegate": "지휘자",  # 지휘자가 위임 머지 워크플로를 돌렸다
}
UNKNOWN = "미상"
# 「에이전트 신원이 하나도 없다」는 **사람이라는 뜻이 아니다** — 신원 설정을 빠뜨린 에이전트도
# 같은 모양이고 리드와 같은 git 신원을 쓰므로 가를 수 없다. 종전엔 이 자리를 「사람」으로
# 적었는데, 그것은 없는 사실을 기록하는 것이다 (CONTEXT 2026-08-09: 「모르는 것은 미상으로
# 적는다」). 바로 앞 `UNKNOWN` 과 구분되게 사유를 함께 싣는다 — 그쪽은 커밋을 아예 못 읽었거나
# 신원이 판독 불가인 경우다.
NO_IDENTITY = "미상(신원 없음)"
COAUTHOR_PREFIX = "Co-authored-by: "


def _strip_subject(message: str) -> str:
    """커밋 메시지에서 제목 줄과 뒤따르는 빈 줄을 뗀다 (단일 커밋 squash 의 본문)."""
    lines = (message or "").split("\n")
    rest = lines[1:]
    while rest and not rest[0].strip():
        rest.pop(0)
    return "\n".join(rest).rstrip()


def _is_merge(commit) -> bool:
    """머지 커밋인가 — 부모가 둘 이상. GitHub 은 이것의 메시지를 squash 본문에 안 넣는다."""
    try:
        return int(commit.get("parents") or 1) > 1
    except (TypeError, ValueError):
        return False


def coauthor_trailers(commits) -> list[str]:
    """`Co-authored-by:` 줄 목록 — 커밋 **저자**를 첫 등장 순서로, 중복 없이.

    커미터는 안 본다 (실측: dependabot 커밋의 커미터는 `GitHub <noreply@github.com>` 인데
    트레일러에 안 실린다). 머지 커밋의 저자도 그대로 싣는다 (PR #55: `Merge branch 'main'
    into …` 의 저자가 트레일러에 있다).

    **머지 주체 제외는 재현하지 않는다.** GitHub 은 버튼을 누른 사람이 커밋 저자이기도 하면
    그 사람을 트레일러에서 뺀다 (머지된 PR 51건 대조에서 #69·#24 두 건이 그 모양이다).
    우리 경로에서는 그 규칙이 발동하지 않는다 — 워크플로 머지의 주체는 `github-actions[bot]`
    이고 그 신원으로 커밋한 사람은 없다. 그래서 「저자 전부」가 우리 경로에서는 정확하고,
    사람 버튼 경로는 애초에 이 함수가 닿지 않는다 (파일 머리 「이 줄이 닿지 않는 자리」).
    빼는 쪽으로 틀리면 진짜 기여자가 사라지지만, 안 빼서 틀리면 사실이 한 줄 더 남을 뿐이다.
    """
    seen, out = set(), []
    for c in commits or []:
        if not isinstance(c, dict):
            continue
        name, email = c.get("author_name"), c.get("author_email")
        if not name or not email or (name, email) in seen:
            continue
        seen.add((name, email))
        out.append(f"{COAUTHOR_PREFIX}{name} <{email}>")
    return out


def _tail_trailer_block(core: str) -> list[str]:
    """본문 끝에 붙어 있는 트레일러 줄들 — 없으면 빈 목록."""
    lines = (core or "").rstrip("\n").split("\n")
    block: list[str] = []
    for line in reversed(lines):
        if not _looks_like_trailer(line):
            break
        block.insert(0, line)
    return block


def signoff_trailers(commits, core: str) -> list[str]:
    """커밋 메시지 안의 `Signed-off-by:` 를 마지막 트레일러 블록으로 끌어올린다.

    GitHub 이 그렇게 한다 (PR #20 실측: 커밋 셋을 `*` 로 이어 붙이면 dependabot 의
    `Signed-off-by:` 가 `---------` 뒤에 **한 번 더** 나타난다). 단일 커밋이라 본문이 이미
    그 트레일러로 끝나면 다시 붙이지 않는다 (PR #55 실측: 한 번만 나온다) — 그래서
    이미 끝 블록에 있는 것은 뺀다.
    """
    present = set(_tail_trailer_block(core))
    seen, out = set(), []
    for c in commits or []:
        if not isinstance(c, dict) or _is_merge(c):
            continue
        for line in (c.get("message") or "").split("\n"):
            line = line.strip()
            if not line.startswith("Signed-off-by:"):
                continue
            if line in present or line in seen:
                continue
            seen.add(line)
            out.append(line)
    return out


def _looks_like_trailer(line: str) -> bool:
    """`Token: value` 꼴인가 — 트레일러 블록에 이어 붙일지 가르는 기준."""
    return bool(_TRAILER_LINE.match(line or ""))


def append_trailers(core: str, trailers: list[str]) -> str:
    """본문에 트레일러를 잇는다 — 이미 트레일러로 끝나면 **빈 줄 없이** 붙인다.

    dependabot 커밋은 `Signed-off-by:` 로 끝나는데, 실물 squash 본문은 거기에 빈 줄 없이
    `Co-authored-by:` 를 이어 붙인다. 빈 줄을 넣으면 트레일러 블록이 둘로 갈린다.
    """
    if not trailers:
        return core
    block = "\n".join(trailers)
    if not core:
        return block
    last = core.rstrip("\n").split("\n")[-1]
    joiner = "\n" if _looks_like_trailer(last) else "\n\n"
    return f"{core.rstrip(chr(10))}{joiner}{block}"


def final_trailers(commits, core: str) -> list[str]:
    """마지막 트레일러 블록 — 끌어올린 `Signed-off-by:` 뒤에 `Co-authored-by:` 가 온다."""
    return signoff_trailers(commits, core) + coauthor_trailers(commits)


def reproduce_squash_body(commits) -> str:
    """GitHub 이 `COMMIT_MESSAGES` 설정에서 만드는 squash 본문을 그대로 재현한다."""
    core = _core_from(commits)
    return append_trailers(core, final_trailers(commits, core))


def _core_from(commits) -> str:
    """커밋 메시지 조립부 — **머지 커밋은 뺀다** (GitHub 이 그렇게 한다, PR #55 실측)."""
    messages = [(c.get("message") or "").rstrip() for c in (commits or []) if isinstance(c, dict) and not _is_merge(c)]
    if not messages:
        return ""
    if len(messages) == 1:
        return _strip_subject(messages[0])
    return "\n\n".join(f"* {m}" for m in messages) + "\n\n---------"


def describe_author(commits, head_ref) -> str:
    """작성 축 — 커밋 신원에서 읽는다. 형식 판독의 SoT 는 `review_route` 하나다."""
    emails = [(c or {}).get("author_email") or "" for c in (commits or []) if isinstance(c, dict)]
    if not emails:
        return UNKNOWN
    identity = review_route.identify_author(emails, head_ref or "")
    if identity["unknown_agentish"]:
        # 어휘 밖 에이전트형 신원은 사람이 아니라 판독 불가다 (review_record 와 같은 규율)
        return UNKNOWN
    vendors = identity["vendors"]
    no_identity = any(e and not e.endswith("@noreply.local") for e in emails)
    if not vendors:
        return NO_IDENTITY if no_identity else UNKNOWN
    tier = identity["author_tier"]
    label = ",".join(vendors)
    if vendors == ["claude"]:
        label = f"claude({tier or '티어 미상'})"
    return f"{label} + {NO_IDENTITY}" if no_identity else label


def describe_reviewer(model, tier) -> str:
    """리뷰 축 — 마커의 `model=`·`tier=` 에서 읽는다. 티어는 관측값만 온다."""
    if model not in review_route.VENDOR_TIERS:
        return UNKNOWN
    if model != "claude":
        # kimi·codex 는 티어 축이 예약만 된 상태다 — `kimi(티어 미상)` 은 독자를 헷갈린다
        return model
    return f"claude({tier or '티어 미상'})"


def provenance_line(payload) -> str:
    author = describe_author(payload.get("commits"), payload.get("head_ref"))
    if payload.get("pr_author_is_bot"):
        author = "봇"
    reviewer = describe_reviewer(payload.get("reviewer_model") or "", payload.get("reviewer_tier") or "")
    merged = MERGED_BY.get(payload.get("merged_by") or "", UNKNOWN)
    return f"작성: {author} · 리뷰: {reviewer} · 머지: {merged}"


def build_body(payload, *, with_line: bool = True) -> str:
    """재현한 squash 본문 + provenance 줄 (트레일러 블록 **앞**에 넣는다)."""
    commits = payload.get("commits")
    core = _core_from(commits)
    # 트레일러는 **provenance 줄을 넣기 전의** 코어로 정한다 — 넣은 뒤에 정하면 코어가
    # 트레일러로 끝나지 않게 되어 이미 있는 `Signed-off-by:` 가 한 번 더 붙는다
    trailers = final_trailers(commits, core)
    if not with_line:
        return append_trailers(core, trailers)
    # provenance 줄은 **마지막 트레일러 블록 앞**의 자기 문단이다. 코어가 이미 트레일러로
    # 끝나면(dependabot 의 `Signed-off-by:`) 그 블록을 떼었다가 줄 뒤에 다시 붙인다 —
    # 사이에 산문 한 줄이 끼면 트레일러 블록이 둘로 갈려 git 의 트레일러 판독이 깨진다.
    tail = _tail_trailer_block(core)
    lines = core.rstrip("\n").split("\n") if core else []
    prose = "\n".join(lines[: len(lines) - len(tail)]).rstrip("\n")
    line = provenance_line(payload)
    prose = f"{prose}\n\n{line}" if prose else line
    return append_trailers(prose, tail + trailers)


def main(argv) -> int:
    command = argv[1] if len(argv) > 1 else ""
    payload = json.load(sys.stdin)
    if command == "line":
        json.dump({"line": provenance_line(payload)}, sys.stdout, ensure_ascii=False)
    elif command == "body":
        with_line = "--no-line" not in argv
        json.dump(
            {
                "line": provenance_line(payload),
                "body": build_body(payload, with_line=with_line),
            },
            sys.stdout,
            ensure_ascii=False,
        )
    else:
        print(f"::error::알 수 없는 서브커맨드: {command!r} (line|body)")
        return 1
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
