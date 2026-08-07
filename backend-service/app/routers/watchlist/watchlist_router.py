# router/watchlist_router.py
from core.auth_context import get_email
from core.authorization import ROLE_ADMIN, ROLE_OPERATOR, require_role, require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request
from schemas.common_schema import CreateOut, DeleteOut, UpdateOut
from schemas.watchlist.watchlist_schema import (
    WatchlistCreateIn,
    WatchlistOut,
    WatchlistsOut,
    WatchlistUpdateIn,
)
from services.watchlist.watchlist_service import WatchlistService
from utils.common.devextreme_utils import parse_filter_sort

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=WatchlistsOut, dependencies=[Depends(verify_access_token), Depends(require_user)])
@inject
def select_watchlist_list(
    request: Request,
    skip: int = Query(0),
    take: int | None = None,
    filter: str | None = None,
    sort: str | None = None,
    watchlist_service: WatchlistService = Depends(Provide[Container.watchlist_service]),
):
    filter_obj, sort_obj = parse_filter_sort(filter, sort)
    args = {"skip": skip, "take": take, "filter": filter_obj, "sort": sort_obj}

    items, total_count = watchlist_service.select_watchlist_list(args)
    return WatchlistsOut(items=items, total_count=total_count)


@router.post(
    "",
    response_model=CreateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def insert_watchlist(
    request: Request,
    body: WatchlistCreateIn,
    watchlist_service: WatchlistService = Depends(Provide[Container.watchlist_service]),
):
    args = body.model_dump()
    args["reg_id"] = get_email()

    keys = watchlist_service.insert_watchlist(args)
    return CreateOut(data={"ticker": keys[0]} if keys else None)


@router.get(
    "/{ticker}", response_model=WatchlistOut, dependencies=[Depends(verify_access_token), Depends(require_user)]
)
@inject
def select_watchlist(
    request: Request,
    ticker: str,
    watchlist_service: WatchlistService = Depends(Provide[Container.watchlist_service]),
):
    args = {"ticker": ticker}
    return watchlist_service.select_watchlist(args)


@router.put(
    "/{ticker}",
    response_model=UpdateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def update_watchlist(
    request: Request,
    ticker: str,
    body: WatchlistUpdateIn,
    watchlist_service: WatchlistService = Depends(Provide[Container.watchlist_service]),
):
    args = body.model_dump()
    args["ticker"] = ticker
    args["mod_id"] = get_email()

    watchlist_service.update_watchlist(args)
    return UpdateOut()


@router.delete(
    "/{ticker}",
    response_model=DeleteOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def delete_watchlist(
    request: Request,
    ticker: str,
    watchlist_service: WatchlistService = Depends(Provide[Container.watchlist_service]),
):
    args = {"ticker": ticker}
    watchlist_service.delete_watchlist(args)
    return DeleteOut()
