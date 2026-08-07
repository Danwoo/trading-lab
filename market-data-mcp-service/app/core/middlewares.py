import time

from core.config import settings
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class McpHeaderMiddleware(BaseHTTPMiddleware):
    """MCP tool 내부 호출 시 Authorization 헤더를 FastMCP ContextVar 에서 request scope 에 주입.

    fastmcp 는 MCP 서버에만 설치 — 그 외 백엔드에선 import 실패 → no-op.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if "authorization" not in dict(request.headers):
            try:
                from fastmcp.server.dependencies import get_http_headers
            except ModuleNotFoundError:
                get_http_headers = None
            mcp_auth = get_http_headers(include={"authorization"}).get("authorization") if get_http_headers else None
            if mcp_auth:
                headers_list = list(request.scope["headers"])
                headers_list.append((b"authorization", mcp_auth.encode("utf-8")))
                request.scope["headers"] = tuple(headers_list)
        response = await call_next(request)
        return response


class ProcessTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response


def get_middlewares():
    return [
        Middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ALLOW_ORIGINS,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(McpHeaderMiddleware),
        Middleware(ProcessTimeMiddleware),
    ]
