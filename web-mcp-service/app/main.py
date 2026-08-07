from contextlib import asynccontextmanager

import uvicorn
from core.config import settings
from core.container import Container
from core.exception_handler import get_exception_handlers
from core.logger import logger
from core.middlewares import get_middlewares
from fastapi import FastAPI
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.providers.openapi import MCPType, RouteMap
from routers.web.web_router import router as web_router
from utils.common.few_shot import attach_tool_meta, attached_tool_names


@asynccontextmanager
async def lifespan(app: FastAPI):
    # mcp_app 은 아래 from_fastapi 로 생성된다(startup 시점엔 존재 — lazy 참조). mcp_app.lifespan 이
    # StreamableHTTP 세션매니저 task group 을 띄우므로(미실행 시 transport 사망) 그 컨텍스트 안에서
    # 서비스가 돌고, 종료 시 web_client 를 정리한다.
    async with mcp_app.lifespan(app):
        yield
    await app.container.web_client().aclose()
    logger.info("WEB MCP service shutdown")


# 단일 FastAPI 앱 — 기존 REST 레이어(@inject 라우터 → service → repository → Tavily API)·DI·예외핸들러 그대로.
# from_fastapi 가 이 앱의 라우트를 MCP tool 로 변환하고, tool 실행은 ASGI 로 다시 이 앱의 라우트를 호출한다.
app = FastAPI(
    title="WEB MCP Service API",
    description="Tavily 웹 검색 API",
    version="1.0",
    lifespan=lifespan,
    middleware=get_middlewares(),
    exception_handlers=get_exception_handlers(),
)
app.container = Container()
app.include_router(web_router)

# 이 서버의 도메인 자기소개 — tool docstring·스키마로 안 드러나는 "서버-전역 운용·답변 정책"만 둔다.
# 검색 깊이·max_results 같은 인자·0건 처리는 각 tool docstring·스키마가 SoT (여기 중복 금지).
INSTRUCTIONS = """\
### web — Tavily 웹 검색
- 결과는 관련도 순. 최신 뉴스·동향·실시간 정보가 필요한 질문에 적합하다."""

# from_fastapi: 라우트→MCP tool (operation_id=이름·docstring=설명·response_model=출력·instructions=자기소개). route_maps 로 전부 TOOL 고정 — GET 도 tool 이어야 call_tool 동작.
# 인증 — MCP: JWTVerifier / REST(/web/*): router.dependencies.
mcp = FastMCP.from_fastapi(
    app=app,
    name="WEB MCP",
    instructions=INSTRUCTIONS,
    route_maps=[RouteMap(mcp_type=MCPType.TOOL)],
    mcp_component_fn=attach_tool_meta,
    auth=JWTVerifier(public_key=settings.JWT_SECRET, algorithm="HS256"),
)
# few-shot 부착 가시화 — 0개면 선언/배선 누락 의심 (조용한 실패 방지)
logger.info("[few-shot] %d tool 부착: %s", len(attached_tool_names()), attached_tool_names())
mcp_app = mcp.http_app(path="/mcp")

# /mcp (Streamable HTTP). REST(/web/*)·/openapi.json 은 먼저 등록돼 우선 매칭되고, 나머지는 mcp_app 로.
app.mount("/", mcp_app)

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8007, reload=True)
    except KeyboardInterrupt:
        pass
