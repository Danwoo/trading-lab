"""프론트 프록시 라우트에 소비자가 있는지 대조한다 — fail-closed (stdlib 전용).

## 왜 있나

`frontend/app/api/external/**/route.ts` 는 백엔드로 나가는 문이다. 문만 만들고 부르는 쪽을 안
만들어도 **아무것도 빨개지지 않는다** — 타입체커는 통과하고 린터도 조용하다. 실측(2026-08-09,
이슈 #2): `bar/gaps` 라우트가 백엔드 계약·프록시까지 서 있는데 프론트 소비자가 0건이라, 설계가
정한 갭 표시(MD-AD-23)가 화면에서 통째로 빠져 있었다. 라우트가 있으니 "됐다"고 읽힌 것이다.

이 스크립트는 그 클래스를 닫는다: 라우트마다 `frontend/services/**` 에 그 경로를 부르는 곳이
있는지 본다. 없으면 실패한다 — 라우트를 지우든 소비자를 만들든 사람이 정하게 만든다.

## 어떻게 대조하나

서비스는 URL 을 통째 리터럴로 쓰지 않고 상수 + 템플릿으로 조립한다
(`const BAR_URL = "/api/external/backend/bar"` → `` `${BAR_URL}/gaps` ``). 그래서 문자열 포함
검사로는 못 잡는다. 세 단계로 푼다:

1. 서비스 파일에서 `const NAME = "리터럴"` 을 모은다.
2. 문자열·템플릿 리터럴을 훑어 `${NAME}` 을 1에서 치환한다. 못 푼 `${...}`(경로 변수 등)은
   **세그먼트 와일드카드**로 남긴다.
3. 라우트 경로의 `[param]` 도 와일드카드로 바꿔, 세그먼트 수와 값이 맞는 소비자가 있는지 본다.

와일드카드는 **세그먼트 하나**만 삼킨다 — `${id}` 가 여러 칸을 먹는다고 보면 아무 라우트나
아무 소비자에 매칭돼 그물이 무력해진다.

**fail-closed**: 라우트를 0건 수집하거나 서비스 파일을 0건 수집하면 통과가 아니라 실패다.
검사한 개수를 출력해, 초록이 "위반 없음"인지 "아무것도 안 봤음"인지 구분되게 한다.

실행: `python3 scripts/verify_proxy_route_consumers.py` (cwd 무관).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = REPO_ROOT / "frontend" / "app"
ROUTE_ROOT = APP_ROOT / "api" / "external"
# 소비자가 사는 곳. 룰 6(fetch/axios 직접 사용 금지)이 클라이언트 호출을 이 층으로 모은다.
SERVICE_ROOT = REPO_ROOT / "frontend" / "services"

# 라우트·서비스가 통째로 사라지면(경로 변경·삭제) 조용히 초록이 되지 않도록 하는 하한.
MIN_ROUTES = 10
MIN_SERVICE_FILES = 5

# 소비자가 없는 것을 **알고** 남겨 둔 라우트. 이 그물이 처음 돌 때 잡은 것이고, 지울지 배선할지는
# 사람이 정한다(이슈 #2 PR 「발견」).
#
# **예외는 존재를 강제한다** — 여기 적힌 경로가 실제로 고아가 아니게 되면(누가 배선했거나 라우트를
# 지웠으면) 실패한다. 낡은 예외가 남아 새 고아를 덮는 것이 이 그물의 유일한 우회로이므로 막는다
# (`run_verify_scripts.py` 의 `--skip` 규칙과 같은 이유).
KNOWN_ORPHANS = {
    # multi-agent 의 네이티브 SSE 엔드포인트. 프론트는 ai-chatbot 호환 경로(`/agent/example-ai`)만
    # 쓴다 — 이 문을 열어 둘지는 리서치 화면(2026-08-09 결정 §25)을 지을 때 정해진다.
    "/api/external/multi-agent/agent",
}

WILDCARD = "\x00"

CONST_LITERAL = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*[\"'`]([^\"'`]*)[\"'`]\s*;")
# 문자열·템플릿 리터럴 중 프록시 경로가 될 수 있는 것 — `/api/...` 로 시작하거나 `${X}` 로 시작.
URL_LIKE = re.compile(r"[\"'`]((?:/api/|\$\{)[^\"'`]*)[\"'`]")
TEMPLATE_SLOT = re.compile(r"\$\{([^}]*)\}")


def collect_const_literals(sources: list[str]) -> dict[str, str]:
    """`const NAME = "리터럴"` 전수. 서비스 파일 사이에서도 이름이 겹치지 않는다고 보지 않고,
    같은 이름이 다른 값이면 나중 값으로 덮지 않고 **둘 다** 후보로 남긴다면 매칭이 느슨해지므로,
    파일 단위로 풀고 여기서는 파일별 맵을 각각 쓴다."""
    resolved: dict[str, str] = {}
    for source in sources:
        for name, literal in CONST_LITERAL.findall(source):
            resolved[name] = literal
    return resolved


def resolve_urls(source: str) -> set[str]:
    """한 파일 안에서 조립 가능한 URL 문자열을 푼다. 못 푼 슬롯은 세그먼트 와일드카드."""
    consts = collect_const_literals([source])
    urls: set[str] = set()
    for raw in URL_LIKE.findall(source):
        resolved = TEMPLATE_SLOT.sub(lambda m: consts.get(m.group(1).strip(), WILDCARD), raw)
        # 중첩 상수(상수가 상수를 참조)를 한 번 더 푼다. 깊이는 실사용상 2면 충분하고,
        # 더 깊으면 못 푼 채로 남아 와일드카드가 되므로 거짓 통과가 아니라 느슨한 통과다.
        resolved = TEMPLATE_SLOT.sub(lambda m: consts.get(m.group(1).strip(), WILDCARD), resolved)
        if resolved.startswith("/api/external/"):
            urls.add(resolved)
    return urls


def segments(path: str) -> list[str]:
    return [seg for seg in path.strip("/").split("/") if seg != ""]


def matches(route_segs: list[str], consumer_segs: list[str]) -> bool:
    if len(route_segs) != len(consumer_segs):
        return False
    for route_seg, consumer_seg in zip(route_segs, consumer_segs, strict=False):
        route_dynamic = route_seg.startswith("[") and route_seg.endswith("]")
        consumer_dynamic = WILDCARD in consumer_seg
        if route_dynamic or consumer_dynamic:
            continue
        if route_seg != consumer_seg:
            return False
    return True


def main() -> int:
    if not ROUTE_ROOT.is_dir():
        print(f"::error::프록시 라우트 디렉터리가 없습니다: {ROUTE_ROOT.relative_to(REPO_ROOT)}")
        return 1
    if not SERVICE_ROOT.is_dir():
        print(f"::error::서비스 디렉터리가 없습니다: {SERVICE_ROOT.relative_to(REPO_ROOT)}")
        return 1

    route_files = sorted(ROUTE_ROOT.rglob("route.ts"))
    service_files = sorted(SERVICE_ROOT.rglob("*.ts"))

    if len(route_files) < MIN_ROUTES:
        print(f"::error::프록시 라우트를 {len(route_files)}건 수집했습니다 (하한 {MIN_ROUTES}) — fail-closed 종료")
        print("::error::경로가 바뀌었거나 라우트가 대량 삭제됐을 수 있습니다. 확인하세요.")
        return 1
    if len(service_files) < MIN_SERVICE_FILES:
        print(
            f"::error::서비스 파일을 {len(service_files)}건 수집했습니다 (하한 {MIN_SERVICE_FILES}) — fail-closed 종료"
        )
        return 1

    consumer_urls: set[str] = set()
    for path in service_files:
        consumer_urls |= resolve_urls(path.read_text(encoding="utf-8"))

    if not consumer_urls:
        print("::error::서비스에서 /api/external 경로를 0건 풀었습니다 — 파서가 형식 변화를 못 따라간 것입니다")
        return 1

    consumer_segments = [segments(url) for url in sorted(consumer_urls)]

    orphans: list[str] = []
    for route_file in route_files:
        route_path = "/" + route_file.parent.relative_to(APP_ROOT).as_posix()
        route_segs = segments(route_path)
        if not any(matches(route_segs, consumer) for consumer in consumer_segments):
            orphans.append(route_path)

    print(
        f"프록시 라우트 {len(route_files)}건 · 서비스 파일 {len(service_files)}건 · "
        f"푼 소비 URL {len(consumer_urls)}건 · 알려진 예외 {len(KNOWN_ORPHANS)}건 검사"
    )

    orphan_set = set(orphans)
    stale = sorted(KNOWN_ORPHANS - orphan_set)
    if stale:
        print(f"::error::KNOWN_ORPHANS 에 적힌 라우트가 더는 고아가 아닙니다 {len(stale)}건 — 예외를 지우세요")
        for path in stale:
            print(f"::error::  {path}")
        return 1

    unexpected = sorted(orphan_set - KNOWN_ORPHANS)
    if unexpected:
        print(f"::error::소비자가 없는 프록시 라우트 {len(unexpected)}건 — 라우트를 지우거나 서비스에서 부르세요")
        for path in unexpected:
            print(f"::error::  {path}")
        return 1

    print(f"소비자 없는 라우트 0건 (알려진 예외 {len(KNOWN_ORPHANS)}건 제외)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
