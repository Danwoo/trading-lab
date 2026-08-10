"""PR 의 커밋 저자 신원을 브랜치 선언과 대조한다 — 순수 판정, stdlib 전용 (#23 Task 9).

## 왜 있나

리드 지시: **「근원적으로 누가 썼는지 모르는 PR 이 나오면 안 된다.」**

에이전트 워크트리는 디스패치 때 `git config --worktree user.email` 로 §6.1 신원을 받는다.
그 설정을 빠뜨리면 커밋이 리드 신원(`tjeksdn173@gmail.com`)으로 찍히고, squash 머지 뒤
main 에는 **사람이 쓴 것**으로 남는다. 지금 그것을 잡는 그물이 하나도 없었다.

## 무엇을 위반으로 보나 (근거는 아래 「판정 범위의 한계」와 함께 읽어라)

  R0 검사 대상 0건 — 커밋 목록이 비었거나 리스트가 아니다. **fail-closed** 다:
     「볼 게 없어서 통과」가 되면 그물이 초록으로 죽는다
  R1 어휘 밖 에이전트형 신원 — `<벤더>[-<티어>]-agent@noreply.local` 형식은 맞는데 벤더·티어가
     어휘(`review_route.VENDOR_TIERS`) 밖이다. 누가 썼는지 못 읽는다
  R2 `noreply.local` 인데 신원 형식이 아예 아니다 (`claude@noreply.local`·`agent@noreply.local`).
     **`review_route._AGENTISH` 는 `-agent@` 접미만 보므로 이런 근접 오타를 「사람 저자」로
     읽는다** — 신원을 흉내 낸 것이 사람으로 접히는 자리라 여기서 막는다
  R3 브랜치가 에이전트를 선언했는데 그 벤더의 신원 커밋이 0건 — 디스패치가 신원 설정을
     빠뜨린 바로 그 모양이다
  R4 브랜치가 선언한 벤더와 커밋 신원의 벤더가 어긋난다 (커밋에 에이전트 신원은 있는데
     선언된 벤더가 그 목록에 없다)

봇 PR(dependabot 등)은 R1·R2·R3·R4 면제다 — 봇 신원은 GitHub 이 보증한다. R0 은 면제가 없다.
사람 브랜치·사람 신원은 정상이다.

## 브랜치가 에이전트를 선언한다는 것

레포 규약 두 가지가 벤더를 브랜치명에 싣는다 — 전역 `CLAUDE.md` 의 `fix-<이슈>-<에이전트>` 와
루트 `CLAUDE.md` 「목표층 문서 변경」의 `goal-<주제>-<에이전트>`. 둘의 공통 신호는 **끝의
`-<벤더>`** 이므로 그것을 본다. `review_route` 의 라우팅용 판별(`^fix-N-<벤더>$`)보다 넓은데,
의도적이다: 라우팅은 리뷰어를 배정하려고 벤더를 **확신**해야 하지만 이 그물은 「에이전트라고
선언했다」만 알면 되고, 넓을수록 더 잡는다. 실측(2026-08-09, 최근 머지 PR 15건)에서
`^fix-N-<벤더>$` 에 걸리는 브랜치는 **0건**이고 접미형은 3건이었다.

## 판정 범위의 한계 — 이 그물이 못 잡는 것

**`Danwoo/<슬러그>` 꼴 브랜치는 벤더를 선언하지 않는다.** Orca 워크트리가 만드는 이름이고
에이전트도 리드도 쓴다 (실측: `Danwoo/ci-task7-followup` 은 에이전트, `Danwoo/m2-orientation`
은 리드). 그런 브랜치에서 에이전트가 신원 설정을 빠뜨리면 커밋은 리드 신원이 되고, **이
그물은 그것을 사람 저자와 구분할 수 없다** — 리드와 에이전트가 같은 GitHub 계정·같은 git
신원을 쓰기 때문이고, 그 사실은 서버측에서도 못 가른다는 것이 2026-08-09 결정에 이미 적혀
있다. 즉 이 검사는 **선언한 것을 지켰는지**를 보는 그물이지 「모든 PR 의 저자를 안다」의
증명이 아니다. 남은 구멍은 브랜치 이름 규약을 지키는 것으로만 닫힌다.

## 실행

  echo '<payload>' | python3 scripts/pr_authorship.py     # 종료코드 0 통과 · 1 위반
"""

from __future__ import annotations

import json
import re
import sys

import review_route

# 브랜치가 에이전트를 선언하는 신호 — 끝의 `-<벤더>` (위 「브랜치가 에이전트를 선언한다는 것」)
_BRANCH_DECLARES = re.compile(r"-(?P<vendor>claude|kimi|codex)\Z")
# 에이전트 신원 도메인. 이 도메인을 쓰면서 형식이 안 맞으면 사람이 아니라 **판독 불가**다.
_AGENT_DOMAIN = "@noreply.local"


