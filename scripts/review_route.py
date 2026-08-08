"""커밋 신원으로 저자를 판별해 반대 모델 리뷰어를 배정한다 — 순수 판정, stdlib 전용.

`cross-review.yml` 의 `route` 잡이 이것을 부른다 — 리뷰어 배정 판정의 정본은 여기 하나다.
티어 어휘는 로컬에서 실재를 확인한 것만 받는다.
"""

import json
import os
import re
import sys

CLAUDE_TIERS = ("opus", "sonnet", "fable", "haiku")
KIMI_TIERS = ("k3", "k3-256k", "kimi-for-coding", "kimi-for-coding-highspeed")
CODEX_TIERS = ("gpt-5.6-terra",)

_VENDOR_TIERS = {"claude": CLAUDE_TIERS, "kimi": KIMI_TIERS, "codex": CODEX_TIERS}
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


def decide(emails, head_ref, issue_risks, codex_on):
    vendors, claude_tiers_seen, unknown_agentish = set(), set(), []
    for raw in emails:
        m = _IDENTITY.match(raw)
        if m and (
            m.group("tier") is None
            or m.group("tier") in _VENDOR_TIERS[m.group("vendor")]
        ):
            vendors.add(m.group("vendor"))
            if m.group("vendor") == "claude":
                claude_tiers_seen.add(m.group("tier") or "unknown")
        elif _AGENTISH.search(raw):
            unknown_agentish.append(raw)

    bm = _BRANCH.match(head_ref or "")
    branch_model = bm.group("vendor") if bm else None

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
    elif branch_model:
        author_kind, author_vendor, identity_source = (
            "agent",
            branch_model,
            "branch-name",
        )
    else:
        author_kind, author_vendor, identity_source = "human", None, "none"

    risk, risk_source = _read_risk(issue_risks)

    candidates = ["claude", "kimi"] + (["codex"] if codex_on else [])
    if author_kind == "agent" and author_vendor == "kimi":
        reviewer = "claude"
    elif author_kind == "agent" and author_vendor == "claude":
        reviewer = "codex" if (risk == "high" and codex_on) else "kimi"
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
        "author_vendors": sorted(vendors),
        "author_tier": author_tier,
        "identity_source": identity_source,
        "risk": risk,
        "risk_source": risk_source,
        "label_allowed": label_allowed,
    }


def main():
    result = decide(
        os.environ.get("EMAILS", "").splitlines(),
        os.environ.get("HEAD_REF", ""),
        os.environ.get("ISSUE_RISKS", "").splitlines(),
        os.environ.get("CODEX_ON", "") == "on",
    )
    json.dump(result, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
