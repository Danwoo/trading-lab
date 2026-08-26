"""review_record 회귀 그물 — 공격 케이스가 본체다 (#23 Task 7).

공개 레포의 위조 표면이 승인·자동 머지로 이어지지 않는지를 못박는다:
  ① 위조 마커(비-멤버 코멘트) ② 접두 sha ③ 낡은 sha ④ `source=manual`
  ⑤ major 봇 PR ⑥ 제목 파싱 실패 ⑦ 봇 사칭(로그인·타입 한쪽만 일치)
  ⑧ PR 번호 참조로 가시화 미러 라벨 읽히기 ⑨ 동일-벤더 자기리뷰
  — 각각이 기록 또는 arm 을 막아야 한다.
경계를 넓힌 자리(봇 폴백 게시분 읽기)는 **양방향으로** 못박는다 — 읽히는 것과 막히는 것을
같이 보지 않으면 방어가 뚫린 걸 못 본다. 케이스를 0건 모으면 실패한다 (fail-closed).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_record as rr  # noqa: E402

HEAD = "a" * 40
OTHER = "b" * 40


def marker(sha=HEAD, verdict="merge_ok", model="kimi", manual=False, tier=None):
    tail = " source=manual" if manual else ""
    tier_field = f" tier={tier}" if tier else ""
    return f"<!-- cross-review v1 model={model}{tier_field} verdict={verdict} sha={sha}{tail} -->"


def comment(
    body,
    association="OWNER",
    url="https://example.test/c/1",
    login="Danwoo",
    user_type="User",
):
    return {
        "body": body,
        "author_association": association,
        "html_url": url,
        "user_login": login,
        "user_type": user_type,
    }


def bot_comment(body, login="github-actions[bot]", user_type="Bot"):
    # 워크플로 자신의 게시분 — GITHUB_TOKEN 발이라 author_association 은 NONE 이다
    return comment(body, association="NONE", login=login, user_type=user_type)


def approval(sha=HEAD, state="APPROVED", login="github-actions[bot]"):
    return {"user_login": login, "state": state, "commit_id": sha}


RECORD_CASES = [
    # (설명, payload, 기대 dict 부분집합)
    (
        "멤버 merge_ok 마커 → APPROVE 게시 + arm 후보",
        {"head_sha": HEAD, "comments": [comment(marker())], "existing_reviews": []},
        {
            "post_review": True,
            "review_event": "APPROVE",
            "arm_candidate": True,
            "marker_sha": HEAD,
            "manual": False,
        },
    ),
    (
        "위조 마커(비-멤버 NONE) → 무행동  (공격 ①)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(), association="NONE")],
            "existing_reviews": [],
        },
        {"post_review": False, "review_event": None, "arm_candidate": False},
    ),
    (
        "cross-review publish 폴백 게시(github-actions[bot], association NONE) → 읽힌다",
        {
            "head_sha": HEAD,
            "comments": [bot_comment(marker())],
            "existing_reviews": [],
        },
        {"post_review": True, "review_event": "APPROVE", "arm_candidate": True},
    ),
    (
        "봇 사칭 — 로그인은 github-actions 인데 타입이 User → 무행동  (공격 ⑦)",
        {
            "head_sha": HEAD,
            "comments": [
                comment(
                    marker(),
                    association="NONE",
                    login="github-actions",
                    user_type="User",
                )
            ],
            "existing_reviews": [],
        },
        {"post_review": False, "arm_candidate": False, "marker_sha": None},
    ),
    (
        "봇 사칭 — 타입은 Bot 인데 다른 앱(dependabot[bot]) → 무행동  (공격 ⑦)",
        {
            "head_sha": HEAD,
            "comments": [bot_comment(marker(), login="dependabot[bot]")],
            "existing_reviews": [],
        },
        {"post_review": False, "arm_candidate": False, "marker_sha": None},
    ),
    (
        "봇 사칭 — 타입 Bot + 로그인 유사(github-actions-ci[bot]) → 무행동  (공격 ⑦)",
        {
            "head_sha": HEAD,
            "comments": [bot_comment(marker(), login="github-actions-ci[bot]")],
            "existing_reviews": [],
        },
        {"post_review": False, "arm_candidate": False},
    ),
    (
        "승인 App(trading-lab-ci[bot]) 게시분도 읽힌다 — 승인 신원이 둘이다 (2026-08-25)",
        {
            "head_sha": HEAD,
            "comments": [bot_comment(marker(), login="trading-lab-ci[bot]")],
            "existing_reviews": [],
        },
        {"post_review": True, "review_event": "APPROVE", "arm_candidate": True},
    ),
    (
        "승인 App 사칭 — 로그인 유사(trading-lab-ci-bot[bot]) → 무행동  (공격 ⑦)",
        {
            "head_sha": HEAD,
            "comments": [bot_comment(marker(), login="trading-lab-ci-bot[bot]")],
            "existing_reviews": [],
        },
        {"post_review": False, "arm_candidate": False, "marker_sha": None},
    ),
    (
        "승인 App 사칭 — 로그인은 맞는데 타입이 User → 무행동  (공격 ⑦)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(), association="NONE", login="trading-lab-ci", user_type="User")],
            "existing_reviews": [],
        },
        {"post_review": False, "arm_candidate": False, "marker_sha": None},
    ),
    (
        "App 승인이 이미 같은 head 에 있으면 중복 게시하지 않는다 (멱등)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker())],
            "existing_reviews": [approval(login="trading-lab-ci[bot]")],
        },
        {"post_review": False, "arm_candidate": True},
    ),
    # ── 신원 승계 — 「수정 필요 → 고침 → 승인」이 교착 없이 도는가 (2026-08-25) ──────
    # GitHub 의 `reviewDecision` 은 **저자별 마지막 리뷰**로 계산된다. 그래서 같은 App 이
    # CHANGES_REQUESTED 를 남긴 뒤 APPROVE 를 덧쓰면 교착이 안 생긴다. 신원이 갈리면
    # (옛 `github-actions[bot]` ↔ 새 App) 덧쓰기가 안 되고 사람이 해제해야 한다 —
    # 실제로 이 PR 의 이행기에 한 번 그 조치가 필요했다.
    (
        "앞 head 에서 App 이 수정 요청했어도 새 head 의 merge_ok 는 APPROVE 를 덧쓴다",
        {
            "head_sha": HEAD,
            "comments": [comment(marker())],
            "existing_reviews": [approval(sha=OTHER, state="CHANGES_REQUESTED", login="trading-lab-ci[bot]")],
        },
        {"post_review": True, "review_event": "APPROVE", "arm_candidate": True},
    ),
    (
        "같은 head 에 App 수정 요청이 있어도 merge_ok 마커면 APPROVE 로 덧쓴다",
        {
            "head_sha": HEAD,
            "comments": [comment(marker())],
            "existing_reviews": [approval(state="CHANGES_REQUESTED", login="trading-lab-ci[bot]")],
        },
        {"post_review": True, "review_event": "APPROVE", "arm_candidate": True},
    ),
    (
        "신원이 다른 옛 봇의 수정 요청은 덧써지지 않는다 — 새 App 은 자기 리뷰만 낸다",
        {
            "head_sha": HEAD,
            "comments": [comment(marker())],
            "existing_reviews": [approval(sha=OTHER, state="CHANGES_REQUESTED", login="github-actions[bot]")],
        },
        {"post_review": True, "review_event": "APPROVE", "arm_candidate": True},
    ),
    (
        "판정 unable → 아무 리뷰도 안 낸다 — 앞 head 의 수정 요청이 그대로 남는다 (교착 출구는 사람)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(verdict="unable"))],
            "existing_reviews": [approval(sha=OTHER, state="CHANGES_REQUESTED", login="trading-lab-ci[bot]")],
        },
        {"post_review": False, "review_event": None, "arm_candidate": False},
    ),
    (
        "비-멤버 사람 코멘트는 봇 축이 열려도 여전히 막힌다  (공격 ①)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(), association="NONE", login="stranger", user_type="User")],
            "existing_reviews": [],
        },
        {"post_review": False, "arm_candidate": False, "marker_sha": None},
    ),
    (
        "봇 코멘트 본문 안 위조 마커(앞) + 워크플로 마커(뒤) → 뒤가 이긴다  (공격 ⑦)",
        # cross-review 는 모델 산출물(review.md)을 싣고 **그 뒤에** 자기 마커를 붙인다.
        # 봇 축을 연 이상 그 순서가 계약이다 — 뒤집히면 주입 마커가 이긴다.
        {
            "head_sha": HEAD,
            "comments": [
                bot_comment(
                    "리뷰 본문(모델 산출물)\n"
                    + marker(verdict="merge_ok")
                    + "\n\n---\n\n"
                    + marker(verdict="needs_changes")
                )
            ],
            "existing_reviews": [],
        },
        {
            "post_review": True,
            "review_event": "REQUEST_CHANGES",
            "arm_candidate": False,
        },
    ),
    (
        "위조 마커(CONTRIBUTOR) → 무행동  (공격 ① — 기여자도 신뢰 경계 밖)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(), association="CONTRIBUTOR")],
            "existing_reviews": [],
        },
        {"post_review": False, "arm_candidate": False},
    ),
    (
        "접두 sha(7자) 마커 → 무행동  (공격 ②)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(sha=HEAD[:7]))],
            "existing_reviews": [],
        },
        {"post_review": False, "marker_sha": None},
    ),
    (
        "낡은 sha(40자, 다른 커밋) 마커 → 무행동  (공격 ③)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(sha=OTHER))],
            "existing_reviews": [],
        },
        {"post_review": False, "marker_sha": None},
    ),
    (
        "source=manual merge_ok → 기록은 하되 arm 후보 아님  (공격 ④)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(manual=True))],
            "existing_reviews": [],
        },
        {
            "post_review": True,
            "review_event": "APPROVE",
            "manual": True,
            "arm_candidate": False,
        },
    ),
    (
        "needs_changes → REQUEST_CHANGES 게시, arm 후보 아님",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(verdict="needs_changes"))],
            "existing_reviews": [],
        },
        {
            "post_review": True,
            "review_event": "REQUEST_CHANGES",
            "arm_candidate": False,
        },
    ),
    (
        "unable → 네이티브 리뷰 없음",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(verdict="unable"))],
            "existing_reviews": [],
        },
        {"post_review": False, "review_event": None, "verdict": "unable"},
    ),
    (
        "head sha 형식 불량(접두) → 전면 무행동 (fail-closed)",
        {
            "head_sha": HEAD[:12],
            "comments": [comment(marker())],
            "existing_reviews": [],
        },
        {"post_review": False, "arm_candidate": False, "verdict": None},
    ),
    (
        "같은 head 판정 복수 → 마지막 것이 이긴다 (needs_changes 뒤 merge_ok)",
        {
            "head_sha": HEAD,
            "comments": [
                comment(marker(verdict="needs_changes")),
                comment(marker(verdict="merge_ok")),
            ],
            "existing_reviews": [],
        },
        {"review_event": "APPROVE", "arm_candidate": True},
    ),
    (
        "동일 상태 리뷰가 이미 있으면 게시 생략 (멱등) — arm 후보는 유지",
        {
            "head_sha": HEAD,
            "comments": [comment(marker())],
            "existing_reviews": [approval()],
        },
        {"post_review": False, "arm_candidate": True},
    ),
    (
        "이전 REQUEST_CHANGES 뒤 merge_ok → APPROVE 다시 게시",
        {
            "head_sha": HEAD,
            "comments": [comment(marker())],
            "existing_reviews": [approval(state="CHANGES_REQUESTED")],
        },
        {"post_review": True, "review_event": "APPROVE"},
    ),
    (
        "멤버 산문 속 위조-비슷 문자열(마커 문법 불일치) → 무행동",
        {
            "head_sha": HEAD,
            "comments": [comment(f"cross-review v1 merge_ok sha={HEAD}")],
            "existing_reviews": [],
        },
        {"post_review": False, "marker_sha": None},
    ),
    # ── 리뷰어 티어 필드 (#23 Task 9) — 옛 마커·새 마커 양쪽에서 판정이 서야 한다 ────
    (
        "티어 없는 옛 마커 → 그대로 읽히고 tier 는 미상(None)",
        {"head_sha": HEAD, "comments": [comment(marker())], "existing_reviews": []},
        {"post_review": True, "arm_candidate": True, "model": "kimi", "tier": None},
    ),
    (
        "티어 있는 새 마커 → 읽히고 tier 가 실린다",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(model="claude", tier="sonnet"))],
            "existing_reviews": [],
        },
        {
            "post_review": True,
            "arm_candidate": True,
            "model": "claude",
            "tier": "sonnet",
        },
    ),
    (
        "어휘 밖 티어(claude tier=opus5) → 마커는 읽되 tier 는 미상으로 접는다",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(model="claude", tier="opus5"))],
            "existing_reviews": [],
        },
        {"post_review": True, "model": "claude", "tier": None},
    ),
    (
        "남의 벤더 티어(kimi tier=opus) → 마커는 읽되 tier 는 미상으로 접는다",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(model="kimi", tier="opus"))],
            "existing_reviews": [],
        },
        {"post_review": True, "model": "kimi", "tier": None},
    ),
    (
        "티어 + source=manual → 티어를 실어도 arm 후보가 되지 않는다  (공격 ④)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(model="claude", tier="sonnet", manual=True))],
            "existing_reviews": [],
        },
        {"post_review": True, "arm_candidate": False, "manual": True, "tier": "sonnet"},
    ),
    (
        "티어 필드가 낡은 sha 를 실어도 head 대조가 먼저다  (공격 ③)",
        {
            "head_sha": HEAD,
            "comments": [comment(marker(sha=OTHER, model="claude", tier="sonnet"))],
            "existing_reviews": [],
        },
        {"post_review": False, "marker_sha": None, "tier": None},
    ),
]

ARM_BASE = {
    "head_sha": HEAD,
    "marker_sha": HEAD,
    "marker_model": "kimi",  # 저자(claude)와 교차 벤더
    "marker_tier": None,  # 교차 벤더라 티어 축이 필요 없다 (kimi 는 티어를 안 싣는다)
    "verdict": "merge_ok",
    "manual": False,
    "reviews": [approval()],
    "pr_author_login": "Danwoo",
    "pr_author_is_bot": False,
    "pr_title": "feat: 예시",
    "issue_refs": [{"number": 23, "labels": ["risk: low"]}],
    "commit_author_emails": ["claude-opus-agent@noreply.local"],
    "head_ref": "Danwoo/ci-task7-followup",
}

ARM_CASES = [
    # (설명, payload 덮어쓰기, 기대 dict 부분집합)
    ("risk: low + 봇 승인 → arm", {}, {"arm": True, "risk": "low"}),
    (
        "App(trading-lab-ci) 승인도 조건 ②를 채운다 — 승인 신원이 둘이다 (2026-08-25)",
        {"reviews": [approval(login="trading-lab-ci[bot]")]},
        {"arm": True, "risk": "low"},
    ),
    (
        "목록 밖 봇 승인(dependabot) → arm 금지 (조건 ② — 승인 신원 위조 차단)",
        {"reviews": [approval(login="dependabot[bot]")]},
        {"arm": False},
    ),
    (
        "source=manual → arm 금지  (공격 ④)",
        {"manual": True},
        {"arm": False},
    ),
    (
        "낡은 마커 sha → arm 금지  (공격 ③)",
        {"marker_sha": OTHER},
        {"arm": False},
    ),
    (
        "접두 sha → arm 금지  (공격 ②)",
        {"marker_sha": HEAD[:7]},
        {"arm": False},
    ),
    (
        "봇 승인 리뷰 없음 → arm 금지 (조건 ②)",
        {"reviews": []},
        {"arm": False},
    ),
    (
        "승인 commit_id 가 head 와 다름 → arm 금지 (낡은 승인)",
        {"reviews": [approval(sha=OTHER)]},
        {"arm": False},
    ),
    (
        "승인 뒤 같은 head 에 CHANGES_REQUESTED 가 더 늦게 → arm 금지",
        {"reviews": [approval(), approval(state="CHANGES_REQUESTED")]},
        {"arm": False},
    ),
    (
        "타인 명의 APPROVED 만 있음 → arm 금지 (봇 승인만 센다)",
        {"reviews": [approval(login="Danwoo")]},
        {"arm": False},
    ),
    (
        "risk: high → 사람 경로",
        {"issue_refs": [{"number": 23, "labels": ["risk: high"]}]},
        {"arm": False, "risk": "high"},
    ),
    (
        "이슈 여럿이면 최고 위험 (low+high → high)",
        {
            "issue_refs": [
                {"number": 2, "labels": ["risk: low"]},
                {"number": 23, "labels": ["risk: high"]},
            ]
        },
        {"arm": False, "risk": "high"},
    ),
    (
        "참조 이슈에 risk 라벨 없음 → 미선언 = 저위험(리드 결정 2026-08-18)",
        {"issue_refs": [{"number": 7, "labels": ["bug"]}]},
        {"arm": True, "risk": "undeclared"},
    ),
    (
        "이슈 참조 없음 → 미선언 = 저위험(리드 결정 2026-08-18)",
        {"issue_refs": []},
        {"arm": True, "risk": "undeclared"},
    ),
    # ── ② `Refs #N` 의 N 이 PR 인 경우 — PR 의 risk 라벨은 가시화 미러다 ──────────
    (
        "Refs 가 PR 번호뿐 → 배제되어 미선언 = 저위험(리드 결정 2026-08-18)  (공격 ⑧)",
        {"issue_refs": [{"number": 13, "is_pr": True, "labels": ["risk: low"]}]},
        {"arm": True, "risk": "undeclared", "excluded_pr_refs": [13]},
    ),
    (
        "PR 미러(low) + 고위험 이슈 → 고위험을 취한다  (공격 ⑧)",
        {
            "issue_refs": [
                {"number": 13, "is_pr": True, "labels": ["risk: low"]},
                {"number": 23, "labels": ["risk: high"]},
            ]
        },
        {"arm": False, "risk": "high", "excluded_pr_refs": [13]},
    ),
    (
        "PR 미러 + 저위험 이슈 → 이슈만 읽어 arm (배제가 정상 판독을 막지 않는다)",
        {
            "issue_refs": [
                {"number": 13, "is_pr": True, "labels": ["risk: high"]},
                {"number": 2, "labels": ["risk: low"]},
            ]
        },
        {"arm": True, "risk": "low", "excluded_pr_refs": [13]},
    ),
    (
        "코드·인용에서 버린 참조 후보가 있으면 low 를 미선언으로 접는다  (공격 ⑪)",
        {"issue_refs": [{"number": 1, "labels": ["risk: low"]}], "dropped_refs": [23]},
        {"arm": True, "risk": "undeclared"},
    ),
    (
        "버린 후보가 있어도 high 는 그대로 (위험도를 올리는 쪽으로만 쓴다)",
        {"issue_refs": [{"number": 23, "labels": ["risk: high"]}], "dropped_refs": [1]},
        {"arm": False, "risk": "high"},
    ),
    (
        "버린 후보가 읽은 참조와 같은 번호면 영향 없음",
        {"issue_refs": [{"number": 1, "labels": ["risk: low"]}], "dropped_refs": [1]},
        {"arm": True, "risk": "low"},
    ),
    (
        "참조 0건 + 버린 후보 있음 → 미선언 → arm (근거는 그대로 남는다)",
        {"issue_refs": [], "dropped_refs": [1]},
        {"arm": True, "risk": "undeclared"},
    ),
    (
        "이슈 조회 실패 → 미선언 = 사람 경로 (fail-closed)",
        {"issue_refs": [{"number": 23, "lookup_failed": True}]},
        {"arm": False, "risk": "undeclared"},
    ),
    (
        "저위험 이슈 + 조회 실패 이슈 → 미선언 (실패가 low 에 묻히지 않는다)",
        {
            "issue_refs": [
                {"number": 2, "labels": ["risk: low"]},
                {"number": 23, "lookup_failed": True},
            ]
        },
        {"arm": False, "risk": "undeclared"},
    ),
    # ── ③ 저자 신원 축 — 동일-벤더면 티어를 알아야 arm 한다 ──────────────────────
    (
        "동일-벤더 + 작성 티어 미상(구형식 claude-agent@) → arm 거부  (공격 ⑨)",
        {
            "marker_model": "claude",
            "commit_author_emails": ["claude-agent@noreply.local"],
        },
        {"arm": False, "self_vendor": True, "author_tier": None},
    ),
    # ── 동일-벤더의 티어 대조 (#23 Task 9) — 「작성 티어를 안다」만으로는 못 푼다 ────
    # 종전엔 이 케이스가 arm=True 였다. 근거는 「폴백이 반대 티어를 고른다」는 cross-review
    # 쪽 계약이었는데, `--agent claude` 가 모델 인자를 못 받아 그 계약이 실제로는 안 지켜지고
    # 있었다 (배정 sonnet · 기동 배너 Opus 5 실측). 이제 양쪽 티어를 직접 대조한다.
    (
        "동일-벤더 + 작성 티어 명시 + **리뷰어 티어 미상** → arm 거부  (공격 ⑨)",
        {
            "marker_model": "claude",
            "commit_author_emails": ["claude-opus-agent@noreply.local"],
        },
        {
            "arm": False,
            "self_vendor": True,
            "author_tier": "opus",
            "reviewer_tier": None,
        },
    ),
    (
        "동일-벤더 + 작성 opus + 리뷰어 sonnet → 교차 축이 살아 있어 arm",
        {
            "marker_model": "claude",
            "marker_tier": "sonnet",
            "commit_author_emails": ["claude-opus-agent@noreply.local"],
        },
        {
            "arm": True,
            "self_vendor": True,
            "author_tier": "opus",
            "reviewer_tier": "sonnet",
        },
    ),
    (
        "동일-벤더 + **동일 티어**(opus 가 opus 를 리뷰) → arm 거부  (공격 ⑨)",
        {
            "marker_model": "claude",
            "marker_tier": "opus",
            "commit_author_emails": ["claude-opus-agent@noreply.local"],
        },
        {
            "arm": False,
            "self_vendor": True,
            "author_tier": "opus",
            "reviewer_tier": "opus",
        },
    ),
    (
        "동일-벤더 + 리뷰어 티어는 아는데 **작성 티어 미상** → arm 거부  (공격 ⑨)",
        {
            "marker_model": "claude",
            "marker_tier": "sonnet",
            "commit_author_emails": ["claude-agent@noreply.local"],
        },
        {"arm": False, "self_vendor": True, "author_tier": None},
    ),
    (
        "동일-벤더 kimi + 리뷰어 티어를 실어도 → 티어 축이 없어 arm 거부  (공격 ⑨)",
        {
            "marker_model": "kimi",
            "marker_tier": "k3",
            "commit_author_emails": ["kimi-agent@noreply.local"],
        },
        {"arm": False, "self_vendor": True},
    ),
    (
        "동일-벤더 + claude 티어 혼재 → 티어 미상으로 접혀 arm 거부  (공격 ⑨)",
        {
            "marker_model": "claude",
            "commit_author_emails": [
                "claude-opus-agent@noreply.local",
                "claude-sonnet-agent@noreply.local",
            ],
        },
        {"arm": False, "self_vendor": True, "author_tier": None},
    ),
    (
        "동일-벤더 + 브랜치명 단독 판별(커밋 신원 없음) → arm 거부  (공격 ⑨)",
        {
            "marker_model": "claude",
            "commit_author_emails": ["dev@example.test"],
            "head_ref": "fix-23-claude",
        },
        {"arm": False, "self_vendor": True, "identity_source": "branch-name"},
    ),
    (
        "교차 벤더(claude 저자 · kimi 리뷰) → 티어 미상이어도 arm",
        {"commit_author_emails": ["claude-agent@noreply.local"]},
        {"arm": True, "self_vendor": False},
    ),
    (
        "사람 저자(에이전트형이 아닌 이메일) → 자기리뷰 축 미해당, risk: low 면 arm",
        {
            "marker_model": "claude",
            "commit_author_emails": ["dev@example.test"],
            "head_ref": "feature/x",
        },
        {"arm": True, "self_vendor": False, "identity_source": "none"},
    ),
    (
        "어휘 밖 티어 신원(claude-opus5-agent@) → 사람 저자로 접지 않고 arm 거부  (공격 ⑨)",
        {
            "marker_model": "claude",
            "commit_author_emails": ["claude-opus5-agent@noreply.local"],
            "head_ref": "feature/x",
        },
        {"arm": False, "unknown_agentish": ["claude-opus5-agent@noreply.local"]},
    ),
    (
        "어휘 밖 벤더형 신원(gemini-agent@) → arm 거부  (공격 ⑨)",
        {
            "marker_model": "claude",
            "commit_author_emails": ["gemini-agent@noreply.local"],
            "head_ref": "feature/x",
        },
        {"arm": False, "unknown_agentish": ["gemini-agent@noreply.local"]},
    ),
    (
        "혼재 저자(claude+kimi) + kimi 리뷰 → 다른 벤더의 티어로 차단이 풀리지 않는다  (공격 ⑨)",
        {
            "marker_model": "kimi",
            "commit_author_emails": [
                "claude-opus-agent@noreply.local",
                "kimi-agent@noreply.local",
            ],
        },
        {"arm": False, "self_vendor": True, "author_tier": "opus"},
    ),
    (
        "혼재 저자(claude+kimi) + codex 리뷰 → 교차 벤더라 arm",
        {
            "marker_model": "codex",
            "commit_author_emails": [
                "claude-opus-agent@noreply.local",
                "kimi-agent@noreply.local",
            ],
        },
        {"arm": True, "self_vendor": False},
    ),
    (
        "어휘 안 신원 + 어휘 밖 신원 혼재 → arm 거부 (한 건이라도 판독 불가면 접는다)",
        {
            "marker_model": "kimi",
            "commit_author_emails": [
                "claude-opus-agent@noreply.local",
                "claude-opus5-agent@noreply.local",
            ],
        },
        {"arm": False, "author_models": "claude"},
    ),
    (
        "커밋 저자 이메일 0건(조회 실패) → arm 거부 (fail-closed)",
        {"commit_author_emails": []},
        {"arm": False, "self_vendor": None},
    ),
    (
        "커밋 저자 이메일 키 부재 → arm 거부 (fail-closed)",
        {"commit_author_emails": None},
        {"arm": False, "self_vendor": None},
    ),
    (
        "마커 모델 미상 → 자기리뷰 판정 불가로 arm 거부 (fail-closed)",
        {"marker_model": ""},
        {"arm": False, "self_vendor": None},
    ),
    (
        "마커 모델이 어휘 밖 → arm 거부 (fail-closed)",
        {"marker_model": "gpt"},
        {"arm": False, "self_vendor": None},
    ),
    (
        "봇 PR minor 상승 → 위험 미선언이어도 arm  (설계 §2-1)",
        {
            "pr_author_is_bot": True,
            "pr_author_login": "dependabot[bot]",
            "pr_title": "build(deps): bump pyjwt from 2.12.1 to 2.13.0 in /template-mcp-service",
            "issue_refs": [],
            "commit_author_emails": ["49699333+dependabot[bot]@users.noreply.github.com"],
        },
        {"arm": True, "bot_bump": "non-major", "self_vendor": False},
    ),
    (
        "봇 PR major 상승 → 사람 경로  (공격 ⑤)",
        {
            "pr_author_is_bot": True,
            "pr_title": "build(deps): bump cryptography from 48.0.1 to 50.0.0 in /market-data-mcp-service",
            "issue_refs": [],
            "commit_author_emails": ["49699333+dependabot[bot]@users.noreply.github.com"],
        },
        {"arm": False, "bot_bump": "major"},
    ),
    (
        "봇 PR 제목 파싱 실패 → arm 금지  (공격 ⑥ fail-closed)",
        {
            "pr_author_is_bot": True,
            "pr_title": "build(deps): bump the pip group with 3 updates",
            "issue_refs": [],
            "commit_author_emails": ["49699333+dependabot[bot]@users.noreply.github.com"],
        },
        {"arm": False, "bot_bump": None},
    ),
    (
        "사람 저자 + major 꼴 제목 → 봇 경로 미적용 (미선언 = 저위험(리드 결정 2026-08-18))",
        {
            "pr_title": "build(deps): bump x from 1.0 to 2.0",
            "issue_refs": [],
        },
        {"arm": True},
    ),
    (
        "판정 needs_changes → arm 금지",
        {"verdict": "needs_changes"},
        {"arm": False},
    ),
    # ── 새 제목 형식(`update X requirement from ~=A to ~=B`) — #106 버전 업데이트로 생겼다 ──
    (
        "봇 PR 새 형식 patch 상승(실물 #118) → 위험 미선언이어도 arm",
        {
            "pr_author_is_bot": True,
            "pr_author_login": "dependabot[bot]",
            "pr_title": (
                "build(deps): update uvicorn[standard] requirement from ~=0.47.0 to ~=0.52.1 in /backend-service"
            ),
            "issue_refs": [],
            "commit_author_emails": ["49699333+dependabot[bot]@users.noreply.github.com"],
        },
        {"arm": True, "bot_bump": "non-major", "self_vendor": False},
    ),
    (
        "봇 PR 새 형식 major 상승 → 사람 경로 (제약 연산자를 걷어낸 숫자로 가른다)",
        {
            "pr_author_is_bot": True,
            "pr_title": (
                "build(deps): update psycopg[binary] requirement from ~=3.2.13 to ~=4.0.1 in /multi-agent-service"
            ),
            "issue_refs": [],
            "commit_author_emails": ["49699333+dependabot[bot]@users.noreply.github.com"],
        },
        {"arm": False, "bot_bump": "major"},
    ),
    (
        "봇 PR 묶음 제목(실물 #114) → 형식 밖이라 arm 금지  (공격 ⑥ fail-closed)",
        {
            "pr_author_is_bot": True,
            "pr_title": ("build(deps): bump the non-major group across 10 directories with 19 updates"),
            "issue_refs": [],
            "commit_author_emails": ["49699333+dependabot[bot]@users.noreply.github.com"],
        },
        {"arm": False, "bot_bump": None},
    ),
]

# (설명, 제목, 기대 상승 종류) — 판정부는 순수 함수라 여기서 직접 못박는다.
# **제목은 실물이다** (`gh pr list --state all` 2026-08-13). 실물이 없어 지은 것은 설명에
# 그렇게 적었다 — 지금 열린·머지된 PR 에 새 형식 major 와 범위 제약이 아직 없다.
TITLE_CASES = [
    # ── ① 종전 형식 `bump X from A to B` — 깨지지 않았는지 ──
    (
        "bump 형식 patch 상승 (실물 #9)",
        "build(deps): bump mcp from 1.27.2 to 1.28.1 in /web-mcp-service",
        "non-major",
    ),
    (
        "bump 형식 major 상승 (실물 #54)",
        "build(deps): bump cryptography from 48.0.1 to 50.0.0 in /market-data-mcp-service",
        "major",
    ),
    (
        "bump 형식 major 상승 — deps-dev·스코프 패키지 (실물 #109)",
        "build(deps): bump @tanstack/react-table from 8.21.3 to 9.1.2 in /frontend",
        "major",
    ),
    (
        "bump 형식 major 상승 — deps-dev (실물 #124)",
        "build(deps-dev): bump mcp from 1.28.1 to 2.0.0 in /multi-agent-service",
        "major",
    ),
    # ── ② 새 형식 `update X requirement from ~=A to ~=B` — extras 대괄호 + 제약 연산자 ──
    (
        "새 형식 patch 상승 — extras 대괄호 (실물 #118)",
        "build(deps): update uvicorn[standard] requirement from ~=0.47.0 to ~=0.52.1 in /backend-service",
        "non-major",
    ),
    (
        "새 형식 minor 상승 — extras 대괄호 (실물 #115)",
        "build(deps): update alembic[tz] requirement from ~=1.18.4 to ~=1.19.1 in /backend-service",
        "non-major",
    ),
    (
        "새 형식 minor 상승 — major 자리 3 유지 (실물 #122)",
        "build(deps): update psycopg[binary] requirement from ~=3.2.13 to ~=3.3.4 in /multi-agent-service",
        "non-major",
    ),
    (
        "새 형식 major 상승 — 실물 #122 의 버전만 major 넘게 바꾼 변형 (새 형식 major 실물은 아직 열린 적 없다)",
        "build(deps): update psycopg[binary] requirement from ~=3.2.13 to ~=4.0.1 in /multi-agent-service",
        "major",
    ),
    (
        "새 형식 — 제약 연산자 없는 버전도 읽는다 (실물 #115 에서 `~=` 만 뗀 변형)",
        "build(deps): update alembic[tz] requirement from 1.18.4 to 2.0.0 in /backend-service",
        "major",
    ),
    # ── 못 읽는 제목은 그대로 못 읽어야 한다 (fail-closed — arm 거부로 이어진다) ──
    (
        "묶음 PR — from/to 가 없다 (실물 #114)",
        "build(deps): bump the non-major group across 10 directories with 19 updates",
        None,
    ),
    (
        "보안 업데이트 — 버전이 제목에 없다 (실물 #63)",
        "build(deps): bump brace-expansion in /frontend",
        None,
    ),
    (
        "복수 패키지 — 버전이 제목에 없다 (실물 #130)",
        "build(deps): bump @hono/node-server and prisma in /frontend",
        None,
    ),
    (
        "동사 없는 `from A to B` 는 상승 선언이 아니다 — 아무 제목의 두 토막을 읽지 않는다",
        "docs: 마이그레이션 노트를 from 1.0 to 2.0 기준으로 고쳐 쓴다",
        None,
    ),
    (
        "`update` 인데 `requirement` 가 없다 — 아는 형식이 아니다",
        "build(deps): update uvicorn[standard] from ~=0.47.0 to ~=0.52.1 in /backend-service",
        None,
    ),
    (
        "범위 제약 — major 가 하나로 안 정해진다 (지어낸 제목: 범위 실물은 아직 없다)",
        "build(deps): update requests requirement from >=2.0,<3.0 to >=2.0,<4.0 in /backend-service",
        None,
    ),
    (
        "숫자로 시작하지 않는 버전 — 못 읽는다 (지어낸 제목)",
        "build(deps): bump mcp from latest to next in /web-mcp-service",
        None,
    ),
    (
        "상승이 둘 실린 제목 — 뒤의 major 가 앞의 non-major 뒤에 숨는다 (지어낸 제목)",
        "build(deps): bump mcp from 1.0.0 to 1.1.0 and starlette from 1.0.0 to 2.0.0",
        None,
    ),
    (
        "상승이 둘 — 앞이 major 여도 마찬가지로 안 읽는다 (지어낸 제목)",
        "build(deps): bump mcp from 1.0.0 to 2.0.0 and starlette from 1.0.0 to 1.1.0",
        None,
    ),
    (
        "epoch 버전 — major 자리를 단정할 수 없다 (지어낸 제목)",
        "build(deps): bump foo from 1!2.0 to 1!3.0 in /backend-service",
        None,
    ),
    ("제목 없음", "", None),
    ("제목 None", None, None),
]

REFS_CASES = [
    # (설명, 본문, 기대 번호 목록)
    ("Refs 단건", "…\n\nRefs #23\n", [23]),
    ("Refs 복수(쉼표)", "Refs #23, #24", [23, 24]),
    ("Closes 도 위험도 출처", "Closes #2", [2]),
    ("Fixes/Resolves 혼합 + 중복 제거", "Fixes #5\nresolves #5, #9", [5, 9]),
    ("키워드 없는 #N 은 참조 아님", "PR #47 머지 이후의 작업이다", []),
    ("본문 없음", "", []),
    # 참조 선언이 아닌 자리 — 여기서 읽으면 예시 한 줄이 위험도 출처가 된다 (공격 ⑩)
    (
        "코드 펜스 안의 `Refs #N` 은 참조 아님",
        "Refs #23\n\n```bash\nfor B in 'Refs #1' 'Refs #999'; do run \"$B\"; done\n```\n",
        [23],
    ),
    (
        "인용문의 `Refs #N` 은 참조 아님",
        "> 리뷰어 지적: Refs #1 만 있는 PR 은 low 로 접힌다\n\nRefs #23\n",
        [23],
    ),
    (
        "인라인 코드의 `Refs #N` 은 참조 아님",
        "본문에 `Refs #1` 만 있는 PR 은 위험도가 접힌다.\n\nRefs #23\n",
        [23],
    ),
    (
        "산문 끝의 참조는 읽는다 (레포 관행 — 확인용 PR)",
        "게이트 반응을 보기 위한 확인용 PR. 확인이 끝나면 닫는다. Refs #23",
        [23],
    ),
    (
        "펜스가 안 닫힌 본문 — 이후 전부 코드로 보고 버린다 (fail-closed)",
        "Refs #23\n\n```\nRefs #1\n",
        [23],
    ),
    (
        "중첩 펜스(백틱 4개 안의 백틱 3개) — 안쪽에서 안팎이 뒤집히지 않는다",
        "Refs #23\n\n````\n```\nRefs #1\n```\n````\n",
        [23],
    ),
    (
        "4칸 들여쓰기 코드블록의 `Refs #N` 은 참조 아님",
        "Refs #23\n\n예시:\n\n    Refs #1\n",
        [23],
    ),
    (
        "인용의 lazy 연속행(`>` 없는 다음 줄)도 인용으로 접는다",
        "Refs #23\n\n> 리뷰어 지적:\nRefs #1 만 있으면 접힌다\n",
        [23],
    ),
    (
        "인용이 끝난 뒤(빈 줄) 산문의 참조는 읽는다",
        "> 인용\n\nRefs #23\n",
        [23],
    ),
]

# 버린 자리의 참조 후보 — 이것을 그냥 없애면 위험도가 **내려간다** (공격 ⑪)
DROPPED_CASES = [
    # (설명, 본문, 기대 refs, 기대 dropped)
    (
        "리스트 연속행(4칸)의 고위험 참조 + 산문의 저위험 참조",
        "- 배경:\n    Closes #23\n\nRefs #1\n",
        [1],
        [23],
    ),
    (
        "코드 펜스 안의 참조 후보",
        "Refs #23\n\n```\nRefs #1\n```\n",
        [23],
        [1],
    ),
    (
        "인용 안의 참조 후보",
        "> Closes #99\n\nRefs #23\n",
        [23],
        [99],
    ),
    (
        "인라인 코드의 참조 후보",
        "본문에 `Refs #1` 만 있는 PR.\n\nRefs #23\n",
        [23],
        [1],
    ),
    (
        "산문에도 있는 번호는 버린 것으로 세지 않는다",
        "Refs #23\n\n```\nRefs #23\n```\n",
        [23],
        [],
    ),
    ("버릴 것이 없으면 빈 목록", "Refs #23\n", [23], []),
    (
        "펜스 여는 줄의 info string 에 적힌 참조 (산문도 코드도 아닌 자리)",
        "Refs #1\n\n```text Closes #23\nx\n```\n",
        [1],
        [23],
    ),
    (
        "펜스 닫는 줄 꼬리에 적힌 참조",
        "Refs #1\n\n```\nx\n``` Closes #23\n",
        [1],
        [23],
    ),
    (
        "줄바꿈으로 이어진 참조 목록은 둘 다 읽는다 (산문이므로)",
        "Refs #1,\n#23\n",
        [1, 23],
        [],
    ),
    (
        "버린 블록이 앞뒤 산문을 잇지 않는다 — 없던 참조를 만들지 않는다  (공격 ⑫)",
        "Refs:\n\n```\ncode\n```\n\n#1\n",
        [],
        [],
    ),
    (
        "인용이 앞뒤 산문을 잇지 않는다  (공격 ⑫)",
        "Refs:\n> 인용\n#1\n",
        [],
        [],
    ),
    (
        "이중 백틱 인라인 코드도 접는다",
        "``Refs #1`` 를 인용한다.\n\nRefs #23\n",
        [23],
        [1],
    ),
    (
        "HTML 주석의 숨은 선언은 참조 아님  (공격 ⑬ — 본문만 읽는 사람에게 안 보인다)",
        "<!-- Refs #1 -->\n\nRefs #23\n",
        [23],
        [1],
    ),
    (
        "여러 줄 HTML 주석도 접는다",
        "<!--\nRefs #1\n-->\n\nRefs #23\n",
        [23],
        [1],
    ),
    (
        "닫히지 않은 `<!--` 는 그 자리부터 끝까지 주석 (fail-closed)",
        "Refs #23\n\n<!-- Refs #1\n",
        [23],
        [1],
    ),
    (
        "주석이 앞뒤 산문을 잇지 않는다",
        "Refs:\n<!-- x -->\n#1\n",
        [],
        [],
    ),
    (
        "산문이 인용한 짝 없는 `<!--` 는 그 뒤를 주석으로 먹지 않는다  (인라인 코드가 먼저)",
        "`<!--` 를 설명한다.\n\nRefs #23\n\n```\nRefs #1\n```\n",
        [23],
        [1],
    ),
    (
        "코드 블록 안의 짝 없는 `<!--` 도 주석이 아니다 (펜스가 먼저)",
        'Refs #23\n\n```\nGREP="<!--"\n```\n\n```\nRefs #1\n```\n',
        [23],
        [1],
    ),
]

# ── 위임 머지 (#23 Task 9) — 조건 하나씩 깨뜨린 입력이 **각각** 거부돼야 한다 ──────
# base 는 셋 다 맞는 입력이다. 저자는 claude·리뷰어는 kimi 라 교차 벤더이고, 위험도는 low,
# 게이트는 pass. 여기서 조건을 하나씩만 깨뜨린다.
DELEGATE_BASE = {**ARM_BASE, "gate_state": "pass"}

DELEGATE_CASES = [
    # (설명, payload 덮어쓰기, 기대 allow, 사유에 들어 있어야 할 조각)
    ("셋 다 충족 → 머지 허용", {}, True, None),
    # ① 리뷰 통과 마커
    (
        "① 판정이 needs_changes → 거부",
        {"verdict": "needs_changes"},
        False,
        "① 리뷰 통과 마커",
    ),
    ("① 마커 없음(판정 빈 값) → 거부", {"verdict": ""}, False, "① 리뷰 통과 마커"),
    (
        "① source=manual 마커 → 거부 (사람이 타이핑한 한 줄일 수 있다)",
        {"manual": True},
        False,
        "source=manual",
    ),
    (
        "① 낡은 sha 마커 → 거부",
        {"marker_sha": OTHER},
        False,
        "① 마커가 현재 head 의 것이 아님",
    ),
    # ② required 게이트
    ("② 게이트 fail → 거부", {"gate_state": "fail"}, False, "② required 게이트 비초록"),
    (
        "② 게이트 wait(아직 도는 중) → 거부 — 위임 머지는 기다리지 않는다",
        {"gate_state": "wait"},
        False,
        "기다리지 않는다",
    ),
    (
        "② 게이트 상태 미상 → 거부 (fail-closed)",
        {"gate_state": None},
        False,
        "② required 게이트 비초록",
    ),
    # ③ 저위험 확정
    (
        "③ risk: high → 거부",
        {"issue_refs": [{"number": 23, "labels": ["risk: high"]}]},
        False,
        "③ 저위험 확정 아님",
    ),
    (
        "③ 미선언(라벨 없음) → 허용 (미선언 = 저위험)",
        {"issue_refs": [{"number": 23, "labels": []}]},
        True,
        None,
    ),
    # 미선언 = 저위험 (리드 결정 2026-08-18) — arm 경로와 같은 규칙으로 맞췄다.
    # 「못 읽음」(조회 실패)과 봇 PR 은 여전히 거부다 — 아래 케이스가 그것을 못박는다.
    ("③ 연결 이슈 없음 → 허용 (미선언 = 저위험)", {"issue_refs": []}, True, None),
    (
        "③ 봇 major 아님이어도 저위험이 아니면 거부 — 위임 경로는 봇 예외를 안 탄다",
        {
            "issue_refs": [],
            "pr_author_is_bot": True,
            "pr_title": "bump x from 1.0 to 1.1",
        },
        False,
        "③ 저위험 확정 아님",
    ),
    # 부가 조건 — 셋으로 환원되지 않는 것도 막는다
    ("승인 리뷰 없음 → 거부 (부가 조건)", {"reviews": []}, False, "부가 조건 미충족"),
    (
        "동일-벤더·동일-티어 자기리뷰 → 거부 (부가 조건)",
        {"marker_model": "claude", "marker_tier": "opus"},
        False,
        "부가 조건 미충족",
    ),
    (
        "커밋 신원 0건 → 거부 (부가 조건 — fail-closed)",
        {"commit_author_emails": []},
        False,
        "부가 조건 미충족",
    ),
    # 사유는 하나만 내지 않는다
    (
        "조건 셋이 동시에 깨지면 사유 셋을 **모두** 돌려준다",
        {"verdict": "needs_changes", "gate_state": "fail", "issue_refs": []},
        False,
        None,
    ),
]


def _checks(count, *, start=1, status="completed", conclusion="success"):
    """`test: ` 체크런 count 개 — 게이트 전수 판정의 입력."""
    return [
        {
            "id": start + i,
            "name": f"test: job{start + i}",
            "status": status,
            "conclusion": conclusion,
        }
        for i in range(count)
    ]


FLOOR = rr.gate_lib.MIN_TEST_CHECKS
FULL = _checks(FLOOR)

# 대표자 잡(`test: gate`)을 없앤 뒤의 전수 판정 (2026-08-25). 종전 케이스는 그 잡 하나의
# 색만 봤다 — 그대로 두면 잡이 사라진 지금 「없음 = 미완 → --final 에 실패」로 자동 머지가
# 통째로 멎는 것을 그물이 못 잡는다.
GATE_CASES = [
    # (설명, records, final, 기대 상태)
    ("test: 체크 전수 초록 → pass", FULL, False, "pass"),
    (
        "하나가 in_progress → wait",
        FULL[:-1] + _checks(1, start=99, status="in_progress", conclusion=None),
        False,
        "wait",
    ),
    (
        "하나가 in_progress + final → fail (상한 초과 fail-closed)",
        FULL[:-1] + _checks(1, start=99, status="in_progress", conclusion=None),
        True,
        "fail",
    ),
    (
        "하나가 failure → fail (미완이 남아 있어도 즉시 접는다)",
        FULL[:-2]
        + _checks(1, start=98, conclusion="failure")
        + _checks(1, start=99, status="in_progress", conclusion=None),
        False,
        "fail",
    ),
    ("skipped 는 통과로 센다", _checks(FLOOR, conclusion="skipped"), False, "pass"),
    ("체크런 0건 → wait (아직 스케줄 전)", [], False, "wait"),
    ("체크런 0건 + final → fail (조회 실패도 여기로 접힌다)", [], True, "fail"),
    (
        "하한 미만(전부 초록이어도) → wait — 잡이 사라졌거나 조회가 샜다",
        _checks(FLOOR - 1),
        False,
        "wait",
    ),
    ("하한 미만 + final → fail (fail-closed)", _checks(FLOOR - 1), True, "fail"),
    (
        "재실행으로 같은 이름 복수 → id 최대만 (옛 failure 무시)",
        # **순서가 판정을 결정하면 안 된다** — 새 것(id 901, 초록)을 먼저 두고 옛 것(id 900,
        # 빨강)을 뒤에 둔다. 「나중에 온 것이 이긴다」로 짜면 여기서 빨개진다.
        FULL
        + [{"id": 901, "name": "test: rerun", "status": "completed", "conclusion": "success"}]
        + [{"id": 900, "name": "test: rerun", "status": "completed", "conclusion": "failure"}],
        False,
        "pass",
    ),
    (
        "없앤 대표자 `test: gate` 하나만 초록 → wait (그 잡에 기대던 판정은 사라졌다)",
        [{"id": 2, "name": "test: gate", "status": "completed", "conclusion": "success"}],
        False,
        "wait",
    ),
    (
        "`test: ` 접두가 아닌 체크는 안 센다 (리뷰·CodeQL 이 게이트를 흔들지 않는다)",
        FULL
        + [
            {
                "id": 950,
                "name": "review: cross (비게이트)",
                "status": "completed",
                "conclusion": "failure",
            }
        ],
        False,
        "pass",
    ),
]


def check_subset(actual: dict, expected: dict, label: str, failures: list) -> None:
    for key, want in expected.items():
        got = actual.get(key)
        if got != want:
            failures.append(f"{label}: {key} 기대 {want!r} ≠ 실제 {got!r}")


def main() -> int:
    failures: list[str] = []
    total = 0

    for desc, payload, expected in RECORD_CASES:
        total += 1
        check_subset(rr.decide_record(payload), expected, f"record: {desc}", failures)

    for desc, override, expected in ARM_CASES:
        total += 1
        check_subset(rr.decide_arm({**ARM_BASE, **override}), expected, f"arm: {desc}", failures)

    for desc, title, expected in TITLE_CASES:
        total += 1
        got = rr.classify_bump(title)
        if got != expected:
            failures.append(f"title: {desc}: 기대 {expected!r} ≠ 실제 {got!r}")

    for desc, body, expected in REFS_CASES:
        total += 1
        got = rr.parse_refs(body)
        if got != expected:
            failures.append(f"refs: {desc}: 기대 {expected!r} ≠ 실제 {got!r}")

    for desc, body, expected_refs, expected_dropped in DROPPED_CASES:
        total += 1
        got = rr.scan_refs(body)
        want = {"refs": expected_refs, "dropped": expected_dropped}
        if got != want:
            failures.append(f"scan_refs: {desc}: 기대 {want!r} ≠ 실제 {got!r}")

    # 불변식 두 항의 성질이 다르다:
    #   · 첫 항(missing)은 `dropped := 탐욕 − 산문` 정의상 **항상 참**이다. 검사가 아니라
    #     리팩터 가드다 — `dropped` 를 다시 「버린 줄에서 긁는」 방식으로 되돌리면 빨개진다.
    #   · 둘째 항(invented)이 실제 검사다. 좁힘이 **없던 참조를 만들어 내는** 방향은 차집합이
    #     정의상 못 잡으므로 여기서만 걸린다 (버린 자리 표시가 빠지면 빨개진다).
    for desc, body, *_ in REFS_CASES + DROPPED_CASES:
        total += 1
        got = rr.scan_refs(body)
        greedy = rr._numbers_in(body or "")
        missing = greedy - set(got["refs"]) - set(got["dropped"])
        if missing:
            failures.append(
                f"보존 불변식: {desc}: 탐욕 판독의 {sorted(missing)!r} 이 "
                f"refs·dropped 어디에도 없다 (위험도가 내려갈 수 있다)"
            )
        # 대칭 항: 좁힘이 **없던 참조를 만들어 내면** 그 번호는 dropped 가 정의상 못 잡는다
        invented = set(got["refs"]) - greedy
        if invented:
            failures.append(
                f"보존 불변식(대칭): {desc}: 탐욕 판독에 없던 {sorted(invented)!r} 이 "
                f"refs 에 생겼다 (버린 자리가 앞뒤 산문을 이었다)"
            )

    for desc, override, expect_allow, needle in DELEGATE_CASES:
        total += 1
        got = rr.decide_delegate({**DELEGATE_BASE, **override})
        if got["allow"] != expect_allow:
            failures.append(f"delegate: {desc}: allow 기대 {expect_allow} ≠ 실제 {got['allow']} ({got['reasons']})")
            continue
        if needle and not any(needle in r for r in got["reasons"]):
            failures.append(f"delegate: {desc}: 사유에 {needle!r} 이 없다 ({got['reasons']})")
        # 허용은 사유 0건, 거부는 사유 1건 이상 — 둘이 어긋나면 코멘트가 비거나 거짓이 된다
        if bool(got["reasons"]) == got["allow"]:
            failures.append(f"delegate: {desc}: allow 와 사유 목록이 어긋난다 ({got})")

    # 사유를 하나만 내고 끊지 않는지 — 지휘자가 고치고 다시 요청할 때마다 하나씩 나오면 안 된다
    total += 1
    multi = rr.decide_delegate(
        {
            **DELEGATE_BASE,
            "verdict": "needs_changes",
            "gate_state": "fail",
            "issue_refs": [],
        }
    )
    if len(multi["reasons"]) < 3:
        failures.append(
            f"delegate: 조건 셋이 동시에 깨졌는데 사유가 {len(multi['reasons'])}건뿐이다 ({multi['reasons']})"
        )

    for desc, records, final, expected_state in GATE_CASES:
        total += 1
        state, _lines = rr.judge_gate(records, final=final)
        if state != expected_state:
            failures.append(f"gate: {desc}: 기대 {expected_state!r} ≠ 실제 {state!r}")

    print(f"review_record 케이스 {total}건 검사")
    if total == 0:
        print("::error::케이스를 0건 수집했습니다 — 검사가 비었습니다 (fail-closed)")
        return 1
    if failures:
        for failure in failures:
            print(f"::error::{failure}")
        print(f"판정: 실패 {len(failures)}건 / {total}건")
        return 1
    print(f"판정: {total}건 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
