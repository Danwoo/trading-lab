#!/usr/bin/env python3
"""제품이 「아직 없다」고 말한 단계가 실제로 없는지 대조한다.

이 그물이 존재하는 이유: 정문(`README.md`)과 제품 홈(`constants/stages.ts`)이 **둘 다** 백테스트를
「아직 없다」고 말하는 동안, 백테스트 라우터는 등록돼 있었고 격자는 값으로 차 있었다. 사람이 손으로
고치는 것 말고 갱신 경로가 없어서 낡은 것이다.

**판정 규칙** — 단계가 `state: "next"`·`"later"`(아직 안 왔다)인데 그 단계의 **증거**(백엔드 라우터
등록 + 프론트 화면)가 다 있으면 실패한다. 반대 방향(`now` 인데 증거가 없다)도 실패한다.

증거를 「파일이 있다」가 아니라 **「등록됐다」**로 본다 — 파일만 있고 `modules.py` 에 안 실린
라우터는 제품에 없는 것이다.

    python3 scripts/verify_stage_claims.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STAGES = REPO_ROOT / "frontend" / "constants" / "stages.ts"
MODULES = REPO_ROOT / "backend-service" / "app" / "modules.py"
FRONT = REPO_ROOT / "frontend"

#: 단계 id → (등록돼 있어야 하는 라우터 모듈 조각, 그 단계를 그리는 화면 파일)
#: 증거를 못 세는 단계(외부 사정에 걸린 것)는 여기 두지 않는다 — 그런 것은 이 그물의 대상이 아니다.
EVIDENCE: dict[str, tuple[str, str]] = {
    "build": ("routers.bot.bot_router", "components/features/Bot/BotForm.tsx"),
    "verify": (
        "routers.backtest.backtest_router",
        "components/features/Bench/GridRunForm.tsx",
    ),
    "load": (
        "routers.ingest.ingest_router",
        "components/features/Terminal/IngestConsole.tsx",
    ),
}
ARRIVED = {"now"}
NOT_YET = {"next", "later"}

STAGE_RE = re.compile(r'\{\s*id:\s*"(?P<id>[^"]+)"[^}]*?state:\s*"(?P<state>[^"]+)"', re.DOTALL)


def main() -> int:
    for path in (STAGES, MODULES):
        if not path.is_file():
            print(
                f"::error::필수 경로가 없습니다: {path} — fail-closed 종료",
                file=sys.stderr,
            )
            return 1

    declared = {m.group("id"): m.group("state") for m in STAGE_RE.finditer(STAGES.read_text(encoding="utf-8"))}
    if not declared:
        print(
            f"::error::단계를 0건 찾았습니다: {STAGES} — 선언 모양이 바뀌었을 수 있습니다",
            file=sys.stderr,
        )
        return 1

    registered = MODULES.read_text(encoding="utf-8")
    violations: list[str] = []
    checked = 0
    for stage_id, (router, screen) in EVIDENCE.items():
        state = declared.get(stage_id)
        if state is None:
            violations.append(f"{stage_id}: 이 그물이 아는 단계인데 stages.ts 에 없습니다")
            continue
        checked += 1
        has_router = f'"{router}"' in registered
        has_screen = (FRONT / screen).is_file()
        arrived = has_router and has_screen
        if state in NOT_YET and arrived:
            violations.append(
                f"{stage_id}: state={state!r}(아직 안 왔다)인데 라우터({router})와 화면({screen})이 둘 다 있습니다"
            )
        elif state in ARRIVED and not arrived:
            missing = "라우터" if not has_router else "화면"
            violations.append(f"{stage_id}: state={state!r}(왔다)인데 {missing}이 없습니다")

    print(f"단계 {checked}건 대조 (stages.ts ↔ modules.py 등록 + 화면 파일)")
    if checked < len(EVIDENCE):
        print(
            f"::error::{len(EVIDENCE)}건을 봐야 하는데 {checked}건만 봤습니다 — 검사가 줄었습니다",
            file=sys.stderr,
        )
        return 1
    for line in violations:
        print(f"::error::{line}", file=sys.stderr)
    if violations:
        print(
            "::error::제품이 자기 상태를 잘못 말하고 있습니다 — stages.ts 를 고치세요",
            file=sys.stderr,
        )
        return 1
    print("위반 0건 — 「아직 없다」고 말한 단계는 실제로 없습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
