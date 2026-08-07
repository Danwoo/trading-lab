"""#284 — _GraphDeps 전 필드 필수 dataclass 문제 (LLM 호출 0회).

이전엔 _GraphDeps 의 모든 필드가 기본값 없는 위치 인자 가능 필수값이라, 필드를 하나 추가할
때마다 모든 생성처(테스트·스크립트의 직접 `_GraphDeps(...)` 포함)를 함께 고쳐야 했다
(#275 의 guardrail_timeout_s 추가가 실측: builder.py 포함 4곳 — grep 근거는 이슈 코멘트).

처방: kw_only=True + "안전한 기본값이 있는 튜닝 노브"(타임아웃·재시도·플래그·임계값)에
build_plan_execute_graph() 파라미터 기본값과 동일한 기본값을 부여. LLM·콜러블·agents·프롬프트처럼
안전한 기본값이 없는 핵심 배선은 의도적으로 필수로 남긴다.

이 테스트는 그 계약을 고정한다: (1) 튜닝 노브만 생략해도 생성이 성공하고 기본값이
build_plan_execute_graph() 시그니처와 일치, (2) 핵심 배선 필드 누락은 여전히 즉시 실패
(fail-closed 유지 — 전부 옵션이 되는 과잉수정 방지), (3) 위치 인자 생성은 금지(kw_only).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_graph_deps_defaults.py
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from graphs.plan_execute.builder import build_plan_execute_graph  # noqa: E402
from graphs.plan_execute.deps import _GraphDeps  # noqa: E402

# _GraphDeps 생성에 안전한 기본값 없이 반드시 채워야 하는 핵심 배선 필드만.
_REQUIRED_FIELDS = {
    "planner": None,
    "clarifier": None,
    "replanner": None,
    "generator_llm": None,
    "guardrail_llm": None,
    "guardrail_fn": None,
    "writer_llm": None,
    "agents": {},
    "plan_system": "",
    "replan_system": "",
}


def test_tuning_knobs_omittable_and_default_to_builder_values() -> str:
    """새 노브가 생겨도 기존처럼 필수 필드만 채우면 생성이 성공하고, 기본값이 builder 시그니처와 일치."""
    deps = _GraphDeps(**_REQUIRED_FIELDS)

    builder_sig = inspect.signature(build_plan_execute_graph)
    # deps 필드명 → builder 파라미터명 매핑 (동일 이름이 아닌 경우만 명시)
    checked = 0
    for field_name in (
        "agent_timeout",
        "agent_max_retries",
        "agent_retry_delay",
        "react_recursion_limit",
        "plan_timeout_s",
        "answer_timeout_s",
        "clarify_timeout_s",
        "guardrail_timeout_s",
        "map_timeout_s",
        "history_max_chars",
        "enable_clarify",
        "enable_guardrail",
        "max_replan",
        "map_reduce_domain_threshold",
        "map_concurrency",
        "reduce_mode",
    ):
        builder_default = builder_sig.parameters[field_name].default
        deps_default = getattr(deps, field_name)
        assert deps_default == builder_default, (
            f"{field_name}: deps 기본값({deps_default!r}) != builder 기본값({builder_default!r}) — lockstep 위반"
        )
        checked += 1
    assert checked == 16, f"검사한 노브 필드 수 변동: {checked} (16 기대) — 필드가 늘거나 줄면 이 목록도 갱신"
    return "test_tuning_knobs_omittable_and_default_to_builder_values"


def test_missing_core_wiring_field_still_fails_fast() -> str:
    """핵심 배선 필드(예: planner) 누락은 여전히 즉시 TypeError — 전부 옵션이 되는 과잉수정 방지."""
    incomplete = dict(_REQUIRED_FIELDS)
    del incomplete["planner"]
    try:
        _GraphDeps(**incomplete)
    except TypeError:
        return "test_missing_core_wiring_field_still_fails_fast"
    raise AssertionError("planner 없이 _GraphDeps 생성이 성공함 — fail-closed 계약 위반")


def test_positional_construction_rejected() -> str:
    """kw_only=True — 위치 인자로 생성 시도 시 TypeError (필드 순서 의존 차단)."""
    args = [None] * 10  # _REQUIRED_FIELDS 개수만큼
    try:
        _GraphDeps(*args)
    except TypeError:
        return "test_positional_construction_rejected"
    raise AssertionError("위치 인자로 _GraphDeps 생성이 성공함 — kw_only 미적용")


def _main() -> int:
    tests = [
        test_tuning_knobs_omittable_and_default_to_builder_values,
        test_missing_core_wiring_field_still_fails_fast,
        test_positional_construction_rejected,
    ]
    passed = 0
    for tc in tests:
        print(f"PASS {tc()}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
