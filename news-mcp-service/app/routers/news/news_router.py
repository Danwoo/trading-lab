# routers/news/news_router.py
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from schemas.news.news_schema import (
    NewsCompanyIn,
    NewsDataOut,
    NewsDetailIn,
    NewsDisclosureIn,
    NewsSearchIn,
    NewsSentimentIn,
)
from services.news.news_service import NewsService
from utils.common.few_shot import few_shot

# operation_id 가 MCP tool 이름의 SoT — multi-agent-service `agents/domains/*` 의 SUBAGENT_SPECS.mcp_tools
# 가 이 이름으로 바인딩 (변경 시 lockstep). docstring 이 tool description, Pydantic In/Out 이 tool 입출력 스키마.
router = APIRouter(prefix="/news", dependencies=[Depends(verify_access_token)])


@router.post(
    "/search",
    operation_id="news_search",
    openapi_extra=few_shot(
        [
            {"질문": "반도체 실적 관련 뉴스 검색", "호출": {"keyword": "실적", "category": "실적"}},
            {"질문": "HBM 공급 계약 뉴스 찾아줘", "호출": {"keyword": "HBM"}},
            {"질문": "최근 배당 관련 시장 뉴스", "호출": {"category": "배당"}},
            {"질문": "AI 가속기 수요 관련 기사", "호출": {"keyword": "AI 가속기"}},
        ]
    ),
)
@inject
async def news_search(
    body: NewsSearchIn,
    news_service: NewsService = Depends(Provide[Container.news_service]),
) -> NewsDataOut:
    """키워드·카테고리로 금융 뉴스를 전반 검색 — 특정 종목에 한정되지 않은 '시장/테마/이슈' 류 질문의 기본 진입점. keyword(제목·본문 매칭)·category(실적/공시/시장/M&A/배당/거시 등)를 선택적으로 조합한다 (전부 비우면 최신순 전체). 특정 종목의 뉴스만 보려면 종목 코드·종목명으로 news_company 가 정확하다. 기사 1건의 본문까지 파보려면 결과의 article_id 로 news_detail 을 이어 호출한다. 수치(주가 영향·실적)는 기사·공시 근거 범위로 한정하고 단정 금지."""
    return await news_service.news_search(body)


@router.post(
    "/company",
    operation_id="news_company",
    openapi_extra=few_shot(
        [
            {"질문": "삼성전자 최근 뉴스", "호출": {"company_name": "삼성전자"}},
            {"질문": "005930 실적 뉴스만", "호출": {"ticker": "005930", "category": "실적"}},
            {"질문": "엔비디아 관련 기사 보여줘", "호출": {"company_name": "엔비디아"}},
            {"질문": "AAPL 공시 카테고리 뉴스", "호출": {"ticker": "AAPL", "category": "공시"}},
        ]
    ),
)
@inject
async def news_company(
    body: NewsCompanyIn,
    news_service: NewsService = Depends(Provide[Container.news_service]),
) -> NewsDataOut:
    """특정 종목에 연관된 뉴스 검색 — '~종목/~기업 뉴스, ~의 최근 이슈'처럼 발행사가 특정될 때 쓴다. ticker(종목 코드, 예: 005930·AAPL) 또는 company_name(종목명, 예: 삼성전자·Apple) 중 가진 쪽을 넣고 category 로 좁힐 수 있다 — 둘 다 비면 0건이니 종목 식별자는 필수에 가깝다. 종목 무관 테마·시장 전반 질문은 news_search 가 맞다. 종목의 센티먼트 집계는 news_sentiment, 공시연계 뉴스는 news_disclosure 로 분기한다. 0건이면 category 를 빼고 재시도(service 가 1회 자동 완화)."""
    return await news_service.news_company(body)


