import os
from contextlib import asynccontextmanager

import uvicorn
from core.config import settings
from core.container import Container
from core.exception_handler import get_exception_handlers
from core.logger import logger
from core.middlewares import get_middlewares
from core.session_timezone import SessionTimezoneError, ensure_session_timezone_utc
from fastapi import FastAPI
from routers.agent.agent_router import router as agent_router

# LangSmith — API_KEY 있으면 langchain 이 읽는 os.environ 에 주입 (없으면 trace off). 개인 키라 .env 는 placeholder.
if settings.LANGSMITH_API_KEY:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT


def _dispose_sql_client(sql_client) -> None:
    """커넥션 풀 회수 — 기동 실패로 롤백하는 경로에서도 부른다(안 하면 풀이 남는다).

    backend-service `main.py` 와 같은 모양이다 — 한쪽만 회수하면 같은 사고에서 두 서비스가
    다르게 죽는다.
    """
    try:
        sql_client.dispose()
        logger.info("SQL Database disconnect successful")
    except Exception as e:
        logger.error(f"SQL Database disconnect failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    sql_client = app.container.sql_client()
    # 세션 타임존부터 본다 (#359) — 멀티턴 히스토리를 쓰는 `ai_chat_history.reg_dt` 가
    # `timestamptz` 라, 세션이 UTC 가 아니면 저장·조회 시각이 조용히 어긋난다. fail-closed.
    try:
        ensure_session_timezone_utc(sql_client)
    except SessionTimezoneError:
        _dispose_sql_client(sql_client)
        raise
    # 그래프 빌드(MCP tool 수집 포함)는 기동 시 1회 — 실패해도 도구 0개 fail-soft 로 서비스는 뜬다
    await app.container.agent_service().initialize()

    yield

    logger.info("Multi-Agent service shutdown")
    _dispose_sql_client(sql_client)


# MCP '소비자' 서비스 — backend-service 와 동일한 순수 FastAPI 구성 (FastMCP 서버 아님).
# 5개 MCP 서버(market-data/disclosure/news/web/doc-search)의 tool 을 MultiServerMCPClient 로 모아
# Plan-Execute 멀티 에이전트가 오케스트레이션한다.
app = FastAPI(
    title="Multi-Agent Service API",
    description="투자 리서치 Plan-Execute 멀티 에이전트 (5 MCP 서버 오케스트레이션)",
    version="1.0",
    lifespan=lifespan,
    middleware=get_middlewares(),
    exception_handlers=get_exception_handlers(),
)
app.container = Container()
app.include_router(agent_router)

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
    except KeyboardInterrupt:
        pass
