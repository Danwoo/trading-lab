"""백테스트 라우트 — 실행이 곧 격자 실행이고(D-Q1), 칸 클릭은 조회다 (#203).

단일 실행이 따로 있는 이유는 격자의 한 칸을 계보(`parent_run_id`)에 이어 다시 볼 때다 —
새 탐색은 `/grid` 로 시작한다.
"""

from core.auth_context import get_email, get_workspace_id
from core.authorization import ROLE_ADMIN, ROLE_OPERATOR, require_role, require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from schemas.backtest.backtest_schema import (
    BacktestGridIn,
    BacktestRunIn,
    BotRunListOut,
    GridOut,
    RunCreatedOut,
    RunReportOut,
)
from services.backtest.backtest_service import BacktestService

router = APIRouter(prefix="/backtest-run", tags=["backtest-run"])


@router.post(
    "",
    response_model=RunCreatedOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def insert_backtest_run(
    body: BacktestRunIn,
    backtest_service: BacktestService = Depends(Provide[Container.backtest_service]),
):
    args = body.model_dump()
    args["workspace_id"] = get_workspace_id()
    args["reg_id"] = get_email()
    return RunCreatedOut(**backtest_service.run(args))


@router.post(
    "/grid",
    response_model=GridOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def insert_backtest_grid(
    body: BacktestGridIn,
    backtest_service: BacktestService = Depends(Provide[Container.backtest_service]),
):
    args = body.model_dump()
    args["workspace_id"] = get_workspace_id()
    args["reg_id"] = get_email()
    return GridOut(**backtest_service.run_grid(args))


@router.get(
    "/by-bot/{bot_id}",
    response_model=BotRunListOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
    operation_id="select_backtest_runs_by_bot",
)
@inject
def select_backtest_runs_by_bot(
    bot_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    backtest_service: BacktestService = Depends(Provide[Container.backtest_service]),
):
    """한 봇의 검증 이력. `/{run_id}` 보다 위에 둔다 — 아래 두면 `by-bot` 이 run_id 로 먹힌다."""
    return BotRunListOut(
        **backtest_service.select_runs_by_bot(
            {"bot_id": bot_id, "workspace_id": get_workspace_id(), "limit": limit}
        )
    )


@router.get(
    "/{run_id}",
    response_model=RunReportOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
)
@inject
def select_backtest_report(
    run_id: int,
    backtest_service: BacktestService = Depends(Provide[Container.backtest_service]),
):
    return RunReportOut(**backtest_service.select_report({"run_id": run_id, "workspace_id": get_workspace_id()}))
