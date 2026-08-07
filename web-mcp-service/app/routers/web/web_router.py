# routers/web/web_router.py
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from schemas.web.web_schema import WebSearchIn, WebSearchOut
from services.web.web_service import WebService
from utils.common.few_shot import few_shot

# operation_id 가 MCP tool 이름의 SoT — multi-agent-service `agents/domains/*` 의 SUBAGENT_SPECS.mcp_tools
# 가 이 이름으로 바인딩 (변경 시 lockstep). docstring 이 tool description, Pydantic In/Out 이 tool 입출력 스키마.
router = APIRouter(prefix="/web", dependencies=[Depends(verify_access_token)])


@router.post(
    "/search",
    operation_id="web_search",
    openapi_extra=few_shot(
        [
            {
                "질문": "2024 반도체 업황 전망 상세 검색 10개",
                "호출": {"query": "2024 반도체 업황 전망", "search_depth": "advanced", "max_results": 10},
            },
            {
                "질문": "미국 연준 기준금리 인하 최신 뉴스 8개",
                "호출": {"query": "미국 연준 기준금리 인하", "max_results": 8},
            },
            {
                "질문": "2차전지 섹터 수급과 전기차 수요 동향, 수급은 심층 검색",
                "호출": {"query": "2차전지 섹터 수급", "search_depth": "advanced", "max_results": 5},
            },
            {
                "질문": "원/달러 환율, 국채 금리, 코스피 외국인 순매수 세 가지 비교",
                "호출": {"query": "원달러 환율 전망", "max_results": 5},
            },
        ]
    ),
)
@inject
async def web_search(
    body: WebSearchIn,
    web_service: WebService = Depends(Provide[Container.web_service]),
) -> WebSearchOut:
    """Tavily 웹 검색. 시장·종목·매크로 관련 뉴스, 업황 동향, 실시간 정보를 검색한다.

    검색 깊이: basic(빠름) 또는 advanced(깊음, 기본값).
    결과는 관련도 점수(score) 기준 필터링(0.15 이하 제외).
    내용은 500자, 제목은 150자로 제한.
    """
    return await web_service.search(body)
