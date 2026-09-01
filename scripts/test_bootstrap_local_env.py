#!/usr/bin/env python3
"""bootstrap_local_env 의 「직접 채워야 하는 키」 판정 — 비워 두는 것이 정답인 키를 가른다 (#407 F23).

실측: 부트스트랩이 `STRATEGIES_DIR` 을 "외부 서비스 자격증명이라 자동 생성 불가" 목록에 넣어
채우라고 시켰는데, 그 키는 비우면 레포 루트 `strategies/` 를 쓰는 것이 정답이었다. 절대 경로를
짐작해 넣으면 워크트리·클론마다 틀린다. 표식은 `.env.example` 의 키 바로 위 주석(`비워도 된다`)이다.

이 그물이 못박는 것: ① 표식이 붙은 빈 키는 `optional` 로 간다 ② 표식 없는 빈 키는 종전대로
`leftover` 다 ③ 표식과 키 사이에 빈 줄이 있으면 안 붙는다(엉뚱한 키에 새지 않게) ④ 값이 있는
키는 어느 쪽에도 안 간다 ⑤ 실제 `bot-agent-service/app/.env.example` 에서 `STRATEGIES_DIR` 은
optional 이고 `ANTHROPIC_API_KEY` 는 여전히 leftover 다. 케이스를 0건 모으면 실패한다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap_local_env as boot  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

SAMPLE = """# 설명 한 줄. 비워도 된다 — 비우면 기본값을 쓴다.
OPT=""

# 외부 서비스 키
KEY=""
# 비워도 된다

FAR=""
JWT_SECRET="CHANGE_ME"
# 비워도 된다 — 이미 값이 있다
SET=x
"""

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def main() -> int:
    _, filled, leftover, optional = boot.render(SAMPLE, {"JWT_SECRET": "s"})
    check(
        "표식 붙은 빈 키는 optional 로, 주석 문장을 데리고 간다",
        optional,
        [("OPT", "설명 한 줄. 비워도 된다 — 비우면 기본값을 쓴다.")],
    )
    check("표식 없는 빈 키는 leftover — 빈 줄 건너의 표식은 안 붙는다", leftover, ["KEY", "FAR"])
    check("관리 키는 종전대로 채운다", filled, ["JWT_SECRET"])
    check("값이 있는 키는 어느 목록에도 없다", any("SET" in row for row in (leftover, [k for k, _ in optional])), False)

    example = REPO_ROOT / "bot-agent-service" / "app" / ".env.example"
    if not example.is_file():
        print(f"::error::{example} 가 없다 — 실물 대조를 못 한다", file=sys.stderr)
        return 1
    _, _, real_leftover, real_optional = boot.render(example.read_text(encoding="utf-8"), {"JWT_SECRET": "s"})
    check("실물: STRATEGIES_DIR 은 비워 두어도 되는 키다", [k for k, _ in real_optional], ["STRATEGIES_DIR"])
    check("실물: ANTHROPIC_API_KEY 는 여전히 직접 채워야 한다", real_leftover, ["ANTHROPIC_API_KEY"])

    print(f"검사한 케이스 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과, {len(FAILURES)}건 실패")
    if CHECKED < 6:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
