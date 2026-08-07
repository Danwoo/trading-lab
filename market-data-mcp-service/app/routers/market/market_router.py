# routers/market/market_router.py
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from schemas.market.market_schema import (
    MarketDataOut,
    MarketFxIn,
    MarketIndexIn,
    MarketOhlcIn,
    MarketQuoteIn,
    MarketSearchIn,
)
from services.market.market_service import MarketService
from utils.common.few_shot import few_shot

# operation_id 가 MCP tool 이름의 SoT — multi-agent-service `agents/domains/*` 의 SUBAGENT_SPECS.mcp_tools
# 가 이 이름으로 바인딩 (변경 시 lockstep). docstring 이 tool description, Pydantic In/Out 이 tool 입출력 스키마.
router = APIRouter(prefix="/market", dependencies=[Depends(verify_access_token)])


@router.post(
    "/quote",
    operation_id="market_quote",
    openapi_extra=few_shot(
        [
            {"질문": "삼성전자 현재가 알려줘", "호출": {"symbol": "005930"}},
            {"질문": "애플 주가 얼마야", "호출": {"symbol": "AAPL"}},
            {"질문": "SK하이닉스와 NAVER 시세 비교", "호출": {"symbol": "000660"}},
            {"질문": "엔비디아 등락률 어때", "호출": {"symbol": "NVDA"}},
        ]
    ),
)
@inject
async def market_quote(
    body: MarketQuoteIn,
    market_service: MarketService = Depends(Provide[Container.market_service]),
) -> MarketDataOut:
    """단일 종목의 실시간(스냅샷) 시세를 조회한다 — 현재가·전일종가·등락폭·등락률·거래량·시가총액·기준시각. '~ 주가/현재가/등락률/거래량 얼마'처럼 한 종목의 현시점 가격이 핵심인 질문의 기본 진입점. symbol 은 국내는 6자리 종목코드(예: 005930), 미국은 티커(예: AAPL). 종목코드를 모르면 먼저 market_search 로 symbol 을 확정한 뒤 호출한다. 기간별 추세·차트 데이터는 market_ohlc, 시장 전체 지수는 market_index 가 맞다. 반환되는 수치는 응답의 asof(기준시각) 시점 값이며, 답변 시 종목명·현재가·등락률·기준시각을 함께 제시한다."""
    return await market_service.quote(body)


@router.post(
    "/ohlc",
    operation_id="market_ohlc",
    openapi_extra=few_shot(
        [
            {"질문": "삼성전자 최근 20일 일봉 보여줘", "호출": {"symbol": "005930", "interval": "1d", "count": 20}},
            {"질문": "애플 주봉 추세 분석", "호출": {"symbol": "AAPL", "interval": "1w", "count": 12}},
            {"질문": "엔비디아 최근 한 달 변동성", "호출": {"symbol": "NVDA", "interval": "1d", "count": 30}},
            {"질문": "마이크로소프트 월봉 흐름", "호출": {"symbol": "MSFT", "interval": "1mo", "count": 12}},
        ]
    ),
)
@inject
async def market_ohlc(
    body: MarketOhlcIn,
    market_service: MarketService = Depends(Provide[Container.market_service]),
) -> MarketDataOut:
    """한 종목의 기간별 OHLCV 캔들(시가·고가·저가·종가·거래량)을 최신순으로 조회한다 — 추세·변동성·기술적 분석의 입력. '~ 최근 N일/주/월 흐름·차트·변동성·추세'처럼 시간축이 있는 질문에 쓴다. interval 로 주기(1d 일봉·1w 주봉·1mo 월봉), count 로 개수를 정한다 (1~120). 현시점 한 점의 가격만 필요하면 market_ohlc 가 아니라 market_quote 가 맞다. 시장 전체 추세는 market_index. 캔들 수치로 수익률·변동성을 계산해 제시할 때는 사용한 캔들 구간(기간·주기)을 함께 명시한다."""
    return await market_service.ohlc(body)


