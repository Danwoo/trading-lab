"""인증 강화 회귀 검증 — core/security.py 가 backend-service 강화판(62194b9)과 동일 계약인지.

계약 (fail-closed):
  (1) 무효/무토큰 → 401 (AUTH_DEV_BYPASS=false 기본값에서 dev 우회 없음)
  (2) 토큰은 Authorization 헤더 전용 — query param `?token=` 미수용
  (3) 서비스 토큰(typ=service)은 is_service_token()=True 로 구분
  (4) AUTH_DEV_BYPASS=true 일 때만 dev_user/admin 폴백 (opt-in)
  (5) Settings 는 비-dev 에서 AUTH_DEV_BYPASS=true / 빈 JWT_SECRET 기동을 거부 (fail-fast)

실제 core/security.py 를 그대로 의존성으로 쓰는 최소 probe 앱으로 검사 — DB/LLM/MCP 불필요.
pydantic·fastapi import 필요 (stdlib 불가) — `uv run python scripts/verify_auth_hardening.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import jwt as pyjwt  # noqa: E402
from core.auth_context import get_role, get_user_id, is_service_token  # noqa: E402
from core.config import Settings, settings  # noqa: E402
from core.exception_handler import get_exception_handlers  # noqa: E402
from core.security import create_access_token, verify_access_token  # noqa: E402
from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

app = FastAPI(exception_handlers=get_exception_handlers())


@app.post("/probe", dependencies=[Depends(verify_access_token)])
async def probe():
    return {"user_id": get_user_id(), "role": get_role(), "is_service": is_service_token()}


def main() -> int:
    client = TestClient(app)
    secret = settings.JWT_SECRET
    user_tok = pyjwt.encode(
        {"sub": "u1", "email": "a@b.com", "role": "user", "exp": int(time.time()) + 60},
        secret,
        algorithm="HS256",
    )
    problems: list[str] = []

    def check(name: str, cond: bool) -> None:
        if not cond:
            problems.append(name)

    settings.AUTH_DEV_BYPASS = False
    check("무효 토큰 → 401", client.post("/probe", headers={"Authorization": "Bearer bad"}).status_code == 401)
    check("토큰 없음 → 401", client.post("/probe").status_code == 401)
    check("query param 토큰 미수용 → 401", client.post(f"/probe?token={user_tok}").status_code == 401)

    r = client.post("/probe", headers={"Authorization": f"Bearer {user_tok}"})
    check("사용자 토큰 → 200", r.status_code == 200)
    check("사용자 토큰 is_service=False", r.status_code == 200 and r.json()["is_service"] is False)

    r = client.post("/probe", headers={"Authorization": f"Bearer {create_access_token()}"})
    check("서비스 토큰 → 200", r.status_code == 200)
    check("서비스 토큰 is_service=True", r.status_code == 200 and r.json()["is_service"] is True)

    settings.AUTH_DEV_BYPASS = True
    r = client.post("/probe", headers={"Authorization": "Bearer bad"})
    check("bypass=true 무효 토큰 → dev_user/admin", r.status_code == 200 and r.json()["user_id"] == "dev_user")
    settings.AUTH_DEV_BYPASS = False

    try:
        Settings(APP_ENV="staging", JWT_SECRET="x", AUTH_DEV_BYPASS=True)
        check("비-dev AUTH_DEV_BYPASS 기동 거부", False)
    except ValueError:
        pass
    try:
        Settings(APP_ENV="staging", JWT_SECRET="")
        check("비-dev 빈 JWT_SECRET 기동 거부", False)
    except ValueError:
        pass

    if problems:
        print("auth hardening 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("auth hardening OK — 헤더 전용 fail-closed 인증, 서비스 토큰 typ 구분, dev 우회는 opt-in + 비-dev 기동 거부")
    return 0


if __name__ == "__main__":
    sys.exit(main())
