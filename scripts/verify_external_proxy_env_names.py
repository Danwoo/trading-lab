#!/usr/bin/env python3
"""프록시 라우트가 **자기 폴더 이름의 서비스**만 가리키는가 — fail-closed (stdlib 전용).

## 왜 있나

`frontend/app/api/external/{service}/**` 는 루트 `CLAUDE.md` 의 규약대로 `{service}` 가 목적지
서비스를 뜻하고, 그 라우트는 `{SERVICE}_SERVICE_URL` 을 읽어야 한다. 그런데 그 규약을 어겨도
**아무것도 빨개지지 않는다** — 타입도 린트도 통과하고, 잘못된 이름이 비어 있으면 요청은
`undefined/scheduler` 로 나가 화면에 「총 0건」으로만 남는다.

실측(#361): 통합 앱 하나를 프론트가 두 이름으로 가리켰다 — `BACKEND_SERVICE_URL` 과, 흡수된
서비스의 잔재인 `DEV_ACTIVITY_SERVICE_URL`. 한쪽만 새 주소로 옮기자 관리자 화면 두 개가
**조용히** 죽었다. 같은 앱을 두 이름으로 가리키면 그 둘이 어긋나는 날이 오고, 어긋났는지
확인하는 자리가 없었다.

이 스크립트가 그 자리다: 라우트가 자기 폴더가 뜻하는 서비스 이름만 읽게 한다. 한 앱에 두
번째 이름을 붙이려면 폴더를 새로 파야 하고, 그 폴더는 **정말 다른 서비스**여야 한다.

## 무엇을 보나

`frontend/app/api/external/{service}/**/route.ts` 안의 `env.<NAME>` 을 전부 모아, 그것이 그
폴더의 이름에서 나온 것인지 본다 (`backend` → `BACKEND_SERVICE_URL`, `multi-agent` →
`MULTI_AGENT_SERVICE_URL`). 서비스 URL 이 아닌 env(예: `NODE_ENV`)는 이 검사의 대상이 아니다.

**fail-closed**: 라우트를 0건 찾거나 기대보다 적으면 실패한다. 폴더가 옮겨져도 "대상 없음 =
위반 없음" 으로 조용히 초록이 되지 않게, 검사한 개수를 출력에 남긴다.

실행: `python3 scripts/verify_external_proxy_env_names.py` (cwd 무관).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ROUTE_ROOT = REPO / "frontend" / "app" / "api" / "external"

#: 라우트가 통째로 사라지는 방식의 우회를 막는 하한. 지금 수보다 낮게 잡아 둔다.
MIN_ROUTES = 20

ENV_READ = re.compile(r"\benv\.([A-Z0-9_]+)\b")
SERVICE_URL_ENV = re.compile(r"^[A-Z0-9_]+_SERVICE_URL$")


def expected_env(service_dir: str) -> str:
    """폴더 이름 → 그 폴더가 읽어야 할 env 이름. `bot-agent` → `BOT_AGENT_SERVICE_URL`."""
    return service_dir.replace("-", "_").upper() + "_SERVICE_URL"


def main() -> int:
    print("프록시 라우트 env 이름 대조 (#361)")
    if not ROUTE_ROOT.is_dir():
        print(f"FAIL: 라우트 경로가 없다 — 옮겨졌다: {ROUTE_ROOT}")
        return 1

    routes = sorted(ROUTE_ROOT.rglob("route.ts"))
    if not routes:
        print(f"FAIL: 프록시 라우트를 0건 찾았다 — 경로 관례가 바뀌었다: {ROUTE_ROOT}")
        return 1
    if len(routes) < MIN_ROUTES:
        print(f"FAIL: 라우트가 {len(routes)}건뿐이다 (하한 {MIN_ROUTES}) — 검사가 줄었다")
        return 1

    services: dict[str, int] = {}
    violations: list[str] = []
    for path in routes:
        service = path.relative_to(ROUTE_ROOT).parts[0]
        services[service] = services.get(service, 0) + 1
        wanted = expected_env(service)
        used = {name for name in ENV_READ.findall(path.read_text(encoding="utf-8")) if SERVICE_URL_ENV.match(name)}
        for name in sorted(used - {wanted}):
            violations.append(f"{path.relative_to(REPO)} — {name} (이 폴더가 읽어야 할 것: {wanted})")

    listing = " · ".join(f"{name}({count})" for name, count in sorted(services.items()))
    print(f"  라우트 {len(routes)}개 · 서비스 폴더 {len(services)}개: {listing}")

    if violations:
        print(f"FAIL: 자기 폴더가 아닌 서비스를 가리키는 라우트 {len(violations)}건")
        for line in violations:
            print(f"  {line}")
        print("  한 앱을 두 이름으로 가리키면 그 둘이 어긋나는 날 화면이 조용히 죽는다 (#361).")
        return 1

    print("위반 0건 — 라우트가 자기 폴더의 서비스만 가리킨다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
