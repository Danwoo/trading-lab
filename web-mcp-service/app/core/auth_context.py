"""인증 신원 컨텍스트 (ContextVar).

JWT 에서 확정한 요청자 신원(user_id/email/role/workspace_id)을 요청 단위로 보관한다.
verify_access_token 이 요청 진입 시 set 하고, service/permission 계층이 인자 드릴링 없이 읽는다.
- 각 요청은 자체 task(=자체 context copy)에서 실행되므로 요청 간 값 누수 없음.
- run_in_threadpool 은 context 를 복사하므로 sync DB 작업에서도 동일 값을 본다.
- 미설정(요청 밖 호출) 시 None → 권한 계층에서 fail-closed 처리.
"""

from contextvars import ContextVar

from core.exceptions import UnauthorizedError

_user_id: ContextVar[str | None] = ContextVar("auth_user_id", default=None)
_email: ContextVar[str | None] = ContextVar("auth_email", default=None)
_role: ContextVar[str | None] = ContextVar("auth_role", default=None)
_workspace_id: ContextVar[int | None] = ContextVar("auth_workspace_id", default=None)
_is_service: ContextVar[bool] = ContextVar("auth_is_service", default=False)


def set_auth_context(
    *,
    user_id: str | None,
    role: str | None,
    workspace_id: int | None,
    email: str | None = None,
    is_service: bool = False,
) -> None:
    _user_id.set(user_id)
    _email.set(email)
    _role.set(role)
    _workspace_id.set(workspace_id)
    _is_service.set(is_service)


def get_user_id() -> str | None:
    return _user_id.get()


def get_email() -> str | None:
    return _email.get()


def get_role() -> str | None:
    return _role.get()


def get_workspace_id() -> int | None:
    return _workspace_id.get()


def is_service_token() -> bool:
    return _is_service.get()


def require_workspace_id() -> int:
    """테넌트 격리 쿼리용 workspace_id 를 fail-closed 로 반환 (미설정=요청 밖/서비스 토큰 → 401)."""
    workspace_id = _workspace_id.get()
    if workspace_id is None:
        raise UnauthorizedError()
    return workspace_id
