# [가이드 7/8] main.py — FastAPI 앱에 from_fastapi 로 MCP 를 얹음. REST 테스트가 곧 tool 테스트.
# 복사 후 title·라우터·INSTRUCTIONS·name·포트. INSTRUCTIONS 는 서버 전역 정책만 (도구 선택·인자 규칙은 docstring·스키마 몫).
# 함정: lifespan 에 mcp_app.lifespan 필수(없으면 /mcp 죽음) · route_maps 로 GET 도 TOOL 고정 ·
#   JWTVerifier 는 이름과 달리 HS256 대칭키 · --workers=1.

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
from routers.example.example_router import router as example_router
from utils.common.few_shot import attach_tool_meta, attached_tool_names


@asynccontextmanager
async def lifespan(app: FastAPI):
    # mcp_app 은 아래 from_fastapi 로 생성된다(startup 시점엔 존재 — lazy 참조). mcp_app.lifespan 이
    # StreamableHTTP 세션매니저 task group 을 띄우므로(미실행 시 transport 사망) 그 컨텍스트 안에서 서비스가 돈다.
    # (외부 client 를 쓰면 여기 종료 시 aclose 를 추가한다 — echo 템플릿은 의존 0 이라 정리 대상 없음)
    async with mcp_app.lifespan(app):
        yield
    logger.info("Template MCP service shutdown")


# 단일 FastAPI 앱 — 기존 REST 레이어(@inject 라우터 → service)·DI·예외핸들러 그대로.
# from_fastapi 가 이 앱의 라우트를 MCP tool 로 변환하고, tool 실행은 ASGI 로 다시 이 앱의 라우트를 호출한다.
app = FastAPI(
    title="Template MCP Service API",
    description="신규 MCP 서비스 개발 템플릿 — 입력을 그대로 돌려주는 echo tool (외부 의존 0)",
    version="1.0",
    lifespan=lifespan,
    middleware=get_middlewares(),
    exception_handlers=get_exception_handlers(),
)
app.container = Container()
app.include_router(example_router)

# 이 서버의 도메인 자기소개 — tool docstring·스키마로 안 드러나는 "서버-전역 운용·답변 정책"만 둔다.
# 도구 선택·인자 규칙은 각 tool docstring·스키마가 SoT (여기 중복 금지). 복사 후 실제 도메인 정책으로 교체.
INSTRUCTIONS = """\
### example — 템플릿 echo (신규 MCP 서비스 출발점)
- 입력 텍스트를 그대로 돌려주는 최소 예시다. 복사 후 이 자리에 실제 서버-전역 운용·답변 정책을 적는다."""

# from_fastapi: 라우트→MCP tool (operation_id=이름·docstring=설명·response_model=출력·instructions=자기소개). route_maps 로 전부 TOOL 고정 — GET 도 tool 이어야 call_tool 동작.
# 인증 — MCP: JWTVerifier / REST(/example/*): router.dependencies.
mcp = FastMCP.from_fastapi(
    app=app,
    name="Template MCP",
    instructions=INSTRUCTIONS,
    route_maps=[RouteMap(mcp_type=MCPType.TOOL)],
    mcp_component_fn=attach_tool_meta,
    auth=JWTVerifier(public_key=settings.JWT_SECRET, algorithm="HS256"),
)
# few-shot 부착 가시화 — 0개면 선언/배선 누락 의심 (조용한 실패 방지)
logger.info("[few-shot] %d tool 부착: %s", len(attached_tool_names()), attached_tool_names())
mcp_app = mcp.http_app(path="/mcp")

# /mcp (Streamable HTTP). REST(/example/*)·/openapi.json 은 먼저 등록돼 우선 매칭되고, 나머지는 mcp_app 로.
app.mount("/", mcp_app)

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8009, reload=True)
    except KeyboardInterrupt:
        pass
