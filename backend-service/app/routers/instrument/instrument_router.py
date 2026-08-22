"""종목 마스터 검색 라우트 — 터미널이 종목을 고르는 자리 (#318).

`/bar` 는 종목을 **이미 안다는 전제**로 `(market, symbol)` 을 받는다. 그 전제를 세워 주는 것이
이 라우트다: 사람이 아는 말(종목명)로 마스터를 훑어 코드를 찾아 준다.
"""

from core.authorization import require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request
from schemas.instrument.instrument_schema import InstrumentsOut
from services.instrument.instrument_service import InstrumentService

router = APIRouter(prefix="/instrument", tags=["instrument"])


@router.get("", response_model=InstrumentsOut, dependencies=[Depends(verify_access_token), Depends(require_user)])
@inject
def select_instrument_list(
    request: Request,
    q: str | None = Query(None, description="종목명 또는 종목코드의 일부 — 비우면 앞에서부터"),
    market: str | None = Query(None, description="주면 그 시장만 — KOSPI·KOSDAQ·NASDAQ·NYSE 등"),
    skip: int = Query(0),
    take: int | None = Query(None, description="한 번에 받을 종목 수 — 기본 20, 최대 100"),
    instrument_service: InstrumentService = Depends(Provide[Container.instrument_service]),
):
    args = {"q": q, "market": market, "skip": skip, "take": take}
    return InstrumentsOut(**instrument_service.select_instrument_list(args))
