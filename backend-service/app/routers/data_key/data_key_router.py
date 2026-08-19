"""데이터 소스 키 상태 — 「어디에 무엇을 넣어야 하나」 (#225).

**읽기 전용이고 값을 내지 않는다.** 키를 넣는 경로(`.env` 쓰기)는 승인 뒤 별도로 온다 —
그쪽은 앱이 파일을 쓰는 것이라 위험이 다른 층이다 (결정 로그 2026-08-19).
"""

from core.authorization import require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from schemas.data_key.data_key_schema import DataKeyStatusListOut
from services.data_key.data_key_service import DataKeyService

router = APIRouter(prefix="/data-key", tags=["data-key"])


@router.get(
    "",
    response_model=DataKeyStatusListOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
    operation_id="select_data_key_status",
)
@inject
def select_data_key_status(
    data_key_service: DataKeyService = Depends(Provide[Container.data_key_service]),
):
    rows = data_key_service.list_key_status()
    return DataKeyStatusListOut(items=rows, total_count=len(rows))
