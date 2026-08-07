# routers/portfolio/portfolio_router.py
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from schemas.portfolio.portfolio_schema import (
    AccountActivityIn,
    AccountActivityOut,
    AccountsOut,
    HoldingsIn,
    HoldingsOut,
    SearchOrdersIn,
    SearchOrdersOut,
    SearchTransactionsIn,
    SearchTransactionsOut,
)
from services.portfolio.portfolio_service import PortfolioService

# operation_id 가 MCP tool 이름의 SoT — multi-agent-service `agents/domains/*` 의 SUBAGENT_SPECS.mcp_tools
# 가 이 이름으로 바인딩 (변경 시 lockstep). docstring 이 tool description, Pydantic In/Out 이 tool 입출력 스키마.
router = APIRouter(prefix="/portfolio", dependencies=[Depends(verify_access_token)])


@router.get("/accounts", operation_id="portfolio_list_accounts")
@inject
async def list_accounts(
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
) -> AccountsOut:
    """전체 계좌 목록 (account_no 마스킹·유형·기준통화·NAV·예수금). 어떤 계좌가 있는지/계좌 잔고·NAV 류 질문에, 그리고 보유·거래·주문·활동 조회 전에 account_id 를 확정해야 할 때 먼저 쓴다. account_no(계좌번호)는 가운데가 가려진 채 제공되며 복원할 수 없다. 전역 조회라 사후 필터를 적용하지 않는다."""
    accounts = await portfolio_service.list_accounts()
    return AccountsOut(items=accounts, total_count=len(accounts))


@router.post("/holdings", operation_id="portfolio_list_holdings")
@inject
async def list_holdings(
    body: HoldingsIn,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
) -> HoldingsOut:
    """보유종목 조회 (수량·평균단가·현재가·평가금액·평가손익·계좌내 비중, 평가금액 내림차순). '무슨 종목 들고 있어'·'비중'·'평가손익' 류 질문에 쓴다. account_id 지정 시 그 계좌만, 미지정 시 전체 계좌 합산. asset_class/ticker_keywords/min_weight 로 좁힌다. 평가금액·손익·비중은 보유·시세 데이터에서 결정론적으로 계산된 값 — 지어내지 마라. NL 추출·요약 없음."""
    result = await portfolio_service.list_holdings(
        account_id=body.account_id,
        asset_class=body.asset_class,
        ticker_keywords=body.ticker_keywords,
        min_weight=body.min_weight,
        base_currency=body.base_currency,
    )
    return HoldingsOut(**result)


@router.post("/search-transactions", operation_id="portfolio_search_transactions")
@inject
async def search_transactions(
    body: SearchTransactionsIn,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
) -> SearchTransactionsOut:
    """구조화 조건으로 거래(체결·입출금·배당·수수료) 검색 (필터·시간순 오래된→최신). '무슨 거래/매매/입출금/배당'·'순현금흐름' 류 질문에. amount 는 부호 포함(매수·출금·수수료 음수, 매도·입금·배당 양수), net_amount_by_currency 는 통화별 부호합 dict. 미체결 '주문'은 거래가 아니니 portfolio_search_orders 로. since/until 미지정 시 최근 30일. NL 추출·요약 없음."""
    result = await portfolio_service.search_transactions(
        account_id=body.account_id,
        tx_type=body.tx_type,
        ticker_keywords=body.ticker_keywords,
        since=body.since,
        until=body.until,
        base_currency=body.base_currency,
    )
    return SearchTransactionsOut(**result)


@router.post("/search-orders", operation_id="portfolio_search_orders")
@inject
async def search_orders(
    body: SearchOrdersIn,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
) -> SearchOrdersOut:
    """구조화 조건으로 주문 검색 (status/side/종목/기간, 최신 접수순, 최대 250건). '주문/미체결/체결/취소' 류 질문은 이 도구를 쓴다 — 체결된 거래내역(현금흐름)은 portfolio_search_transactions 로 ('미체결'=status open, '취소'=canceled). 기간은 주문 접수일 기준. NL 추출·요약 없음."""
    result = await portfolio_service.search_orders(
        account_id=body.account_id,
        status=body.status,
        side=body.side,
        ticker_keywords=body.ticker_keywords,
        since=body.since,
        until=body.until,
    )
    return SearchOrdersOut(**result)


@router.post("/account-activity", operation_id="portfolio_get_account_activity")
@inject
async def get_account_activity(
    body: AccountActivityIn,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
) -> AccountActivityOut:
    """특정 한 계좌(account_id 정확일치)의 활동 이벤트 (체결·주문·입출금·배당 통합, 최신순, 최대 250건). 계좌 단위 '최근에 무슨 일 있었어' 류에 쓴다 — 계좌가 특정 안 되면 먼저 portfolio_list_accounts 로 account_id 확정. account_id 미존재 시 found=false 로 반환 — '활동 0건'과 구분. detail 의 계좌번호 등 식별자는 마스킹된 상태."""
    result = await portfolio_service.get_account_activity(
        account_id=body.account_id, since=body.since, until=body.until
    )
    return AccountActivityOut(**result)
