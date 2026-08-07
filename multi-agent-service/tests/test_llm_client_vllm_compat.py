"""#188 Phase C 회귀 방지 — router/planner 의 vLLM 전용 extra_body 전송이 토글로 제어됨을 확인.

vLLM 전용 chat_template_kwargs 를 무조건 보내면 Groq 등 상용 OpenAI 호환 API 가 400 으로
거부해 plan·guardrail·clarify 가 전멸한다. ROUTER_LLM_VLLM_COMPAT 토글(기본 true)로
전송 여부를 가른다 — true 면 기존 vLLM 배포와 동일, false 면 extra_body 미전송.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_llm_client_vllm_compat.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

# app 소스 루트(절대 import)와 dev 설정을 app 모듈 import 전에 준비한다.
os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from clients.llm.llm_client import _NO_THINKING, get_planner_llm, get_router_llm  # noqa: E402
from core.config import Settings  # noqa: E402


def _config(vllm_compat: bool) -> SimpleNamespace:
    """팩토리가 읽는 필드만 가진 최소 config 더블 (실서버 접속 없음 — 생성만 검증)."""
    return SimpleNamespace(
        ROUTER_LLM_BASE_URL="http://localhost:9/v1",
        ROUTER_LLM_API_KEY="test-key",
        ROUTER_LLM_MODEL="test-model",
        ROUTER_LLM_VLLM_COMPAT=vllm_compat,
    )


def test_compat_on_sends_no_thinking_extra_body() -> str:
    """토글 true(vLLM): router/planner 모두 extra_body 로 enable_thinking=false 를 보낸다(기존 동작 유지)."""
    for factory in (get_router_llm, get_planner_llm):
        llm = factory(_config(vllm_compat=True))
        assert llm.extra_body == _NO_THINKING, f"{factory.__name__}: extra_body={llm.extra_body!r}"
    return "test_compat_on_sends_no_thinking_extra_body"


def test_compat_off_omits_extra_body() -> str:
    """토글 false(Groq 등 상용 API): extra_body 를 아예 싣지 않는다 — 400 거부 회피."""
    for factory in (get_router_llm, get_planner_llm):
        llm = factory(_config(vllm_compat=False))
        assert llm.extra_body is None, f"{factory.__name__}: extra_body={llm.extra_body!r}"
    return "test_compat_off_omits_extra_body"


def test_settings_default_is_true() -> str:
    """Settings 기본값 true — env 미설정인 기존 vLLM 배포는 동작 변화가 없다."""
    default = Settings.model_fields["ROUTER_LLM_VLLM_COMPAT"].default
    assert default is True, f"기본값이 true 여야 기존 배포 무영향: {default!r}"
    return "test_settings_default_is_true"


def _main() -> int:
    tests = [
        test_compat_on_sends_no_thinking_extra_body,
        test_compat_off_omits_extra_body,
        test_settings_default_is_true,
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
