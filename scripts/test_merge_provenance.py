"""merge_provenance 회귀 그물 — 실물 대조가 본체다 (#23 Task 9).

두 가지를 못박는다:

  ① **재현식이 실물과 바이트 동등한가.** `gh pr merge --body` 는 GitHub 이 만들 본문을
     대체하므로, 재현이 틀리면 커밋 메시지와 `Co-authored-by:`(지금 살아 있는 유일한 저자
     provenance)를 우리가 지운다. 그래서 머지된 PR 의 실제 squash 본문을 픽스처로 박아
     매번 대조한다 (`fixtures/squash_bodies.json` — 실물에서 뜬 것이지 손으로 쓴 게 아니다).
  ② **provenance 줄이 그 본문을 훼손하지 않는가.** 줄을 넣은 본문에서 그 줄만 빼면 재현본과
     같아야 하고, `Co-authored-by:` 는 여전히 **마지막 트레일러 블록**이어야 한다.

그리고 어휘 — 모르는 것이 「미상」으로 나오는지, 지어내지 않는지.
케이스를 0건 모으면 실패한다 (fail-closed).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merge_provenance as mp  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "squash_bodies.json"

AGENT_OPUS = "claude-opus-agent@noreply.local"
AGENT_SONNET = "claude-sonnet-agent@noreply.local"
LEAD = "tjeksdn173@gmail.com"


def commit(email, message="feat: 예시\n\n본문", name="a", parents=1):
    return {
        "message": message,
        "author_name": name,
        "author_email": email,
        "parents": parents,
    }


# (설명, payload, 기대 줄)
LINE_CASES = [
    (
        "에이전트 저자(티어 있음) + claude(sonnet) 리뷰 + 자동 머지",
        {
            "commits": [commit(AGENT_OPUS)],
            "head_ref": "Danwoo/x",
            "reviewer_model": "claude",
            "reviewer_tier": "sonnet",
            "merged_by": "auto",
        },
        "작성: claude(opus) · 리뷰: claude(sonnet) · 머지: 자동",
    ),
    (
        "리뷰어 티어 미상(옛 마커) → 「티어 미상」이라고 적는다 (지어내지 않는다)",
        {
            "commits": [commit(AGENT_OPUS)],
            "reviewer_model": "claude",
            "reviewer_tier": "",
            "merged_by": "delegate",
        },
        "작성: claude(opus) · 리뷰: claude(티어 미상) · 머지: 지휘자",
    ),
    (
        "작성 티어 미상(구형식 claude-agent@) → 「티어 미상」",
        {
            "commits": [commit("claude-agent@noreply.local")],
            "reviewer_model": "kimi",
            "merged_by": "auto",
        },
        "작성: claude(티어 미상) · 리뷰: kimi · 머지: 자동",
    ),
    (
        "kimi 리뷰는 티어를 안 적는다 (티어 축이 예약만 된 상태)",
        {
            "commits": [commit(AGENT_OPUS)],
            "reviewer_model": "kimi",
            "reviewer_tier": "",
            "merged_by": "human",
        },
        "작성: claude(opus) · 리뷰: kimi · 머지: 사람",
    ),
    (
        "리뷰어 미상(마커 없음) → 「미상」",
        {"commits": [commit(AGENT_OPUS)], "reviewer_model": "", "merged_by": "auto"},
        "작성: claude(opus) · 리뷰: 미상 · 머지: 자동",
    ),
    (
        "머지 주체 미상(어휘 밖 값) → 「미상」",
        {
            "commits": [commit(AGENT_OPUS)],
            "reviewer_model": "claude",
            "reviewer_tier": "sonnet",
            "merged_by": "???",
        },
        "작성: claude(opus) · 리뷰: claude(sonnet) · 머지: 미상",
    ),
    (
        "사람 저자",
        {
            "commits": [commit(LEAD)],
            "reviewer_model": "claude",
            "reviewer_tier": "opus",
            "merged_by": "human",
        },
        "작성: 사람 · 리뷰: claude(opus) · 머지: 사람",
    ),
    (
        "에이전트 + 사람 혼재",
        {
            "commits": [commit(AGENT_OPUS), commit(LEAD)],
            "reviewer_model": "kimi",
            "merged_by": "auto",
        },
        "작성: claude(opus) + 사람 · 리뷰: kimi · 머지: 자동",
    ),
    (
        "claude 티어 혼재 → 티어 미상 (한쪽으로 정하지 않는다)",
        {
            "commits": [commit(AGENT_OPUS), commit(AGENT_SONNET)],
            "reviewer_model": "kimi",
            "merged_by": "auto",
        },
        "작성: claude(티어 미상) · 리뷰: kimi · 머지: 자동",
    ),
    (
        "벤더 혼재(claude+kimi) → 목록으로 적는다",
        {
            "commits": [commit(AGENT_OPUS), commit("kimi-agent@noreply.local")],
            "reviewer_model": "codex",
            "merged_by": "auto",
        },
        "작성: claude,kimi · 리뷰: codex · 머지: 자동",
    ),
    (
        "어휘 밖 에이전트형 신원 → 사람이 아니라 「미상」",
        {
            "commits": [commit("gemini-agent@noreply.local")],
            "reviewer_model": "claude",
            "reviewer_tier": "opus",
            "merged_by": "auto",
        },
        "작성: 미상 · 리뷰: claude(opus) · 머지: 자동",
    ),
    (
        "봇 PR → 「봇」",
        {
            "commits": [commit("49699333+dependabot[bot]@users.noreply.github.com")],
            "pr_author_is_bot": True,
            "reviewer_model": "claude",
            "reviewer_tier": "sonnet",
            "merged_by": "auto",
        },
        "작성: 봇 · 리뷰: claude(sonnet) · 머지: 자동",
    ),
    (
        "커밋 0건(조회 실패) → 작성 미상 (빈 값을 사람으로 접지 않는다)",
        {
            "commits": [],
            "reviewer_model": "claude",
            "reviewer_tier": "sonnet",
            "merged_by": "auto",
        },
        "작성: 미상 · 리뷰: claude(sonnet) · 머지: 자동",
    ),
    (
        "어휘 밖 리뷰어 벤더 → 리뷰 미상",
        {
            "commits": [commit(AGENT_OPUS)],
            "reviewer_model": "gpt",
            "reviewer_tier": "x",
            "merged_by": "auto",
        },
        "작성: claude(opus) · 리뷰: 미상 · 머지: 자동",
    ),
]


def load_fixtures():
    if not FIXTURES.is_file():
        return []
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def main() -> int:
    failures = []

    # ── ① 재현식 ↔ 실물 바이트 대조 ────────────────────────────────────────────
    fixtures = load_fixtures()
    if not fixtures:
        print(f"::error::실물 픽스처를 0건 읽었습니다: {FIXTURES} (fail-closed)")
        return 1
    for fx in fixtures:
        got = mp.reproduce_squash_body(fx["commits"]).rstrip("\n")
        if got != fx["expected_body"]:
            failures.append(
                f"PR #{fx['pr']} ({fx['desc']}) 재현본이 실물과 다르다\n"
                f"    기대 끝: {fx['expected_body'][-160:]!r}\n"
                f"    실제 끝: {got[-160:]!r}"
            )

    # ── ② provenance 줄이 본문을 훼손하지 않는가 ───────────────────────────────
    for fx in fixtures:
        payload = {
            "commits": fx["commits"],
            "head_ref": "Danwoo/x",
            "reviewer_model": "claude",
            "reviewer_tier": "sonnet",
            "merged_by": "auto",
        }
        line = mp.provenance_line(payload)
        body = mp.build_body(payload)
        base = mp.reproduce_squash_body(fx["commits"]).rstrip("\n")
        if line not in body:
            failures.append(f"PR #{fx['pr']}: provenance 줄이 본문에 없다")
            continue

        # **무손실 불변식**: 줄을 뺀 뒤 비어 있지 않은 줄의 나열이 재현본과 순서까지 같아야
        # 한다. 빈 줄 위치는 안 본다 — 문단 경계는 이 줄을 어디에 끼우느냐에 따라 달라지지만
        # 내용이 사라지거나 순서가 뒤바뀌는 것은 훼손이다.
        def nonempty(text):
            return [ln for ln in text.split("\n") if ln.strip()]

        got_lines = [ln for ln in nonempty(body) if ln != line]
        if got_lines != nonempty(base):
            failures.append(
                f"PR #{fx['pr']}: provenance 줄을 빼면 재현본과 줄 나열이 달라진다 — 본문이 훼손됐다\n"
                f"    기대 끝: {nonempty(base)[-3:]!r}\n"
                f"    실제 끝: {got_lines[-3:]!r}"
            )
        # `Co-authored-by:` 는 마지막 트레일러 블록에 남아야 한다
        coauthors = mp.coauthor_trailers(fx["commits"])
        if coauthors:
            tail = mp._tail_trailer_block(body)
            missing = [c for c in coauthors if c not in tail]
            if missing:
                failures.append(
                    f"PR #{fx['pr']}: Co-authored-by 가 마지막 트레일러 블록에 없다 — "
                    f"{missing} (트레일러 판독이 깨진다)"
                )

    # ── ③ 어휘 ────────────────────────────────────────────────────────────────
    for desc, payload, expected in LINE_CASES:
        got = mp.provenance_line(payload)
        if got != expected:
            failures.append(f"{desc}\n    기대: {expected}\n    실제: {got}")

    total = len(fixtures) * 2 + len(LINE_CASES)
    if not LINE_CASES:
        print("::error::어휘 케이스를 0건 모았습니다 (fail-closed)")
        return 1
    print(
        f"merge_provenance 케이스 {total}건 검사 "
        f"(실물 재현 {len(fixtures)}건 · 무손실 {len(fixtures)}건 · 어휘 {len(LINE_CASES)}건)"
    )
    if failures:
        for f in failures:
            print(f"::error::{f}")
        print(f"판정: {len(failures)}건 실패")
        return 1
    print(f"판정: {total}건 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
