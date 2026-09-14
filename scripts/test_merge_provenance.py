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
import re
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


#: 지우는 것 / 남기는 것 — 이 경계가 규약의 전부다.
STRIP_CASES = [
    ("Claude 공동저자 트레일러", "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>", False),
    ("대소문자가 달라도", "co-authored-by: Claude <noreply@anthropic.com>", False),
    ("세션 링크", "Claude-Session: https://claude.ai/code/session_abc", False),
    ("맨 claude.ai 링크", "https://claude.ai/code/session_abc", False),
    ("생성 배지", "\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)", False),
    ("에이전트 신원은 남는다", "Co-authored-by: claude-opus-agent <claude-opus-agent@noreply.local>", True),
    ("사람 신원은 남는다", "Co-authored-by: Danwoo <tjeksdn173@gmail.com>", True),
    ("dependabot 서명은 남는다", "Signed-off-by: dependabot[bot] <support@github.com>", True),
    ("본문 문장은 남는다", "claude 로 만든 봇이 아니라 사용자가 만든 봇이다", True),
]


#: 재현본에 자기 광고가 남았는지 — **판정부의 정규식과 별개로** 한 겹 더 본다.
#:
#: 맨 부분 문자열(`"anthropic.com" in got`)로 보지 않는 이유: 그 모양은 URL 의 아무 자리에나
#: 걸리는 불완전한 검사라 CodeQL 의 `py/incomplete-url-substring-sanitization` 이 잡는다
#: (실측 — 이 줄이 경보 #49 였다). 여기서는 **줄 단위**로 보고 경계를 고정한다:
#: 주소는 `@` 뒤에서 끝나야 하고, 세션 줄은 줄머리여야 한다.
_RESIDUE = re.compile(r"@anthropic\.com\b|^Claude-Session:", re.M)


