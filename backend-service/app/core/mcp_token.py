"""on-behalf 서비스 토큰 — 하류 MCP(portfolio 등)가 테넌트 격리를 강제할 수 있도록 요청자 테넌트를 실어 발급한다.

`core/security.py` 의 `create_access_token()` 은 `sub`·`typ` 만 담는 순수 서비스 토큰이고, 그 파일은
전 서비스 byte-identical lockstep(`scripts/verify_auth_lockstep.py`) 대상이라 여기서 확장하지 않는다.
대신 이 서비스-로컬 모듈이 현재 요청 컨텍스트의 `workspace_id` 를 payload 에 실어 최소 델타로 on-behalf 를 구현한다.

수신 측 portfolio-mcp `verify_access_token` 은 이미 payload 의 `workspace_id`·`typ` 를 읽어 컨텍스트에 박고
`require_workspace_id()` 로 스코핑한다 — 컨텍스트에 workspace_id 가 없으면(요청 밖·미인증) 필드 미포함 → 수신 측 fail-closed.
"""

from datetime import UTC, datetime, timedelta

import jwt
from core.auth_context import get_workspace_id
from core.config import settings

ALGORITHM = "HS256"


def create_onbehalf_service_token() -> str:
    """요청자 테넌트(workspace_id)를 실은 서비스 JWT(exp 1분). workspace_id 미설정 시 필드 없이 순수 서비스 토큰."""
    now = datetime.now(UTC)
    payload: dict = {
        "sub": settings.SERVICE_NAME,
        "typ": "service",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=1)).timestamp()),
    }
    workspace_id = get_workspace_id()
    if workspace_id is not None:
        payload["workspace_id"] = workspace_id
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)
