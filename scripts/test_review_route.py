"""review_route.decide 회귀 그물 — 종전 cross-review.yml 의 bash decide() 와 동작 동일.

배정이 뒤집히기 쉬운 세 자리를 케이스로 못박는다:
  ① 고위험 codex 는 **claude 저자**일 때다 (kimi 저자가 아니다)
  ② 벤더 혼재 + codex 불가 → reviewer=none (후보 소진)
  ③ 커밋 신원이 없어도 브랜치명(fix-N-<model>)으로 저자를 판별한다
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_route as rr  # noqa: E402

C = "claude-opus-agent@noreply.local"
C_BARE = "claude-agent@noreply.local"
K = "kimi-agent@noreply.local"
X = "codex-agent@noreply.local"
HUMAN = "danwoo@example.com"
BOT = "49699333+dependabot[bot]@users.noreply.github.com"

CASES = [
    # (설명, emails, head_ref, issue_risks, codex_on, 기대 dict 부분집합)
    (
        "claude 저자 + 저위험 → kimi",
        [C],
        "",
        ["low"],
        False,
        {
            "reviewer": "kimi",
            "author_kind": "agent",
            "author_tier": "opus",
            "author_vendors": ["claude"],
            "label_allowed": True,
        },
    ),
    (
        "claude 저자 + 고위험 + codex 가용 → codex  (①)",
        [C],
        "",
        ["high"],
        True,
        {"reviewer": "codex", "risk": "high"},
    ),
    (
        "claude 저자 + 고위험 + codex 불가 → kimi",
        [C],
        "",
        ["high"],
        False,
        {"reviewer": "kimi"},
    ),
    (
        "kimi 저자 + 고위험 + codex 가용 → claude  (① 반대 방향 확인)",
        [K],
        "",
        ["high"],
        True,
        {"reviewer": "claude"},
    ),
    ("codex 저자 → claude", [X], "", ["low"], False, {"reviewer": "claude"}),
    (
        "혼재 + codex 가용 → codex  (②)",
        [C, K],
        "",
        ["low"],
        True,
        {
            "reviewer": "codex",
            "author_kind": "mixed",
            "author_vendors": ["claude", "kimi"],
            "label_allowed": False,
        },
    ),
    (
        "혼재 + codex 불가 → none  (②)",
        [C, K],
        "",
        ["low"],
        False,
        {
            "reviewer": "none",
            "author_kind": "mixed",
            "author_vendors": ["claude", "kimi"],
        },
    ),
    (
        "신원 없음 + 브랜치명 fix-42-claude → agent/claude  (③)",
        [HUMAN],
        "fix-42-claude",
        ["low"],
        False,
        {
            "reviewer": "kimi",
            "author_kind": "agent",
            "author_vendor": "claude",
            "author_vendors": [],
            "identity_source": "branch-name",
            "label_allowed": False,
        },
    ),
    (
        "신원 없음 + 브랜치명 없음 → human/claude",
        [HUMAN],
        "some-branch",
        ["low"],
        False,
        {
            "reviewer": "claude",
            "author_kind": "human",
            "author_vendors": [],
            "label_allowed": False,
        },
    ),
    (
        "봇 저자 → human 취급",
        [BOT],
        "",
        ["low"],
        False,
        {
            "reviewer": "claude",
            "author_kind": "human",
            "author_vendors": [],
            "label_allowed": False,
        },
    ),
    (
        "이슈 없음 → risk high (fail-closed)",
        [C],
        "",
        [],
        True,
        {"risk": "high", "risk_source": "no-issue-fail-closed", "reviewer": "codex"},
    ),
    (
        "이슈 라벨에 low·high 혼재 → high",
        [C],
        "",
        ["low", "high"],
        False,
        {"risk": "high"},
    ),
    (
        "구형식 claude-agent@ → 티어 미상",
        [C_BARE],
        "",
        ["low"],
        False,
        {"author_tier": None, "reviewer": "kimi", "label_allowed": True},
    ),
    (
        "claude 티어 혼재 → 티어 미상",
        [C, "claude-sonnet-agent@noreply.local"],
        "",
        ["low"],
        False,
        {"author_tier": None, "author_kind": "agent", "author_vendors": ["claude"]},
    ),
    (
        "목록 밖 에이전트형 이메일 → 라벨 금지",
        ["claude-sonar-agent@noreply.local"],
        "",
        ["low"],
        False,
        {"author_kind": "human", "label_allowed": False},
    ),
    (
        "커밋 신원과 브랜치명 불일치 → 커밋 신원 우선",
        [C],
        "fix-7-kimi",
        ["low"],
        False,
        {"author_vendor": "claude", "identity_source": "commit-email"},
    ),
    (
        "앞뒤 공백이 붙은 신원 → 신원 아님, 라벨 금지",
        [f"  {C}  "],
        "",
        ["low"],
        False,
        {"author_kind": "human", "author_vendors": [], "label_allowed": False},
    ),
    (
        "위험 라벨에 빈 줄이 섞이면 미선언 → high",
        [C],
        "",
        ["low", ""],
        False,
        {"risk": "high", "risk_source": "undeclared-fail-closed"},
    ),
]


def main() -> int:
    failures = 0
    for desc, emails, head_ref, risks, codex_on, want in CASES:
        got = rr.decide(emails, head_ref, risks, codex_on)
        for k, v in want.items():
            if got[k] != v:
                print(f"FAIL [{desc}] {k}: got {got[k]!r}, want {v!r}")
                failures += 1
    print(f"review_route 케이스 {len(CASES)}건 검사 · 실패 {failures}건")
    if not CASES:
        print("FAIL 검사 대상 0건")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
