"""데이터 소스 키 — 상태는 누구나 읽고, **넣는 것은 시스템관리자만** 한다 (#225·#344).

읽기(`GET`)와 쓰기(`PUT`·`POST /probe`)의 관문이 다르다. 읽기는 값을 내지 않아 부작용이
없지만, 쓰기는 **이 설치를 쓰는 모두**에게 간다 — `.env` 한 줄은 워크스페이스에 속하지
않는 프로세스 전역 설정이고, 되돌릴 사본도 남기지 않는다(`utils/env_file/env_writer.py`).

그래서 `operator` 도 제외한다. `operator` 의 범위는 자기 워크스페이스이고, 전역에 미치는
변경은 이 레포에서 이미 시스템관리자 전용이다 (`frontend/constants/protected.ts` 의
권한관리 주석 — "전역(워크스페이스 무관) … 모든 워크스페이스에 영향이라 시스템관리자 전용").

`POST /probe` 도 쓰기 쪽이다. 값을 파일에 남기지는 않지만 이 설치의 이름으로 외부 소스를
호출해 한도를 쓰고, 합성 자격에서는 **이미 저장된 나머지 반쪽**을 함께 태워 그것이 통하는지
알려준다 — 저장된 비밀에 대한 신탁(oracle)이다.
"""

from core.authorization import ROLE_ADMIN, require_role, require_user
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

#: `.env` 를 건드리는 쪽의 관문. 이름을 한 번만 적어 두 라우트가 갈라지지 않게 한다.
require_key_writer = require_role(ROLE_ADMIN)


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
    dependencies=[Depends(verify_access_token), Depends(require_key_writer)],
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
    return DataKeyProbeOut(**await data_key_service.probe_key(body.source, body.value, body.setting))


@router.put(
    "",
    response_model=DataKeySaveOut,
    dependencies=[Depends(verify_access_token), Depends(require_key_writer)],
    operation_id="save_data_key",
)
@inject
def save_data_key(
    body: DataKeySaveIn,
    data_key_service: DataKeyService = Depends(Provide[Container.data_key_service]),
):
    """키를 이 서비스의 `.env` 에 쓴다 — 로컬 개발에서, 시스템관리자만.

    `PUT` 인 이유: 같은 소스에 두 번 보내면 결과가 같다(그 변수 한 줄이 그 값이 된다).
    """
    return DataKeySaveOut(**data_key_service.save_key(body.source, body.value, body.setting))
