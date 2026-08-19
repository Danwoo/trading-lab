"""데이터 소스 키 상태 — 「어디에 무엇을 넣어야 하나」 (#225).

**읽기 전용이고 값을 내지 않는다.** 키를 넣는 경로(`.env` 쓰기)는 승인 뒤 별도로 온다 —
그쪽은 앱이 파일을 쓰는 것이라 위험이 다른 층이다 (결정 로그 2026-08-19).
"""

from core.authorization import require_user
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from schemas.data_key.data_key_schema import (
    DataKeyProbeOut,
    DataKeySaveIn,
    DataKeySaveOut,
    DataKeyStatusListOut,
)
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


@router.post(
    "/probe",
    response_model=DataKeyProbeOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
    operation_id="probe_data_key",
)
@inject
async def probe_data_key(
    body: DataKeySaveIn,
    data_key_service: DataKeyService = Depends(Provide[Container.data_key_service]),
):
    """넣으려는 값으로 소스에 한 번 물어본다 — **저장 전에** 확인할 수 있게.

    저장 뒤에 확인하려면 재기동이 필요하다(설정은 기동 시 읽는다). 그래서 값을 그대로
    태워 저장 전에 답을 준다.
    """
    return DataKeyProbeOut(**await data_key_service.probe_key(body.source, body.value))


@router.put(
    "",
    response_model=DataKeySaveOut,
    dependencies=[Depends(verify_access_token), Depends(require_user)],
    operation_id="save_data_key",
)
@inject
def save_data_key(
    body: DataKeySaveIn,
    data_key_service: DataKeyService = Depends(Provide[Container.data_key_service]),
):
    """키를 이 서비스의 `.env` 에 쓴다 — 로컬 개발에서만 열린다.

    `PUT` 인 이유: 같은 소스에 두 번 보내면 결과가 같다(그 변수 한 줄이 그 값이 된다).
    """
    return DataKeySaveOut(**data_key_service.save_key(body.source, body.value))
