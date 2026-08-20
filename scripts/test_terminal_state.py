"""터미널 준비·접수 판정 회귀 그물 — 실제로 읽은 화면으로 판다 (stdlib 전용).

`scripts/terminal_state.py` 가 대체한 종전 판정은 `latestCursor` 성장을 신호로 썼고,
Claude Code TUI 가 화면을 제자리에서 다시 그려 그 값이 안 움직이는 바람에 리뷰 경로가
통째로 죽었다 (열린 PR 6건이 전부 `review: unable`).

그래서 이 테스트는 두 가지를 판다:

  1. **화면 판정** — `scripts/fixtures/terminal_screens.json` 의 화면 전건에 대해
     `agent_ready`·`input_pending`·`prompt_accepted` 가 손으로 적은 기대값과 맞는가.
     화면은 전부 2026-08-08 에 리뷰 워커 터미널에서 실제로 읽은 것이다.
  2. **차등** — 같은 실측 커서 수열에 종전 신호(`now > base`)를 돌려 **claude 에서 거짓,
     kimi 에서 참**임을 보인다. 즉 ① 이 버그가 실재했고 ② 타임아웃을 늘려도 무효였으며
     ③ kimi 경로는 종전 신호로도 섰다는 것 — 새 판정은 그 kimi 화면에서도 서야 한다.

**fail-closed**: 케이스를 0건 수집하면 실패한다. 화면·수열의 하한도 함께 건다.

    python3 scripts/test_terminal_state.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import terminal_state as ts  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "terminal_screens.json"

# 하한 — 화면이나 수열이 사라지면 조용히 초록이 되지 않는다.
MIN_SCREENS = 11
MIN_SEQUENCES = 3
# 두 에이전트 **양쪽**에서 판정이 서는지가 이 task 의 불변식이다. 한쪽 화면이 통째로
# 빠지면 "claude 만 고치고 kimi 를 깨뜨렸다"가 초록으로 지나간다.
MIN_PER_AGENT = {"claude": 5, "kimi": 5}

MODES = ("ready", "pending", "accepted")
CHECK = {
    "ready": lambda tail, needle: ts.agent_ready(tail),
    "pending": ts.input_pending,
    "accepted": ts.prompt_accepted,
}


def old_signal_fires(base: int, samples: list[int]) -> bool:
    """종전 판정 — 커서가 기준보다 커지는 순간이 오는가 (`cross-review.yml` 의 `now > base`)."""
    return any(s > base for s in samples)


def check_screens(screens: list[dict]) -> list[str]:
    failures: list[str] = []
    for screen in screens:
        tail, needle = screen["tail"], screen["needle"]
        for mode in MODES:
            got = CHECK[mode](tail, needle)
            want = screen["expect"][mode]
            if got is not want:
                failures.append(
                    f"{screen['name']}/{mode}: 기대 {want} · 실제 {got} "
                    f"(needle={needle!r}, 출처 {screen['captured_from']})"
                )
    return failures


def check_call_order_contract(screens: list[dict]) -> list[str]:
    """`pending` 과 `accepted` 는 동시에 참일 수 없다 — 접수 판정의 전제."""
    return [
        f"{s['name']}: pending 과 accepted 가 동시에 참이다 — 판정이 서로를 배제하지 못한다"
        for s in screens
        if ts.input_pending(s["tail"], s["needle"]) and ts.prompt_accepted(s["tail"], s["needle"])
    ]


def check_differential(sequences: list[dict], screens: list[dict]) -> list[str]:
    """종전 신호가 claude 에서 안 서고 kimi 에서 서는지 — 이 교체의 근거를 고정한다."""
    failures: list[str] = []
    by_agent: dict[str, bool] = {}
    for seq in sequences:
        fired = old_signal_fires(seq["base"], seq["samples"])
        agent = seq["agent"]
        if agent == "claude" and fired:
            failures.append(f"{seq['name']}: 종전 신호가 claude 에서 섰다 — 이 픽스처는 버그 재현이 아니다")
        if agent == "kimi" and not fired:
            failures.append(f"{seq['name']}: 종전 신호가 kimi 에서 안 섰다 — kimi 경로 근거가 무너진다")
        by_agent[agent] = by_agent.get(agent, False) or fired
    for agent in ("claude", "kimi"):
        if agent not in by_agent:
            failures.append(f"{agent} 커서 수열이 없다 — 차등을 증명할 수 없다")

    # 종전 신호가 죽은 그 화면들에서 새 판정은 서야 한다. 안 그러면 교체의 의미가 없다.
    for screen in screens:
        if screen["agent"] == "claude" and screen["expect"]["ready"]:
            if not ts.agent_ready(screen["tail"]):
                failures.append(f"{screen['name']}: 새 준비 판정이 claude 화면에서 안 선다")
    return failures


def main() -> int:
    if not FIXTURE.is_file():
        print(f"::error::픽스처가 없습니다: {FIXTURE}")
        return 1
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    screens = data.get("screens", [])
    sequences = data.get("cursor_sequences", [])

    per_agent: dict[str, int] = {}
    for screen in screens:
        per_agent[screen["agent"]] = per_agent.get(screen["agent"], 0) + 1

    print(f"수집한 화면 {len(screens)}건 (하한 {MIN_SCREENS}) · 커서 수열 {len(sequences)}건 (하한 {MIN_SEQUENCES})")
    for agent in sorted(per_agent):
        floor = MIN_PER_AGENT.get(agent)
        print(f"  · {agent}: {per_agent[agent]}건" + (f" (하한 {floor})" if floor else ""))
    for screen in screens:
        print(f"  - {screen['name']} (latestCursor={screen['latestCursor']}, {len(screen['tail'])}줄)")

    failures: list[str] = []
    if len(screens) < MIN_SCREENS:
        failures.append(f"화면을 {len(screens)}건만 수집했습니다 (하한 {MIN_SCREENS}) — fail-closed")
    if len(sequences) < MIN_SEQUENCES:
        failures.append(f"커서 수열을 {len(sequences)}건만 수집했습니다 (하한 {MIN_SEQUENCES}) — fail-closed")
    for agent, floor in MIN_PER_AGENT.items():
        if per_agent.get(agent, 0) < floor:
            failures.append(f"{agent} 화면이 {per_agent.get(agent, 0)}건입니다 (하한 {floor}) — fail-closed")

    failures += check_screens(screens)
    failures += check_call_order_contract(screens)
    failures += check_differential(sequences, screens)

    print()
    print(f"판정 {len(screens) * len(MODES)}건 대조 · 차등 수열 {len(sequences)}건 대조")
    if failures:
        for f in failures:
            print(f"::error::{f}")
        return 1
    print("모든 케이스가 기대와 같습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
