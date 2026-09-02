"""review_route.decide 회귀 그물 — 종전 cross-review.yml 의 bash decide() 와 동작 동일.

배정이 뒤집히기 쉬운 네 자리를 케이스로 못박는다:
  ① 고위험 codex 는 **claude 저자**일 때다 (kimi 저자가 아니다)
  ② 벤더 혼재 + codex 불가 → reviewer=none (후보 소진)
  ③ 커밋 신원이 없어도 **옛 형식** 브랜치명(fix-N-<model>)으로 저자를 판별한다 (전환기 잔존)
  ④ **아무 신호도 없으면 `unknown`** — `human` 으로 접히지 않는다 (리드 결정 2026-08-28).
     이 한 글자가 `review_record` 의 arm 판정을 뒤집는다: `human` 이면 자기리뷰 축에
     해당 없음으로 통과하고, `unknown` 이면 fail-closed 로 막힌다.

새 브랜치 규약(`feature/<이슈>-<설명>` · `chore/<설명>` · `docs/<주제>`)에는 벤더 신호가
없다 — 그 네 갈래(옛 형식 · 새 형식 · 신원만 · 아무 신호 없음)를 아래 「브랜치 규약 전환」
묶음이 전부 판다.
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

# 「아무 신호 없음」의 주의 문구 — 이 문장이 판정 코멘트에 실려 사람에게 무슨 일인지 말한다.
UNKNOWN_NOTE = (
    "저자 신원 미상 — 커밋에 에이전트 신원이 없고 브랜치도 벤더를 선언하지 않는다. "
    "사람일 수도, `git config --worktree user.email` 을 빠뜨린 에이전트일 수도 있어 "
    "**둘을 가를 방법이 없다** — 판정 라벨 미부착 · 자동 머지 arm 거부(사람이 머지한다)"
)

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
            "author_models": "claude",
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
            "author_models": "claude,kimi",
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
            "author_models": "claude,kimi",
            "identity_note": "복수 에이전트 신원 혼재 — 리뷰어는 전 저자 모델 제외로 산출, 판정 라벨 미부착(사람 경로)",
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
            "author_models": "claude",
            "identity_source": "branch-name",
            "label_allowed": False,
            "identity_note": "커밋에 에이전트 신원 없음 — 브랜치명 단독 판별 "
            "(§6.1 디스패치 계약 미이행, 실수 방지 점검 요망. "
            "라우팅·표기 전용 — 판정 라벨 미부착); "
            "브랜치명 단독 판별이라 작성 티어를 알 수 없다 "
            "(커밋에 claude 신원 자체가 없다) — 폴백 리뷰 시 판정 라벨 미부착",
        },
    ),
    (
        "신원 없음 + 브랜치명 없음 → unknown/claude  (④ 리뷰는 하되 저자는 미상)",
        [HUMAN],
        "some-branch",
        ["low"],
        False,
        {
            "reviewer": "claude",
            "author_kind": "unknown",
            "author_models": "",
            "label_allowed": False,
            "identity_note": UNKNOWN_NOTE,
        },
    ),
    (
        "봇 저자 → unknown 취급 (봇 면제는 arm 판정 쪽에 있다 — review_record)",
        [BOT],
        "",
        ["low"],
        False,
        {
            "reviewer": "claude",
            "author_kind": "unknown",
            "author_models": "",
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
        {
            "author_tier": None,
            "reviewer": "kimi",
            "label_allowed": True,
            "identity_note": "claude 작성 티어 미기록(구형식 claude-agent@) — "
            "폴백 리뷰 시 판정 라벨 미부착. §6.1 의 티어 신원을 쓰면 해소된다",
        },
    ),
    (
        "claude 티어 혼재 → 티어 미상",
        [C, "claude-sonnet-agent@noreply.local"],
        "",
        ["low"],
        False,
        {
            "author_tier": None,
            "author_kind": "agent",
            "author_models": "claude",
            "identity_note": "claude 작성 티어 혼재(opus,sonnet) — 티어 미상 처리 (폴백 리뷰 시 판정 라벨 미부착)",
        },
    ),
    (
        "목록 밖 에이전트형 이메일 → 라벨 금지",
        ["claude-sonar-agent@noreply.local"],
        "",
        ["low"],
        False,
        {"author_kind": "unknown", "label_allowed": False},
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
        {"author_kind": "unknown", "author_models": "", "label_allowed": False},
    ),
    (
        "브랜치명과 커밋 신원 불일치 → 주의 문구를 남긴다",
        [C],
        "fix-42-kimi",
        ["low"],
        False,
        {"identity_note": "브랜치명(kimi)과 커밋 신원(claude) 불일치 — §6.1 일관성 점검 실패, 커밋 신원 우선"},
    ),
    (
        "목록 밖 에이전트형 이메일 → 관측 문구를 남긴다",
        [C, "Claude-Opus-Agent@noreply.local"],
        "",
        ["low"],
        False,
        {
            "author_kind": "agent",
            "label_allowed": False,
            "identity_note": "목록 밖 에이전트형 이메일 관측: Claude-Opus-Agent@noreply.local",
        },
    ),
    (
        "위험 라벨에 빈 줄이 섞이면 미선언 → high",
        [C],
        "",
        ["low", ""],
        False,
        {"risk": "high", "risk_source": "undeclared-fail-closed"},
    ),
    # ── codex 를 플래그로 체인에서 빼지 않는다 (2026-08-18) ──────────────────
    # 종전엔 CROSS_REVIEW_CODEX 를 끄면 codex 가 **체인에 들어가지도 못했다** — 한도가
    # 남아 있어도 안 쓰였다(실측: 변수를 2026-08-08 에 끄고 10일간 아무도 안 켰고,
    # 그 사이 codex 는 정상이었다). 한도 판정은 사전 프로브가 한다.
    #
    # 이 함수는 **1순위만** 정한다 — 체인(폴백 순서)은 워크플로가 세우고, 못 쓰는 후보는
    # 프로브가 건너뛴다.
    (
        "codex_on 이 꺼져도 claude 저자의 1순위는 kimi (종전과 같다)",
        ["claude-opus-agent@noreply.local"],
        "fix-1-claude",
        "",
        False,
        {"reviewer": "kimi"},
    ),
    (
        "고위험 + codex_on 이면 codex 가 1순위 — 예산은 1순위로만 아낀다",
        ["claude-opus-agent@noreply.local"],
        "fix-1-claude",
        "#1=high",
        True,
        {"reviewer": "codex"},
    ),
    (
        "codex 저자는 claude 가 본다 — 자기 벤더를 피한다",
        ["codex-agent@noreply.local"],
        "fix-1-codex",
        "",
        True,
        {"reviewer": "claude"},
    ),
    # ── 브랜치 규약 전환 `fix-<이슈>-<벤더>` → `feature/<이슈>-<설명>` (2026-08-27/28) ──
    # 네 갈래를 전부 판다. ③ 과 ④ 를 가르는 것이 이 전환의 전부다 — 옛 이름은 벤더를
    # 실어 날랐고 새 이름은 안 싣는다. 새 이름에서 신원까지 없으면 **모르는 것**이다.
    (
        "전환 ㉠ 옛 형식 + 신원 없음 → 브랜치명으로 판별 (전환기 동안 유지)",
        [HUMAN],
        "fix-42-claude",
        ["low"],
        False,
        {
            "author_kind": "agent",
            "author_vendor": "claude",
            "identity_source": "branch-name",
            "label_allowed": False,
        },
    ),
    (
        "전환 ㉡ 새 형식 + 신원 있음 → 커밋 신원으로 판별 (정상 경로, 변화 없음)",
        [C],
        "feature/359-timestamptz-audit-columns",
        ["low"],
        False,
        {
            "author_kind": "agent",
            "author_vendor": "claude",
            "author_tier": "opus",
            "identity_source": "commit-email",
            "reviewer": "kimi",
            "label_allowed": True,
        },
    ),
    (
        "전환 ㉢ 브랜치명 없음 + 신원만 있음 → 커밋 신원으로 판별",
        [K],
        "",
        ["low"],
        False,
        {
            "author_kind": "agent",
            "author_vendor": "kimi",
            "identity_source": "commit-email",
            "reviewer": "claude",
            "label_allowed": True,
        },
    ),
    (
        "전환 ㉣ 새 형식 + 신원 없음 → **unknown** (human 으로 안 떨어진다 — 이 전환의 핵심)",
        [HUMAN],
        "feature/359-timestamptz-audit-columns",
        ["low"],
        False,
        {
            "author_kind": "unknown",
            "author_vendor": None,
            "author_models": "",
            "identity_source": "none",
            "reviewer": "claude",
            "label_allowed": False,
            "identity_note": UNKNOWN_NOTE,
        },
    ),
    (
        "전환 ㉤ chore/ 도 벤더를 선언하지 않는다 → unknown",
        [HUMAN],
        "chore/ci-npm-cache",
        ["low"],
        False,
        {"author_kind": "unknown", "identity_source": "none"},
    ),
    (
        "전환 ㉥ docs/ 도 벤더를 선언하지 않는다 → unknown",
        [HUMAN],
        "docs/decision-log-0827",
        ["low"],
        False,
        {"author_kind": "unknown", "identity_source": "none"},
    ),
    (
        # 옛 `pr_authorship._BRANCH_DECLARES` 는 **끝의 `-<벤더>`** 를 부분 검색했으므로 이
        # 이름을 claude 선언으로 읽었다. `review_route._BRANCH` 는 줄 전체 앵커라 안 읽는다 —
        # 그 차이가 새 규약에서 오탐이 되는 자리이므로 반례로 못박는다.
        "전환 ㉦ 설명이 우연히 벤더 이름으로 끝나도 선언이 아니다 → unknown",
        [HUMAN],
        "feature/42-refactor-claude",
        ["low"],
        False,
        {"author_kind": "unknown", "author_vendor": None, "identity_source": "none"},
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
