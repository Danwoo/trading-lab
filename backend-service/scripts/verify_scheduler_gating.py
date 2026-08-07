"""스케줄러 라우트 권한/테넌트 게이팅 회귀 검증 (#71).

배경: devactivity `scheduler_router` 전 라우트가 인증(`verify_access_token`)만 걸고 role/테넌트
게이팅이 없어, 일반 user 가 스케줄러를 만들어 타인 account_id 를 멤버로 등록·발송할 수 있었다.
backend-service `require_role`(서비스 토큰 거부 + workspace_id 필수) 패턴을 이식하고 서비스/리포지토리
workspace_id 스코핑을 추가했다. 이 스크립트는 그 계약을 실제 라우터로 재현한다.

계약 (fail-closed):
  (1) 서비스 토큰(typ=service, workspace_id 없음) → 전 라우트 403 (사용자 데이터 접근 거부)
  (2) workspace_id 없는 사용자 토큰 → 401 (테넌트 미확정 거부)
  (3) role=user → 쓰기·run 라우트 403, 읽기 라우트 200 (require_role vs require_user)
  (4) role=operator/admin → 쓰기 허용
  (5) 테넌트 소유: 타 workspace 소유 스케줄러 조회/수정/삭제/run → 404 (workspace_id WHERE 스코핑)
  (6) 교차테넌트 멤버 주입: 타 workspace 스케줄러에 멤버 등록 → 404 (insert_member 소유 선검사)
  (7) 요청 경로 repo 호출에 인증 컨텍스트의 workspace_id 가 그대로 전달됨 (스파이 확인)
  (9) #115 계좌 소유/존재: 소유 스케줄러라도 요청자 테넌트 미소유·미존재 account_id 멤버 등록 → 404
      (portfolio-mcp on-behalf 조회로 소유 확인, 미존재/타테넌트 무구분 — 존재 오라클 차단).
      portfolio-mcp 장애로 검증 불가 시 → 503 (fail-closed, 무음 통과 금지)

검증 경계: CI 에 MS SQL 이 없어 repo 는 workspace_id 시맨틱을 모사하는 인메모리 스파이로 대체한다.
라우터 role/서비스토큰 게이트(상태코드)와 service→repo 로의 workspace_id 인자 스레딩까지 재현하며,
교차테넌트는 스파이가 workspace_id 불일치 시 None 을 돌려 404 를 증명한다. 실제 SQL `workspace_id =`
등가필터 문자열은 정적으로만 확인(아래 (8)) — DB 통합 검증에서 완전 확인 대상.

pydantic·fastapi import 필요 — `uv run python scripts/verify_scheduler_gating.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "verify-secret")
os.environ.setdefault("APP_ENV", "production")
# core.config Settings 필수 필드 (DB 는 스파이로 대체하므로 값은 더미)
for key in (
    "BACKEND_SQL_DB_DRIVER",
    "BACKEND_SQL_DB_ODBC_DRIVER",
    "BACKEND_SQL_DB_HOST",
    "BACKEND_SQL_DB_NAME",
    "BACKEND_SQL_DB_USER",
    "BACKEND_SQL_DB_PASSWORD",
):
    os.environ.setdefault(key, "x")
os.environ.setdefault("BACKEND_SQL_DB_PORT", "1433")
for key in ("SFTP_HOST", "SFTP_USERNAME", "SFTP_PASSWORD"):
    os.environ.setdefault(key, "x")
os.environ.setdefault("SFTP_PORT", "22")

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))

import clients.mcp.mcp_client as mcp_client_module  # noqa: E402
import jwt as pyjwt  # noqa: E402
import routers.scheduler.scheduler_router as scheduler_router_module  # noqa: E402
from core.config import settings  # noqa: E402
from core.container import Container  # noqa: E402
from core.exception_handler import get_exception_handlers  # noqa: E402
from core.security import create_access_token  # noqa: E402
from dependency_injector import providers  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

WORKSPACE_A = 1
WORKSPACE_B = 2


class FakeManager:
    """APScheduler 매니저 스텁 — 라우터의 sync/unregister 부작용 차단."""

    def sync(self, scheduler_id: str) -> None:
        pass

    def unregister(self, scheduler_id: str) -> None:
        pass


class FakeReport:
    """ActivityReportService 스텁 — run 백그라운드 태스크 무해화."""

    def period(self, period_weeks: int):
        return (0, 0)

    async def generate_for(self, members, since, until):
        return
        yield  # async generator 로 만들기 위한 no-op


class _FakeListAccountsTool:
    """portfolio_list_accounts MCP tool 스텁 — call_mcp_tool 이 기대하는 content block 배열 반환."""

    name = "portfolio_list_accounts"

    def __init__(self, client: FakeMcpClient):
        self._client = client

    async def ainvoke(self, args):
        if self._client.down:
            raise ConnectionError("portfolio-mcp 연결 실패 (모사)")
        items = [{"account_id": aid} for aid in sorted(self._client.owned_ids)]
        return [{"type": "json", "json": {"items": items, "total_count": len(items)}}]


class FakeMcpClient:
    """portfolio-mcp 스텁 — insert_member 의 계좌 소유 검증(portfolio_list_accounts)을 모사한다.

    on-behalf 토큰 workspace_id 로 스코핑된 '요청자 테넌트 소유 계좌' 목록을 돌려준다. down=True 면
    portfolio-mcp 장애를 모사해 예외를 던져 fail-closed 경로(등록 거절)를 재현한다.
    """

    def __init__(self, owned_ids: set[str]):
        self.owned_ids = owned_ids
        self.down = False

    async def get_tools(self):
        return [_FakeListAccountsTool(self)]


class SpyRepo:
    """workspace_id 시맨틱을 모사하는 인메모리 리포지토리 + 인자 스파이."""

    def __init__(self):
        # scheduler_id -> {workspace_id, period_weeks, ...}
        self.schedulers: dict[str, dict] = {}
        # (scheduler_id, account_id) -> {workspace_id, ...}
        self.members: dict[tuple[str, str], dict] = {}
        self.workspace_ids_seen: list[int] = []

    def seed_scheduler(self, scheduler_id: str, workspace_id: int) -> None:
        self.schedulers[scheduler_id] = {
            "scheduler_id": scheduler_id,
            "workspace_id": workspace_id,
            "scheduler_nm": scheduler_id,
            "day_of_week": "mon",
            "hour": 9,
            "minute": 0,
            "period_weeks": 1,
            "use_at": "N",
            "description": None,
        }

    # ── request 경로 (workspace_id 스코핑) ─────────────────────────────────
    def select_scheduler_list(self, args: dict):
        self.workspace_ids_seen.append(args["workspace_id"])
        rows = [s for s in self.schedulers.values() if s["workspace_id"] == args["workspace_id"]]
        return rows, len(rows)

    def select_scheduler(self, args: dict):
        self.workspace_ids_seen.append(args["workspace_id"])
        s = self.schedulers.get(args["scheduler_id"])
        return dict(s) if s and s["workspace_id"] == args["workspace_id"] else None

    def insert_scheduler(self, args: dict):
        self.workspace_ids_seen.append(args["workspace_id"])
        self.schedulers[args["scheduler_id"]] = dict(args)
        return (args["scheduler_id"],)

    def update_scheduler(self, args: dict):
        self.workspace_ids_seen.append(args["workspace_id"])

    def delete_scheduler(self, args: dict):
        self.workspace_ids_seen.append(args["workspace_id"])

    def select_member_list(self, args: dict):
        self.workspace_ids_seen.append(args["workspace_id"])
        rows = [
            m
            for (sid, _), m in self.members.items()
            if sid == args["scheduler_id"] and m["workspace_id"] == args["workspace_id"]
        ]
        return rows, len(rows)

    def select_member(self, args: dict):
        self.workspace_ids_seen.append(args["workspace_id"])
        m = self.members.get((args["scheduler_id"], args["account_id"]))
        return dict(m) if m and m["workspace_id"] == args["workspace_id"] else None

    def insert_member(self, args: dict):
        self.workspace_ids_seen.append(args["workspace_id"])
        self.members[(args["scheduler_id"], args["account_id"])] = dict(args)

    def delete_member(self, args: dict):
        self.workspace_ids_seen.append(args["workspace_id"])
        self.members.pop((args["scheduler_id"], args["account_id"]), None)

    # ── 시스템 경로 (요청 밖 — workspace_id 미주입) ─────────────────────────
    def select_active_schedulers(self):
        return list(self.schedulers.values())

    def select_scheduler_for_job(self, scheduler_id: str):
        # 실제 리포지토리와 같은 키를 돌려준다 — cron 경로가 workspace_id 로 on-behalf 토큰을 스코핑하므로,
        # 스파이가 그 키를 빠뜨리면 검사를 cron 까지 넓히는 순간 KeyError 로 죽는다 (지금은 라우터 경로만 시험).
        s = self.schedulers.get(scheduler_id)
        return (
            {"scheduler_id": scheduler_id, "workspace_id": s["workspace_id"], "period_weeks": s["period_weeks"]}
            if s
            else None
        )

    def select_members_for_job(self, scheduler_id: str):
        return [m for (sid, _), m in self.members.items() if sid == scheduler_id]


def _token(secret: str, *, role: str | None, workspace_id: int | None) -> str:
    payload: dict = {"sub": "u1", "email": "u1@a.com", "exp": int(time.time()) + 60}
    if role is not None:
        payload["role"] = role
    if workspace_id is not None:
        payload["workspace_id"] = workspace_id
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def build_client(repo: SpyRepo, fake_mcp: FakeMcpClient) -> TestClient:
    container = Container()
    container.scheduler_repository.override(providers.Object(repo))
    container.activity_report_service.override(providers.Object(FakeReport()))
    container.mcp_client.override(providers.Object(fake_mcp))
    scheduler_router_module.scheduler_manager = FakeManager()

    app = FastAPI(exception_handlers=get_exception_handlers())
    app.container = container
    app.include_router(scheduler_router_module.router)
    return TestClient(app, raise_server_exceptions=True)


def main() -> int:
    settings.AUTH_DEV_BYPASS = False
    secret = settings.JWT_SECRET

    repo = SpyRepo()
    repo.seed_scheduler("s-a", WORKSPACE_A)  # workspace A 소유
    repo.seed_scheduler("s-b", WORKSPACE_B)  # workspace B 소유
    # portfolio-mcp 스텁 — workspace A 요청자에게 보이는 소유 계좌는 acct-owned 하나 (#115 계좌 검증용)
    fake_mcp = FakeMcpClient(owned_ids={"acct-owned"})
    client = build_client(repo, fake_mcp)

    service_tok = create_access_token()  # typ=service, workspace_id 없음
    user_a = _token(secret, role="user", workspace_id=WORKSPACE_A)
    op_a = _token(secret, role="operator", workspace_id=WORKSPACE_A)
    op_no_workspace = _token(secret, role="operator", workspace_id=None)

    problems: list[str] = []

    def check(name: str, cond: bool) -> None:
        if not cond:
            problems.append(name)

    create_body = {"scheduler_id": "s-new", "scheduler_nm": "n"}
    member_body = {"account_id": "acct-victim", "email": "u1@a.com"}

    # (1) 서비스 토큰 → 전 라우트 403
    check("서비스토큰 GET 리스트 → 403", client.get("/scheduler", headers=_hdr(service_tok)).status_code == 403)
    check(
        "서비스토큰 POST 생성 → 403",
        client.post("/scheduler", headers=_hdr(service_tok), json=create_body).status_code == 403,
    )
    check(
        "서비스토큰 POST run → 403",
        client.post("/scheduler/s-a/run", headers=_hdr(service_tok)).status_code == 403,
    )
    check(
        "서비스토큰 POST member → 403",
        client.post("/scheduler/s-a/member", headers=_hdr(service_tok), json=member_body).status_code == 403,
    )

    # (2) workspace_id 없는 사용자 토큰 → 401
    check("workspace 없는 토큰 GET → 401", client.get("/scheduler", headers=_hdr(op_no_workspace)).status_code == 401)
    check(
        "workspace 없는 토큰 POST → 401",
        client.post("/scheduler", headers=_hdr(op_no_workspace), json=create_body).status_code == 401,
    )

    # (3) role=user → 쓰기·run 403, 읽기 200
    check("user 읽기 리스트 → 200", client.get("/scheduler", headers=_hdr(user_a)).status_code == 200)
    check("user 읽기 상세(소유) → 200", client.get("/scheduler/s-a", headers=_hdr(user_a)).status_code == 200)
    check("user 쓰기 생성 → 403", client.post("/scheduler", headers=_hdr(user_a), json=create_body).status_code == 403)
    check(
        "user 멤버 등록 → 403",
        client.post("/scheduler/s-a/member", headers=_hdr(user_a), json=member_body).status_code == 403,
    )
    check("user run → 403", client.post("/scheduler/s-a/run", headers=_hdr(user_a)).status_code == 403)

    # (4) operator → 쓰기 허용 (소유 스케줄러)
    check(
        "operator 생성 → 200",
        client.post("/scheduler", headers=_hdr(op_a), json=create_body).status_code == 200,
    )
    check("operator run(소유) → 200", client.post("/scheduler/s-a/run", headers=_hdr(op_a)).status_code == 200)

    # (5) 테넌트 소유 — workspace A operator 가 workspace B 소유 s-b 접근 → 404
    check("operator 타테넌트 상세 → 404", client.get("/scheduler/s-b", headers=_hdr(op_a)).status_code == 404)
    check(
        "operator 타테넌트 수정 → 404",
        client.put("/scheduler/s-b", headers=_hdr(op_a), json={"scheduler_nm": "x"}).status_code == 404,
    )
    check("operator 타테넌트 삭제 → 404", client.delete("/scheduler/s-b", headers=_hdr(op_a)).status_code == 404)
    check("operator 타테넌트 run → 404", client.post("/scheduler/s-b/run", headers=_hdr(op_a)).status_code == 404)
    check("user 타테넌트 상세 → 404", client.get("/scheduler/s-b", headers=_hdr(user_a)).status_code == 404)

    # (6) 교차테넌트 멤버 주입 — workspace A operator 가 workspace B 스케줄러에 멤버 등록 → 404
    r_inject = client.post("/scheduler/s-b/member", headers=_hdr(op_a), json=member_body)
    check("교차테넌트 멤버 주입 → 404", r_inject.status_code == 404)
    check("교차테넌트 멤버 미기록", ("s-b", "acct-victim") not in repo.members)

    # (7) 요청 경로 repo 호출은 항상 인증 컨텍스트 workspace_id 로만 스코핑 (다른 테넌트 값 누출 없음)
    check("repo 는 인증 workspace_id 만 관측", set(repo.workspace_ids_seen) <= {WORKSPACE_A})

    # (8) 실제 SQL 에 workspace_id 등가필터 존재 (정적 — DB 없이 확인 가능한 최소 보증)
    repo_src = (APP_DIR / "repositories" / "scheduler" / "scheduler_repository.py").read_text()
    for needle in (
        "WHERE workspace_id = :workspace_id",
        "AND workspace_id   = :workspace_id",
        "AND workspace_id = :workspace_id",
    ):
        check(f"repo SQL 에 '{needle}' 존재", needle in repo_src)
    # 인증 파일에 실제로 게이트가 붙었는지 (require_role/require_user)
    router_src = (APP_DIR / "routers" / "scheduler" / "scheduler_router.py").read_text()
    check("라우터에 require_role 게이트", len(re.findall(r"require_role\(", router_src)) >= 5)
    check("라우터에 require_user 게이트", "require_user" in router_src)

    # (9) #115 계좌 소유·존재 검증 — 소유 스케줄러(s-a)에 대해서만 검증한다 (교차테넌트는 (6)에서 이미 404)
    mcp_client_module._cached_tools = None  # tool 목록 모듈 전역 캐시 초기화 (스텁 tool 이 잡히도록)
    # (9a) 요청자 테넌트 소유 계좌 → 200, 실제 기록됨
    r_own = client.post(
        "/scheduler/s-a/member", headers=_hdr(op_a), json={"account_id": "acct-owned", "email": "u1@a.com"}
    )
    check("#115 소유 계좌 등록 → 200", r_own.status_code == 200)
    check("#115 소유 계좌 기록됨", ("s-a", "acct-owned") in repo.members)
    # (9b) 미소유·미존재 계좌 → 404, 미기록 (미존재/타테넌트 무구분 거절 — 존재 오라클 차단)
    r_bad = client.post(
        "/scheduler/s-a/member", headers=_hdr(op_a), json={"account_id": "acct-nonexistent", "email": "u1@a.com"}
    )
    check("#115 미소유·미존재 계좌 등록 → 404", r_bad.status_code == 404)
    check("#115 미소유·미존재 계좌 미기록", ("s-a", "acct-nonexistent") not in repo.members)
    # (9c) fail-closed — portfolio-mcp 장애로 검증 불가 시 등록 거절(503), 미기록 (미검증 계좌 무음 통과 금지)
    fake_mcp.down = True
    r_down = client.post(
        "/scheduler/s-a/member", headers=_hdr(op_a), json={"account_id": "acct-owned-2", "email": "u1@a.com"}
    )
    check("#115 portfolio-mcp 장애 → 503 (fail-closed)", r_down.status_code == 503)
    check("#115 장애 시 미기록", ("s-a", "acct-owned-2") not in repo.members)
    fake_mcp.down = False

    if problems:
        print("스케줄러 게이팅 검증 실패:")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print("스케줄러 게이팅 검증 통과 — 서비스토큰 거부·role 게이트·workspace_id 테넌트 스코핑 확인")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
