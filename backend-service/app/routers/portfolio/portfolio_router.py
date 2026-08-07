from core.auth_context import get_email
from core.authorization import ROLE_ADMIN, ROLE_OPERATOR, require_role, require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request
from schemas.common_schema import CreateOut, DeleteOut, UpdateOut
from schemas.portfolio.portfolio_schema import (
    HoldingCreateIn,
    HoldingOut,
    HoldingsOut,
    HoldingUpdateIn,
    PortfolioCreateIn,
    PortfolioOut,
    PortfoliosOut,
    PortfolioUpdateIn,
)
from services.portfolio.portfolio_service import PortfolioService
from utils.common.devextreme_utils import parse_filter_sort

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


# ── Portfolio (master) ─────────────────────────────────────────────────
@router.get("", response_model=PortfoliosOut, dependencies=[Depends(verify_access_token), Depends(require_user)])
@inject
async def select_portfolio_list(
    request: Request,
    skip: int = Query(0),
    take: int | None = None,
    filter: str | None = None,
    sort: str | None = None,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
):
    filter_obj, sort_obj = parse_filter_sort(filter, sort)
    args = {"skip": skip, "take": take, "filter": filter_obj, "sort": sort_obj}
    items, total_count = portfolio_service.select_portfolio_list(args)
    return PortfoliosOut(items=items, total_count=total_count)


@router.post(
    "",
    response_model=CreateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
async def insert_portfolio(
    request: Request,
    body: PortfolioCreateIn,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
):
    args = body.model_dump()
    args["reg_id"] = get_email()
    keys = portfolio_service.insert_portfolio(args)
    return CreateOut(data={"portfolio_id": keys[0]} if keys else None)


@router.get(
    "/{portfolio_id}", response_model=PortfolioOut, dependencies=[Depends(verify_access_token), Depends(require_user)]
)
@inject
async def select_portfolio(
    request: Request,
    portfolio_id: str,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
):
    args = {"portfolio_id": portfolio_id}
    return portfolio_service.select_portfolio(args)


@router.put(
    "/{portfolio_id}",
    response_model=UpdateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
async def update_portfolio(
    request: Request,
    portfolio_id: str,
    body: PortfolioUpdateIn,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
):
    args = body.model_dump()
    args["portfolio_id"] = portfolio_id
    args["mod_id"] = get_email()
    portfolio_service.update_portfolio(args)
    return UpdateOut()


@router.delete(
    "/{portfolio_id}",
    response_model=DeleteOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
async def delete_portfolio(
    request: Request,
    portfolio_id: str,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
):
    args = {"portfolio_id": portfolio_id}
    portfolio_service.delete_portfolio(args)
    return DeleteOut()


# ── Holding (detail) ───────────────────────────────────────────────────
@router.get(
    "/{portfolio_id}/holding",
    response_model=HoldingsOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
)
@inject
async def select_holding_list(
    request: Request,
    portfolio_id: str,
    skip: int = Query(0),
    take: int | None = None,
    filter: str | None = None,
    sort: str | None = None,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
):
    filter_obj, sort_obj = parse_filter_sort(filter, sort)
    args = {"portfolio_id": portfolio_id, "skip": skip, "take": take, "filter": filter_obj, "sort": sort_obj}
    items, total_count = portfolio_service.select_holding_list(args)
    return HoldingsOut(items=items, total_count=total_count)


@router.post(
    "/{portfolio_id}/holding",
    response_model=CreateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
async def insert_holding(
    request: Request,
    portfolio_id: str,
    body: HoldingCreateIn,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
):
    args = body.model_dump()
    args["portfolio_id"] = portfolio_id
    args["reg_id"] = get_email()
    keys = portfolio_service.insert_holding(args)
    return CreateOut(data={"portfolio_id": keys[0], "ticker": keys[1]} if keys else None)


@router.get(
    "/{portfolio_id}/holding/{ticker}",
    response_model=HoldingOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
)
@inject
async def select_holding(
    request: Request,
    portfolio_id: str,
    ticker: str,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
):
    args = {"portfolio_id": portfolio_id, "ticker": ticker}
    return portfolio_service.select_holding(args)


@router.put(
    "/{portfolio_id}/holding/{ticker}",
    response_model=UpdateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
async def update_holding(
    request: Request,
    portfolio_id: str,
    ticker: str,
    body: HoldingUpdateIn,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
):
    args = body.model_dump()
    args["portfolio_id"] = portfolio_id
    args["ticker"] = ticker
    args["mod_id"] = get_email()
    portfolio_service.update_holding(args)
    return UpdateOut()


@router.delete(
    "/{portfolio_id}/holding/{ticker}",
    response_model=DeleteOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
async def delete_holding(
    request: Request,
    portfolio_id: str,
    ticker: str,
    portfolio_service: PortfolioService = Depends(Provide[Container.portfolio_service]),
):
    args = {"portfolio_id": portfolio_id, "ticker": ticker}
    portfolio_service.delete_holding(args)
    return DeleteOut()
