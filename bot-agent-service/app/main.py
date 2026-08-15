"""FastAPI 앱 — 봇 만들기 대화(Claude Agent SDK 임베드). 순수 REST+SSE.

**로컬 배포 모드 전용이다.** 호스팅에서는 이 서비스를 띄우지 않는 것으로 분리한다 —
셸 권한이 테넌트 격리를 무력화하기 때문이다(결정 2026-07-28). 라우트를 골라 빼는 것보다
프로세스를 안 띄우는 편이 빠뜨릴 자리가 없다.
"""

import uvicorn
from core.container import Container
from core.exception_handler import get_exception_handlers
from core.middlewares import get_middlewares
from fastapi import FastAPI
from routers.bot_agent.bot_agent_router import router as bot_agent_router

app = FastAPI(
    title="Bot Agent Service API",
    description="봇 만들기 대화 — Claude Agent SDK 임베드 (로컬 배포 모드 전용)",
    version="1.0",
    middleware=get_middlewares(),
    exception_handlers=get_exception_handlers(),
)

app.container = Container()

app.include_router(bot_agent_router)

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8011, reload=True)
    except KeyboardInterrupt:
        pass
