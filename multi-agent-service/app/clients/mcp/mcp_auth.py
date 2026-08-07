"""매 요청마다 fresh JWT 토큰을 주입하는 httpx Auth 어댑터.

MCP streamable-http 는 매 요청마다 별도 HTTP 요청을 보내므로, 세션 생성 시 고정으로 토큰을
담으면 1분 만료 후 401 발생한다. ``auth_flow`` 가 요청 직전 호출되는 성격을 이용해 토큰 갱신.
"""

import httpx
from core.mcp_token import create_onbehalf_service_token


class ServiceJwtAuth(httpx.Auth):
    """요청마다 fresh 서비스 JWT(exp 1분) 주입. 요청자 테넌트(workspace_id)를 실어 하류 MCP 가 테넌트 격리를 강제하게 한다."""

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {create_onbehalf_service_token()}"
        yield request
