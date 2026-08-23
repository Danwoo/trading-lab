"""#344 — **`.env` 를 고쳐 쓰는 자리는 시스템관리자만 통과한다** (DB·네트워크 없음).

`.env` 한 줄은 워크스페이스에 속하지 않는다. 프로세스 전체가 그것을 읽고, 효과는 이 설치를
쓰는 모두에게 가며, 되돌릴 사본도 남지 않는다. 그런데 그 자리가 `require_user`(로그인만 하면
통과)로 열려 있었고, 같은 계정이 자기 워크스페이스의 관심종목 한 줄 추가는 403 을 받았다.

이 그물이 잠그는 것:

  ① **`.env` 쓰기를 여는 서비스를 코드에서 찾는다** — 손으로 적은 목록이 아니다.
     레포의 모든 서비스(`*/app/services/**`)에서 `set_env_value` 를 부르는 모듈을 훑어
     0건이면 실패한다. backend-service 밖에서 나오면 **모르는 채로 통과시키지 않고** 실패한다
     — 그 서비스의 라우터 관문은 이 그물이 아직 못 보기 때문이다.
  ② 그 서비스를 노출하는 라우터의 **쓰기 라우트(POST/PUT/PATCH/DELETE)** 를 전부 센다 — 0건이면 실패.
  ③ 각 쓰기 라우트의 관문을 **실제로 실행해** 판정한다. 데코레이터 문자열을 grep 하지 않는다:
     `user`·`operator`·서비스 토큰·워크스페이스 없음은 막히고, `admin` 만 통과한다.
  ④ 읽기 라우트는 `user` 가 그대로 통과한다 — 과하게 조여 화면을 죽이지 않았음을 같이 잡는다.

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_env_write_role_gate.py
"""

from __future__ import annotations

import asyncio
import importlib
import os
import re
import sys
from pathlib import Path

# 설정을 세우고 나서 import 한다 — `test_data_key_write_boundary.py` 와 같은 관용구다.
os.environ["APP_ENV"] = "env-write-role-gate-test"
for _name, _value in {
    "BACKEND_SQL_DB_DRIVER": "postgresql+psycopg",
    "BACKEND_SQL_DB_HOST": "localhost",
    "BACKEND_SQL_DB_PORT": "5432",
    "BACKEND_SQL_DB_NAME": "test",
    "BACKEND_SQL_DB_USER": "test",
    "BACKEND_SQL_DB_PASSWORD": "test",
    "SFTP_HOST": "localhost",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "test",
    "SFTP_PASSWORD": "test",
    "JWT_SECRET": "test-secret",
}.items():
    os.environ.setdefault(_name, _value)

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _SERVICE_DIR.parent
_APP_DIR = _SERVICE_DIR / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.auth_context import set_auth_context  # noqa: E402
from core.authorization import ROLE_ADMIN, ROLE_OPERATOR, ROLE_USER  # noqa: E402
from core.exceptions import ForbiddenError, UnauthorizedError  # noqa: E402

#: `.env` 한 줄을 갈아 끼우는 유일한 함수. 이 이름을 import 하는 서비스가 곧 「쓰기를 여는 서비스」다.
ENV_WRITER = "set_env_value"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

#: 관문을 실행할 신원들. (이름, set_auth_context 인자, 기대 결과)
#: `admin` 만 통과해야 한다 — 나머지는 전부 막힌다.
IDENTITIES = [
    ("역할 user", dict(user_id="u1", role=ROLE_USER, workspace_id=1, email="u@x"), ForbiddenError),
    ("역할 operator", dict(user_id="u2", role=ROLE_OPERATOR, workspace_id=1, email="o@x"), ForbiddenError),
    ("역할 없음", dict(user_id="u3", role=None, workspace_id=1, email="n@x"), ForbiddenError),
    ("모르는 역할", dict(user_id="u4", role="superuser", workspace_id=1, email="s@x"), ForbiddenError),
    ("서비스 토큰", dict(user_id="svc", role=None, workspace_id=None, is_service=True), ForbiddenError),
    ("워크스페이스 없음", dict(user_id="u5", role=ROLE_ADMIN, workspace_id=None, email="a@x"), UnauthorizedError),
    ("역할 admin", dict(user_id="u6", role=ROLE_ADMIN, workspace_id=1, email="a@x"), None),
]

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def env_writing_services() -> list[Path]:
    """`.env` 쓰기를 여는 서비스 모듈 — **레포 전체에서 코드로 찾는다**, 목록을 적지 않는다.

    이 레포의 backend 는 여러 개일 수 있다(`app/main.py` 가 있는 모든 폴더). 그래서 한 서비스만
    훑으면 다른 서비스가 `.env` 를 쓰기 시작해도 이 그물이 초록인 채로 못 본다.
    """
    pattern = re.compile(rf"\b{ENV_WRITER}\b")
    return sorted(
        path
        for path in _REPO_ROOT.glob("*/app/services/**/*_service.py")
        if pattern.search(path.read_text(encoding="utf-8"))
    )