@router.post(
    "/detail",
    operation_id="news_detail",
    openapi_extra=few_shot(
        [
            {"질문": "기사 N000010001 본문 상세", "호출": {"article_id": "N000010001"}},
            {"질문": "N000040001 기사 전문 보여줘", "호출": {"article_id": "N000040001"}},
            {"질문": "N000020001 기사 상세 분석", "호출": {"article_id": "N000020001"}},
        ]
    ),
)
@inject
async def news_detail(
    body: NewsDetailIn,
    news_service: NewsService = Depends(Provide[Container.news_service]),
) -> NewsDataOut:
    """기사 ID(article_id, 'N'+9자리, 예: N000012345)로 그 기사의 본문·메타(센티먼트·주가 영향·공시연계 여부)를 상세 조회한다. 키워드 검색이 아니다 — article_id 는 news_search·news_company 결과에서 확보한 뒤 호출한다. 특정 기사를 인용·근거로 깊이 파볼 때 쓰는 후속 도구. 0건이면 ID 오기이거나 존재하지 않는 기사다. 본문의 수치는 그 기사 범위로만 인용하고 전체 시장으로 일반화 금지."""
    return await news_service.news_detail(body)


@router.post(
    "/sentiment",
    operation_id="news_sentiment",
    openapi_extra=few_shot(
        [
            {"질문": "삼성전자 뉴스 센티먼트", "호출": {"company_name": "삼성전자"}},
            {"질문": "005930 시장 분위기 점수", "호출": {"ticker": "005930"}},
            {"질문": "엔비디아 뉴스 긍부정 분석", "호출": {"company_name": "엔비디아"}},
            {"질문": "AAPL 센티먼트 집계", "호출": {"ticker": "AAPL"}},
        ]
    ),
)
@inject
async def news_sentiment(
    body: NewsSentimentIn,
    news_service: NewsService = Depends(Provide[Container.news_service]),
) -> NewsDataOut:
    """종목 뉴스의 센티먼트(긍정/중립/부정) 점수와 평균 집계를 조회한다 — '~종목 뉴스 분위기, 긍부정, 시장 심리'류 질문에 쓴다. 결과 첫 항목은 평균(avg_sentiment·is_summary=true), 이후 기사별 sentiment(-1.0~+1.0)·price_impact_pct. ticker 또는 company_name 으로 종목을 특정해야 하며, 비면 0건. 센티먼트는 뉴스 톤 지표일 뿐 시세·실적 자체가 아니므로 투자 판단의 단일 근거로 단정 금지 — 재무·공시 근거와 교차 확인하도록 안내한다."""
    return await news_service.news_sentiment(body)


@router.post(
    "/disclosure",
    operation_id="news_disclosure",
    openapi_extra=few_shot(
        [
            {"질문": "삼성전자 공시 연계 뉴스", "호출": {"company_name": "삼성전자"}},
            {"질문": "005930 배당 공시 뉴스", "호출": {"ticker": "005930", "disclosure_type": "배당"}},
            {"질문": "엔비디아 실적 공시 관련 기사", "호출": {"company_name": "엔비디아", "disclosure_type": "실적"}},
            {"질문": "최근 공시에 연결된 뉴스 전체", "호출": {}},
        ]
    ),
)
@inject
async def news_disclosure(
    body: NewsDisclosureIn,
    news_service: NewsService = Depends(Provide[Container.news_service]),
) -> NewsDataOut:
    """공시(실적·배당·지분·M&A·유상증자 등)에 연결된 뉴스만 추려 조회한다 — 기사에 disclosure_id 가 붙어 공시 원문과 연계된 항목이라 '근거 있는 수치'의 출처가 된다. 막연한 루머·시황 기사와 달리 공시 기반이므로 실적·배당 등 정량 주장의 1차 근거로 적합하다. ticker·company_name 으로 종목을 좁히거나(비우면 전체), disclosure_type 으로 유형을 거른다. 0건이면 disclosure_type 을 빼고 재시도(service 가 1회 자동 완화). 공시 상세 수치 자체는 disclosure-mcp 가 SoT 다."""
    return await news_service.news_disclosure(body)
