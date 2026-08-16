#!/usr/bin/env python3
"""부트스트랩 대상에서 서비스가 빠지는 것을 막는다.

최초 1회 절차(`scripts/bootstrap_local_env.py`)는 대상을 **경로 글롭**(`*/app/.env.example`)으로
잡는다. 그래서 어떤 서비스가 그 파일을 안 가지면 **대상 목록에 아예 안 들어가고**, 부트스트랩은
"할 일 없음"으로 조용히 초록이 된다 — 그 서비스만 `JWT_SECRET` 을 못 받아 런타임에 401 을 낸다.

실제로 그렇게 빠져 있었다: `bot-agent-service` 가 config 를 가진 11개 중 유일하게 `.env.example`
이 없었고, 그 결과 봇 만들기 대화가 사유 없는 401 로 죽었다.

**기준은 「config 를 가진 서비스」다** — `app/core/config.py` 가 있으면 그 서비스는 설정을 읽고,
설정을 읽으면 부트스트랩이 채워 줘야 할 항목이 있다는 뜻이다. 서비스 목록을 손으로 적지 않는
이유가 그것이다: 손목록은 새 서비스가 생겨도 안 늘어난다.

standalone 실행:
    python3 scripts/verify_env_example_coverage.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_NAME = ".env.example"

# 부트스트랩이 프론트도 대상으로 잡는다 — 파이썬 서비스와 규칙이 달라 따로 확인한다.
FRONTEND_EXAMPLE = REPO_ROOT / "frontend" / EXAMPLE_NAME

# 이 아래로 내려가면 그물이 죽은 것이다. 서비스는 늘기만 했지 준 적이 없다.
MIN_SERVICES = 10


def services_with_config() -> list[str]:
    """`app/core/config.py` 를 가진 서비스 — 설정을 읽는 모든 폴더."""
    return sorted(p.parents[2].name for p in REPO_ROOT.glob("*/app/core/config.py"))


def main() -> int:
    services = services_with_config()
    missing = [
        s for s in services if not (REPO_ROOT / s / "app" / EXAMPLE_NAME).is_file()
    ]

    print(
        f"config 를 가진 서비스 {len(services)}개 검사 · {EXAMPLE_NAME} 누락 {len(missing)}건"
    )

    if len(services) < MIN_SERVICES:
        print(
            f"::error::검사 대상이 {len(services)}개뿐이다 — 그물이 죽어 있다 (하한 {MIN_SERVICES}). "
            "글롭이 가리키는 경로가 바뀌었는지 보라.",
            file=sys.stderr,
        )
        return 1

    if not FRONTEND_EXAMPLE.is_file():
        print(
            f"::error::frontend/{EXAMPLE_NAME} 가 없다 — 부트스트랩이 프론트를 건너뛴다",
            file=sys.stderr,
        )
        return 1

    if missing:
        for name in missing:
            print(
                f"::error::{name}/app/{EXAMPLE_NAME} 가 없다 — 부트스트랩 대상에서 빠져 "
                "JWT_SECRET 을 못 받는다 (런타임에 401)",
                file=sys.stderr,
            )
        return 1

    print(
        f"판정: 모든 서비스가 부트스트랩 대상이다 (frontend 포함 {len(services) + 1}개)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
