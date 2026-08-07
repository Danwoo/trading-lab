"""캔들 조회 라우트 (갈래 1 — 적재본 읽기).

**anti-patterns 룰 6(페이지네이션)의 해석**: 차트는 페이지가 아니라 **기간 윈도**로 자른다.
`skip/take` 로 캔들을 넘기는 소비자는 존재하지 않고(스크롤은 기간을 옮긴다), 그래서 이 라우트는
`date_from`·`date_to` 필수 + `limit` 상한을 페이지네이션 자리에 둔다. 상한을 넘는 요청은 조용히
잘리지 않고 400 이다 — 잘린 캔들로 그린 차트는 틀린 차트다.

기존 MCP `market_ohlc`(최신순 1~120)와 **섞지 않는다**. 그쪽은 LLM 컨텍스트 보호가 목적인 별개
계약이고(구현설계 §5.3), 이 라우트가 "기간 지정 조회"의 자리다.
"""

import datetime as dt

from core.auth_context import get_workspace_id
from core.authorization import require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request
from schemas.bar.bar_schema import BarsOut, GapsOut
from services.bar.bar_service import BarService

router = APIRouter(prefix="/bar", tags=["bar"])


@router.get("/daily", response_model=BarsOut, dependencies=[Depends(verify_access_token), Depends(require_user)])
@inject
def select_daily_bar_list(
    request: Request,
    market: str = Query(..., description="KOSPI·KOSDAQ·KONEX·NASDAQ·NYSE·AMEX"),
    symbol: str = Query(..., description="국내 6자리 종목코드 또는 미국 티커"),
    date_from: dt.date = Query(...),
    date_to: dt.date = Query(...),
    limit: int | None = Query(None),
    bar_service: BarService = Depends(Provide[Container.bar_service]),
):
    args = {
        "market": market,
        "symbol": symbol,
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
        "workspace_id": get_workspace_id(),
    }
    return BarsOut(**bar_service.select_daily_bar_list(args))


@router.get("/minute", response_model=BarsOut, dependencies=[Depends(verify_access_token), Depends(require_user)])
@inject
def select_minute_bar_list(
    request: Request,
    market: str = Query(...),
    symbol: str = Query(...),
    ts_from: dt.datetime = Query(...),
    ts_to: dt.datetime = Query(...),
    interval_min: int = Query(1, description="1·5·15·30·60 — 1분봉에서 합성한다"),
    limit: int | None = Query(None),
    bar_service: BarService = Depends(Provide[Container.bar_service]),
):
    args = {
        "market": market,
        "symbol": symbol,
        "ts_from": ts_from,
        "ts_to": ts_to,
        "interval_min": interval_min,
        "limit": limit,
        "workspace_id": get_workspace_id(),
    }
    return BarsOut(**bar_service.select_minute_bar_list(args))


@router.get("/gaps", response_model=GapsOut, dependencies=[Depends(verify_access_token), Depends(require_user)])
@inject
def select_bar_gaps(
    request: Request,
    market: str = Query(...),
    symbol: str = Query(...),
    date_from: dt.date = Query(...),
    date_to: dt.date = Query(...),
    bar_service: BarService = Depends(Provide[Container.bar_service]),
):
    """캘린더상 거래일인데 적재본에 없는 날짜 — 결측과 휴장을 가른다 (MD-AD-23)."""
    args = {"market": market, "symbol": symbol, "date_from": date_from, "date_to": date_to}
    return GapsOut(**bar_service.find_gaps(args))
