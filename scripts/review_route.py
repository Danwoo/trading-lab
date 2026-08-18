"""커밋 신원으로 저자를 판별해 반대 모델 리뷰어를 배정한다 — 순수 판정, stdlib 전용.

`cross-review.yml` 의 `route` 잡이 이것을 부른다 — 리뷰어 배정 판정과 **신원 형식의 SoT** 는
여기 하나다. 디스패치 쪽(§6.1 표·conductor·worker 스킬)이 이 형식에 맞춘다.
신원 형식은 `<벤더>[-<티어>]-agent@noreply.local` 이고 **명시 목록만** 받는다 (와일드카드
금지). 구형식 `<벤더>-agent@`(티어 미상)도 계속 유효하다.
"""

import json
import os
import re
import sys

# 티어 어휘 — **지어내지 않는다.** 여기 없는 이름은 로컬에서 확인되지 않은 것이고, 새 모델이
# 붙으면 그때 같은 방법(설정 파일·실행 배너)으로 확인해 추가한다. 확인 방법:
#   claude — `claude --model <별칭>` 으로 실재 확인
#   kimi   — 로컬 ~/.kimi-code/config.toml 의 등록 모델 실측
#   codex  — `codex exec` 실행 배너의 `model:` 값 실측
# kimi·codex 티어는 **축만 예약**이다: 라우팅은 벤더 축으로만 하고 티어는 폴백 티어 선택
# (claude 전용 규칙)에만 쓴다. 그래도 형식을 열어 둬야 그쪽 디스패치가 티어를 적기 시작할 때
# 판별이 깨지지 않는다.
CLAUDE_TIERS = ("opus", "sonnet", "fable", "haiku")
KIMI_TIERS = ("k3", "k3-256k", "kimi-for-coding", "kimi-for-coding-highspeed")
CODEX_TIERS = ("gpt-5.6-terra",)

# 신원 판독(여기)과 마커의 `tier=` 판독(`review_record.read_marker_tier`)이 같은 어휘를
# 봐야 한다 — 갈리면 한쪽이 인정한 티어를 다른 쪽이 미상으로 접는다. 그래서 공개 이름이다.
VENDOR_TIERS = {"claude": CLAUDE_TIERS, "kimi": KIMI_TIERS, "codex": CODEX_TIERS}
# 줄 전체가 신원이어야 한다. 앞뒤 공백을 다듬지 않는다 — 다듬으면 원본 grep 앵커보다
# 관대해지고, 그 관대함이 label_allowed(게이트 입력)를 사람에서 에이전트로 뒤집는다.
_IDENTITY = re.compile(
    r"^(?P<vendor>claude|kimi|codex)(?:-(?P<tier>[a-z0-9.\-]+))?-agent@noreply\.local\Z"
)
# 미상 신원 관측은 접미만 본다 — 앞 공백은 통과하고 뒤 공백은 못 통과한다
_AGENTISH = re.compile(r"-agent@noreply\.local\Z", re.I)
_BRANCH = re.compile(r"^fix-[0-9]+-(?P<vendor>claude|kimi|codex)\Z")


def _read_risk(issue_risks):
    """이슈 라벨에서 위험도를 읽는다 — 미선언·이슈 없음은 high (fail-closed).

    빈 줄도 「low 가 아닌 값」으로 센다. 걸러내면 미선언이 low 로 읽힌다.
    """
    vals = list(issue_risks)
    if not vals:
        return "high", "no-issue-fail-closed"
    if "high" in vals:
        return "high", "issue-label"
    if all(v == "low" for v in vals):
        return "low", "issue-label"
    return "high", "undeclared-fail-closed"


def _identity_note(
    author_kind,
    author_models,
    identity_source,
    branch_vendor,
    unknown_agentish,
    author_tier,
    claude_tiers_seen,
):
    """판정 코멘트에 `주의:` 로 실리는 사람 대상 신호 — 사실과 다르면 엉뚱한 곳을 고치러 간다."""
    parts = []
    if author_kind == "agent" and identity_source == "commit-email":
        if branch_vendor and branch_vendor != author_models:
            parts.append(
                f"브랜치명({branch_vendor})과 커밋 신원({author_models}) 불일치 — "
                "§6.1 일관성 점검 실패, 커밋 신원 우선"
            )
    elif author_kind == "mixed":
        parts.append(
            "복수 에이전트 신원 혼재 — 리뷰어는 전 저자 모델 제외로 산출, "
            "판정 라벨 미부착(사람 경로)"
        )
    elif identity_source == "branch-name":
        parts.append(
            "커밋에 에이전트 신원 없음 — 브랜치명 단독 판별 "
            "(§6.1 디스패치 계약 미이행, 실수 방지 점검 요망. "
            "라우팅·표기 전용 — 판정 라벨 미부착)"
        )
    else:
        parts.append("에이전트 신원 없음 — 사람 저자 취급, 판정 라벨 미부착(사람 경로)")

    if unknown_agentish:
        parts.append(f"목록 밖 에이전트형 이메일 관측: {','.join(unknown_agentish)}")

    # 티어 미상 주의는 claude 저자일 때만 의미가 있다 (폴백이 발동하면 라벨이 안 붙는다).
    if author_kind == "agent" and author_models == "claude" and not author_tier:
        if identity_source == "branch-name":
            parts.append(
                "브랜치명 단독 판별이라 작성 티어를 알 수 없다 "
                "(커밋에 claude 신원 자체가 없다) — 폴백 리뷰 시 판정 라벨 미부착"
            )
        elif len(claude_tiers_seen) > 1:
            parts.append(
                f"claude 작성 티어 혼재({','.join(sorted(claude_tiers_seen))}) — "
                "티어 미상 처리 (폴백 리뷰 시 판정 라벨 미부착)"
            )
        else:
            parts.append(
                "claude 작성 티어 미기록(구형식 claude-agent@) — "
                "폴백 리뷰 시 판정 라벨 미부착. §6.1 의 티어 신원을 쓰면 해소된다"
            )
    return "; ".join(parts)


