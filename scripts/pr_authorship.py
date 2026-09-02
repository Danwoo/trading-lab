"""PR 의 커밋 저자 신원이 읽히는지 판정한다 — 순수 판정, stdlib 전용 (#23 Task 9).

## 왜 있나

리드 지시: **「근원적으로 누가 썼는지 모르는 PR 이 나오면 안 된다.」**

에이전트 워크트리는 디스패치 때 `git config --worktree user.email` 로 §6.1 신원을 받는다.
그 설정을 빠뜨리면 커밋이 리드 신원(`tjeksdn173@gmail.com`)으로 찍히고, squash 머지 뒤
main 에는 **사람이 쓴 것**으로 남는다.

이 그물이 보는 것은 **실려 있는 신원이 읽히는가**다 — 신원을 흉내 냈지만 형식·어휘가
어긋나 조용히 「사람」으로 접히는 값을 막는다. 신원이 아예 없는 경우는 여기서 못 가르고
(아래 「판정 범위의 한계」), 자동 머지 arm 을 막는 것으로 받는다.

## 무엇을 위반으로 보나 (근거는 아래 「판정 범위의 한계」와 함께 읽어라)

  R0 검사 대상 0건 — 커밋 목록이 비었거나 리스트가 아니다. **fail-closed** 다:
     「볼 게 없어서 통과」가 되면 그물이 초록으로 죽는다
  R1 어휘 밖 에이전트형 신원 — `<벤더>[-<티어>]-agent@noreply.local` 형식은 맞는데 벤더·티어가
     어휘(`review_route.VENDOR_TIERS`) 밖이다. 누가 썼는지 못 읽는다
  R2 `noreply.local` 인데 신원 형식이 아예 아니다 (`claude@noreply.local`·`agent@noreply.local`).
     **`review_route._AGENTISH` 는 `-agent@` 접미만 보므로 이런 근접 오타를 「사람 저자」로
     읽는다** — 신원을 흉내 낸 것이 사람으로 접히는 자리라 여기서 막는다

봇 PR(dependabot 등)은 R1·R2 면제다 — 봇 신원은 GitHub 이 보증한다. R0 은 면제가 없다.
사람 신원은 정상이다.

## 없어진 R3·R4 — 브랜치가 벤더를 선언하지 않게 됐다 (2026-08-28)

종전에는 두 규칙이 더 있었다:

  R3 브랜치가 에이전트를 선언했는데 그 벤더의 신원 커밋이 0건 — 디스패치가
     `git config --worktree user.email` 을 빠뜨린 바로 그 모양이다
  R4 브랜치가 선언한 벤더와 커밋 신원의 벤더가 어긋난다

둘 다 입력이 **브랜치명 끝의 `-<벤더>`** 하나였다 (옛 규약 `fix-<이슈>-<에이전트>` ·
`goal-<주제>-<에이전트>`). 새 규약 `feature/<이슈>-<설명>`(리드 결정 2026-08-27)에는 그
선언이 없다 — 즉 두 규칙은 **영영 안 뜨는 채로 「검사했다」고 출력하는 상태**가 된다.
조용히 초록인 그물을 남기지 않는다는 원칙에 따라 지웠다 (리드 결정 2026-08-28).

**대신 받는 자리가 있다.** R3 이 잡던 「디스패치가 신원을 빠뜨렸다」는 이제
`review_route.identify_author` 가 `author_kind="unknown"` 으로 읽고
`review_record.judge_author_identity` 가 **자동 머지 arm 을 거부**한다 (봇만 면제).
R3 보다 넓다 — R3 은 브랜치가 벤더를 선언했을 때만 떴지만, arm 차단은 신원 없는 PR 전부에
걸린다. 대신 약하다 — CI 를 빨갛게 만들지 않고 자동 머지만 막는다. 그 교환이 필요한 이유는
아래 「판정 범위의 한계」다: **사람 PR 과 신원 없는 에이전트 PR 을 가를 방법이 없어**,
「신원 커밋 0건 = 위반」으로 하면 리드가 직접 쓴 PR 도 전부 빨간불이 된다.

## 판정 범위의 한계 — 이 그물이 못 잡는 것

**커밋 신원이 없는 PR 의 저자를 이 그물은 모른다.** 에이전트가 신원 설정을 빠뜨리면 커밋은
리드 신원(`tjeksdn173@gmail.com`)으로 찍히는데, **리드가 직접 쓴 것과 구분할 수 없다** —
리드와 에이전트가 같은 GitHub 계정·같은 git 신원을 쓰기 때문이고, 서버측에서도 못 가른다는
것이 2026-08-09 결정에 이미 적혀 있다. 즉 이 검사는 **신원이 실려 있을 때 그것이 읽히는지**를
보는 그물이지 「모든 PR 의 저자를 안다」의 증명이 아니다. 남은 구멍은 두 가지로만 좁혀진다 —
워크트리 신원 설정을 지키는 것(`.work/orders/BRANCH-RULE.md`), 그리고 신원 없는 PR 의 자동
머지를 막는 것(`review_record` 의 조건 ③).

## 실행

  echo '<payload>' | python3 scripts/pr_authorship.py     # 종료코드 0 통과 · 1 위반
"""

from __future__ import annotations

import json
import sys

import review_route

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
            or identity.group("tier") in review_route.VENDOR_TIERS[identity.group("vendor")]
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


def judge(payload) -> dict:
    """위반 목록과 판독 결과를 낸다 — `violations` 가 비어야 통과다."""
    commits = payload.get("commits")
    # 브랜치명은 **판정에 쓰지 않는다** — 새 규약에 벤더 선언이 없다 (위 「없어진 R3·R4」).
    # 로그에는 남긴다: 어느 PR 의 판정인지 사람이 알아보는 데 쓴다.
    head_ref = payload.get("head_ref") or ""
    is_bot = bool(payload.get("pr_author_is_bot"))

    base = {
        "head_ref": head_ref,
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
    # 「사람」이라 단정하지 않는다 — 신원 설정을 빠뜨린 에이전트도 같은 모양이고 가를 수 없다
    # (위 「판정 범위의 한계」). arm 판정도 이 입력을 `unknown` 으로 읽는다 — 표기를 맞춘다.
    return "미상(에이전트 신원 없음 — 사람이거나 신원 미설정)"


def main(argv) -> int:
    payload = json.load(sys.stdin)
    result = judge(payload)
    print(f"브랜치: {result['head_ref'] or '(미상)'} · 검사한 커밋 {result['commits_checked']}건")
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
