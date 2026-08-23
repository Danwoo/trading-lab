#!/usr/bin/env python3
"""역할 게이트가 걸린 쓰기를 화면이 **누르기 전에** 설명하는지 대조한다 — fail-closed (#341).

## 왜 있나

`require_role(ROLE_ADMIN, ROLE_OPERATOR)` 는 backend 에만 있고, 그 사실을 화면은 모른다.
그래서 게스트 계정에서 「저장」·「적재 실행」·「등록」이 **활성인 채로 서 있다가 누르는
순간에만** 403 이 왔다. 이 스크립트는 그 어긋남을 기계가 잡게 한다.

## 네 축을 본다

1. **역할 대조** — backend `core/authorization.py` 의 `WRITE_ROLES` 가 푸는 역할 값과
   frontend `constants/writeAccess.ts` 의 `WRITE_AUTHOR_IDS` 가 같은 집합인가.
2. **가입 배정** — `constants/protected.ts` 의 `SIGNUP_AUTHOR_ID` 가 그 쓰기 역할 중 하나인가.
   (리드 결정 2026-08-23 — 가입자는 자기 워크스페이스의 운영자다. 게스트로 되돌리면 여기서 갈린다.)
3. **경계 대조** — 게이트가 걸린 라우터의 prefix 집합 == `ROLE_GATED_WRITE_PREFIXES`.
4. **설명 대조** — 그 prefix 로 쓰기를 내는 서비스 함수를 import 하는 화면 파일이, 권한 판정
   (`useWriteAccess`) 이나 그것을 대신 지는 공용 패널 플래그(`writeGated`) 를 실제로 참조하는가.

## fail-closed

라우터 파일·서비스 파일·화면 파일·게이트 엔드포인트가 **0건이면 실패**한다. 경로가 옮겨져도
"대상 없음 = 위반 없음" 으로 조용히 초록이 되지 않게, 축마다 검사한 건수를 출력에 남긴다.

`EXEMPT` 는 **위임**만 담는다 — 쓰기 함수를 부르지만 조작부를 세우지 않아 설명할 자리가 없는
파일이다. 위임처가 실제로 게이트를 지는지는 사람이 판단하고 여기 사유로 남긴다. 면제가 낡는
것도 실패다: 목록에 있는데 더는 쓰기 함수를 import 하지 않으면 빨간불이 된다.

실행: `python3 scripts/verify_write_gate_coverage.py`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND_ROUTERS = REPO / "backend-service" / "app" / "routers"
AUTHORIZATION_PY = REPO / "backend-service" / "app" / "core" / "authorization.py"
FRONTEND = REPO / "frontend"
WRITE_ACCESS_TS = FRONTEND / "constants" / "writeAccess.ts"
PROTECTED_TS = FRONTEND / "constants" / "protected.ts"
SERVICES = FRONTEND / "services"
SCREEN_DIRS = [FRONTEND / "components", FRONTEND / "hooks", FRONTEND / "app"]

# 화면이 「막혔다」를 스스로 말하거나(훅), 그것을 지는 공용 패널에 위임하는 표식.
GATE_MARKERS = ("useWriteAccess", "writeGated")

# 쓰기 함수를 부르지만 조작부가 없어 설명할 자리가 없는 파일 → 게이트는 호출자가 진다.
EXEMPT: dict[str, str] = {
    "components/features/Bot/deleteBotWithConfirm.tsx": (
        "확인창만 띄우는 헬퍼다. 조작부(BotList 의 행 「삭제」·BotWorkbench 의 「삭제」)가 게이트를 진다."
    ),
    "hooks/bench/useBacktestBoard.ts": (
        "격자 실행의 상태 보관소다. 조작부(Bench/GridRunForm 의 「격자 실행」)가 게이트를 진다."
    ),
    "components/features/Scheduler/SchedulerDetailForm.tsx": (
        "등록·수정 폼이라 DetailPanel(writeGated)이 권한 없는 계정에는 아예 세우지 않는다 — 구성원 추가·제거도 그 안에 있다."
    ),
}

METHOD_RE = re.compile(r'method:\s*"(POST|PUT|PATCH|DELETE)"')


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def ts_string_consts(path: Path) -> dict[str, str]:
    """`export const NAME = "value";` 을 이름 → 값으로. 별칭(`A = B`)은 한 번 더 푼다."""
    text = path.read_text(encoding="utf-8")
    values = dict(re.findall(r'export const (\w+)\s*=\s*"([^"]+)"', text))
    for name, alias in re.findall(r"export const (\w+)(?::\s*[\w<>\[\]| ]+)?\s*=\s*(\w+);", text):
        if alias in values:
            values[name] = values[alias]
    return values


def backend_write_roles() -> set[str]:
    text = AUTHORIZATION_PY.read_text(encoding="utf-8")
    consts = dict(re.findall(r'^(ROLE_\w+)\s*=\s*"([^"]+)"', text, re.M))
    match = re.search(r"^WRITE_ROLES\s*=\s*\(([^)]*)\)", text, re.M)
    if match is None:
        fail(f"{AUTHORIZATION_PY.relative_to(REPO)} 에서 WRITE_ROLES 를 못 읽었다")
    names = [n.strip() for n in match.group(1).split(",") if n.strip()]
    unknown = [n for n in names if n not in consts]
    if unknown:
        fail(f"WRITE_ROLES 가 값을 모르는 이름을 담고 있다: {unknown}")
    roles = {consts[n] for n in names}
    if not roles:
        fail("backend WRITE_ROLES 가 비었다 — 쓰기를 여는 역할이 0건이다")
    return roles


def frontend_write_roles() -> set[str]:
    consts = ts_string_consts(PROTECTED_TS)
    text = WRITE_ACCESS_TS.read_text(encoding="utf-8")
    match = re.search(r"WRITE_AUTHOR_IDS[^=]*=\s*\[([^\]]*)\]", text)
    if match is None:
        fail(f"{WRITE_ACCESS_TS.relative_to(REPO)} 에서 WRITE_AUTHOR_IDS 를 못 읽었다")
    names = [n.strip() for n in match.group(1).split(",") if n.strip()]
    unknown = [n for n in names if n not in consts]
    if unknown:
        fail(f"WRITE_AUTHOR_IDS 가 값을 모르는 이름을 담고 있다: {unknown}")
    roles = {consts[n] for n in names}
    if not roles:
        fail("frontend WRITE_AUTHOR_IDS 가 비었다 — 화면이 「아무도 못 쓴다」고 믿는다")
    return roles


def signup_role() -> str:
    consts = ts_string_consts(PROTECTED_TS)
    if "SIGNUP_AUTHOR_ID" not in consts:
        fail(f"{PROTECTED_TS.relative_to(REPO)} 에 SIGNUP_AUTHOR_ID 가 없다 — 가입이 주는 역할을 못 읽는다")
    return consts["SIGNUP_AUTHOR_ID"]


def backend_gated_prefixes() -> tuple[set[str], int]:
    """require_role 이 걸린 라우터의 prefix 와 그 엔드포인트 수."""
    prefixes: set[str] = set()
    endpoints = 0
    router_files = sorted(BACKEND_ROUTERS.glob("*/*_router.py"))
    if not router_files:
        fail(f"라우터 파일이 0건이다 — 경로가 옮겨졌다: {BACKEND_ROUTERS}")
    for path in router_files:
        text = path.read_text(encoding="utf-8")
        hits = text.count("require_role(")
        if hits == 0:
            continue
        match = re.search(r'APIRouter\(\s*\n?\s*prefix="([^"]+)"', text)
        if match is None:
            fail(f"{path.relative_to(REPO)} 에 require_role 이 있는데 prefix 를 못 읽었다")
        prefixes.add(match.group(1))
        endpoints += hits
    print(f"  backend: 라우터 {len(router_files)}개를 읽어 게이트 엔드포인트 {endpoints}개 · prefix {len(prefixes)}개")
    if endpoints == 0:
        fail("require_role 이 걸린 엔드포인트가 0건이다 — 게이트가 통째로 사라졌거나 이름이 바뀌었다")
    return prefixes, endpoints


def declared_prefixes() -> set[str]:
    text = WRITE_ACCESS_TS.read_text(encoding="utf-8")
    match = re.search(r"ROLE_GATED_WRITE_PREFIXES[^=]*=\s*\[(.*?)\]", text, re.S)
    if match is None:
        fail(f"{WRITE_ACCESS_TS.relative_to(REPO)} 에서 ROLE_GATED_WRITE_PREFIXES 를 못 읽었다")
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def gated_write_functions(prefixes: set[str]) -> dict[str, set[str]]:
    """게이트 걸린 prefix 로 쓰기를 내는 서비스 모듈 → 함수 이름 집합."""
    result: dict[str, set[str]] = {}
    service_files = sorted(SERVICES.glob("*/*.ts"))
    if not service_files:
        fail(f"서비스 파일이 0건이다 — 경로가 옮겨졌다: {SERVICES}")
    for path in service_files:
        text = path.read_text(encoding="utf-8")
        urls = re.findall(r'^const \w*URL\w* = "([^"]+)"', text, re.M)
        # `/api/external/{service}/{prefix}` 에서 prefix 를 떼어 백엔드 라우터와 맞춘다.
        module_prefixes = {
            "/" + url.split("/")[4] for url in urls if url.startswith("/api/external/") and len(url.split("/")) > 4
        }
        if not (module_prefixes & prefixes):
            continue
        writers: set[str] = set()
        for block in re.split(r"\n(?=export )", text):
            name = re.match(r"export (?:const|async function|function) (\w+)", block)
            if name and METHOD_RE.search(block):
                writers.add(name.group(1))
        if writers:
            result[str(path.relative_to(FRONTEND))] = writers
    if not result:
        fail("게이트 걸린 prefix 로 쓰기를 내는 서비스 모듈이 0건이다 — 서비스 배치가 바뀌었다")
    total = sum(len(v) for v in result.values())
    print(f"  frontend: 서비스 {len(service_files)}개 중 게이트 모듈 {len(result)}개 · 쓰기 함수 {total}개")
    return result


def screens_calling(writers: dict[str, set[str]]) -> dict[str, set[str]]:
    """쓰기 함수를 import 하는 화면 파일 → 부르는 함수 이름."""
    by_module = {"@/" + module[: -len(".ts")]: names for module, names in writers.items()}
    found: dict[str, set[str]] = {}
    for root in SCREEN_DIRS:
        if not root.is_dir():
            fail(f"화면 경로가 없다 — 옮겨졌다: {root}")
        for path in sorted(root.rglob("*.ts*")):
            text = path.read_text(encoding="utf-8")
            hit: set[str] = set()
            for spec, names in by_module.items():
                for match in re.finditer(r"import\s*\{([^}]*)\}\s*from\s*\"" + re.escape(spec) + r"\"", text, re.S):
                    hit |= {n.strip() for n in match.group(1).split(",")} & names
            if hit:
                found[str(path.relative_to(FRONTEND))] = hit
    if not found:
        fail("쓰기 함수를 부르는 화면 파일이 0건이다 — import 경로 관례가 바뀌었다")
    return found


def main() -> int:
    print("역할 게이트 쓰기 — 역할·가입·경계·설명 대조 (#341)")

    backend_roles = backend_write_roles()
    front_roles = frontend_write_roles()
    if backend_roles != front_roles:
        fail(
            "쓰기를 여는 역할이 backend 와 frontend 에서 다르다\n"
            f"  backend WRITE_ROLES:        {sorted(backend_roles)}\n"
            f"  frontend WRITE_AUTHOR_IDS:  {sorted(front_roles)}"
        )
    print(f"  역할 대조 통과 — 쓰기 역할 {sorted(backend_roles)}")

    granted = signup_role()
    if granted not in backend_roles:
        fail(
            f"가입이 배정하는 역할({granted!r})로는 쓰기가 안 열린다 — 새 계정은 저장·실행이 전부 403 이다.\n"
            f"  쓰기 역할: {sorted(backend_roles)} (리드 결정 2026-08-23: 가입자는 자기 워크스페이스의 운영자다)"
        )
    print(f"  가입 배정 통과 — SIGNUP_AUTHOR_ID={granted!r} 가 쓰기 역할에 든다")

    backend, endpoints = backend_gated_prefixes()
    declared = declared_prefixes()
    if backend != declared:
        fail(
            "backend 의 게이트 prefix 와 constants/writeAccess.ts 가 어긋난다\n"
            f"  backend 에만: {sorted(backend - declared)}\n"
            f"  프론트에만:   {sorted(declared - backend)}"
        )
    print(f"  경계 대조 통과 — prefix {len(declared)}개 · 엔드포인트 {endpoints}개")

    writers = gated_write_functions(backend)
    screens = screens_calling(writers)

    ungated: list[str] = []
    for rel, names in sorted(screens.items()):
        if rel in EXEMPT:
            continue
        text = (FRONTEND / rel).read_text(encoding="utf-8")
        if not any(marker in text for marker in GATE_MARKERS):
            ungated.append(f"{rel} — {', '.join(sorted(names))}")

    stale = sorted(set(EXEMPT) - set(screens))
    print(f"  화면 대조 — 쓰기를 부르는 파일 {len(screens)}개 (면제 {len(EXEMPT)}개)")

    if stale:
        fail("면제 목록이 낡았다 — 더는 쓰기 함수를 부르지 않는다:\n  " + "\n  ".join(stale))
    if ungated:
        fail("누르기 전에 막힘을 말하지 않는 화면이 있다 (useWriteAccess·writeGated 없음):\n  " + "\n  ".join(ungated))

    print(f"OK — 게이트 엔드포인트 {endpoints}개 · 화면 {len(screens)}개 전부 사유를 미리 말한다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