def identify_author(emails, head_ref):
    """커밋 author 이메일·브랜치명으로 저자 신원을 판별한다 — 신원 형식 판독의 단일 자리.

    `review_record` 의 자기리뷰 차단(동일-벤더 + 티어 미상 → arm 거부)도 이것을 부른다.
    """
    vendors, claude_tiers_seen, unknown_agentish = set(), set(), []
    for raw in emails:
        m = _IDENTITY.match(raw)
        if m and (
            m.group("tier") is None
            or m.group("tier") in VENDOR_TIERS[m.group("vendor")]
        ):
            vendors.add(m.group("vendor"))
            if m.group("vendor") == "claude":
                claude_tiers_seen.add(m.group("tier") or "unknown")
        elif _AGENTISH.search(raw):
            unknown_agentish.append(raw)

    bm = _BRANCH.match(head_ref or "")
    branch_vendor = bm.group("vendor") if bm else None

    author_tier = None
    if len(claude_tiers_seen) == 1 and "unknown" not in claude_tiers_seen:
        author_tier = next(iter(claude_tiers_seen))

    if len(vendors) == 1:
        author_kind, author_vendor, identity_source = (
            "agent",
            next(iter(vendors)),
            "commit-email",
        )
    elif len(vendors) > 1:
        author_kind, author_vendor, identity_source = "mixed", None, "commit-email"
    elif branch_vendor:
        author_kind, author_vendor, identity_source = (
            "agent",
            branch_vendor,
            "branch-name",
        )
    else:
        author_kind, author_vendor, identity_source = "human", None, "none"

    return {
        "author_kind": author_kind,
        "author_vendor": author_vendor,
        # 저자 표기 — 혼재는 벤더 목록, 브랜치명 단독 판별은 그 벤더 (커밋 신원이 없다)
        "author_models": ",".join(sorted(vendors)) or (author_vendor or ""),
        "author_tier": author_tier,
        "identity_source": identity_source,
        "branch_vendor": branch_vendor,
        "unknown_agentish": unknown_agentish,
        "claude_tiers_seen": sorted(claude_tiers_seen),
        "vendors": sorted(vendors),
    }


def decide(emails, head_ref, issue_risks, codex_on, kimi_off=False):
    identity = identify_author(emails, head_ref)
    author_kind = identity["author_kind"]
    author_vendor = identity["author_vendor"]
    author_models = identity["author_models"]
    author_tier = identity["author_tier"]
    identity_source = identity["identity_source"]
    branch_vendor = identity["branch_vendor"]
    unknown_agentish = identity["unknown_agentish"]
    claude_tiers_seen = identity["claude_tiers_seen"]
    vendors = identity["vendors"]

    risk, risk_source = _read_risk(issue_risks)

    # 한도가 소진된 벤더는 **배정에서 뺀다.** 폴백 체인이 자동으로 claude 로 넘겨 주지만,
    # 그 전에 매번 워크트리·터미널·TUI 준비에 60초 이상을 태우고 나서야 403 을 본다 —
    # 리뷰마다 그 시간이 그대로 붙는다. 한도가 돌아오면 변수를 지운다.
    kimi_on = not kimi_off
    candidates = (
        ["claude"] + (["kimi"] if kimi_on else []) + (["codex"] if codex_on else [])
    )
    if author_kind == "agent" and author_vendor == "kimi":
        reviewer = "claude"
    elif author_kind == "agent" and author_vendor == "claude":
        if risk == "high" and codex_on:
            reviewer = "codex"
        elif kimi_on:
            reviewer = "kimi"
        else:
            # 교차가 불가능하다 — **같은 벤더의 반대 티어**로 간다. 자기리뷰가 아니게
            # 티어를 가르는 것이 §9 의 「교차 불가 시」 규약이고, 코멘트가 그 사실을 적는다.
            reviewer = "claude"
    elif author_kind == "agent" and author_vendor == "codex":
        reviewer = "claude"
    elif author_kind == "human":
        reviewer = "claude"
    else:
        reviewer = next((c for c in candidates if c not in vendors), "none")

    label_allowed = (
        author_kind == "agent"
        and identity_source == "commit-email"
        and not unknown_agentish
    )

    return {
        "reviewer": reviewer,
        "author_kind": author_kind,
        "author_vendor": author_vendor,
        # 혼재 저자는 author_vendor 로 환원되지 않는다 — 저자 표기·자기벤더 판정이 목록을 쓴다
        "author_models": author_models,
        "author_tier": author_tier,
        "identity_source": identity_source,
        "identity_note": _identity_note(
            author_kind,
            author_models,
            identity_source,
            branch_vendor,
            unknown_agentish,
            author_tier,
            claude_tiers_seen,
        ),
        "risk": risk,
        "risk_source": risk_source,
        # 왜 이 리뷰어인지 — 한도로 후보에서 빠진 벤더가 있으면 코멘트가 그 사실을 적는다.
        "routing_note": (
            "kimi 는 한도 소진으로 배정에서 제외됨 (KIMI_OFF=on)" if kimi_off else None
        ),
        "label_allowed": label_allowed,
    }


def main():
    result = decide(
        os.environ.get("EMAILS", "").splitlines(),
        os.environ.get("HEAD_REF", ""),
        os.environ.get("ISSUE_RISKS", "").splitlines(),
        os.environ.get("CODEX_ON", "") == "on",
        os.environ.get("KIMI_OFF", "") == "on",
    )
    json.dump(result, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
