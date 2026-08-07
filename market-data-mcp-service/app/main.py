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
from routers.market.market_router import router as market_router
from utils.common.few_shot import attach_tool_meta, attached_tool_names


@asynccontextmanager
async def lifespan(app: FastAPI):
    # mcp_app 은 아래 from_fastapi 로 생성된다(startup 시점엔 존재 — lazy 참조). mcp_app.lifespan 이
    # StreamableHTTP 세션매니저 task group 을 띄우므로(미실행 시 transport 사망) 그 컨텍스트 안에서
    # 서비스가 돌고, 종료 시 market_client 를 정리한다.
    async with mcp_app.lifespan(app):
        yield
    await app.container.market_client().aclose()
    logger.info("Market-data MCP service shutdown")


# 단일 FastAPI 앱 — 기존 REST 레이어(@inject 라우터 → service → repository → 시세 store)·DI·예외핸들러 그대로.
# from_fastapi 가 이 앱의 라우트를 MCP tool 로 변환하고, tool 실행은 ASGI 로 다시 이 앱의 라우트를 호출한다.
app = FastAPI(
    title="Market-data MCP Service API",
    description="시세·캔들·지수·환율·종목검색 시장데이터 API (기본 MOCK, USE_REAL_API 토글)",
    version="1.0",
    lifespan=lifespan,
    middleware=get_middlewares(),
    exception_handlers=get_exception_handlers(),
)
app.container = Container()
app.include_router(market_router)

# 이 서버의 도메인 자기소개 — tool docstring·스키마로 안 드러나는 "서버-전역 운용·답변 정책"만 둔다.
# 도구 선택·식별자 형식·0건 완화 같은 tool 단위 지식은 각 tool docstring 이 SoT (여기 중복 금지).
INSTRUCTIONS = """\
### market-data — 시세·캔들·지수·환율·종목검색
- 모든 수치(가격·등락률·지수·환율)는 응답의 asof(기준시각) 시점 스냅샷이다. 실시간 체결가가 아니며, 답변에 기준시각을 함께 명시한다.
- 종목코드/티커를 모르면 market_search 로 symbol 을 먼저 확정한 뒤 시세·캔들 도구를 호출한다.
- 이 데이터는 정보 제공 목적이며 투자 조언이 아니다 — 수치 기반 단정·매수/매도 권유를 답변에 넣지 않는다."""

# from_fastapi: 라우트→MCP tool (operation_id=이름·docstring=설명·response_model=출력·instructions=자기소개). route_maps 로 전부 TOOL 고정 — GET 도 tool 이어야 call_tool 동작.
# 인증 — MCP: JWTVerifier / REST(/market/*): router.dependencies.
mcp = FastMCP.from_fastapi(
    app=app,
    name="Market-data MCP",
    instructions=INSTRUCTIONS,
    route_maps=[RouteMap(mcp_type=MCPType.TOOL)],
    mcp_component_fn=attach_tool_meta,
    auth=JWTVerifier(public_key=settings.JWT_SECRET, algorithm="HS256"),
)
# few-shot 부착 가시화 — 0개면 선언/배선 누락 의심 (조용한 실패 방지)
logger.info("[few-shot] %d tool 부착: %s", len(attached_tool_names()), attached_tool_names())
mcp_app = mcp.http_app(path="/mcp")

# /mcp (Streamable HTTP). REST(/market/*)·/openapi.json 은 먼저 등록돼 우선 매칭되고, 나머지는 mcp_app 로.
app.mount("/", mcp_app)

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)
    except KeyboardInterrupt:
        pass