def _has_self_reference(body: str) -> bool:
    return bool(mp._AI_SELF_REFERENCE.search(body) or _RESIDUE.search(body))


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
    # **기대값을 검사 대상 함수로 만들지 않는다.** 종전에는 `want` 를
    # `strip_ai_self_reference(실물)` 로 만들었는데, 그러면 그 함수가 과하게 지워도 `want` 가
    # 똑같이 과하게 줄어 **항상 통과한다** — 검사할 수 없는 구조였다 (#489 리뷰 지적).
    #
    # 이제 필터가 닿는 픽스처는 **필터 후 본문을 픽스처 파일에 글자 그대로 고정**해 두고
    # (`expected_after_filter`, 지워진 줄을 사람이 읽고 확인했다), 나머지는 실물과 **바이트
    # 동일**을 요구한다 — AI 언급이 없는 커밋이 한 글자라도 바뀌면 여기서 걸린다.
    stripped_any = 0
    for fx in fixtures:
        got = mp.reproduce_squash_body(fx["commits"]).rstrip("\n")
        if "expected_after_filter" in fx:
            stripped_any += 1
            want = fx["expected_after_filter"].rstrip("\n")
        else:
            want = fx["expected_body"].rstrip("\n")
        if got != want:
            failures.append(
                f"PR #{fx['pr']} ({fx['desc']}) 재현본이 실물(자기 광고 제외)과 다르다\n"
                f"    기대 끝: {want[-160:]!r}\n"
                f"    실제 끝: {got[-160:]!r}"
            )
        if _has_self_reference(got):
            failures.append(f"PR #{fx['pr']}: 재현본에 AI 자기 광고가 남았다")

    # 필터가 살아 있는지 **실물로** 증명한다 — 아무 데서도 아무것도 안 지우면 그 필터는 죽은
    # 것이고, 죽은 필터는 다음 커밋에서 조용히 통과시킨다.
    if stripped_any == 0:
        failures.append(
            "AI 자기 광고를 지우는 픽스처가 0건이다 — 필터가 죽었거나 픽스처가 그 경로를 안 덮는다 (fail-closed)"
        )
    else:
        print(f"AI 자기 광고를 지운 픽스처: {stripped_any}/{len(fixtures)}건 (나머지는 실물과 바이트 동일 요구)")

    # **AI 언급이 없으면 한 글자도 바뀌지 않는다.** 이 모듈의 계약이 「재현」이므로, 필터가
    # 있다는 이유로 무관한 커밋의 문단 경계가 달라지면 그 계약이 깨진다.
    untouched = "fix: 원장 조정\n\n재현 로그:\n```\nERROR\n```\n\n\n위 로그가 원인이다."
    if mp.strip_ai_self_reference(untouched) != untouched:
        failures.append(
            "AI 언급이 없는 메시지가 바뀌었다 — 연속 빈 줄을 무조건 접으면 재현 계약이 깨진다\n"
            f"    기대: {untouched!r}\n    실제: {mp.strip_ai_self_reference(untouched)!r}"
        )
    # 이음매는 접는다 — 지운 자리에 빈 줄이 겹친 채로 두면 문단이 벌어진다.
    seam = "제목\n\n본문\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n\n꼬리"
    if mp.strip_ai_self_reference(seam) != "제목\n\n본문\n\n꼬리":
        failures.append(f"제거 이음매의 겹친 빈 줄이 안 접혔다 — 실제: {mp.strip_ai_self_reference(seam)!r}")

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

    # ── ②-1 잔류 검사의 경계 ───────────────────────────────────────────────────
    # 맨 부분 문자열로 보면 URL 아무 자리의 `anthropic.com` 에도 걸린다 — 경보가 아니라
    # **오탐**이 되고, 이 검사가 무엇을 보는지 읽는 사람이 모르게 된다.
    RESIDUE_CASES = [
        ("진짜 트레일러", "Co-Authored-By: Claude <noreply@anthropic.com>", True),
        ("세션 줄", "Claude-Session: https://claude.ai/code/session_x", True),
        ("URL 안에 낀 비슷한 도메인", "참고: https://evil.example/?q=anthropic.com.attacker.net", False),
        ("줄머리가 아닌 인용", "본문에 Claude-Session: 을 인용한 문장", False),
        ("평범한 본문", "fix: 무언가 고친다", False),
    ]
    for desc, body, expected in RESIDUE_CASES:
        if _has_self_reference(body) != expected:
            failures.append(f"잔류 검사 경계 — {desc}: 기대 {expected}")

    # ── ②-2 무엇을 지우고 무엇을 남기는가 ──────────────────────────────────────
    if not STRIP_CASES:
        print("::error::자기 광고 경계 케이스를 0건 모았습니다 (fail-closed)")
        return 1
    for desc, line, keep in STRIP_CASES:
        body = f"제목\n\n본문\n{line}\n"
        survived = line in mp.strip_ai_self_reference(body)
        if survived != keep:
            failures.append(
                f"자기 광고 경계 — {desc}: 기대 {'남김' if keep else '지움'} · 실제 {'남김' if survived else '지움'}"
            )

    # ── ③ 어휘 ────────────────────────────────────────────────────────────────
    for desc, payload, expected in LINE_CASES:
        got = mp.provenance_line(payload)
        if got != expected:
            failures.append(f"{desc}\n    기대: {expected}\n    실제: {got}")

    total = len(fixtures) * 3 + len(STRIP_CASES) + len(LINE_CASES) + 2 + len(RESIDUE_CASES)
    if not LINE_CASES:
        print("::error::어휘 케이스를 0건 모았습니다 (fail-closed)")
        return 1
    print(
        f"merge_provenance 케이스 {total}건 검사 "
        f"(실물 재현 {len(fixtures)}건 · 자기 광고 잔류 {len(fixtures)}건 · 무손실 {len(fixtures)}건 · "
        f"자기 광고 경계 {len(STRIP_CASES)}건 · 잔류 검사 경계 {len(RESIDUE_CASES)}건 · "
        f"무관 커밋 보존 2건 · 어휘 {len(LINE_CASES)}건)"
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
