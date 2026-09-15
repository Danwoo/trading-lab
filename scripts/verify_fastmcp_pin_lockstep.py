"""fastmcp 핀 lockstep + mcp major 유입 차단 — 한 결정의 두 얼굴을 함께 지킨다.

배경: `template-mcp-service/pyproject.toml` 이 규약을 글로 못박는다 — *"[dependency-groups] main 의
fastmcp 는 MCP 서버의 핵심 — 버전 핀을 타 MCP 서비스와 맞춘다."* 그런데 이 규약에는 검사가 없었고,
어긋나도 CI 가 말해 주지 않아 사람이 읽어야만 잡혔다.

무엇을 막는가 — `.github/dependabot.yml` 의 `mcp` major ignore 는 **이름으로 걸리므로 전이 의존을
못 막는다.** fastmcp 4.0.2 는 `fastmcp-slim[client,server]` 를 거쳐 mcp 2.1.1 을 끌고 들어오고,
그래서 그 ignore 를 통과한 채 한 서비스만 mcp 2.x 로 갈라놓는다 (PR #474 리뷰에서 uv.lock 으로
확인 — base 1.29.1 → 2.1.1). dependabot ignore 를 fastmcp 로 넓혀도 그것은 **봇이 여는 PR** 만
막는다 — 손으로 올리거나 다른 패키지가 끌고 오는 경로는 그대로 열려 있다. 그 자리를 여기서 막는다.

검사 2가지:
  (1) `*-mcp-service/pyproject.toml` 의 `[dependency-groups] main` fastmcp 핀이 전부 같은 문자열
  (2) 모든 `*-service/uv.lock` 의 해석된 `mcp` 가 1.x — 2.0 마이그레이션은 리드 결정으로 보류다
      (근거·해제 조건은 `.github/dependabot.yml` 의 같은 자리 주석)

stdlib 전용: `python3 scripts/verify_fastmcp_pin_lockstep.py` (cwd 무관).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]

# 신규 MCP 서비스는 glob 이 자동 흡수 — 이 목록은 삭제·이름변경 감지용 하한이다.
EXPECTED_MCP_SERVICES = [
    "disclosure-mcp-service",
    "doc-search-mcp-service",
    "market-data-mcp-service",
    "news-mcp-service",
    "portfolio-mcp-service",
    "template-mcp-service",
    "web-mcp-service",
]

# 보류 중인 major. 이 상한을 올리는 것은 8개 서비스 마이그레이션이 서는 시점이고,
# 그때 dependabot.yml 의 두 ignore 항목도 함께 지운다.
MCP_ALLOWED_MAJOR = 1

FASTMCP_SPEC = re.compile(r"^fastmcp\s*(?P<pin>.+)$")


def fastmcp_pin(pyproject: Path) -> str | None:
    """그 서비스가 선언한 fastmcp 제약 문자열 — 선언이 없으면 None."""
    data = tomllib.loads(pyproject.read_text())
    for entry in data.get("dependency-groups", {}).get("main", []):
        if isinstance(entry, str):
            matched = FASTMCP_SPEC.match(entry.strip())
            if matched:
                return matched.group("pin").strip()
    return None


def locked_mcp_version(lock: Path) -> str | None:
    """uv.lock 이 해석한 mcp 버전 — 그 lock 에 mcp 가 없으면 None."""
    for package in tomllib.loads(lock.read_text()).get("package", []):
        if package.get("name") == "mcp":
            return package.get("version")
    return None


def main() -> int:
    problems: list[str] = []

    pyprojects = sorted(REPO_ROOT.glob("*-mcp-service/pyproject.toml"))
    services = [p.parent.name for p in pyprojects]
    if not services:
        # 검사 0건은 통과가 아니다 — 글롭이 못 찾으면 그물이 끊긴 것이다.
        print(f"MCP 서비스 0개 — glob '*-mcp-service/pyproject.toml' 이 {REPO_ROOT} 에서 아무것도 못 찾았다.")
        return 1
    problems += [
        f"{s}: pyproject.toml 미발견 (삭제·이름변경?)" for s in sorted(set(EXPECTED_MCP_SERVICES) - set(services))
    ]

    pins: dict[str, str] = {}
    for pyproject in pyprojects:
        pin = fastmcp_pin(pyproject)
        if pin is None:
            problems.append(f"{pyproject.parent.name}: [dependency-groups] main 에 fastmcp 선언이 없다")
        else:
            pins[pyproject.parent.name] = pin
    if len(set(pins.values())) > 1:
        spread = ", ".join(f"{name} {pin}" for name, pin in sorted(pins.items()))
        problems.append(f"fastmcp 핀이 갈렸다 — {spread}")

    locks = sorted(REPO_ROOT.glob("*-service/uv.lock"))
    if not locks:
        print(f"uv.lock 0개 — glob '*-service/uv.lock' 이 {REPO_ROOT} 에서 아무것도 못 찾았다.")
        return 1
    checked_locks = 0
    for lock in locks:
        version = locked_mcp_version(lock)
        if version is None:
            continue
        checked_locks += 1
        if int(version.split(".")[0]) > MCP_ALLOWED_MAJOR:
            problems.append(
                f"{lock.parent.name}: mcp {version} — {MCP_ALLOWED_MAJOR}.x 만 받는다 "
                f"(전이 의존으로 들어왔는지 `uv tree` 로 상위 패키지를 확인하세요)"
            )
    if checked_locks == 0:
        print(f"mcp 를 담은 uv.lock 0개 — lock {len(locks)}개를 읽었으나 mcp 항목이 하나도 없다 (해석 규약 변경?).")
        return 1

    if problems:
        print("fastmcp·mcp 버전 규약 위반:")
        for problem in problems:
            print(f"  - {problem}")
        print(
            "  → fastmcp 핀은 전 MCP 서비스가 같아야 하고(template-mcp-service/pyproject.toml 주석), "
            "mcp major 는 8개 서비스 동시 마이그레이션이 서기 전까지 보류다(.github/dependabot.yml)."
        )
        return 1

    print(
        f"fastmcp·mcp OK — MCP 서비스 {len(pins)}개가 fastmcp {next(iter(set(pins.values())))} 로 일치, "
        f"uv.lock {checked_locks}개의 mcp 가 {MCP_ALLOWED_MAJOR}.x"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
