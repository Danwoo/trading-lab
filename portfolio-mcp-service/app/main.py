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
from routers.portfolio.portfolio_router import router as portfolio_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # mcp_app 은 아래 from_fastapi 로 생성된다(startup 시점엔 존재 — lazy 참조). mcp_app.lifespan 이
    # StreamableHTTP 세션매니저 task group 을 띄우므로(미실행 시 transport 사망) 그 컨텍스트 안에서
    # 서비스가 돌고, 종료 시 portfolio_client 를 정리한다.
    async with mcp_app.lifespan(app):
        yield
    await app.container.portfolio_client().aclose()
    await app.container.fx_rate_client().aclose()
    logger.info("Portfolio MCP service shutdown")


# 단일 FastAPI 앱 — 기존 REST 레이어(@inject 라우터 → service → repository → 브로커리지/MOCK)·DI·예외핸들러 그대로.
# from_fastapi 가 이 앱의 라우트를 MCP tool 로 변환하고, tool 실행은 ASGI 로 다시 이 앱의 라우트를 호출한다.
app = FastAPI(
    title="Portfolio MCP Service API",
    description="브로커리지 계좌·보유·거래·주문·활동 데이터 조회 (기본 MOCK)",
    version="1.0",
    lifespan=lifespan,
    middleware=get_middlewares(),
    exception_handlers=get_exception_handlers(),
)
app.container = Container()
app.include_router(portfolio_router)

# 이 서버의 도메인 자기소개 — tool description·스키마로 안 드러나는 운용·답변 지침만. 소비자가 모아 시스템 프롬프트에 주입.
INSTRUCTIONS = """\
### portfolio — 브로커리지 계좌·보유종목·거래·주문·계좌활동 조회
- 계좌 식별: 계좌가 모호하면(별칭·번호 일부로만 말하거나 여러 계좌 보유) 먼저 portfolio_list_accounts 로 account_id 를 확정한 뒤 조회한다. 활동 조회가 미존재(found=false)면 그 계좌가 없는 것이니(활동 0건과 다름) 후보를 보여주고 되물어라. 계좌가 특정 안 되면 보유·거래는 전체 계좌 합산으로 답하되, 그 사실을 머리말에 밝혀라.
- 날짜(오늘 KST 기준): 상대기간(이번주·지난주·이번달·지난달·최근 7/30일)은 제공된 "오늘 날짜와 기간 기준"의 계산값을 그대로 since·until 에 써라(직접 계산 금지). 거기 없는 기간만 오늘 기준 계산(연도 없는 월은 올해). 모호하면 비워라(최근 30일). 미래 기간이면 기록이 있을 수 없음을 설명. 시작>끝이면 바로잡아 재조회.
- 도구 선택: '들고 있는 종목·비중·평가손익'은 portfolio_list_holdings, '체결된 매매·입출금·배당 등 현금흐름'은 portfolio_search_transactions, '주문(미체결/체결/취소) 상태'는 portfolio_search_orders 로. 미체결 주문을 거래로 세지 마라 — 주문은 아직 현금흐름이 아니다.
- 숫자·근거: 평가금액·평가손익·비중·NAV·net_amount 는 도구가 보유·체결·시세 데이터에서 결정론적으로 계산해 돌려준 값이다. 그 값만 인용하고 임의 추정·반올림 변형·연환산 등 가공 수치를 새로 만들지 마라. 수치 주장은 반드시 도구가 준 값으로 뒷받침하고, 시세는 지연될 수 있음을 필요 시 밝혀라.
- 데이터 한계·민감정보: 계좌번호(account_no)·detail 의 식별자는 가운데가 가려진 채(`[계좌번호 일부 가려짐]`) 제공된다 — 그대로 두고 복원하려 하지 마라. 통화가 섞이면 `*_by_currency` 는 통화별 분리합(환산 없음)이고 `*_in_base` 는 base_currency 로 환산한 합이다. `unconverted_currencies` 가 비어 있지 않으면 그 통화는 환율이 없어 `*_in_base` 에서 빠졌다는 뜻이니, 환산 총액을 전체인 양 말하지 말고 빠진 통화를 함께 밝혀라. 환율은 `fx_rates_used` 의 값·기준시각만 인용하고 임의 추정·역산하지 마라. 결과가 잘렸으면(truncated) "최근 250건 기준"이라 밝히고 범위를 좁히도록 권하며 총건수·전수집계를 단정하지 마라.
- 0건: 지어내지 말고 도구가 준 기간·계좌를 함께 밝혀 "그 범위에 기록이 없습니다"라고 한다. 무조건 "없음"으로 끝내지 말고 계좌 선택·기간/종목 필터가 좁을 가능성을 짚고 범위 완화를 제안하라.
- 출력: 머리말에 조회 메타를 한 줄로 — `기간 <시작>~<끝> · <N>개 계좌 · <M>건` (꺾쇠는 실제 값). 기본은 간결 요약(계좌·종목·날짜별 집계). 표가 필요하면 종목|수량|평가금액|비중 또는 일자|구분|종목|금액. 금액은 통화 기호와 함께.
- 컴플라이언스: 답변 끝에 반드시 "ⓘ 정보 제공 목적이며 투자 조언이 아닙니다" 를 덧붙인다. 이 데이터는 사용자 보유 자산 조회 결과일 뿐 매수·매도 권유가 아니다."""

# from_fastapi: 라우트→MCP tool (operation_id=이름·docstring=설명·response_model=출력·instructions=자기소개). route_maps 로 전부 TOOL 고정 — GET 도 tool 이어야 call_tool 동작.
# 인증 — MCP: JWTVerifier / REST(/portfolio/*): router.dependencies.
mcp = FastMCP.from_fastapi(
    app=app,
    name="Portfolio MCP",
    instructions=INSTRUCTIONS,
    route_maps=[RouteMap(mcp_type=MCPType.TOOL)],
    auth=JWTVerifier(public_key=settings.JWT_SECRET, algorithm="HS256"),
)
mcp_app = mcp.http_app(path="/mcp")

# /mcp (Streamable HTTP). REST(/portfolio/*)·/openapi.json 은 먼저 등록돼 우선 매칭되고, 나머지는 mcp_app 로.
app.mount("/", mcp_app)

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
    except KeyboardInterrupt:
        pass
