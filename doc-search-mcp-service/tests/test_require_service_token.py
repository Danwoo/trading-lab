"""#160 슬라이스 A B1 — 인제스트 서비스-토큰 게이트(require_service_token) 인가 회귀 방지.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    JWT_SECRET=x SERVICE_NAME=doc-search-mcp uv run python tests/test_require_service_token.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상: verify_access_token 이 채운 신원 컨텍스트(is_service)를 보고, 서비스 토큰(typ=service)만
통과시키고 유효 JWT 를 든 일반 사용자·에이전트는 ForbiddenError(403)로 막는다는 불변식.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# core.config 가 import 시점에 Settings()를 만든다 — 비-dev 에서 빈 JWT_SECRET 이면 기동 거부되므로 먼저 채운다.
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("SERVICE_NAME", "doc-search-mcp")

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.auth_context import set_auth_context  # noqa: E402
from core.exceptions import ForbiddenError  # noqa: E402
from core.service_guard import require_service_token  # noqa: E402


def test_service_token_passes_gate() -> str:
    """서비스 토큰(is_service=True) 컨텍스트는 예외 없이 통과한다 — backend 오케스트레이터 경로."""
    set_auth_context(user_id="doc-search-mcp", role=None, workspace_id=None, is_service=True)
    require_service_token()  # ForbiddenError 가 나면 안 됨
    return "test_service_token_passes_gate"


def test_user_token_is_forbidden() -> str:
    """유효 JWT 라도 사용자 토큰(is_service=False)이면 ForbiddenError(403) — 타 테넌트 오염 차단."""
    set_auth_context(user_id="user-42", role="user", workspace_id=7, is_service=False)
    try:
        require_service_token()
    except ForbiddenError as exc:
        assert exc.status_code == 403, f"403 이어야 함: {exc.status_code}"
        return "test_user_token_is_forbidden"
    raise AssertionError("사용자 토큰인데 ForbiddenError 가 발생하지 않음 — 게이트가 열려 있음")


def test_missing_context_is_forbidden() -> str:
    """신원 미설정(요청 밖/컨텍스트 누락, is_service 기본 False)도 fail-closed 로 막힌다."""
    set_auth_context(user_id=None, role=None, workspace_id=None, is_service=False)
    try:
        require_service_token()
    except ForbiddenError:
        return "test_missing_context_is_forbidden"
    raise AssertionError("컨텍스트 미설정인데 통과함 — fail-closed 가 아님")


def _main() -> int:
    tests = [
        test_service_token_passes_gate,
        test_user_token_is_forbidden,
        test_missing_context_is_forbidden,
    ]
    passed = 0
    for tc in tests:
        name = tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
