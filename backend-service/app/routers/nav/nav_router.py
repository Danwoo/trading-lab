# routers/nav/nav_router.py
from core.authorization import require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request
from schemas.nav.nav_schema import NavHistoryOut
from services.nav.nav_service import NavService

router = APIRouter(prefix="/nav", tags=["nav"])


@router.get(
    "/history",
    response_model=NavHistoryOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
)
@inject
def select_nav_history(
    request: Request,
    minutes: int = Query(30, ge=1, le=2880),
    nav_service: NavService = Depends(Provide[Container.nav_service]),
):
    items, total_count = nav_service.select_history(minutes)
    return NavHistoryOut(items=items, total_count=total_count)
