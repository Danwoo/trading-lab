"""적재 잡 라우트 — 요청·상태 조회가 같은 표를 본다 (M2-AD-12).

FR-010("어디까지 받았고 무엇이 실패했는지 화면에서 보인다")이 별도 화면 API 가 아니라 이
목록 조회로 끝나는 이유가 그것이다.
"""

from core.auth_context import get_email, get_workspace_id
from core.authorization import ROLE_ADMIN, ROLE_OPERATOR, require_role, require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request
from schemas.common_schema import CreateOut
from schemas.ingest.ingest_schema import IngestRunCreateIn, IngestRunsOut
from services.ingest.ingest_service import IngestService
from utils.common.devextreme_utils import parse_filter_sort

router = APIRouter(prefix="/ingest-run", tags=["ingest-run"])


@router.get("", response_model=IngestRunsOut, dependencies=[Depends(verify_access_token), Depends(require_user)])
@inject
def select_ingest_run_list(
    request: Request,
    skip: int = Query(0),
    take: int | None = None,
    filter: str | None = None,
    sort: str | None = None,
    ingest_service: IngestService = Depends(Provide[Container.ingest_service]),
):
    filter_obj, sort_obj = parse_filter_sort(filter, sort)
    args = {"skip": skip, "take": take, "filter": filter_obj, "sort": sort_obj}

    items, total_count = ingest_service.select_ingest_run_list(args)
    return IngestRunsOut(items=items, total_count=total_count)


@router.post(
    "",
    response_model=CreateOut,
    dependencies=[Depends(verify_access_token), Depends(require_role(ROLE_ADMIN, ROLE_OPERATOR))],
)
@inject
def insert_ingest_run(
    request: Request,
    body: IngestRunCreateIn,
    ingest_service: IngestService = Depends(Provide[Container.ingest_service]),
):
    """수동 적재 요청 — 잡을 큐에 넣고 즉시 반환한다. 실행은 백그라운드 워커가 집어 간다."""
    args = body.model_dump()
    args["workspace_id"] = get_workspace_id()
    args["reg_id"] = get_email()

    run_id = ingest_service.enqueue(args)
    return CreateOut(data={"run_id": run_id})
