from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from core.auth_context import set_auth_context
from core.config import settings
from core.exceptions import UnauthorizedError
from fastapi import Request, Security
from fastapi.security import APIKeyHeader

ALGORITHM = "HS256"
HEADER_KEY = "Authorization"


def _decode_jwt_token(token: str | None) -> dict[str, Any]:
    """JWT 토큰 디코딩 및 사용자 ID/만료 검증"""
    clean_token = (token or "").removeprefix("Bearer ")
    payload = jwt.decode(
        clean_token,
        settings.JWT_SECRET,
        algorithms=[ALGORITHM],
        options={"require": ["sub", "exp"]},
    )

    if not payload.get("sub"):
        raise ValueError("Invalid token")
    return payload


async def verify_access_token(
    request: Request,
    token: str | None = Security(APIKeyHeader(name=HEADER_KEY, auto_error=False)),
) -> None:
    """FastAPI Depends 인증. 일반 요청은 Authorization 헤더에서, MCP tool 호출은 McpHeaderMiddleware 가 scope 에 주입한 헤더에서 토큰을 읽는다."""
    jwt_token = token or request.headers.get("Authorization")
    try:
        payload = _decode_jwt_token(jwt_token)
    except (jwt.PyJWTError, ValueError):
        if settings.AUTH_DEV_BYPASS:
            set_auth_context(user_id="dev_user", email=None, role="admin", workspace_id=None)
            return
        raise UnauthorizedError() from None

    set_auth_context(
        user_id=payload["sub"],
        email=payload.get("email"),
        role=payload.get("role"),
        workspace_id=payload.get("workspace_id"),
        is_service=payload.get("typ") == "service",
    )


def verify_websocket_token(token: str | None) -> dict[str, Any]:
    """WebSocket 연결용 JWT 토큰 검증 (query param)"""
    try:
        return _decode_jwt_token(token)
    except (jwt.PyJWTError, ValueError):
        if settings.AUTH_DEV_BYPASS:
            return {"sub": "dev_user", "role": "admin", "workspace_id": None}
        raise UnauthorizedError() from None


def create_access_token() -> str:
    """내부 서비스간 호출용 Access Token 생성 (HS256/JWT_SECRET, sub=SERVICE_NAME).

    수신 측 verify_access_token 이 동일 JWT_SECRET 으로 검증하고 sub 만 확인한다.
    exp 가 분 단위로 짧으니 장시간·다회 요청(MCP 등)은 정적 헤더 대신 매 요청 재발급할 것.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": settings.SERVICE_NAME,
        "typ": "service",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=1)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)
