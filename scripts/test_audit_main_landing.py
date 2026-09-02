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

from audit_main_landing import judge_all, judge_commit  # noqa: E402

HEAD = "abc1234def5678"
GREEN = [{"name": n, "conclusion": "success"} for n in ("test: backend", "test: frontend", "test: repo")]


def marker(sha: str = HEAD, verdict: str = "merge_ok") -> dict:
    return {"body": f"판정 코멘트\n\n<!-- cross-review v1 model=kimi verdict={verdict} sha={sha} -->"}


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
        violated(ev(pulls=[pr(comments=[marker(sha="9999999")])])),
        True,
    )
    check(
        "짧은 sha 로 적힌 마커도 같은 커밋이면 통과", violated(ev(pulls=[pr(comments=[marker(sha=HEAD[:7])])])), False
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
    docs_bad_gate = pr(files=["CONTEXT.md"], comments=[], checks=GREEN[:1])
    check("문서 전용이어도 게이트는 요구한다", violated(ev(pulls=[docs_bad_gate])), True)
    mixed = pr(files=["CONTEXT.md", "frontend/app/page.tsx"], comments=[{"body": "마커 없음"}])
    check("문서에 코드가 섞이면 면제가 사라진다", violated(ev(pulls=[mixed])), True)

    # ── fail-closed ──────────────────────────────────────────
    check("조회 실패(None)를 통과로 읽지 않는다", violated(ev(pulls=None)), True)
    check("체크 조회 실패를 통과로 읽지 않는다", violated(ev(pulls=[pr(checks=None)])), True)
    check("코멘트 조회 실패를 통과로 읽지 않는다", violated(ev(pulls=[pr(comments=None)])), True)
    check("검사 대상 0건은 실패다", judge_all([])[1], 1)

    for line in FAILURES:
        print(f"FAIL {line}")
    print(f"\n검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    print("판정: 사후 감사가 양성(PR 미경유·리뷰 없음·게이트 실패)을 잡고, 정상 착륙은 통과시킨다")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
