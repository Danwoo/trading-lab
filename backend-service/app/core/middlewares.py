import time

from core.config import settings
from core.logger import logger
from fastapi import Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


class MaxRequestBodySizeMiddleware(BaseHTTPMiddleware):
    """업로드 엔드포인트(POST /file)에서 멀티파트 파싱/temp spool 이전에 Content-Length 를 검사해,
    남용 수준의 거대한 요청만 조기 413 으로 거절한다 (대역폭·temp 디스크·파싱 자원 소모 차단, #109).

    이건 정밀 한도가 아니라 **남용 차단선**이다:

    - 기준은 settings.max_request_body_bytes(요청 바디 전체) — 파일당 한도가 아니다. Content-Length 는
      멀티파트 전체 바디(파일들 + 경계·파트 헤더·폼필드) 크기라, 파일당 한도로 재면 정상 다중파일 배치가
      오탐 거절된다. 그래서 정상 사용을 절대 막지 않을 만큼 넉넉한 상한만 여기서 본다.
    - **파일당 20MB 정밀 판정은 파싱 후 실측 검사(FileService.upload_files 의 file.size)가 정본**이며,
      이 미들웨어는 그 검사를 대체하지 않는다.
    - Content-Length 헤더는 조기 거절 '힌트'일 뿐이다 — 없거나 위조·누락될 수 있어 신뢰하지 않는다.
      힌트가 없으면 그대로 통과시키고 실측 검사에 맡긴다.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        if self._is_upload_request(request):
            content_length = self._parse_content_length(request)
            if content_length is not None:
                limit = settings.max_request_body_bytes
                if content_length > limit:
                    logger.warning(
                        f"{request.method} {request.url.path} 413: "
                        f"Content-Length {content_length} > {limit} 조기 거절 (파싱 전)"
                    )
                    return JSONResponse(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        content={
                            "detail": (
                                "요청이 너무 큽니다. 한 번에 보낼 수 있는 요청 크기"
                                f"({settings.MAX_REQUEST_BODY_SIZE_MB}MB)를 초과했습니다. "
                                "파일을 나눠서 업로드해 주세요."
                            )
                        },
                    )
        # 힌트 미검출(헤더 없음·파싱 불가·차단선 이하)이면 통과 — 파일당 판정은 실측 검사가 한다.
        return await call_next(request)

    @staticmethod
    def _is_upload_request(request: Request) -> bool:
        # 유일한 바디 수용 라우트는 POST /file(컬렉션). prefix/root_path 유무와 무관하게 경로 suffix 로 식별.
        return request.method == "POST" and request.url.path.rstrip("/").endswith("/file")

    @staticmethod
    def _parse_content_length(request: Request) -> int | None:
        raw = request.headers.get("content-length")
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None


def get_middlewares():
    return [
        Middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ALLOW_ORIGINS,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        # CORS 다음(바깥에서 두 번째)에 둬, 조기 413 응답에도 CORS 헤더가 붙고 파싱 전에 단락된다.
        Middleware(MaxRequestBodySizeMiddleware),
        Middleware(McpHeaderMiddleware),
        Middleware(ProcessTimeMiddleware),
    ]