def router_module_for(service_path: Path) -> tuple[str, Path]:
    """서비스를 노출하는 라우터. 규약이 깨지면 **모르는 채로 통과시키지 않고 실패한다.**"""
    rel = service_path.relative_to(_APP_DIR).as_posix()  # backend-service 안이라는 것은 호출부가 이미 확인했다
    router_rel = rel.replace("services/", "routers/", 1).replace("_service.py", "_router.py")
    return router_rel[: -len(".py")].replace("/", "."), _APP_DIR / router_rel


def run_gate(gate, identity: dict) -> type[Exception] | None:
    """관문 하나를 그 신원으로 **실행**한다. 막으면 예외 타입, 통과하면 None."""
    set_auth_context(**{"user_id": None, "role": None, "workspace_id": None, **identity})
    try:
        asyncio.run(gate())
    except Exception as exc:  # noqa: BLE001 — 어떤 방식으로 막는지도 판정 대상이다
        return type(exc)
    return None


def verdict(gates, identity: dict) -> type[Exception] | None:
    """라우트의 관문 전체를 순서대로 실행한 결과 — 처음 막은 예외, 아무도 안 막으면 None."""
    for gate in gates:
        blocked = run_gate(gate, identity)
        if blocked is not None:
            return blocked
    return None


def gates_of(route) -> list:
    """이 라우트에 걸린 권한 관문 의존성. 문자열이 아니라 **실행 가능한 객체**를 꺼낸다."""
    return [d.call for d in route.dependant.dependencies if getattr(d.call, "__module__", "") == "core.authorization"]


def main() -> int:
    writers = env_writing_services()
    print(
        f"`.env` 쓰기를 여는 서비스 {len(writers)}개: "
        f"{[p.relative_to(_REPO_ROOT).as_posix() for p in writers] or '없음'}"
    )
    if not writers:
        print(
            f"::error::레포의 어느 */app/services/ 에서도 {ENV_WRITER} 를 부르는 모듈을 못 찾았다 — "
            "그물이 아무것도 안 보고 있다 (함수 이름이 바뀌었는가?)",
            file=sys.stderr,
        )
        return 1

    outside = [p for p in writers if not p.is_relative_to(_APP_DIR)]
    if outside:
        for path in outside:
            print(
                f"::error::{path.relative_to(_REPO_ROOT).as_posix()} 가 {ENV_WRITER} 를 부른다 — "
                "이 그물은 backend-service 의 라우터 관문만 실행해 본다. "
                "그 서비스의 관문도 여기서 검사하도록 이 파일을 넓혀라",
                file=sys.stderr,
            )
        return 1

    write_routes = 0
    read_routes = 0

    for service_path in writers:
        module_name, router_path = router_module_for(service_path)
        if not router_path.exists():
            print(
                f"::error::{service_path.relative_to(_APP_DIR)} 가 {ENV_WRITER} 를 부르는데 "
                f"짝이 되는 라우터({router_path.relative_to(_APP_DIR)})가 없다 — "
                "어느 라우트가 이 쓰기를 여는지 이 그물이 모른다. 여기에 가르쳐라",
                file=sys.stderr,
            )
            return 1

        router = importlib.import_module(module_name).router
        for route in router.routes:
            gates = gates_of(route)
            for method in sorted(route.methods):
                if method == "HEAD":
                    continue
                label = f"{method} {route.path}"
                if method in WRITE_METHODS:
                    write_routes += 1
                    for who, identity, expected in IDENTITIES:
                        check(f"{label} · {who}", verdict(gates, identity), expected)
                else:
                    read_routes += 1
                    # 읽기까지 조이면 화면이 죽는다 — 조인 것이 쓰기뿐임을 같이 잡는다.
                    check(
                        f"{label} · 역할 user 는 읽는다",
                        verdict(gates, dict(user_id="u1", role=ROLE_USER, workspace_id=1, email="u@x")),
                        None,
                    )

    print(f"검사한 라우트: 쓰기 {write_routes}개 · 읽기 {read_routes}개 · 단언 {CHECKED}건")
    if write_routes == 0:
        print("::error::쓰기 라우트가 0건이다 — 검사 대상이 없는데 초록이 될 뻔했다", file=sys.stderr)
        return 1
    if CHECKED < write_routes * len(IDENTITIES):
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1

    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: `.env` 를 여는 쓰기 라우트는 admin 만 통과하고, 읽기는 user 에게 열려 있다 (#344)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
