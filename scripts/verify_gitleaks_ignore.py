"""`.gitleaksignore` 가 문이 되지 않게 한다 (stdlib 전용, fail-closed).

## 왜 있나

히스토리 스캔의 예외는 **필요하다** — 과거 커밋은 고쳐 쓸 수 없고, 가림 기능을 시험하려고
넣은 합성 문자열이 거기 남아 있으면 그물이 상시 빨개진다. 상시 빨간 그물은 아무도 안 보므로
있으나 마나다(`.docs/4-아키텍처/main-보호-위협모델.md` §4.3).

그러나 예외 목록은 조용히 자란다. **진짜 유출을 덮는 데 한 줄을 더하는 것이 가장 싼 길**이기
때문이다. 그래서 규칙을 둔다: `.gitleaksignore` 의 각 줄이 가리키는 파일은 **지금 트리에서도
`gitleaks:allow` 로 스스로를 합성 카나리아라고 밝히고 있어야 한다.** 그 표시는 코드에 남아
리뷰어가 본다 — 한 줄을 더하려면 코드에도 근거를 남겨야 한다.

지문은 `커밋:파일:규칙:줄` 이라 같은 값이 다른 자리에 다시 들어오면 그대로 걸린다. 이름으로
거는 예외와 다른 점이 이것이다.

## fail-closed

읽은 줄이 0건이면 실패한다 — 파일이 사라졌거나 형식이 바뀌어 이 검사가 헛도는 상태를
「위반 없음」으로 읽지 않는다.

    python3 scripts/verify_gitleaks_ignore.py
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORE_FILE = REPO_ROOT / ".gitleaksignore"
MARKER = "gitleaks:allow"


def entries(text: str) -> list[tuple[int, str]]:
    """(줄번호, 지문) — 주석·빈 줄은 뺀다."""
    out: list[tuple[int, str]] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append((number, line))
    return out


def main() -> int:
    if not IGNORE_FILE.is_file():
        # 예외가 아예 없는 상태는 정상이다 — 다만 이 검사가 헛돌지 않게 그 사실을 남긴다.
        print(".gitleaksignore 가 없다 — 히스토리 스캔 예외 0건")
        return 0

    found = entries(IGNORE_FILE.read_text(encoding="utf-8"))
    if not found:
        print("::error::.gitleaksignore 에 읽을 줄이 0건 — 파일은 있는데 항목이 없다. 지우거나 채워라.")
        return 1

    problems: list[str] = []
    for number, fingerprint in found:
        parts = fingerprint.split(":")
        if len(parts) != 4:
            problems.append(f"{number}행: 지문 형식이 아니다 (`커밋:파일:규칙:줄`) — {fingerprint}")
            continue
        _commit, relative, _rule, _line = parts
        target = REPO_ROOT / relative
        if not target.is_file():
            problems.append(f"{number}행: {relative} 가 지금 트리에 없다 — 예외만 남았다면 이 줄을 지워라")
            continue
        if MARKER not in target.read_text(encoding="utf-8", errors="ignore"):
            problems.append(
                f"{number}행: {relative} 에 `{MARKER}` 표시가 없다 — "
                "예외로 덮기 전에 그 값이 합성 카나리아임을 코드에 밝혀라"
            )

    print(f"히스토리 스캔 예외 {len(found)}건 대조 · 위반 {len(problems)}건")
    for problem in problems:
        print(f"::error::{problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
