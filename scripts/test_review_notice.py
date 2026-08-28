"""review_notice.decide 회귀 그물 — 문서 전용 판정이 cross-review paths-ignore 와 일치하는지.

관대해지는 방향(판독 불가·코드 섞임을 문서 전용으로 접음)이 최악이다 — 리뷰가 돈 PR 에
「리뷰 없음」이 붙거나, 그 반대로 리뷰 안 된 PR 이 조용히 흐른다. 양방향을 케이스로 못박는다.
케이스를 0건 수집하면 실패한다 (fail-closed).
"""

from __future__ import annotations

import sys

import review_notice

# (설명, 입력 payload, 기대 docs_only, 기대 error 유무)
CASES = [
    ("루트 md 하나", {"files": ["README.md"]}, True, False),
    ("중첩 md", {"files": [".docs/specs/plan.md", "frontend/CLAUDE.md"]}, True, False),
    ("docs/ 밑 비-md", {"files": ["docs/img/arch.png"]}, True, False),
    ("docs/ 하위 깊은 경로", {"files": ["docs/a/b/c.txt"]}, True, False),
    ("md + docs/ 혼합", {"files": ["README.md", "docs/x.rst"]}, True, False),
    ("코드 하나", {"files": ["scripts/review_notice.py"]}, False, False),
    ("md + 코드 혼합", {"files": ["README.md", "app/main.py"]}, False, False),
    # GitHub 경로 필터는 대소문자를 가린다 — README.MD 는 **.md 에 안 걸려 리뷰가 돈다.
    # 소문자로 접으면(구 review-gate 의 grep -i) 리뷰가 돈 PR 에 「리뷰 없음」이 붙는다.
    ("대문자 확장자는 문서가 아니다", {"files": ["README.MD"]}, False, False),
    # `.docs/` 는 `docs/**` 가 아니다 — 비-md 파일이면 리뷰가 돈다.
    (
        ".docs/ 밑 비-md 는 문서가 아니다",
        {"files": [".docs/specs/a.png"]},
        False,
        False,
    ),
    ("이름이 md 로 끝나는 확장자 없는 파일", {"files": ["READMEmd"]}, False, False),
    # `docs/**` 는 디렉터리 접두다 — 이름이 docs 로 시작할 뿐인 디렉터리는 문서가 아니다.
    ("docs 로 시작하는 다른 디렉터리", {"files": ["docsite/a.txt"]}, False, False),
    ("중간 경로의 docs/ 는 접두가 아니다", {"files": ["frontend/docs/a.txt"]}, False, False),
    # 워크플로·판정부 자체는 문서가 아니다 — 승인 경로를 고치는 PR 은 반드시 리뷰를 받는다.
    ("워크플로 + md", {"files": ["CLAUDE.md", ".github/workflows/ci.yml"]}, False, False),
    ("판정부 + md", {"files": ["README.md", "scripts/review_notice.py"]}, False, False),
    # 판독 불가 → 문서 전용 아님 + error (fail-closed)
    ("빈 목록", {"files": []}, False, True),
    ("files 키 없음", {}, False, True),
    ("files 가 리스트 아님", {"files": "README.md"}, False, True),
    ("빈 문자열 항목 섞임", {"files": ["README.md", ""]}, False, True),
    ("항목이 문자열 아님", {"files": ["README.md", 3]}, False, True),
    ("payload 가 dict 아님", ["README.md"], False, True),
    ("stdin 파싱 실패 표식", {"_parse_error": "x"}, False, True),
]


def main() -> int:
    if not CASES:
        print("::error::케이스 0건 — 그물이 비었다 (fail-closed)")
        return 1
    failures = []
    for desc, payload, want_docs_only, want_error in CASES:
        got = review_notice.decide(payload)
        if got["docs_only"] != want_docs_only:
            failures.append(f"{desc}: docs_only={got['docs_only']} (기대 {want_docs_only})")
        if bool(got["error"]) != want_error:
            failures.append(f"{desc}: error={got['error']!r} (기대 유무 {want_error})")
        if got["docs_only"] and got["error"]:
            failures.append(f"{desc}: docs_only 인데 error 병존 — 판정이 모순")
    print(f"review_notice 케이스 {len(CASES)}건 검사 · 실패 {len(failures)}건")
    for f in failures:
        print(f"::error::{f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
