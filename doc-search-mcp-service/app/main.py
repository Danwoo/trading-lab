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
from routers.vector_search.vector_search_router import router as vector_search_router
from routers.workspace.workspace_router import router as workspace_router
from utils.common.few_shot import attach_tool_meta, attached_tool_names


@asynccontextmanager
async def lifespan(app: FastAPI):
    # mcp_app 은 아래 from_fastapi 로 생성된다(startup 시점엔 존재 — lazy 참조). mcp_app.lifespan 이
    # StreamableHTTP 세션매니저 task group 을 띄우므로(미실행 시 transport 사망) 그 컨텍스트 안에서
    # 서비스가 돌고, 종료 시 임베딩/리랭커 HTTP 클라이언트를 정리한다. Milvus/Redis 는 lazy 연결이라
    # 미접속이어도 기동에 영향 없음 (fail-soft — 첫 검색 요청에서야 연결 시도).
    async with mcp_app.lifespan(app):
        yield
    await app.container.embedding_client().aclose()
    await app.container.reranker_client().aclose()
    workspace_engine = app.container.workspace_engine()
    if workspace_engine is not None:
        await workspace_engine.dispose()
    logger.info("DOC_SEARCH MCP service shutdown")


# 단일 FastAPI 앱 — REST 레이어(@inject 라우터 → service → repository → Milvus)·DI·예외핸들러 그대로.
# from_fastapi 가 이 앱의 라우트를 MCP tool 로 변환하고, tool 실행은 ASGI 로 다시 이 앱의 라우트를 호출한다.
app = FastAPI(
    title="DOC_SEARCH MCP Service API",
    description="금융 문서 지식 Milvus hybrid 벡터 검색 (공시·리포트·약관, dense + sparse + rerank)",
    version="1.0",
    lifespan=lifespan,
    middleware=get_middlewares(),
    exception_handlers=get_exception_handlers(),
)
app.container = Container()
app.include_router(vector_search_router)
app.include_router(workspace_router)

# 이 서버의 도메인 자기소개 — tool description·스키마로 안 드러나는 운용·답변 지침만. 소비자가 모아 시스템 프롬프트에 주입.
INSTRUCTIONS = """\
### doc_search — 금융 문서 지식 벡터 검색 (Milvus hybrid + rerank, 14 분야 × topic/image = 28 tool)
- 공시(사업보고서·실적)·애널리스트 리포트·상품 약관·금융 용어집을 분야별 컬렉션으로 적재한 벡터DB 검색이다. 일반 웹 지식이 아니라 큐레이션된 금융 문서가 출처 — 답변 근거는 반드시 검색 결과(text/question/answer/caption)에서만 가져와라.
- 텍스트 검색의 source: html=문서 본문 청크(text·header_chain·file_nm 으로 출처 제시), label=해설 Q&A(question·answer 가 본문 — text 보다 이 둘을 우선 인용). 미지정이면 통합 검색이며, 정의·설명형 질문엔 label 이, 깊은 본문 근거가 필요하면 html 이 유리하다.
- 점수 해석: score 가 최종 순위 기준 — rerank 성공 시 reranker relevance(0~1, 1 에 가까울수록 관련), 실패 시 hybrid 가중합 폴백(rerank=null 로 구분). dense/doc_sparse_score/meta_sparse_score 는 벡터장별 정규화 기여값(진단용)이다. score 가 일관되게 낮으면(예: rerank 0.2 미만) 관련 문서가 없는 것으로 보고 단정적 인용을 피하라.
- 매출·이익·목표주가·수수료 등 수치 주장은 반드시 검색된 공시·리포트·약관 원문에 근거할 때만 인용하라 — 근거 없는 수치는 만들지 마라.
- 0건 또는 저관련 결과면 지어내지 말고 "검색 결과가 없습니다"라고 답하고, 쿼리 재표현(동의어·한글 용어)이나 source 필터 해제를 제안하라.
- 이미지 검색 결과는 file_url 을 그대로 제시하고 캡션(summary/detailed_caption)으로 내용을 설명하라 — 이미지 내용을 캡션 밖에서 추측하지 마라.
- ⓘ 본 검색 결과는 정보 제공 목적이며 투자 조언이 아니다."""

# from_fastapi: 라우트→MCP tool (operation_id=이름·docstring=설명·response_model=출력·instructions=자기소개). route_maps 로 전부 TOOL 고정 — GET 도 tool 이어야 call_tool 동작.
# 단, 내부 쓰기 경로(인제스트 POST /doc-search/ingest, 청크 회수 DELETE /doc-search/ingest/{atch_file_id})는
# TOOL 매핑 앞에서 EXCLUDE — 쓰기·삭제 능력을 LLM tool 표면에 두면 프롬프트 인젝션으로 근거 코퍼스가
# 오염·훼손될 수 있어 REST 내부(서비스 토큰) 전용으로 격리한다(design-160 AD-1).
# route_maps 는 위→아래 첫 매치가 이긴다.
# 인증 — MCP: JWTVerifier / REST(/doc-search/*): router.dependencies.
mcp = FastMCP.from_fastapi(
    app=app,
    name="DOC_SEARCH MCP",
    instructions=INSTRUCTIONS,
    route_maps=[
        RouteMap(pattern=r"^/doc-search/ingest(?:/.*)?$", mcp_type=MCPType.EXCLUDE),
        RouteMap(mcp_type=MCPType.TOOL),
    ],
    mcp_component_fn=attach_tool_meta,
    auth=JWTVerifier(public_key=settings.JWT_SECRET, algorithm="HS256"),
)
# few-shot 부착 가시화 — 0개면 선언/배선 누락 의심 (조용한 실패 방지)
logger.info("[few-shot] %d tool 부착: %s", len(attached_tool_names()), attached_tool_names())
mcp_app = mcp.http_app(path="/mcp")

# /mcp (Streamable HTTP). REST(/vector-search/*)·/openapi.json 은 먼저 등록돼 우선 매칭되고, 나머지는 mcp_app 로.
app.mount("/", mcp_app)

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8008, reload=True)
    except KeyboardInterrupt:
        pass
