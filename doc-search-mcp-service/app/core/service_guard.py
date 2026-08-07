"""doc-search 로컬 서비스-토큰 게이트 — 인제스트 등 내부 쓰기 경로 전용.

이 게이트를 core/security.py 에 두지 않는 이유: security.py 는 verify_auth_lockstep.py 가
전 *-service 에 대해 backend-service 와 byte-identical 을 강제하는 락스텝 대상이라, 이
서비스에만 필요한 고유 게이트를 넣을 수 없다. 그래서 락스텝 대상이 아닌 로컬 모듈로 분리한다.
(is_service_token 은 공유 auth_context 에, ForbiddenError 는 공유 exceptions 에 이미 존재.)
"""

from core.auth_context import is_service_token
from core.exceptions import ForbiddenError


def require_service_token() -> None:
    """서비스 토큰(typ=service) 전용 게이트 — 내부 쓰기 경로(인제스트)에 건다.

    라우터 레벨 verify_access_token 이 먼저 실행돼 신원 컨텍스트(is_service)를 채운 뒤 이 검사가 돈다.
    서비스 토큰이 아니면(유효 JWT 라도 일반 사용자·에이전트) ForbiddenError(403) — 사용자가 임의
    workspace_id 로 타 테넌트 코퍼스를 오염시키는 것을 도구 표면에서 차단한다(design-160 AD-1).
    """
    if not is_service_token():
        raise ForbiddenError()
