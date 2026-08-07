# ── [가이드 (배선)] main.py — FastAPI 앱 + lifespan(에이전트 1회 초기화). 순수 REST+SSE ──
# 무엇: MCP 소비자라 from_fastapi 없음(서버화 안 함). lifespan 이 기동 시 chat_service.initialize() 로
#   MCP tool 수집·에이전트 빌드를 1회 수행하고, 종료 시 정리한다.
# 복사 후: title·description·라우터 include·포트(8010).
# 함정: initialize 는 lifespan 에서 1회만(요청 핫패스에서 재빌드 금지) · app.container=Container() 가
#   wiring 적용 트리거 · --workers 늘려도 무방하나 tool 캐시·에이전트는 워커별(in-process).

from contextlib import asynccontextmanager

import uvicorn
from core.container import Container
from core.exception_handler import get_exception_handlers
from core.logger import logger
from core.middlewares import get_middlewares
from fastapi import FastAPI
from routers.chat.chat_router import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await app.container.chat_service().initialize()

    yield

    logger.info("Example Agent service shutdown")


app = FastAPI(
    title="Example Agent Service API",
    description="웹 검색 MCP tool 을 소비하는 단일 에이전트 챗 (신규 에이전트 서비스 교본)",
    version="1.0",
    lifespan=lifespan,
    middleware=get_middlewares(),
    exception_handlers=get_exception_handlers(),
)

app.container = Container()

app.include_router(chat_router)

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8010, reload=True)
    except KeyboardInterrupt:
        pass
