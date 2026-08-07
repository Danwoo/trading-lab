"""데이터 소스 capability 조회 — 패널이 "왜 비었는지"를 읽는 경로 (FR-013 · FR-021).

키가 없어도 이 라우트는 200 이다. 그것이 요점이다 — 기동도 응답도 막히지 않고, 못 하는 것이
사유와 함께 데이터로 나온다.
"""

from core.auth_context import get_workspace_id
from core.authorization import require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request
from schemas.capability.capability_schema import CapabilitiesOut, CapabilityOut
from services.capability.capability_service import CapabilityService

router = APIRouter(prefix="/market-capability", tags=["market-capability"])


@router.get("", response_model=CapabilitiesOut, dependencies=[Depends(verify_access_token), Depends(require_user)])
@inject
def select_capability_list(
    request: Request,
    market: str | None = Query(None, description="주면 그 시장만 — 없으면 전 시장"),
    capability_service: CapabilityService = Depends(Provide[Container.capability_service]),
):
    rows = capability_service.list_capabilities(get_workspace_id(), market)
    return CapabilitiesOut(items=[CapabilityOut(**row) for row in rows], total_count=len(rows))
