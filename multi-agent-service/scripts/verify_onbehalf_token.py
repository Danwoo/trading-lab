"""on-behalf 서비스 토큰 검증 (#35) — 요청자 테넌트(workspace_id)가 하류 MCP 로 실려 가는지 새 입력으로 확인.

계약:
  (1) 요청 컨텍스트에 workspace_id 가 있으면 토큰 payload 에 그 값이 실린다 (+ typ=service 유지).
  (2) workspace_id 미설정(요청 밖·순수 서비스 토큰)이면 payload 에 workspace_id 필드가 아예 없다
      → 수신 측 portfolio-mcp 가 require_workspace_id 로 fail-closed(401).
  (3) sub=SERVICE_NAME, exp 존재 — 기존 서비스 토큰 계약 불변.

`core/security.py` 는 byte-identical lockstep 대상이라 손대지 않고, 서비스-로컬 core/mcp_token.py 로만 확장했다.
`uv run python scripts/verify_onbehalf_token.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import jwt  # noqa: E402
from core.auth_context import set_auth_context  # noqa: E402
from core.config import settings  # noqa: E402
from core.mcp_token import create_onbehalf_service_token  # noqa: E402

problems: list[str] = []


def check(name: str, cond: bool) -> None:
    if not cond:
        problems.append(name)


def decode(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"], options={"require": ["sub", "exp"]})


def main() -> int:
    # (1) 테넌트 있는 요청 컨텍스트 → workspace_id 실림
    set_auth_context(user_id="u1", role="operator", workspace_id=42)
    p = decode(create_onbehalf_service_token())
    check("workspace_id 42 가 payload 에 실림", p.get("workspace_id") == 42)
    check("typ=service 유지", p.get("typ") == "service")
    check("sub=SERVICE_NAME", p.get("sub") == settings.SERVICE_NAME)

    # (2) 테넌트 미상 → workspace_id 필드 부재 (수신 측 fail-closed 유도)
    set_auth_context(user_id=None, role=None, workspace_id=None)
    p_none = decode(create_onbehalf_service_token())
    check("workspace_id 미설정 시 payload 에 필드 없음", "workspace_id" not in p_none)
    check("무테넌트에도 typ=service·sub 유지", p_none.get("typ") == "service" and p_none.get("sub"))

    if problems:
        print("on-behalf 토큰 위반:")
        for x in problems:
            print(f"  - {x}")
        return 1
    print("on-behalf 토큰 OK — 컨텍스트 workspace_id 실림·미설정 시 필드 부재(fail-closed 유도)·서비스 토큰 계약 불변")
    return 0


if __name__ == "__main__":
    sys.exit(main())
