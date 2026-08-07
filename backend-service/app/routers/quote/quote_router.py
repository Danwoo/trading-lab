"""일괄 시세 라우트 (갈래 3).

`POST` 인 이유는 종목 목록이 URL 길이 한계에 닿을 수 있어서다 — 상태를 바꾸지 않는 조회이므로
캐시·재시도 관점의 성격은 GET 과 같다.
"""

from core.auth_context import get_workspace_id
from core.authorization import require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request
from schemas.quote.quote_schema import QuoteBatchIn, QuoteOut, QuotesOut
from services.quote.quote_batch_service import QuoteBatchService

router = APIRouter(prefix="/quote", tags=["quote"])


@router.post("/batch", response_model=QuotesOut, dependencies=[Depends(verify_access_token), Depends(require_user)])
@inject
async def select_quote_batch(
    request: Request,
    body: QuoteBatchIn,
    quote_batch_service: QuoteBatchService = Depends(Provide[Container.quote_batch_service]),
):
    symbols = [(item.market, item.symbol) for item in body.symbols]
    result = await quote_batch_service.quotes(get_workspace_id(), symbols)
    return QuotesOut(
        items=[QuoteOut(**row) for row in result["items"]],
        total_count=result["total_count"],
        source=result["source"],
        unavailable=result["unavailable"],
    )
