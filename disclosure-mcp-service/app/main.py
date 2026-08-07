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
from routers.disclosure.disclosure_router import router as disclosure_router
from utils.common.few_shot import attach_tool_meta, attached_tool_names


@asynccontextmanager
async def lifespan(app: FastAPI):
    # mcp_app 은 아래 from_fastapi 로 생성된다(startup 시점엔 존재 — lazy 참조). mcp_app.lifespan 이
    # StreamableHTTP 세션매니저 task group 을 띄우므로(미실행 시 transport 사망) 그 컨텍스트 안에서
    # 서비스가 돌고, 종료 시 disclosure_client 를 정리한다.
    async with mcp_app.lifespan(app):
        yield
    await app.container.disclosure_client().aclose()
    logger.info("Disclosure MCP service shutdown")


# 단일 FastAPI 앱 — 기존 REST 레이어(@inject 라우터 → service → repository → DART API/mock)·DI·예외핸들러 그대로.
# from_fastapi 가 이 앱의 라우트를 MCP tool 로 변환하고, tool 실행은 ASGI 로 다시 이 앱의 라우트를 호출한다.
app = FastAPI(
    title="Disclosure MCP Service API",
    description="기업 전자공시·재무제표·배당·최대주주 조회 (DART 형식, mock 기본)",
    version="1.0",
    lifespan=lifespan,
    middleware=get_middlewares(),
    exception_handlers=get_exception_handlers(),
)
app.container = Container()
app.include_router(disclosure_router)

# 이 서버의 도메인 자기소개 — tool description·스키마로 안 드러나는 운용·답변 지침만. 소비자가 모아 시스템 프롬프트에 주입.
INSTRUCTIONS = """\
### disclosure — 기업 전자공시·재무제표 조회 (발행사·재무·공시목록·공시상세·배당·최대주주)
- 발행사 식별은 회사명·종목코드(6자리)·고유번호(corp_code) 중 무엇이든 받아 정규화한다. corp 인자가 모호하면 disclosure_company 로 먼저 발행사를 확정한 뒤 다른 도구에 넘긴다.
- 재무는 보고서 종류(연간 11011·반기 11012·분기 11013/11014)와 연결(CFS)/별도(OFS)를 구분한다. 답변엔 당기·전기를 함께 제시해 YoY 비교를 돕고, 단위(백만원 등)를 명시한다.
- 모든 수치는 공시(disclosure) 근거여야 한다 — 근거 없는 추정치를 단정하지 말고, 수치 기반 판단을 곧바로 투자 권유로 확장하지 마라. 정보 제공 목적이며 투자 조언이 아니다."""

# from_fastapi: 라우트→MCP tool (operation_id=이름·docstring=설명·response_model=출력·instructions=자기소개). route_maps 로 전부 TOOL 고정 — GET 도 tool 이어야 call_tool 동작.
# 인증 — MCP: JWTVerifier / REST(/disclosure/*): router.dependencies.
mcp = FastMCP.from_fastapi(
    app=app,
    name="Disclosure MCP",
    instructions=INSTRUCTIONS,
    route_maps=[RouteMap(mcp_type=MCPType.TOOL)],
    mcp_component_fn=attach_tool_meta,
    auth=JWTVerifier(public_key=settings.JWT_SECRET, algorithm="HS256"),
)
# few-shot 부착 가시화 — 0개면 선언/배선 누락 의심 (조용한 실패 방지)
logger.info("[few-shot] %d tool 부착: %s", len(attached_tool_names()), attached_tool_names())
mcp_app = mcp.http_app(path="/mcp")

# /mcp (Streamable HTTP). REST(/disclosure/*)·/openapi.json 은 먼저 등록돼 우선 매칭되고, 나머지는 mcp_app 로.
app.mount("/", mcp_app)

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
    except KeyboardInterrupt:
        pass
