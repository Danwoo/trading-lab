"""pr_authorship 회귀 그물 — 신원이 없는 입력에서 실패하는지가 본체다 (#23 Task 9).

못박는 것:
  ① 검사 대상 0건이 **실패**한다 (fail-closed — 「볼 게 없어서 통과」 금지)
  ② 브랜치가 에이전트를 선언했는데 신원 커밋이 0건이면 실패한다
  ③ 어휘 밖·형식 밖 신원이 「사람 저자」로 접히지 않는다
  ④ 정상 입력(에이전트·사람·dependabot)이 통과한다
  ⑤ 이 그물이 **못 잡는 것**을 케이스로 못박는다 — 선언 없는 브랜치의 신원 누락은
     통과한다. 한계를 테스트에 적어 두지 않으면 다음 사람이 잡히는 줄 안다
케이스를 0건 모으면 실패한다 (fail-closed).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_authorship as pa  # noqa: E402

AGENT = "claude-opus-agent@noreply.local"
KIMI = "kimi-agent@noreply.local"
LEAD = "tjeksdn173@gmail.com"
BOT = "49699333+dependabot[bot]@users.noreply.github.com"


def commits(*emails):
    return [{"sha": f"{i:040x}", "author_email": e} for i, e in enumerate(emails)]


def payload(head_ref="Danwoo/x", emails=(LEAD,), is_bot=False, override=None):
    p = {
        "head_ref": head_ref,
        "commits": commits(*emails),
        "pr_author_is_bot": is_bot,
    }
    if override is not None:
        p.update(override)
    return p


# (설명, payload, 기대 위반 건수, 기대 dict 부분집합)
CASES = [
    # ── ① fail-closed — 검사 0건 ────────────────────────────────────────────────
    (
        "커밋 0건 → 실패 (검사 대상 0건은 통과가 아니다)",
        payload(override={"commits": []}),
        1,
        {"commits_checked": 0},
    ),
    (
        "커밋 키 부재 → 실패",
        payload(override={"commits": None}),
        1,
        {"commits_checked": 0},
    ),
    (
        "커밋이 리스트가 아님(조회 실패가 문자열로 옴) → 실패",
        payload(override={"commits": "error"}),
        1,
        {"commits_checked": 0},
    ),
    (
        "봇 PR 이어도 커밋 0건이면 실패 — R0 은 면제가 없다",
        payload(is_bot=True, override={"commits": []}),
        1,
        {"commits_checked": 0},
    ),
    # ── ② 브랜치 선언 불이행 ────────────────────────────────────────────────────
    (
        "goal-<주제>-claude 인데 커밋이 리드 신원뿐 → 실패 (R3, 디스패치 신원 누락)",
        payload(head_ref="goal-doc-toll-claude", emails=(LEAD,)),
        1,
        {"branch_declares": "claude", "authorship": "사람(에이전트 신원 없음)"},
    ),
    (
        "fix-23-claude 인데 커밋이 리드 신원뿐 → 실패 (R3)",
        payload(head_ref="fix-23-claude", emails=(LEAD,)),
        1,
        {"branch_declares": "claude"},
    ),
    (
        "선언은 claude 인데 커밋 신원은 kimi → 실패 (R4)",
        payload(head_ref="docs-x-claude", emails=(KIMI,)),
        1,
        {"branch_declares": "claude", "known_vendors": ["kimi"]},
    ),
    (
        "선언 claude + 커밋에 claude·kimi 혼재 → 통과 (선언한 벤더가 목록 안)",
        payload(head_ref="docs-x-claude", emails=(AGENT, KIMI)),
        0,
        {"known_vendors": ["claude", "kimi"]},
    ),
    # ── ③ 판독 불가 신원이 사람으로 접히지 않는다 ───────────────────────────────
    (
        "어휘 밖 티어(claude-opus5-agent@) → 실패 (R1)",
        payload(emails=("claude-opus5-agent@noreply.local",)),
        1,
        {"authorship": "미상(판독 불가한 신원 포함)"},
    ),
    (
        "어휘 밖 벤더(gemini-agent@) → 실패 (R1)",
        payload(emails=("gemini-agent@noreply.local",)),
        1,
        {"unknown_agentish": ["gemini-agent@noreply.local"]},
    ),
    (
        "접미 계약 위반(claude@noreply.local) → 실패 (R2) — review_route 는 사람으로 접는 자리",
        payload(emails=("claude@noreply.local",)),
        1,
        {"malformed_local": ["claude@noreply.local"]},
    ),
    (
        "접미 계약 위반(agent@noreply.local) → 실패 (R2)",
        payload(emails=("agent@noreply.local",)),
        1,
        {"malformed_local": ["agent@noreply.local"]},
    ),
    (
        "빈 이메일 → 실패 (R2 — 저자를 아예 못 읽는다)",
        payload(override={"commits": [{"sha": "a" * 40, "author_email": ""}]}),
        1,
        {"commits_checked": 1},
    ),
    (
        "정상 신원 + 판독 불가 신원 혼재 → 실패 (한 건이라도 못 읽으면 접는다)",
        payload(emails=(AGENT, "gemini-agent@noreply.local")),
        1,
        {"known_vendors": ["claude"]},
    ),
    # ── ④ 정상 입력은 통과한다 ─────────────────────────────────────────────────
    (
        "에이전트 신원 커밋 + 선언 있는 브랜치 → 통과",
        payload(head_ref="goal-x-claude", emails=(AGENT,)),
        0,
        {"authorship": "claude", "known_vendors": ["claude"]},
    ),
    (
        "사람 브랜치 + 리드 신원 → 통과 (사람 PR 은 정상이다)",
        payload(head_ref="Danwoo/m2-orientation", emails=(LEAD,)),
        0,
        {"branch_declares": None, "authorship": "사람(에이전트 신원 없음)"},
    ),
    (
        "dependabot PR → 통과 (봇 신원은 GitHub 이 보증한다)",
        payload(
            head_ref="dependabot/uv/market-data-mcp-service/pyjwt-2.13.0",
            emails=(BOT,),
            is_bot=True,
        ),
        0,
        {"authorship": "봇"},
    ),
    (
        "에이전트 + 사람 혼재 커밋 → 통과 (둘 다 손댄 것은 정직한 provenance 다)",
        payload(head_ref="docs-ci-review-design", emails=(AGENT, LEAD)),
        0,
        {"authorship": "claude + 사람"},
    ),
    (
        "구형식 신원(claude-agent@, 티어 미상) → 통과 — 티어는 이 그물의 대상이 아니다",
        payload(head_ref="goal-x-claude", emails=("claude-agent@noreply.local",)),
        0,
        {"known_vendors": ["claude"]},
    ),
    (
        "같은 이메일이 여러 커밋에 → 종류로 센다 (목록 길이가 아니라)",
        payload(head_ref="goal-x-claude", emails=(AGENT, AGENT, AGENT)),
        0,
        {"commits_checked": 3, "known_vendors": ["claude"]},
    ),
    # ── ⑤ 못 잡는 것 — 한계를 못박는다 (파일 머리 「판정 범위의 한계」) ──────────
    (
        "선언 없는 브랜치 + 신원 누락 → **통과한다**. 리드와 에이전트가 같은 git 신원을 "
        "써서 구분할 근거가 없다 — 이 그물의 구멍이고 브랜치 규약으로만 닫힌다",
        payload(head_ref="Danwoo/ci-task9-provenance", emails=(LEAD,)),
        0,
        {"branch_declares": None},
    ),
    (
        "봇 PR 은 어휘 밖 신원이어도 통과 — 봇 축은 R1·R2 면제다",
        payload(emails=("gemini-agent@noreply.local",), is_bot=True),
        0,
        {"authorship": "봇"},
    ),
]


def main() -> int:
    failures = []
    for desc, p, expected_count, expected in CASES:
        got = pa.judge(p)
        n = len(got["violations"])
        if n != expected_count:
            failures.append(
                f"{desc}\n    위반 {expected_count}건 기대 · 실제 {n}건: {got['violations']}"
            )
            continue
        for key, want in expected.items():
            if got.get(key) != want:
                failures.append(
                    f"{desc}\n    {key}: {want!r} 기대 · 실제 {got.get(key)!r}"
                )

    # 판정과 종료코드가 어긋나면 CI 는 초록인데 위반이 있는 상태가 된다 — 같이 못박는다.
    for desc, p, expected_count, _ in CASES:
        got = pa.judge(p)
        if bool(got["violations"]) != (expected_count > 0):
            failures.append(f"{desc}\n    위반 목록과 기대 건수의 참거짓이 어긋난다")

    total = len(CASES)
    if total == 0:
        print("::error::케이스를 0건 모았습니다 — 그물이 비었습니다 (fail-closed)")
        return 1
    print(f"pr_authorship 케이스 {total}건 검사")
    if failures:
        for f in failures:
            print(f"::error::{f}")
        print(f"판정: {len(failures)}건 실패")
        return 1
    print(f"판정: {total}건 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
