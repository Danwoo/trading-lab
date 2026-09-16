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
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "cross-review.yml"
JUDGE_SOURCE = Path(__file__).resolve().parent / "terminal_state.py"
# 워크플로가 「이 판정부가 `--agent` 를 아는가」를 판별하는 표식. 판정부에서 이 이름이 사라지면
# 워크플로는 영영 「모르는 판본」으로 읽고, codex 상자는 **아무 소리 없이** 다시 안 잡힌다.
AGENT_FLAG_PROBE = "_split_agent"

# 하한 — 화면이나 수열이 사라지면 조용히 초록이 되지 않는다.
MIN_SCREENS = 13
MIN_SEQUENCES = 3
# 에이전트 **전부**에서 판정이 서는지가 이 task 의 불변식이다. 한쪽 화면이 통째로
# 빠지면 "claude 만 고치고 kimi 를 깨뜨렸다"가 초록으로 지나간다.
MIN_PER_AGENT = {"claude": 5, "kimi": 5, "codex": 2}

MODES = ("ready", "pending", "accepted")
# **화면마다 그 화면의 에이전트로 판정한다.** 캐럿 규칙이 에이전트별로 갈려 있어서
# (codex 의 `›` 는 줄 중간에 온다), 전부 기본값으로 판정하면 그 갈래가 안 돌고 지나간다.
CHECK = {
    "ready": lambda tail, needle, agent: ts.agent_ready(tail, agent),
    "pending": ts.input_pending,
    "accepted": ts.prompt_accepted,
}


def old_signal_fires(base: int, samples: list[int]) -> bool:
    """종전 판정 — 커서가 기준보다 커지는 순간이 오는가 (`cross-review.yml` 의 `now > base`)."""
    return any(s > base for s in samples)


def check_screens(screens: list[dict]) -> list[str]:
    failures: list[str] = []
    for screen in screens:
        tail, needle, agent = screen["tail"], screen["needle"], screen["agent"]
        for mode in MODES:
            got = CHECK[mode](tail, needle, agent)
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
        if ts.input_pending(s["tail"], s["needle"], s["agent"])
        and ts.prompt_accepted(s["tail"], s["needle"], s["agent"])
    ]


# 줄 중간 캐럿을 열어도 삼키면 안 되는 문자열. 종전에 이 규칙을 전 에이전트에 열었다가
# 리뷰가 차단급으로 잡은 자리다.
#
# **앞의 둘은 이 레포에 실재한다** — `frontend/constants/writeAccess.ts` 의 안내 문장과
# `frontend/components/shared/DataTable/DataTablePager.tsx` 의 단독 `›`. 셋째는 실재하지
# 않는 모양 사례다(경로 표기가 셋 이상으로 늘어난 꼴). 실재 여부와 무관하게 규칙이
# 삼키면 안 되는 모양이라 함께 둔다 — 「레포에 있는 것들」이라 적었던 첫 판은 사실이
# 아니었고 `#507` 리뷰가 잡았다.
NOT_A_BOX = (
    "시스템관리 › 권한관리",
    "  ›",
    "돌파 › 체결 › 청산",
)


