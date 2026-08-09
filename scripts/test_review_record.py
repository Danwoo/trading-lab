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


def marker(sha=HEAD, verdict="merge_ok", model="kimi", manual=False):
    tail = " source=manual" if manual else ""
    return f"<!-- cross-review v1 model={model} verdict={verdict} sha={sha}{tail} -->"


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
        "비-멤버 사람 코멘트는 봇 축이 열려도 여전히 막힌다  (공격 ①)",
        {
            "head_sha": HEAD,
            "comments": [
                comment(
                    marker(), association="NONE", login="stranger", user_type="User"
                )
            ],
            "existing_reviews": [],
        },
        {"post_review": False, "arm_candidate": False, "marker_sha": None},
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
]

ARM_BASE = {
    "head_sha": HEAD,
    "marker_sha": HEAD,
    "marker_model": "kimi",  # 저자(claude)와 교차 벤더
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
        "참조 이슈에 risk 라벨 없음 → 미선언 = 사람 경로",
        {"issue_refs": [{"number": 7, "labels": ["bug"]}]},
        {"arm": False, "risk": "undeclared"},
    ),
    (
        "이슈 참조 없음 → 미선언 = 사람 경로",
        {"issue_refs": []},
        {"arm": False, "risk": "undeclared"},
    ),
    # ── ② `Refs #N` 의 N 이 PR 인 경우 — PR 의 risk 라벨은 가시화 미러다 ──────────
    (
        "Refs 가 PR 번호뿐 → 배제되어 미선언 = 사람 경로  (공격 ⑧)",
        {"issue_refs": [{"number": 13, "is_pr": True, "labels": ["risk: low"]}]},
        {"arm": False, "risk": "undeclared", "excluded_pr_refs": [13]},
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
    (
        "동일-벤더 + 작성 티어 명시 → arm (반대 티어가 배정된다)",
        {
            "marker_model": "claude",
            "commit_author_emails": ["claude-opus-agent@noreply.local"],
        },
        {"arm": True, "self_vendor": True, "author_tier": "opus"},
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
            "commit_author_emails": [
                "49699333+dependabot[bot]@users.noreply.github.com"
            ],
        },
        {"arm": True, "bot_bump": "non-major", "self_vendor": False},
    ),
    (
        "봇 PR major 상승 → 사람 경로  (공격 ⑤)",
        {
            "pr_author_is_bot": True,
            "pr_title": "build(deps): bump cryptography from 48.0.1 to 50.0.0 in /market-data-mcp-service",
            "issue_refs": [],
            "commit_author_emails": [
                "49699333+dependabot[bot]@users.noreply.github.com"
            ],
        },
        {"arm": False, "bot_bump": "major"},
    ),
    (
        "봇 PR 제목 파싱 실패 → arm 금지  (공격 ⑥ fail-closed)",
        {
            "pr_author_is_bot": True,
            "pr_title": "build(deps): bump the pip group with 3 updates",
            "issue_refs": [],
            "commit_author_emails": [
                "49699333+dependabot[bot]@users.noreply.github.com"
            ],
        },
        {"arm": False, "bot_bump": None},
    ),
    (
        "사람 저자 + major 꼴 제목 → 봇 경로 미적용 (미선언 = 사람 경로)",
        {
            "pr_title": "build(deps): bump x from 1.0 to 2.0",
            "issue_refs": [],
        },
        {"arm": False},
    ),
    (
        "판정 needs_changes → arm 금지",
        {"verdict": "needs_changes"},
        {"arm": False},
    ),
]

REFS_CASES = [
    # (설명, 본문, 기대 번호 목록)
    ("Refs 단건", "…\n\nRefs #23\n", [23]),
    ("Refs 복수(쉼표)", "Refs #23, #24", [23, 24]),
    ("Closes 도 위험도 출처", "Closes #2", [2]),
    ("Fixes/Resolves 혼합 + 중복 제거", "Fixes #5\nresolves #5, #9", [5, 9]),
    ("키워드 없는 #N 은 참조 아님", "PR #47 머지 이후의 작업이다", []),
    ("본문 없음", "", []),
]

GATE_CASES = [
    # (설명, records, final, 기대 상태)
    (
        "게이트 완료 success → pass",
        [
            {
                "id": 2,
                "name": "test: gate",
                "status": "completed",
                "conclusion": "success",
            }
        ],
        False,
        "pass",
    ),
    (
        "게이트 in_progress → wait",
        [{"id": 2, "name": "test: gate", "status": "in_progress", "conclusion": None}],
        False,
        "wait",
    ),
    (
        "게이트 in_progress + final → fail (상한 초과 fail-closed)",
        [{"id": 2, "name": "test: gate", "status": "in_progress", "conclusion": None}],
        True,
        "fail",
    ),
    (
        "게이트 failure → fail",
        [
            {
                "id": 2,
                "name": "test: gate",
                "status": "completed",
                "conclusion": "failure",
            }
        ],
        False,
        "fail",
    ),
    (
        "체크런 0건 → wait (아직 스케줄 전)",
        [],
        False,
        "wait",
    ),
    (
        "체크런 0건 + final → fail (조회 실패도 여기로 접힌다)",
        [],
        True,
        "fail",
    ),
    (
        "재실행으로 같은 이름 복수 → id 최대만 (옛 failure 무시)",
        [
            {
                "id": 9,
                "name": "test: gate",
                "status": "completed",
                "conclusion": "failure",
            },
            {
                "id": 12,
                "name": "test: gate",
                "status": "completed",
                "conclusion": "success",
            },
        ],
        False,
        "pass",
    ),
    (
        "다른 test: 체크만 있고 게이트 없음 → wait",
        [
            {
                "id": 3,
                "name": "test: repo-scan",
                "status": "completed",
                "conclusion": "success",
            }
        ],
        False,
        "wait",
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
        check_subset(
            rr.decide_arm({**ARM_BASE, **override}), expected, f"arm: {desc}", failures
        )

    for desc, body, expected in REFS_CASES:
        total += 1
        got = rr.parse_refs(body)
        if got != expected:
            failures.append(f"refs: {desc}: 기대 {expected!r} ≠ 실제 {got!r}")

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
