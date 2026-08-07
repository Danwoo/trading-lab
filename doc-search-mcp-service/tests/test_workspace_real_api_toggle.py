"""#190 — WORKSPACE_REAL_API 토글 분리 검증 (config 단위, MOCK/실 4조합 매트릭스).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_workspace_real_api_toggle.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식:
- 미설정이면 USE_REAL_API 상속 — 토글 하나만 쓰던 기존 배포는 동작 무변경.
- 명시하면 워크스페이스(pgvector)와 큐레이션(Milvus, USE_REAL_API)이 독립으로 갈린다.
- 빈 문자열은 조용한 오동작 대신 기동 실패(fail-fast).
컨테이너 배선(워크스페이스만 WORKSPACE_REAL_API 를 받는지)은 별도 함수로 소스 수준 확인한다 —
런타임 2케이스(ingest 가 pg 에 쓰고 / 큐레이션 tool 은 MOCK 유지)는 #190 검증 로그가 실증한다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Settings 가 env_file(.env.{APP_ENV})을 읽는다 — 존재하지 않는 이름을 줘 파일 간섭을 끊고,
# 비-dev 필수인 JWT_SECRET 은 env 로 채운다.
os.environ["APP_ENV"] = "toggle-test"
os.environ.setdefault("JWT_SECRET", "test-secret")

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.config import Settings  # noqa: E402


def _settings(**env: str) -> Settings:
    """env 조합으로 Settings 를 만든다 — 케이스 간 누수가 없도록 대상 키를 매번 재설정."""
    for key in ("USE_REAL_API", "WORKSPACE_REAL_API"):
        os.environ.pop(key, None)
    os.environ.update(env)
    return Settings()


def test_unset_inherits_use_real_api() -> str:
    """미설정 → USE_REAL_API 상속 (기존 배포 무영향 — 4조합 중 상속 2조합)."""
    assert _settings(USE_REAL_API="false").WORKSPACE_REAL_API is False, "false 상속 실패"
    assert _settings(USE_REAL_API="true").WORKSPACE_REAL_API is True, "true 상속 실패"
    return "test_unset_inherits_use_real_api"


def test_explicit_value_splits_toggles() -> str:
    """명시 → 두 토글이 독립 (4조합 중 분리 2조합 — 핵심은 워크스페이스만 실모드)."""
    s = _settings(USE_REAL_API="false", WORKSPACE_REAL_API="true")
    assert s.USE_REAL_API is False and s.WORKSPACE_REAL_API is True, "워크스페이스만 실모드 분리 실패"
    s = _settings(USE_REAL_API="true", WORKSPACE_REAL_API="false")
    assert s.USE_REAL_API is True and s.WORKSPACE_REAL_API is False, "큐레이션만 실모드 분리 실패"
    return "test_explicit_value_splits_toggles"


def test_empty_string_fails_fast() -> str:
    """빈 문자열(WORKSPACE_REAL_API=)은 bool 파싱 실패로 기동 거부 — 조용한 오동작 방지."""
    try:
        _settings(USE_REAL_API="false", WORKSPACE_REAL_API="")
    except Exception:
        os.environ.pop("WORKSPACE_REAL_API", None)
        return "test_empty_string_fails_fast"
    raise AssertionError("빈 문자열인데 기동됨 — fail-fast 가 아님")


def test_container_wires_workspace_toggle_only() -> str:
    """컨테이너 배선 — 워크스페이스만 WORKSPACE_REAL_API, 큐레이션은 USE_REAL_API (소스 수준)."""
    source = (_APP_DIR / "core" / "container.py").read_text(encoding="utf-8")
    assert "use_real_api=config.provided.WORKSPACE_REAL_API" in source, "workspace_service 배선 누락"
    assert "use_real_api=config.provided.USE_REAL_API" in source, "vector_search_service 배선 소실"
    return "test_container_wires_workspace_toggle_only"


def _main() -> int:
    tests = [
        test_unset_inherits_use_real_api,
        test_explicit_value_splits_toggles,
        test_empty_string_fails_fast,
        test_container_wires_workspace_toggle_only,
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
