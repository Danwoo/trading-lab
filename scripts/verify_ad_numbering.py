"""설계 결정 번호(AD-N) 유일성 검사 — #343.

m2-전환설계.md 와 시세적재-구현설계.md 가 한때 AD-13 을 서로 다른 뜻으로 중복 정의했다
(두 문서가 번호 공간을 공유한다고 서술했는데 실제로는 겹쳤다). #343 해소로 문서별
접두사(M2-AD-·MD-AD-)를 도입했다 — 재발 방지로 이 검사가 두 가지를 강제한다:

1. **접두사 필수**: `.docs/**/*.md` 안에서 `AD-\\d+` 를 접두사 없이 쓰면 위반이다.
   (예외: `FE-AD-*` 는 프론트엔드 결정의 별개 스킴, `design-160 AD-*` 는 이미 문서명이
   붙어 있어 별도로 취급한다 — 이 둘은 이 이슈의 충돌 대상이 아니었다.)
2. **정의 유일성**: 같은 접두사의 같은 번호(예: MD-AD-13)가 표 행(`| **MD-AD-13** | ...`)
   으로 두 곳 이상에서 정의되면 위반이다 — 그게 이 번호 충돌이 재발하는 정확한 형태다.

fail-closed: 검사 대상(.md 파일)이 0건이거나, 접두사 표기 자체를 0건 찾으면 실패한다 —
문서가 이동·삭제되거나 표기 규칙이 조용히 사라져도 초록으로 안 남게.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 번호를 실제로 "발급"하는 정본 문서 2개. 다른 문서(예: 시세-데이터-파이프라인.md)는 이 두 문서의
# 결정을 정본 표시 없이 요약 인용할 수 있다(예: MD-AD-25·26 요약 재수록) — 그런 인용까지
# "정의 유일성" 위반으로 잡으면 오탐이라, 새 번호가 실제로 태어나는 이 두 문서만 검사한다.
CANONICAL_DOCS = {
    ".docs/4-아키텍처/m2-전환설계.md",
    ".docs/4-아키텍처/시세적재-구현설계.md",
}

# 이미 자체 접두사/문맥이 있어 이 검사의 "접두사 필수" 규칙에서 예외로 두는 줄
BARE_AD_EXEMPT_LINE = re.compile(r"FE-AD-\d+|design-160\s+AD-\d+")

PREFIXED = re.compile(r"\b(M2|MD)-AD-(\d+)\b")
BARE = re.compile(r"(?<![A-Za-z0-9-])AD-(\d+)\b")
DEF_LINE = re.compile(r"\|\s*\*\*(M2|MD)-AD-(\d+)\*\*")  # 표 행 정의


def main() -> int:
    md_files = sorted((ROOT / ".docs").glob("**/*.md"))
    if not md_files:
        print("::error::.docs 에서 .md 파일을 0건 찾았습니다 — fail-closed 종료")
        return 1

    found_rel_paths = {str(f.relative_to(ROOT)) for f in md_files}
    missing_canonical = CANONICAL_DOCS - found_rel_paths
    if missing_canonical:
        print(
            f"::error::정본 문서가 사라졌거나 옮겨졌습니다: {', '.join(sorted(missing_canonical))} — CANONICAL_DOCS 갱신 필요"
        )
        return 1

    violations: list[str] = []
    definitions: dict[tuple[str, str], list[str]] = {}
    prefixed_count = 0

    for f in md_files:
        rel = f.relative_to(ROOT)
        for i, line in enumerate(f.read_text().splitlines(), start=1):
            if not BARE_AD_EXEMPT_LINE.search(line):
                for m in BARE.finditer(line):
                    violations.append(
                        f"{rel}:{i}: 접두사 없는 AD-{m.group(1)} — M2-AD-{m.group(1)} 또는 "
                        f"MD-AD-{m.group(1)} 처럼 어느 문서 소유인지 표기하세요"
                    )
            for _ in PREFIXED.finditer(line):
                prefixed_count += 1
            if str(rel) in CANONICAL_DOCS:
                for m in DEF_LINE.finditer(line):
                    key = (m.group(1), m.group(2))
                    definitions.setdefault(key, []).append(f"{rel}:{i}")

    if prefixed_count == 0:
        print(
            "::error::M2-AD-*/MD-AD-* 표기를 0건 찾았습니다 — 검사 대상 소실 의심, fail-closed 종료"
        )
        return 1
    if not definitions:
        print(
            "::error::정본 문서 2개에서 표 행 정의(| **M2-AD-N**|MD-AD-N** |)를 0건 찾았습니다 — 표 형식이 바뀌었을 수 있습니다, fail-closed 종료"
        )
        return 1

    for (prefix, number), sites in definitions.items():
        if len(sites) > 1:
            violations.append(
                f"{prefix}-AD-{number} 이 {len(sites)}곳에서 정의됨(유일해야 함): {', '.join(sites)}"
            )

    print(
        f"검사한 .md 파일 {len(md_files)}개, 접두사 표기(M2-AD-/MD-AD-) {prefixed_count}건, "
        f"정의(표 행) {len(definitions)}개 번호"
    )
    if violations:
        for v in violations:
            print(f"::error::{v}")
        return 1
    print("AD 번호 규약 위반 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
