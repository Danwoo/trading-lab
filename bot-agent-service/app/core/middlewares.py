# ── [가이드 2/9] core/middlewares.py — 일반 FastAPI 미들웨어 (CORS + 처리시간) ──
# 무엇: 이 서비스는 MCP 소비자(순수 REST+SSE)라 MCP 서버 전용 McpHeaderMiddleware 가 없다.
# 복사 후: 보통 그대로. 인증은 라우터 dependencies(verify_access_token)가 담당한다.
# 함정: SSE(StreamingResponse) 응답에 ProcessTimeMiddleware 가 헤더를 달려면 스트림 시작 전이어야
#   하니 BaseHTTPMiddleware 1개로 유지(추가 미들웨어가 스트림을 버퍼링하면 토큰이 안 흘러간다).

import time

from core.config import settings
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware


class ProcessTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
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
        Middleware(ProcessTimeMiddleware),
    ]
