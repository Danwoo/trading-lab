"""루트 문서 위생 — 정문에 놓일 것만 놓였는지 + 코드의 문서 포인터가 실재하는지 (stdlib 전용).

## 왜 있나

루트는 이 레포의 정문이다. 처음 온 사람이 README 다음으로 클릭하는 자리라, 여기 놓인 것은
그 자체로 "이 레포가 무엇인가"의 일부가 된다. 그런데 끝난 일회성 리팩터의 작업 일지가
README 보다 긴 분량으로 194줄 놓여 있었다(REFACTOR.md). 「집안일 일지」를 쓰지 않는다는
레포 자기 규율과도 어긋난다.

일지는 한 번 지우면 되지만, **같은 자리에 다시 놓이는 것**은 아무 신호가 없다. 루트에 파일을
하나 더 두는 것은 누구에게나 쉽고, 그것이 정문의 일부라는 사실은 며칠 뒤면 안 보인다.

그 일지를 그냥 지울 수 없었던 이유가 두 번째 검사를 부른다 — `plan_execute/__init__.py` 가
"상세 REFACTOR.md" 로 그 문서를 가리키고 있었다. **코드가 문서를 가리키는 포인터는 문서를
옮기거나 지울 때 조용히 끊어진다.** 링크가 깨진 것을 알려주는 것은 아무것도 없고, 다음에 그
줄을 읽는 사람이 없는 파일을 찾아 헤맨다.

## 무엇을 검사하나

1. **루트 마크다운 인벤토리** — 루트 `*.md` 가 `ROOT_MARKDOWN` 선언과 정확히 일치해야 한다.
   선언에 없는 파일이 생기면 실패한다("정문에 무엇을 두는가"는 결정이지 부수효과가 아니다).
   선언한 파일이 사라져도 실패한다 — 정문 파일을 지웠다면 여기 선언도 함께 지워야 한다.
2. **코드의 `.docs/` 포인터** — 추적 중인 소스·설정(`SOURCE_SUFFIXES`)에서 `.docs/...md`
   형태의 경로를 뽑아 실재를 확인한다. 마크다운끼리의 링크는 대상이 아니다 — 계획 문서는
   "앞으로 만들 문서"를 정상적으로 가리키기 때문이다(`.docs/specs/*-plan.md` 의 「만드는 것」).
   코드 주석에는 그런 용법이 없다: 코드가 문서를 가리키면 그것은 지금 읽으라는 뜻이다.

fail-closed — 각 검사는 대상 수를 세어 하한 미만이면 실패하고, 검사한 건수를 출력에 남긴다.
통과가 "위반 없음"인지 "아무것도 안 봤음"인지 읽는 사람이 구분할 수 있어야 한다.

실행: `python3 scripts/verify_root_doc_hygiene.py` (cwd 무관).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 이 파일 자신은 포인터 스캔 대상이 아니다 — 독스트링·정규식·예외 목록이 설명용 경로 토큰을
# 그대로 품고 있어, 검사기가 자기 예시를 위반으로 읽는다.
SELF_REL = Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()

# 루트에 놓아도 되는 마크다운 — 파일명과 그것이 정문에서 맡는 역할. 여기 없는 것은 루트에
# 두지 않는다. 새로 추가하려면 "처음 온 사람이 README 다음으로 열 만한가"를 먼저 답해야 한다.
ROOT_MARKDOWN: dict[str, str] = {
    "README.md": "제품 정문",
    "CONTEXT.md": "목표층 — 목표·베팅·결정 로그",
    "ROADMAP.md": "목표층 — 마일스톤",
    "CLAUDE.md": "에이전트 규약",
    "AGENTS.md": "에이전트 규약 (CLAUDE.md 와 같은 내용, 다른 도구용)",
    "THIRD-PARTY-NOTICES.md": "라이선스 고지 (생성물 — scripts/generate_notices.py)",
}

# 포인터를 뽑을 파일 확장자 — 사람이 읽는 산문(.md)은 제외한다(위 독스트링 2번).
SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".mjs", ".yml", ".yaml")

# `.docs/...md` 경로 토큰. 글롭(`*`)은 경로가 아니라 패턴 표기라 제외한다.
_DOCS_POINTER = re.compile(r"\.docs/[^\s)\'\"`\]|*]*?\.md")

# 실재하지 않아도 되는 포인터 — (파일, 토큰, 사유). 비우는 것이 기본이다.
# 등록된 항목이 실제로 안 나타나면 실패한다 (낡은 예외 차단).
POINTER_ALLOWLIST: list[tuple[str, str, str]] = [
    (
        "scripts/test_review_notice.py",
        ".docs/specs/plan.md",
        "문서 전용 PR 판정기의 합성 입력 — 경로 필터가 중첩 .md 를 문서로 세는지 보는 픽스처이지, 실재 문서를 가리키는 포인터가 아니다.",
    ),
]

# 하한은 현재 실측치다 (2026-08-20). 정당하게 줄었다면 여기도 함께 내린다 —
# 조용히 넘어가는 대신 시끄럽게 실패하는 것이 의도다.
MIN_SCANNED_SOURCES = 1000
MIN_DOCS_POINTERS = 20


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [f for f in out.split("\0") if f]


def _check_root_markdown() -> list[str]:
    """루트 `*.md` 가 선언과 정확히 일치하는지."""
    actual = {p.name for p in REPO_ROOT.glob("*.md")}
    declared = set(ROOT_MARKDOWN)
    violations = []
    for extra in sorted(actual - declared):
        violations.append(
            f"루트 {extra} — 선언에 없다. 정문에 둘 것이면 ROOT_MARKDOWN 에 역할과 함께 "
            f"추가하고, 특정 서비스·특정 작업의 기록이면 그 서비스 폴더나 .docs/ 로 옮겨라."
        )
    for missing in sorted(declared - actual):
        violations.append(f"루트 {missing} — 선언돼 있으나 실재하지 않는다 ({ROOT_MARKDOWN[missing]}).")
    print(f"[루트 마크다운] 선언 {len(declared)}건 / 실재 {len(actual)}건")
    return violations


def _check_docs_pointers(tracked: list[str]) -> list[str]:
    """소스·설정이 가리키는 `.docs/...md` 가 실재하는지."""
    allowed = {(f, tok) for f, tok, _ in POINTER_ALLOWLIST}
    seen_allowed: set[tuple[str, str]] = set()
    violations: list[str] = []
    scanned = 0
    pointers = 0

    for rel in tracked:
        if rel == SELF_REL or not rel.endswith(SOURCE_SUFFIXES):
            continue
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        scanned += 1
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for token in sorted(set(_DOCS_POINTER.findall(line))):
                pointers += 1
                if (rel, token) in allowed:
                    seen_allowed.add((rel, token))
                    continue
                if not (REPO_ROOT / token).exists():
                    violations.append(f"{rel}:{lineno} — 가리키는 {token} 가 없다.")

    for entry in POINTER_ALLOWLIST:
        if (entry[0], entry[1]) not in seen_allowed:
            violations.append(f"POINTER_ALLOWLIST 의 {entry[0]} → {entry[1]} 가 더는 등장하지 않는다 — 예외를 지워라.")

    print(f"[문서 포인터] 소스 {scanned}개 스캔 / .docs 포인터 {pointers}건 (예외 {len(POINTER_ALLOWLIST)}건)")
    if scanned < MIN_SCANNED_SOURCES:
        violations.append(f"스캔한 소스가 {scanned}개로 하한 {MIN_SCANNED_SOURCES} 미만 — 대상 지정이 현실과 어긋났다.")
    if pointers < MIN_DOCS_POINTERS:
        violations.append(
            f".docs 포인터가 {pointers}건으로 하한 {MIN_DOCS_POINTERS} 미만 — 대상 지정이 현실과 어긋났다."
        )
    return violations


def main() -> None:
    tracked = _tracked_files()
    if not tracked:
        sys.exit("error: 추적 파일 0건 — git 저장소 안에서 실행해야 한다.")

    violations = _check_root_markdown() + _check_docs_pointers(tracked)

    if violations:
        print(f"\n위반 {len(violations)}건:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    print("위반 없음")


if __name__ == "__main__":
    main()