def check_inline_caret_is_scoped(screens: list[dict]) -> list[str]:
    """줄 중간 캐럿은 **그 에이전트에게만** 열려 있는가.

    이 규칙이 전 에이전트로 새면 `시스템관리 › 권한관리` 같은 줄이 입력 상자로 읽히고,
    준비·접수·제출 판정이 한꺼번에 틀어진다. 그래서 두 방향을 다 본다 —
    ㉠ 에이전트를 안 주면 codex 상자도 안 잡힌다(규칙이 기본값으로 새지 않았다)
    ㉡ claude·kimi 로는 `›` 줄이 상자가 아니다

    **codex 에서는 그 줄들도 캐럿 줄로 읽힌다 — 그것이 이 규칙의 한계다.** 여기서 그 사실을
    단언으로 박아 둔다: 지워서 숨기지 않고, 규칙이 조용히 넓어지거나 좁아지면 빨개지게 한다.
    안전은 모양이 아니라 **자리**가 준다 — `caret_index` 는 **마지막** 캐럿 줄을 고르고,
    터미널 tail 은 커서에서 끝나므로 입력 상자가 언제나 그 아래다.
    """
    failures: list[str] = []
    for screen in screens:
        if screen["agent"] != "codex":
            continue
        if ts.agent_ready(screen["tail"]):
            failures.append(f"{screen['name']}: 에이전트 없이도 상자로 읽혔다 — 줄 중간 캐럿이 기본값으로 샜다")
    for line in NOT_A_BOX:
        for agent in (None, "claude", "kimi"):
            if ts.is_caret_line(line, agent):
                failures.append(f"{line!r}: {agent or '기본값'} 에서 캐럿 줄로 읽혔다 — 레포 문자열을 상자로 오인한다")
        if not ts.is_caret_line(line, "codex"):
            failures.append(
                f"{line!r}: codex 에서 캐럿 줄이 아니게 됐다 — 규칙이 좁아졌다면 상자도 못 잡는지 함께 확인하라"
            )
    return failures


def check_workflow_wiring() -> list[str]:
    """워크플로가 **에이전트를 실제로 넘기는가**, 그리고 그 배선이 조용히 죽지 않는가.

    판정만 고치고 호출부를 안 고치면 codex 는 종전대로 죽는다. 반대로 호출부만 앞서 가면
    번들된 옛 판정부가 사용법 오류(2)를 내 **그 PR 자신이 리뷰를 못 받는다** — 판정부는
    head 가 아니라 **base 커밋**에서 번들되기 때문이다.

    그래서 셋을 본다:
      ① 후보 모델을 `SCREEN_AGENT` 로 넘긴다
      ② 판정부가 그 인자를 아는 판본일 때만 넘긴다(호환 가드)
      ③ **가드가 찾는 표식이 판정부에 실재한다** — 이 줄이 이 그물의 몫이다. 표식 이름이
         바뀌면 가드는 말없이 「모른다」로 떨어지고, 아무것도 빨개지지 않은 채 기능만 사라진다.
    """
    if not WORKFLOW.is_file():
        return [f"워크플로를 찾지 못했습니다: {WORKFLOW}"]
    workflow = WORKFLOW.read_text(encoding="utf-8")
    judge = JUDGE_SOURCE.read_text(encoding="utf-8")

    failures: list[str] = []
    if 'SCREEN_AGENT="$m"' not in workflow:
        failures.append("cross-review.yml 이 후보 모델을 SCREEN_AGENT 로 넘기지 않는다 — 판정이 에이전트를 모른다")
    if "--agent" not in workflow:
        failures.append("cross-review.yml 이 판정부에 --agent 를 넘기지 않는다 — 에이전트별 캐럿 규칙이 안 돈다")
    if "TERM_STATE_HAS_AGENT" not in workflow:
        failures.append(
            "cross-review.yml 에 판정부 판본 호환 가드가 없다 — 옛 판정부에 --agent 를 넘기면 그 PR 이 리뷰를 못 받는다"
        )
    if AGENT_FLAG_PROBE not in workflow:
        failures.append(f"호환 가드가 {AGENT_FLAG_PROBE!r} 로 판별하지 않는다 — 이 그물이 지키는 표식과 어긋났다")
    if AGENT_FLAG_PROBE not in judge:
        failures.append(
            f"판정부에 {AGENT_FLAG_PROBE!r} 가 없다 — 워크플로의 호환 가드가 영영 「모르는 판본」으로 읽어"
            " codex 상자 판정이 조용히 죽는다"
        )
    return failures


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
            if not ts.agent_ready(screen["tail"], screen["agent"]):
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
    failures += check_inline_caret_is_scoped(screens)
    failures += check_workflow_wiring()
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