@router.post(
    "/index",
    operation_id="market_index",
    openapi_extra=few_shot(
        [
            {"질문": "코스피 지수 지금 얼마야", "호출": {"index_code": "KOSPI"}},
            {"질문": "나스닥 종합지수 등락", "호출": {"index_code": "IXIC"}},
            {"질문": "S&P500 오늘 어때", "호출": {"index_code": "SPX"}},
            {"질문": "코스피와 코스닥 비교", "호출": {"index_code": "KOSDAQ"}},
        ]
    ),
)
@inject
async def market_index(
    body: MarketIndexIn,
    market_service: MarketService = Depends(Provide[Container.market_service]),
) -> MarketDataOut:
    """시장 대표 지수의 현재값·등락폭·등락률·기준시각을 조회한다 — KOSPI·KOSDAQ(국내), SPX(S&P 500)·IXIC(NASDAQ, 미국). '시장 분위기·지수·코스피/나스닥 어때'처럼 개별 종목이 아니라 시장 전체 방향을 묻는 질문, 또는 밸류에이션·매크로 분석의 시장 기준선이 필요할 때 쓴다. 개별 종목 가격은 market_quote, 환율은 market_fx 가 맞다. 답변 시 지수명·현재값·등락률·기준시각을 함께 제시한다."""
    return await market_service.index(body)


@router.post(
    "/fx",
    operation_id="market_fx",
    openapi_extra=few_shot(
        [
            {"질문": "원달러 환율 지금 얼마야", "호출": {"pair": "USD/KRW"}},
            {"질문": "유로 원화 환율", "호출": {"pair": "EUR/KRW"}},
            {"질문": "엔화 환율 흐름", "호출": {"pair": "JPY/KRW"}},
            {"질문": "달러엔 환율 알려줘", "호출": {"pair": "USD/JPY"}},
        ]
    ),
)
@inject
async def market_fx(
    body: MarketFxIn,
    market_service: MarketService = Depends(Provide[Container.market_service]),
) -> MarketDataOut:
    """통화쌍 환율의 현재값·등락폭·등락률·기준시각을 조회한다 (예: USD/KRW = 1달러당 원화). pair 는 'BASE/QUOTE' 형식 — 원달러는 USD/KRW, 달러엔은 USD/JPY. '환율·원달러·달러/엔 얼마'처럼 통화 가격이 핵심인 질문, 또는 수출입·해외 매출 비중이 큰 종목의 매크로 리스크 분석에 쓴다. 지수는 market_index, 개별 종목은 market_quote 가 맞다. 답변 시 통화쌍·현재값·등락률·기준시각을 함께 제시한다."""
    return await market_service.fx(body)


@router.post(
    "/search",
    operation_id="market_search",
    openapi_extra=few_shot(
        [
            {"질문": "삼성 들어간 종목 찾아줘", "호출": {"keyword": "삼성", "market": "KR"}},
            {"질문": "애플 티커가 뭐야", "호출": {"keyword": "Apple", "market": "US"}},
            {"질문": "하이닉스 종목코드 알려줘", "호출": {"keyword": "하이닉스", "market": "ALL"}},
            {"질문": "엔비디아 심볼 검색", "호출": {"keyword": "NVDA", "market": "US"}},
        ]
    ),
)
@inject
async def market_search(
    body: MarketSearchIn,
    market_service: MarketService = Depends(Provide[Container.market_service]),
) -> MarketDataOut:
    """종목명·티커 키워드로 종목을 검색해 symbol(종목코드/티커)·종목명·시장·통화를 반환한다 — 시세·캔들 도구 호출 전 symbol 을 확정하는 진입점. '~ 종목코드/티커/심볼이 뭐야', '~ 들어간 종목 찾아줘'처럼 식별자가 필요한 질문에 쓴다. market 으로 시장(KR 국내·US 미국·ALL 전체)을 좁힌다. 0건이면 시장 필터(KR/US)를 ALL 로 자동 완화해 재검색한다. symbol 을 확보한 뒤 가격은 market_quote, 차트는 market_ohlc 로 이어 호출한다."""
    return await market_service.search(body)
