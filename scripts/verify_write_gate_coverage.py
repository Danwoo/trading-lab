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
   라우터 파일은 `routers/` 아래를 **깊이·이름 무관**하게 훑고(한 단계 글롭은 `sub/` 에 심은
   라우터를 못 봤다 — #330 이 잡은 `**` 함정과 같은 부류), 한 파일에 `APIRouter` 가 여럿이면
   `require_role` 이 걸린 엔드포인트를 **그 데코레이터의 라우터 변수**로 귀속시킨다(첫 prefix 만
   읽으면 두 번째 게이트 prefix 가 조용히 초록이고, 게이트 없는 첫 라우터를 지목해 오진한다).
4. **설명 대조** — 그 prefix 로 쓰기를 내는 서비스 함수를 import 하는 화면 파일이, 권한 판정
   (`useWriteAccess`) 이나 그것을 대신 지는 공용 패널 플래그(`writeGated`) 를 실제로 참조하는가.

## fail-closed

라우터 파일·서비스 파일·화면 파일·게이트 엔드포인트가 **0건이면 실패**한다. 경로가 옮겨져도
"대상 없음 = 위반 없음" 으로 조용히 초록이 되지 않게, 축마다 검사한 건수를 출력에 남긴다.

`EXEMPT` 는 **위임**만 담는다 — 쓰기 함수를 부르지만 조작부를 세우지 않아 설명할 자리가 없는
파일이다. 위임처를 **경로로** 적어 그 파일이 게이트 표식을 지는지 함께 확인한다(말로만 적으면
위임처에서 게이트가 빠져도 초록이다 — 실측으로 확인한 구멍이다). 면제가 낡는 것도 실패다:
목록에 있는데 더는 쓰기 함수를 import 하지 않으면 빨간불이 된다.

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

# 쓰기 함수를 부르지만 조작부가 없어 설명할 자리가 없는 파일 → 게이트는 **위임처**가 진다.
#
# 위임처를 말로만 적으면 그 자리에서 게이트가 빠져도 이 검사가 초록이다 — 실측으로 확인했다:
# `Bench/GridRunForm.tsx` 의 `useWriteAccess` 를 지워도 통과했다. 그래서 위임처를 **경로로**
# 적고, 그 파일이 실제로 게이트 표식을 지고 있는지 여기서 같이 확인한다.
EXEMPT: dict[str, tuple[str, tuple[str, ...]]] = {
    "components/features/Bot/deleteBotWithConfirm.tsx": (
        "확인창만 띄우는 헬퍼다 — 조작부는 봇 목록의 행 「삭제」와 작업대의 「삭제」다.",
        ("components/features/Bot/BotList.tsx", "components/features/Bot/BotWorkbench.tsx"),
    ),
    "hooks/bench/useBacktestBoard.ts": (
        "격자 실행의 상태 보관소다 — 조작부는 격자 실행 폼의 「격자 실행」이다.",
        ("components/features/Bench/GridRunForm.tsx",),
    ),
    "components/features/Scheduler/SchedulerDetailForm.tsx": (
        "등록·수정 폼이라 막힌 계정에는 아예 서지 않는다 — 구성원 추가·제거도 그 안에 있다.",
        ("components/features/Scheduler/SchedulerContainer.tsx",),
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


def _call_end(text: str, open_paren: int) -> int:
    """`text[open_paren] == "("` 인 호출의 닫는 괄호 다음 인덱스. 문자열 안의 괄호는 세지 않는다."""
    depth = 0
    quote: str | None = None
    i = open_paren
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


ROUTER_DECL_RE = re.compile(r"^(\w+)\s*=\s*APIRouter\(", re.M)
ROUTE_DECORATOR_RE = re.compile(r"^@(\w+)\.(?:get|post|put|patch|delete|api_route|websocket)\(", re.M)


def routers_in(text: str) -> dict[str, tuple[str | None, bool]]:
    """라우터 변수 → (prefix, 라우터 자체에 require_role 이 걸렸는가)."""
    routers: dict[str, tuple[str | None, bool]] = {}
    for match in ROUTER_DECL_RE.finditer(text):
        call = text[match.end() - 1 : _call_end(text, match.end() - 1)]
        prefix = re.search(r'prefix\s*=\s*"([^"]+)"', call)
        routers[match.group(1)] = (prefix.group(1) if prefix else None, "require_role(" in call)
    return routers


def gated_routes_in(text: str) -> dict[str, int]:
    """라우터 변수 → require_role 이 걸린 엔드포인트 수. 라우터 자체가 게이트면 그 라우터의 전 엔드포인트."""
    routers = routers_in(text)
    counts: dict[str, int] = {}
    for match in ROUTE_DECORATOR_RE.finditer(text):
        var = match.group(1)
        call = text[match.end() - 1 : _call_end(text, match.end() - 1)]
        router_gated = routers.get(var, (None, False))[1]
        if router_gated or "require_role(" in call:
            counts[var] = counts.get(var, 0) + 1
    return counts


def backend_gated_prefixes() -> tuple[set[str], int]:
    """require_role 이 걸린 라우터의 prefix 와 그 엔드포인트 수."""
    prefixes: set[str] = set()
    endpoints = 0
    router_files = sorted(p for p in BACKEND_ROUTERS.rglob("*.py") if "APIRouter(" in p.read_text(encoding="utf-8"))
    if not router_files:
        fail(f"라우터 파일이 0건이다 — 경로가 옮겨졌다: {BACKEND_ROUTERS}")
    for path in router_files:
        text = path.read_text(encoding="utf-8")
        if "require_role(" not in text:
            continue
        routers = routers_in(text)
        gated = gated_routes_in(text)
        if not gated:
            fail(f"{path.relative_to(REPO)} 에 require_role 이 있는데 어느 엔드포인트에도 귀속되지 않는다")
        for var, count in gated.items():
            prefix = routers.get(var, (None, False))[0]
            if prefix is None:
                fail(f"{path.relative_to(REPO)} 의 게이트 엔드포인트가 쓰는 라우터 `{var}` 의 prefix 를 못 읽었다")
            prefixes.add(prefix)
            endpoints += count
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

    # 면제의 근거는 「위임처가 게이트를 진다」이므로, 그 위임처를 실제로 열어 확인한다.
    delegates = sorted({d for _, targets in EXEMPT.values() for d in targets})
    if not delegates:
        fail("면제의 위임처가 0건이다 — 면제가 근거 없이 통과한다")
    missing: list[str] = []
    for rel in delegates:
        path = FRONTEND / rel
        if not path.is_file():
            missing.append(f"{rel} — 파일이 없다(옮겨졌다)")
            continue
        if not any(marker in path.read_text(encoding="utf-8") for marker in GATE_MARKERS):
            missing.append(f"{rel} — 게이트 표식이 없다")

    print(f"  화면 대조 — 쓰기를 부르는 파일 {len(screens)}개 (면제 {len(EXEMPT)}개 · 위임처 {len(delegates)}개)")

    if stale:
        fail("면제 목록이 낡았다 — 더는 쓰기 함수를 부르지 않는다:\n  " + "\n  ".join(stale))
    if missing:
        fail("면제의 위임처가 게이트를 지지 않는다 — 면제가 근거를 잃었다:\n  " + "\n  ".join(missing))
    if ungated:
        fail("누르기 전에 막힘을 말하지 않는 화면이 있다 (useWriteAccess·writeGated 없음):\n  " + "\n  ".join(ungated))

    print(
        f"OK — 게이트 엔드포인트 {endpoints}개 · 화면 {len(screens)}개 · 위임처 {len(delegates)}개 전부 사유를 미리 말한다"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
