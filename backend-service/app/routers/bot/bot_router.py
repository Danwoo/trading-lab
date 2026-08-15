# router/bot_router.py
from core.auth_context import get_email
from core.authorization import ROLE_ADMIN, ROLE_OPERATOR, require_role, require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request
from schemas.bot.bot_schema import (
    BotCreateIn,
    BotDetailOut,
    BotsOut,
    BotUpdateIn,
    StrategyCatalogOut,
)
from schemas.common_schema import CreateOut, DeleteOut, UpdateOut
from services.bot.bot_service import BotService
from utils.common.devextreme_utils import parse_filter_sort

router = APIRouter(prefix="/bot", tags=["bot"])


@router.get(
    "/strategy-catalog",
    response_model=StrategyCatalogOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
)
@inject
def select_strategy_catalog(
    request: Request,
    bot_service: BotService = Depends(Provide[Container.bot_service]),
):
    """전략 파일이 선언한 것에서 만든 폼 스키마 목록. 봇 만들기 화면의 재료다."""
    return bot_service.select_strategy_catalog()


@router.get("", response_model=BotsOut, dependencies=[Depends(verify_access_token), Depends(require_user)])
@inject
def select_bot_list(
    request: Request,
    skip: int = Query(0),
    take: int | None = None,
    filter: str | None = None,
    sort: str | None = None,
    bot_service: BotService = Depends(Provide[Container.bot_service]),
):
    filter_obj, sort_obj = parse_filter_sort(filter, sort)
    args = {"skip": skip, "take": take, "filter": filter_obj, "sort": sort_obj}

    items, total_count = bot_service.select_bot_list(args)
    return BotsOut(items=items, total_count=total_count)


@router.post(
    "",
    response_model=CreateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def insert_bot(
    request: Request,
    body: BotCreateIn,
    bot_service: BotService = Depends(Provide[Container.bot_service]),
):
    args = body.model_dump()
    args["reg_id"] = get_email()

    keys = bot_service.insert_bot(args)
    return CreateOut(data={"bot_id": keys[0]} if keys else None)


@router.get(
    "/{bot_id}", response_model=BotDetailOut, dependencies=[Depends(verify_access_token), Depends(require_user)]
)
@inject
def select_bot(
    request: Request,
    bot_id: int,
    bot_service: BotService = Depends(Provide[Container.bot_service]),
):
    return bot_service.select_bot({"bot_id": bot_id})


@router.put(
    "/{bot_id}",
    response_model=UpdateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def update_bot(
    request: Request,
    bot_id: int,
    body: BotUpdateIn,
    bot_service: BotService = Depends(Provide[Container.bot_service]),
):
    args = body.model_dump()
    args["bot_id"] = bot_id
    args["mod_id"] = get_email()

    bot_service.update_bot(args)
    return UpdateOut()


@router.delete(
    "/{bot_id}",
    response_model=DeleteOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def delete_bot(
    request: Request,
    bot_id: int,
    bot_service: BotService = Depends(Provide[Container.bot_service]),
):
    bot_service.delete_bot({"bot_id": bot_id})
    return DeleteOut()
