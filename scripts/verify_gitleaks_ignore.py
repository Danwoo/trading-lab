"""`.gitleaksignore` 가 문이 되지 않게 한다 (stdlib 전용, fail-closed).

## 왜 있나

히스토리 스캔의 예외는 **필요하다** — 과거 커밋은 고쳐 쓸 수 없고, 가림 기능을 시험하려고
넣은 합성 문자열이 거기 남아 있으면 그물이 상시 빨개진다. 상시 빨간 그물은 아무도 안 보므로
있으나 마나다(`.docs/4-아키텍처/main-보호-위협모델.md` §4.3).

그러나 예외 목록은 조용히 자란다. **진짜 유출을 덮는 데 한 줄을 더하는 것이 가장 싼 길**이기
때문이다. 그래서 규칙을 둔다: 지문이 가리키는 **그 줄** 이, 지금 트리에서 `gitleaks:allow` 로
스스로를 합성 카나리아라고 밝히고 있어야 한다. 그 표시는 코드에 남아 리뷰어가 본다.

**「파일 어딘가에 마커가 있다」로는 부족하다** — 같은 파일의 다른 줄에 든 진짜 유출을 그 마커
하나가 덮어 준다. 그래서 지문의 커밋·줄에서 **원문을 꺼내** 지금 트리의 같은 내용 줄을 찾고,
그 줄에 마커가 있는지 본다. 줄 번호는 코드가 움직이면 흔들리므로 번호가 아니라 **내용**으로
맞춘다.

지문은 `커밋:파일:규칙:줄` 이라 같은 값이 다른 자리에 다시 들어오면 그대로 걸린다. 이름으로
거는 예외와 다른 점이 이것이다.

## fail-closed

읽은 줄이 0건이면 실패한다 — 파일이 사라졌거나 형식이 바뀌어 이 검사가 헛도는 상태를
「위반 없음」으로 읽지 않는다. **히스토리를 못 읽어도 실패한다** — 지문의 커밋을 꺼낼 수 없으면
대조가 성립하지 않는다(얕은 체크아웃이면 `fetch-depth: 0` 이 필요하다).

    python3 scripts/verify_gitleaks_ignore.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IGNORE_FILE = REPO_ROOT / ".gitleaksignore"
MARKER = "gitleaks:allow"


def _line_at(commit: str, relative: str, line_no: str) -> str | None:
    """그 커밋의 그 파일 N번째 줄(오른쪽 공백 제거). 못 읽으면 `None` — 통과로 접지 않는다."""
    try:
        index = int(line_no)
    except ValueError:
        return None
    done = subprocess.run(["git", "show", f"{commit}:{relative}"], cwd=REPO_ROOT, capture_output=True, text=True)
    if done.returncode != 0:
        return None
    lines = done.stdout.splitlines()
    if not 1 <= index <= len(lines):
        return None
    return lines[index - 1].rstrip()


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
        commit, relative, _rule, line_no = parts
        target = REPO_ROOT / relative
        if not target.is_file():
            problems.append(f"{number}행: {relative} 가 지금 트리에 없다 — 예외만 남았다면 이 줄을 지워라")
            continue

        historical = _line_at(commit, relative, line_no)
        if historical is None:
            problems.append(
                f"{number}행: {commit[:8]}:{relative}:{line_no} 를 읽지 못했다 — 대조가 성립하지 않는다 "
                "(얕은 체크아웃이면 fetch-depth: 0 이 필요하다)"
            )
            continue

        current = target.read_text(encoding="utf-8", errors="ignore").splitlines()
        # 번호가 아니라 **내용**으로 맞춘다 — 코드가 움직이면 번호는 흔들린다. 지금 줄은 그때
        # 줄에 마커 주석이 붙은 모양이므로, 그때 줄로 시작하면서 마커를 단 줄을 찾는다.
        matched = [ln for ln in current if ln.rstrip().startswith(historical) and MARKER in ln]
        if not matched:
            same_text = [ln for ln in current if ln.rstrip().startswith(historical)]
            detail = (
                f"그 줄이 지금 트리에 있지만 `{MARKER}` 를 안 달고 있다"
                if same_text
                else f"그때 그 줄({historical[:40]!r})이 지금 트리에 없다"
            )
            problems.append(
                f"{number}행: {relative}:{line_no} — {detail}. "
                "예외로 덮기 전에 **그 줄이** 합성 카나리아임을 코드에 밝혀라 "
                "(파일 어딘가의 마커로는 다른 줄의 진짜 유출을 덮을 수 있다)"
            )

    print(f"히스토리 스캔 예외 {len(found)}건 대조 · 위반 {len(problems)}건")
    for problem in problems:
        print(f"::error::{problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
