"""#437 — 합성 NAV 를 만들어 쌓는 것이 남아 있지 않은지 (fail-closed).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행형으로 쓴다:
    uv run python tests/test_no_synthetic_nav.py

**리드 결정 2026-09-03: 합성 NAV 를 걷어낸다.** 기각된 대안은 「유지하되 세 값을 맞물리게」이고,
이유는 **합성 위에 M4「보드를 믿는다」를 지으면 그 화면은 처음부터 믿을 수 없다**는 것이다.

걷어내기 전 상태는 이랬다 — `nav`·`benchmark`·`daily_return`·`drawdown` 이 **서로 독립인 난수
walk** 였다. 수익률에서 NAV 를 되짚을 수 없고 낙폭이 곡선과 무관하다. **검산이라는 개념이
성립하지 않는다.** 그런데도 10초마다 영원히 쌓였고, **읽는 화면은 하나도 없었다**
(`app/api/external/backend/` 에 `nav` 프록시가 아예 없다).

이 그물이 지키는 것은 「지운 것이 다시 안 돌아온다」다. 지우기만 하면 다음 사람이 같은 자리에
같은 것을 다시 만든다 — 지금 코드가 그 유혹을 이미 한 번 이겼다는 근거를 남긴다.

  (1) 합성 NAV producer 가 매니저 등록부에 없다.
  (2) 그 파일 자체가 없다.
  (3) 소비 경로(`nav.snapshot` 토픽)는 **남아 있다** — 실제 체결·평가가 그 자리로 들어온다.
      함께 지우면 실제 경로를 세울 때 배관을 다시 깔아야 한다.
  (4) 매니저 등록부를 실제로 읽었는지 — 0건이면 실패(fail-closed).
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"

CHECKED = 0
FAILURES: list[str] = []


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def _manager_entries() -> list[str]:
    """`modules.py` 의 MANAGER_MODULES 에 적힌 모듈 경로."""
    source = (APP / "modules.py").read_text(encoding="utf-8")
    # 타입 주석의 `list[tuple[str, str]]` 에도 `]` 가 있다 — 목록의 시작은 `= [` 다.
    start = source.index("= [", source.index("MANAGER_MODULES")) + 3
    block = source[start : source.index("]", start)]
    return re.findall(r'\("([^"]+)"\s*,', block)


def main() -> int:
    entries = _manager_entries()

    # (4) fail-closed — 등록부를 못 읽었으면 「없다」가 아니라 「못 봤다」다.
    check("매니저 등록부를 읽었다 (0건이면 그물이 죽은 것)", len(entries) > 0, True)

    # (1) 합성 producer 가 등록에 없다.
    nav_producers = [e for e in entries if "nav_producer" in e]
    check("합성 NAV producer 가 매니저 등록부에 없다", nav_producers, [])

    # (2) 파일 자체가 없다 — 등록만 빼면 다음 사람이 다시 꽂는다.
    check("nav_producer_manager.py 가 없다", (APP / "managers/nav/nav_producer_manager.py").is_file(), False)

    # 난수로 시계열을 만드는 코드가 앱 어디에도 없다 (같은 것이 다른 이름으로 돌아오는 것을 막는다)
    offenders = []
    for path in APP.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "random.uniform" in text and ("nav" in text.lower() or "drawdown" in text.lower()):
            offenders.append(str(path.relative_to(APP)))
    check("난수로 NAV 시계열을 만드는 코드가 없다", offenders, [])

    # (3) 소비 경로는 남는다 — 실제 체결·평가가 들어올 자리다.
    mq = (APP / "services/message_queue/message_queue_service.py").read_text(encoding="utf-8")
    check("nav.snapshot 소비 경로는 남아 있다", "nav.snapshot" in mq, True)
    check("NAV 저장 서비스는 남아 있다", (APP / "services/nav/nav_service.py").is_file(), True)

    for line in FAILURES:
        print(f"FAIL {line}")
    print(f"\n검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과 (매니저 등록 {len(entries)}건 확인)")
    print("판정: 합성 NAV 는 걷어내졌고, 실제 값이 들어올 자리는 남아 있다")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
