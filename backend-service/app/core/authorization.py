"""권한 게이팅 의존성 (admin / operator / user 3종 모델).

`verify_access_token` 이 신원을 ContextVar 에 박은 뒤 실행되는 라우터 레벨 Depends.
- 서비스 토큰(`typ=service`, workspace_id 없음)은 사용자 데이터 라우트에서 거부 (fail-closed).
- 테넌트 격리는 workspace_id 필수 — 미설정 시 401.
"""

from core.auth_context import get_role, get_workspace_id, is_service_token
from core.exceptions import ForbiddenError, UnauthorizedError

ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"
ROLE_USER = "user"

WRITE_ROLES = (ROLE_ADMIN, ROLE_OPERATOR)


def _ensure_tenant_user() -> None:
    if is_service_token():
        raise ForbiddenError("서비스 토큰으로는 사용자 데이터에 접근할 수 없습니다.")
    if get_workspace_id() is None:
        raise UnauthorizedError()


async def require_user() -> None:
    """인증된 테넌트 사용자 (서비스 토큰 거부 + workspace_id 필수). 읽기 라우트 기본 게이트."""
    _ensure_tenant_user()


def require_role(*allowed_roles: str):
    """지정 role 만 허용하는 의존성 팩토리 (쓰기 라우트: operator/admin)."""

    async def _dependency() -> None:
        _ensure_tenant_user()
        if get_role() not in allowed_roles:
            raise ForbiddenError("이 작업을 수행할 권한이 없습니다.")

    return _dependency
