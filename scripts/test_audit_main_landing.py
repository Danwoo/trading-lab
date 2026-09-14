#!/usr/bin/env python3
"""#420 P2 — main 착륙 사후 감사가 무엇을 잡고 무엇을 통과시키는지.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행형으로 쓴다:
    python3 scripts/test_audit_main_landing.py

판정부는 순수 함수라 네트워크 없이 전부 돈다. 이슈 #420 의 완료 조건 2 가 요구하는 두 축을
합성 증거로 세운다 — **양성**(PR 을 안 거친 커밋을 심어 놓으면 빨갛다)과 **음성**(정상 머지는
초록이다). 실제 CI 에서의 확인은 전환 리허설(P4)에서 한다.

fail-closed 축도 함께 본다: 조회가 깨져 0건이 되거나(`--input` 이 빈 배열), 개별 조회가
`None` 으로 오는 경우를 「위반 없음」으로 읽지 않는다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_main_landing as audit
from audit_main_landing import judge_all, judge_commit  # noqa: E402

# 실제 마커는 **40자 sha** 를 싣는다(리뷰 프롬프트 계약). 짧은 값을 픽스처로 쓰면 그물이
# 검사하는 세계가 현실과 달라지고, 접두 비교 같은 느슨함이 초록으로 통과한다.
HEAD = "abc1234def5678" + "0" * 26
GREEN = [{"name": n, "conclusion": "success"} for n in ("test: backend", "test: frontend", "test: repo")]


def marker(sha: str = HEAD, verdict: str = "merge_ok", **author) -> dict:
    """판정 코멘트 — **저자가 붙는다.** 기본은 이 레포의 워크플로가 게시한 실제 모양이다.

    마커는 텍스트일 뿐이고 head sha 는 공개 정보라, 저자를 안 가르면 아무나 코멘트 하나로
    「리뷰 통과」를 만들 수 있다. 그래서 이 픽스처의 기본값도 **저자가 있는** 모양이어야 한다 —
    저자 없는 모양을 기본으로 두면 그물이 검사하는 세계가 현실과 달라진다.
    """
    base = {
        "body": f"판정 코멘트\n\n<!-- cross-review v1 model=kimi verdict={verdict} sha={sha} -->",
        "user": {"login": "github-actions", "type": "Bot"},
        "author_association": "NONE",
    }
    base.update(author)
    return base


def pr(**over) -> dict:
    base = {
        "number": 77,
        "merged": True,
        "head_sha": HEAD,
        "files": ["frontend/app/page.tsx"],
        "comments": [marker()],
        "checks": GREEN,
    }
    base.update(over)
    return base


def ev(**over) -> dict:
    base = {"sha": "0" * 40, "pulls": [pr()]}
    base.update(over)
    return base


CHECKED = 0
FAILURES: list[str] = []


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def violated(evidence: dict) -> bool:
    return bool(judge_commit(evidence)["violations"])


def main() -> int:
    # ── 음성: 규약대로 착륙한 커밋은 통과한다 ─────────────────────
    check("정상 머지는 위반 없음", violated(ev()), False)
    check("정상 머지는 종료 0", judge_all([ev()])[1], 0)

    # ── 양성: PR 을 안 거친 커밋 ────────────────────────────────
    check("PR 없이 착륙 → 위반", violated(ev(pulls=[])), True)
    check("머지 안 된 PR 뿐 → 위반", violated(ev(pulls=[pr(merged=False)])), True)

    # ── 양성: 리뷰 축 ─────────────────────────────────────────
    check("리뷰 마커 없음 → 위반", violated(ev(pulls=[pr(comments=[{"body": "그냥 코멘트"}])])), True)
    check("판정이 merge_ok 아님 → 위반", violated(ev(pulls=[pr(comments=[marker(verdict="unable")])])), True)
    check(
        "리뷰가 본 커밋과 머지된 커밋이 다름 → 위반",
        violated(ev(pulls=[pr(comments=[marker(sha="9" * 40)])])),
        True,
    )
    # **sha 는 40자 동등 비교다.** 종전에는 접두 매치를 허용했는데, 그러면 앞자리만 같은 다른
    # 커밋의 판정이 통과한다 — 같은 마커를 읽는 `review_record` 는 처음부터 동등 비교였다.
    check(
        "짧은 sha 로 적힌 마커는 읽지 않는다 — 실제 마커는 늘 40자다",
        violated(ev(pulls=[pr(comments=[marker(sha=HEAD[:7])])])),
        True,
    )
    check(
        "앞 7자만 같은 다른 커밋의 판정은 통과하지 못한다",
        violated(ev(pulls=[pr(comments=[marker(sha=HEAD[:7] + "f" * 33)])])),
        True,
    )
    # 마커 문법도 정본을 쓴다 — 앞 층이 거부하는 모양을 마지막 방어선이 통과시키면 안 된다.
    loose = {
        **marker(),
        "body": f"<!-- cross-review v1 verdict=merge_ok sha={HEAD} -->",
    }
    check("model 이 없는 마커는 읽지 않는다", violated(ev(pulls=[pr(comments=[loose])])), True)
    unclosed = {**marker(), "body": f"<!-- cross-review v1 model=kimi verdict=merge_ok sha={HEAD}"}
    check("닫히지 않은 마커는 읽지 않는다", violated(ev(pulls=[pr(comments=[unclosed])])), True)
    upper = {**marker(), "body": f"<!-- cross-review v1 model=kimi verdict=merge_ok sha={HEAD.upper()} -->"}
    check("대문자 sha 마커는 읽지 않는다", violated(ev(pulls=[pr(comments=[upper])])), True)

    # 수동 마커는 리뷰가 **있었던** 것이므로 통과시키되, 기록에 남긴다 (#285 규약 — 자동 머지
    # 권한은 얻지 못한다). 「사람이 손으로 붙였다」와 「CI 가 판정했다」를 같은 줄로 적으면
    # 나중에 구분할 근거가 사라진다.
    manual = {**marker(), "body": f"<!-- cross-review v1 model=codex verdict=merge_ok sha={HEAD} source=manual -->"}
    manual_verdict = judge_commit(ev(pulls=[pr(comments=[manual])]))
    check("수동 마커는 위반이 아니다", bool(manual_verdict["violations"]), False)
    check(
        "수동 마커는 기록에 남는다",
        any("source=manual" in note for note in manual_verdict["notes"]),
        True,
    )

    # ── 양성: 게이트 축 ────────────────────────────────────────
    check(
        "게이트 하나 실패 → 위반",
        violated(ev(pulls=[pr(checks=GREEN[:2] + [{"name": "test: repo", "conclusion": "failure"}])])),
        True,
    )
    check("게이트 하나 없음 → 위반", violated(ev(pulls=[pr(checks=GREEN[:2])])), True)

    # ── 문서 면제: 리뷰는 면제, 게이트는 그대로 ──────────────────
    docs = pr(files=["CONTEXT.md"], comments=[{"body": "마커 없음"}])
    check("목표층 문서 전용은 리뷰 마커 면제", violated(ev(pulls=[docs])), False)
    # 면제의 범위는 `review_notice.py` 가 정한다 — 감사가 자기 목록을 들면 이 둘이 위반으로
    # 적힌다. 둘 다 docs-notice 잡이 App 승인 + 자동 머지를 걸어 **정당하게** 착륙하는 모양이다.
    readme = pr(files=["README.md"], comments=[{"body": "마커 없음"}])
    check("md 전용 PR 도 면제다 — 운용 정의와 같은 줄에 선다", violated(ev(pulls=[readme])), False)
    docs_tree = pr(files=[".docs/4-아키텍처/x.md"], comments=[{"body": "마커 없음"}])
    check(".docs 밑 md 도 면제다", violated(ev(pulls=[docs_tree])), False)
    docs_asset = pr(files=[".docs/4-아키텍처/x.png"], comments=[{"body": "마커 없음"}])
    check("문서 트리라도 md 가 아니면 면제가 아니다", violated(ev(pulls=[docs_asset])), True)
    upper = pr(files=["README.MD"], comments=[{"body": "마커 없음"}])
    check("대소문자를 접지 않는다 — README.MD 는 리뷰가 도는 쪽이다", violated(ev(pulls=[upper])), True)
    docs_bad_gate = pr(files=["CONTEXT.md"], comments=[], checks=GREEN[:1])
    check("문서 전용이어도 게이트는 요구한다", violated(ev(pulls=[docs_bad_gate])), True)
    mixed = pr(files=["CONTEXT.md", "frontend/app/page.tsx"], comments=[{"body": "마커 없음"}])
    check("문서에 코드가 섞이면 면제가 사라진다", violated(ev(pulls=[mixed])), True)

    # ── 마커를 아무나 쓰지 못한다 ────────────────────────────────
    # 이 감사는 private 전환으로 사라지는 승인 규칙을 대신하는 **마지막 방어선**이다. 저자를
    # 안 가르면 아무 GitHub 사용자나 코멘트 하나로 그 방어선을 통과한다 — 레포가 public 인
    # 동안에는 지금 당장 살아 있는 표면이다.
    outsider = marker(user={"login": "random-outside-commenter", "type": "User"}, author_association="NONE")
    check("제3자가 쓴 마커는 읽지 않는다", violated(ev(pulls=[pr(comments=[outsider])])), True)
    fake_bot = marker(user={"login": "not-our-bot", "type": "Bot"}, author_association="NONE")
    check("봇처럼 보이는 낯선 신원도 읽지 않는다", violated(ev(pulls=[pr(comments=[fake_bot])])), True)
    half_bot = marker(user={"login": "github-actions", "type": "User"}, author_association="NONE")
    check("로그인만 맞고 타입이 다르면 읽지 않는다", violated(ev(pulls=[pr(comments=[half_bot])])), True)
    no_author = {"body": marker()["body"]}
    check("저자를 모르면 읽지 않는다", violated(ev(pulls=[pr(comments=[no_author])])), True)

    owner = marker(user={"login": "Danwoo", "type": "User"}, author_association="OWNER")
    check("레포 주인이 쓴 마커는 읽는다", violated(ev(pulls=[pr(comments=[owner])])), False)
    app = marker(user={"login": "trading-lab-ci", "type": "Bot"}, author_association="NONE")
    check("승인 App 이 쓴 마커는 읽는다", violated(ev(pulls=[pr(comments=[app])])), False)
    # 위조가 진짜 뒤에 와도 진짜를 덮지 못한다 — 마지막 매치가 이기는 규칙의 사각지대.
    check(
        "제3자 마커가 뒤에 와도 앞의 진짜 판정을 덮지 못한다",
        violated(ev(pulls=[pr(comments=[app, marker(verdict="needs_changes", user={"login": "x", "type": "User"})])])),
        False,
    )

    # ── 잘린 목록을 완전한 것으로 쓰지 않는다 ──────────────────────
    # 한 페이지(100건)만 읽으면 앞 100개가 문서이고 101번째가 코드인 PR 이 「문서 전용」이 되어
    # 리뷰 마커를 면제받는다. 체크런도 같다 — 2페이지의 빨간 체크를 못 보면 초록으로 읽힌다.
    docs_100 = [f"docs/d{i}.md" for i in range(100)]
    check("100개가 전부 문서면 면제한다", violated(ev(pulls=[pr(files=docs_100, comments=[])])), False)
    check(
        "101번째가 코드면 면제가 사라진다",
        violated(ev(pulls=[pr(files=docs_100 + ["app/main.py"], comments=[])])),
        True,
    )
    check("파일 목록을 못 읽으면 면제하지 않는다", violated(ev(pulls=[pr(files=None, comments=[])])), True)

    # 수집부가 실제로 모든 페이지를 따라가는가 — 판정부만 고치면 잘린 목록이 그대로 들어온다.
    calls: list[str] = []

    def fake_gh(path: str):
        calls.append(path)
        page = int(path.split("page=")[-1]) if "page=" in path else 1
        if "/files" in path:
            return [{"filename": f"docs/p{page}-{i}.md"} for i in range(100 if page < 3 else 7)]
        if "/comments" in path:
            return [] if page > 1 else [marker()]
        if "check-runs" in path:
            return {"check_runs": GREEN if page == 1 else []}
        return [{"number": 1, "merged_at": "now", "head": {"sha": HEAD}}]

    original = audit._gh
    audit._gh = fake_gh
    try:
        collected = audit.collect("o/r", "0" * 40)
    finally:
        audit._gh = original
    files = collected["pulls"][0]["files"]
    check("파일을 마지막 페이지까지 모은다", len(files), 207)
    check("페이지를 실제로 넘겼다", sum(1 for c in calls if "/files" in c), 3)

    # 한 페이지라도 못 읽으면 목록이 아니라 `None` 이다 — 빈 목록으로 뭉개면 「볼 것이
    # 없었다」가 「위반이 없었다」로 읽힌다.
    def broken_gh(path: str):
        if "/files" in path and "page=2" in path:
            return None
        return fake_gh(path)

    audit._gh = broken_gh
    try:
        broken = audit.collect("o/r", "0" * 40)
    finally:
        audit._gh = original
    check("한 페이지라도 못 읽으면 목록이 None 이다", broken["pulls"][0]["files"], None)

    # ── fail-closed ──────────────────────────────────────────
    check("조회 실패(None)를 통과로 읽지 않는다", violated(ev(pulls=None)), True)
    check("체크 조회 실패를 통과로 읽지 않는다", violated(ev(pulls=[pr(checks=None)])), True)
    check("코멘트 조회 실패를 통과로 읽지 않는다", violated(ev(pulls=[pr(comments=None)])), True)
    check("검사 대상 0건은 실패다", judge_all([])[1], 1)
    empty_files = pr(files=[], comments=[{"body": "마커 없음"}])
    check("파일 목록이 비면 면제로 접지 않는다", violated(ev(pulls=[empty_files])), True)

    for line in FAILURES:
        print(f"FAIL {line}")
    print(f"\n검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    # 실패한 판에 성공 문구를 찍으면 로그를 읽는 사람이 정반대 사실을 읽는다.
    if FAILURES:
        print("판정: 착륙 감사가 기대와 다르게 동작한다 — 위 FAIL 을 보라")
        return 1
    print("판정: 사후 감사가 양성(PR 미경유·리뷰 없음·게이트 실패)을 잡고, 정상 착륙은 통과시킨다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