def read_identities(commits) -> dict:
    """커밋 목록에서 신원을 갈라 읽는다 — 판정 이전의 사실 수집.

    반환: `known`(어휘 안 신원의 벤더 집합) · `unknown_agentish`(어휘 밖 에이전트형) ·
    `malformed_local`(`noreply.local` 인데 신원 형식이 아닌 것) · `plain`(그 밖의 이메일).
    같은 이메일이 여러 커밋에 있으면 한 번만 센다 — 목록 길이가 아니라 **종류**가 판정 입력이다.
    """
    known: set[str] = set()
    unknown_agentish: list[str] = []
    malformed_local: list[str] = []
    plain: list[str] = []
    for email in sorted({(c or {}).get("author_email") or "" for c in commits}):
        if not email:
            malformed_local.append("(빈 이메일)")
            continue
        identity = review_route._IDENTITY.match(email)
        if identity and (
            identity.group("tier") is None
            or identity.group("tier")
            in review_route.VENDOR_TIERS[identity.group("vendor")]
        ):
            known.add(identity.group("vendor"))
        elif review_route._AGENTISH.search(email):
            unknown_agentish.append(email)
        elif email.lower().endswith(_AGENT_DOMAIN):
            # `claude@noreply.local` 처럼 접미 계약(`-agent@`)을 안 지킨 것. review_route 는
            # 이것을 사람으로 접는다 — 여기서 판독 불가로 막지 않으면 신원 흉내가 사람이 된다.
            malformed_local.append(email)
        else:
            plain.append(email)
    return {
        "known_vendors": sorted(known),
        "unknown_agentish": unknown_agentish,
        "malformed_local": malformed_local,
        "human_emails": plain,
    }


def branch_vendor(head_ref):
    m = _BRANCH_DECLARES.search(head_ref or "")
    return m.group("vendor") if m else None


def judge(payload) -> dict:
    """위반 목록과 판독 결과를 낸다 — `violations` 가 비어야 통과다."""
    commits = payload.get("commits")
    head_ref = payload.get("head_ref") or ""
    is_bot = bool(payload.get("pr_author_is_bot"))
    declared = branch_vendor(head_ref)

    base = {
        "head_ref": head_ref,
        "branch_declares": declared,
        "pr_author_is_bot": is_bot,
        "commits_checked": 0,
        "known_vendors": [],
        "unknown_agentish": [],
        "malformed_local": [],
        "human_emails": [],
        "authorship": "미상",
        "violations": [],
    }

    # R0 — 검사 대상 0건은 통과가 아니다 (fail-closed). 봇도 면제되지 않는다.
    if not isinstance(commits, list) or not commits:
        return {
            **base,
            "violations": [
                "R0 검사 대상 0건 — 커밋 목록이 비었거나 읽지 못했다. "
                "「볼 게 없어서 통과」로 두면 이 그물이 초록으로 죽는다 (fail-closed)"
            ],
        }

    read = read_identities(commits)
    result = {**base, "commits_checked": len(commits), **read}
    result["authorship"] = describe_authorship(read, is_bot)

    if is_bot:
        # 봇 PR — 신원을 GitHub 이 보증한다. R0 만 걸고 나머지는 면제 (dependabot 은 정상)
        return result

    violations: list[str] = []
    for email in read["unknown_agentish"]:
        violations.append(
            f"R1 어휘 밖 에이전트형 커밋 신원: {email} — 벤더·티어가 "
            "review_route 의 어휘에 없어 누가 썼는지 읽을 수 없다. "
            "어휘를 늘리거나 신원을 고쳐라"
        )
    for email in read["malformed_local"]:
        violations.append(
            f"R2 신원 형식이 아닌 {_AGENT_DOMAIN} 커밋 신원: {email} — "
            "형식은 `<벤더>[-<티어>]-agent@noreply.local` 다. 접미 계약을 안 지킨 값은 "
            "사람 저자로 접혀 provenance 가 조용히 사라진다"
        )
    if declared:
        if not read["known_vendors"]:
            violations.append(
                f"R3 브랜치가 에이전트({declared})를 선언했는데 에이전트 신원 커밋이 0건이다 — "
                "디스패치가 `git config --worktree user.email` 을 빠뜨리면 커밋이 리드 신원으로 "
                "찍히고 사람이 쓴 것으로 읽힌다"
            )
        elif declared not in read["known_vendors"]:
            violations.append(
                f"R4 브랜치가 선언한 벤더({declared})가 커밋 신원의 벤더"
                f"({', '.join(read['known_vendors'])})에 없다 — 둘 중 하나가 사실이 아니다"
            )

    result["violations"] = violations
    return result


def describe_authorship(read, is_bot) -> str:
    """읽어 낸 저자 표기 — 위반이 아니어도 항상 로그·요약에 남긴다."""
    if is_bot:
        return "봇"
    if read["unknown_agentish"] or read["malformed_local"]:
        return "미상(판독 불가한 신원 포함)"
    vendors = read["known_vendors"]
    if vendors and read["human_emails"]:
        return f"{','.join(vendors)} + 사람"
    if vendors:
        return ",".join(vendors)
    return "사람(에이전트 신원 없음)"


def main(argv) -> int:
    payload = json.load(sys.stdin)
    result = judge(payload)
    print(
        f"브랜치: {result['head_ref'] or '(미상)'} · "
        f"선언된 에이전트: {result['branch_declares'] or '없음'} · "
        f"검사한 커밋 {result['commits_checked']}건"
    )
    print(f"판독한 저자: {result['authorship']}")
    if result["known_vendors"]:
        print(f"  에이전트 신원 벤더: {', '.join(result['known_vendors'])}")
    if result["human_emails"]:
        print(f"  그 밖의 이메일 {len(result['human_emails'])}종")
    if not result["violations"]:
        print("판정: 저자 신원 위반 0건")
        return 0
    for v in result["violations"]:
        print(f"::error::{v}")
    print(f"판정: 저자 신원 위반 {len(result['violations'])}건")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
