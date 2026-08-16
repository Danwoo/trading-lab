"""권한 게이팅 의존성 — 이 서비스는 **쓰기 권한자만** 대화를 걸 수 있다.

`verify_access_token` 이 신원을 ContextVar 에 박은 뒤 실행되는 라우터 레벨 Depends 다.
정본 규약은 `backend-service/app/core/authorization.py` 이고, 여기서는 이 서비스가 쓰는
부분만 둔다 (이 서비스에는 사용자 데이터 라우트가 없어 읽기 게이트가 필요 없다).

**왜 이 서비스에 게이트가 필요한가** — 대화 한 턴은 기계 소유자의 LLM 자격증명을 소모한다.
개인 워크스페이스 모델은 **읽기전용 게스트 초대**를 전제로 하므로(루트 CLAUDE.md), 게이트가
없으면 초대받은 게스트가 소유자의 자격증명을 태울 수 있다.
"""

from core.auth_context import get_role, get_workspace_id, is_service_token
from core.exceptions import ForbiddenError, UnauthorizedError

ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_USER = "user"

WRITE_ROLES = (ROLE_ADMIN, ROLE_OPERATOR)


def require_role(*allowed_roles: str):
    """지정 role 만 허용하는 의존성 팩토리."""

    async def _dependency() -> None:
        if is_service_token():
            raise ForbiddenError("서비스 토큰으로는 대화를 걸 수 없습니다.")
        if get_workspace_id() is None:
            raise UnauthorizedError()
        if get_role() not in allowed_roles:
            raise ForbiddenError("이 작업을 수행할 권한이 없습니다.")

    return _dependency
