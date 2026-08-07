# ── [가이드 3/9] clients/mcp/mcp_auth.py — MCP 호출용 httpx Auth (매 요청 fresh JWT) ──
# 무엇: MCP streamable-http 는 tool 호출마다 별도 HTTP 요청이라, 세션 생성 시 토큰을 고정하면 1분
#   만료 후 401 이 난다. auth_flow 가 요청 직전 불리는 성격을 이용해 매번 새 서비스 토큰을 박는다.
# 복사 후: 보통 그대로 (SERVICE_NAME·JWT_SECRET 은 config 에서).
# 함정: 정적 토큰 헤더로 대체 금지(exp 1분) · create_access_token 의 exp 가 짧아야 한다(security.py).

import httpx
from core.security import create_access_token


class ServiceJwtAuth(httpx.Auth):
    """요청마다 fresh 서비스 JWT(exp 1분) 주입."""

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {create_access_token()}"
        yield request
