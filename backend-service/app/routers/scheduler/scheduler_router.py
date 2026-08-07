# routers/scheduler/scheduler_router.py
from core.auth_context import get_email, set_auth_context
from core.authorization import ROLE_ADMIN, ROLE_OPERATOR, require_role, require_user
from core.container import Container
from core.logger import logger
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from managers.scheduler_manager import scheduler_manager
from schemas.common_schema import CreateOut, DeleteOut, MessageOut, UpdateOut
from schemas.scheduler.scheduler_schema import (
    SchedulerCreateIn,
    SchedulerMemberIn,
    SchedulerMembersOut,
    SchedulerOut,
    SchedulersOut,
    SchedulerUpdateIn,
)
from services.report.activity_report_service import ActivityReportService
from services.scheduler.scheduler_service import SchedulerService
from utils.common.devextreme_utils import parse_filter_sort

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get(
    "",
    response_model=SchedulersOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
)
@inject
def select_scheduler_list(
    request: Request,
    skip: int = Query(0),
    take: int | None = None,
    filter: str | None = None,
    sort: str | None = None,
    scheduler_service: SchedulerService = Depends(Provide[Container.scheduler_service]),
):
    filter_obj, sort_obj = parse_filter_sort(filter, sort)
    args = {"skip": skip, "take": take, "filter": filter_obj, "sort": sort_obj}
    items, total_count = scheduler_service.select_scheduler_list(args)
    return SchedulersOut(items=items, total_count=total_count)


@router.post(
    "",
    response_model=CreateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def insert_scheduler(
    request: Request,
    body: SchedulerCreateIn,
    scheduler_service: SchedulerService = Depends(Provide[Container.scheduler_service]),
):
    args = body.model_dump()
    args["reg_id"] = get_email()
    keys = scheduler_service.insert_scheduler(args)
    scheduler_manager.sync(args["scheduler_id"])
    return CreateOut(data={"scheduler_id": keys[0]} if keys else None)


@router.get(
    "/{scheduler_id}",
    response_model=SchedulerOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
)
@inject
def select_scheduler(
    request: Request,
    scheduler_id: str,
    scheduler_service: SchedulerService = Depends(Provide[Container.scheduler_service]),
):
    return scheduler_service.select_scheduler({"scheduler_id": scheduler_id})


@router.put(
    "/{scheduler_id}",
    response_model=UpdateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def update_scheduler(
    request: Request,
    scheduler_id: str,
    body: SchedulerUpdateIn,
    scheduler_service: SchedulerService = Depends(Provide[Container.scheduler_service]),
):
    args = body.model_dump()
    args["scheduler_id"] = scheduler_id
    args["mod_id"] = get_email()
    scheduler_service.update_scheduler(args)
    scheduler_manager.sync(scheduler_id)
    return UpdateOut()


@router.delete(
    "/{scheduler_id}",
    response_model=DeleteOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def delete_scheduler(
    request: Request,
    scheduler_id: str,
    scheduler_service: SchedulerService = Depends(Provide[Container.scheduler_service]),
):
    scheduler_service.delete_scheduler({"scheduler_id": scheduler_id})
    scheduler_manager.unregister(scheduler_id)
    return DeleteOut()


@router.get(
    "/{scheduler_id}/member",
    response_model=SchedulerMembersOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
)
@inject
def select_member_list(
    request: Request,
    scheduler_id: str,
    sort: str | None = None,
    scheduler_service: SchedulerService = Depends(Provide[Container.scheduler_service]),
):
    args = {"scheduler_id": scheduler_id, "sort": parse_filter_sort(None, sort)[1]}
    items, total_count = scheduler_service.select_member_list(args)
    return SchedulerMembersOut(items=items, total_count=total_count)


@router.post(
    "/{scheduler_id}/member",
    response_model=CreateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
async def insert_member(
    request: Request,
    scheduler_id: str,
    body: SchedulerMemberIn,
    scheduler_service: SchedulerService = Depends(Provide[Container.scheduler_service]),
):
    args = body.model_dump()
    args["scheduler_id"] = scheduler_id
    args["reg_id"] = get_email()
    await scheduler_service.insert_member(args)
    return CreateOut(data={"account_id": args["account_id"]})


@router.delete(
    "/{scheduler_id}/member/{account_id}",
    response_model=DeleteOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def delete_member(
    request: Request,
    scheduler_id: str,
    account_id: str,
    scheduler_service: SchedulerService = Depends(Provide[Container.scheduler_service]),
):
    scheduler_service.delete_member({"scheduler_id": scheduler_id, "account_id": account_id})
    return DeleteOut()


@router.post(
    "/{scheduler_id}/run",
    response_model=MessageOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
async def run_scheduler_now(
    request: Request,
    scheduler_id: str,
    background_tasks: BackgroundTasks,
    scheduler_service: SchedulerService = Depends(Provide[Container.scheduler_service]),
    activity_report_service: ActivityReportService = Depends(Provide[Container.activity_report_service]),
):
    scheduler = scheduler_service.select_scheduler({"scheduler_id": scheduler_id})
    members = scheduler_service.members_for_run(scheduler_id)
    if not members:
        return MessageOut(message="등록된 발송 대상이 없습니다. 참여 멤버를 먼저 등록해 주세요.", level="warning")
    since, until = activity_report_service.period(scheduler["period_weeks"])
    workspace_id = scheduler[
        "workspace_id"
    ]  # 소유 검증된 스케줄러의 워크스페이스 — 백그라운드 태스크에서 신원 컨텍스트 복원용

    async def _run() -> None:
        try:
            # 백그라운드 태스크는 요청 신원 컨텍스트를 보장받지 못한다 — 하류 MCP on-behalf 토큰이
            # 스케줄러 소속 워크스페이스로 스코핑되도록 workspace_id 를 명시 복원한다 (cron 경로와 동일).
            set_auth_context(user_id=None, role=None, workspace_id=workspace_id)
            async for _msg in activity_report_service.generate_for(members, since, until):
                pass
        except Exception as e:
            logger.warning(f"[스케줄러 {scheduler_id}] 수동 실행 실패: {e}")

    background_tasks.add_task(_run)
    return MessageOut(message="발송을 시작했습니다. 잠시 후 메일이 전송됩니다.")
