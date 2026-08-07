"""#234 — 워크스페이스 pgvector AsyncEngine 도 바인딩 파라미터를 예외 문자열에 남기지 않는지 검증.

doc-search 는 동기 database_utils 대신 자체 create_async_engine 을 쓰는 유일한 서비스라
(design-160-pgvector-delta §1) 같은 처방이 따로 걸려 있어야 한다 — 여기만 빠지면 문서 인제스트
경로의 청크 텍스트가 트레이스백으로 새어 나간다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_workspace_engine_hides_parameters.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

CI 배선: .github/workflows/repo-scans.yml 의 `test: repo-scan-app` 잡(경로 필터 없는 전수
스캔) + ci.yml 의 `test: mcp-services` 스위트(tests/ 글롭). 테스트만 있고 잡이 없으면
그물은 초록으로 죽는다 — 이 파일을 옮기거나 이름을 바꾸면 그 잡도 같이 고쳐야 한다.

외부 DB 없이 돈다 — create_async_engine 은 lazy 라 접속하지 않는다.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Settings 가 env_file(.env.{APP_ENV})을 읽는다 — 존재하지 않는 이름을 줘 파일 간섭을 끊는다.
os.environ["APP_ENV"] = "param-hiding-test"
os.environ.setdefault("JWT_SECRET", "test-secret")

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from clients.postgres.postgres_client import get_workspace_engine  # noqa: E402


@dataclass
class _StubConfig:
    """get_workspace_engine 이 읽는 필드만 가진 최소 config (접속은 lazy 라 실제 DB 불필요)."""

    DOC_VECTOR_DB_HOST: str = "127.0.0.1"
    DOC_VECTOR_DB_PORT: int = 5432
    DOC_VECTOR_DB_NAME: str = "unused"
    DOC_VECTOR_DB_USER: str = "unused"
    DOC_VECTOR_DB_PASSWORD: str = "unused"


def test_workspace_engine_sets_hide_parameters() -> str:
    """엔진에 hide_parameters 가 켜져 있다 (StatementError 문자열에서 바인딩 값 제거)."""
    engine = get_workspace_engine(_StubConfig())
    assert engine is not None, "host 를 줬는데 엔진이 None — 팩토리가 조용히 실패했다"
    assert engine.sync_engine.hide_parameters is True, "AsyncEngine 에 hide_parameters=True 가 없음"
    return "test_workspace_engine_sets_hide_parameters"


def test_missing_host_still_fails_soft() -> str:
    """host 미설정이면 여전히 None — 처방이 fail-soft 기동(#190)을 깨지 않았다."""
    assert get_workspace_engine(_StubConfig(DOC_VECTOR_DB_HOST="")) is None, "host 없는데 엔진이 생겼다"
    return "test_missing_host_still_fails_soft"


def _main() -> int:
    tests = [
        test_workspace_engine_sets_hide_parameters,
        test_missing_host_still_fails_soft,
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
