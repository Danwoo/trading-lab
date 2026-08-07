"""#275 — guardrail 호출에 wait_for 가 없어 프로바이더가 행 걸리면 스트림 머리가 무기한 멈춤
(LLM 호출 0회). #338 — 타임아웃 후 처리는 fail-open(통과) 이 아니라 fail-closed(차단).

clarify·plan 노드와 달리 _guardrail_node 는 asyncio.wait_for 로 감싸지 않아, guardrail_fn
(check_guardrail)이 내부에서 영원히 반환하지 않는 코루틴을 await 하면 그래프 첫 노드가 멈추고
사용자에게는 채팅이 그냥 침묵하는 것으로 보인다.

재현: "영원히 안 끝나는" guardrail_fn 스텁을 주입하고, 테스트 자체의 바깥 타임아웃(짧게)으로
_guardrail_node 호출을 감싼다 — 고치기 전엔 노드가 그 바깥 타임아웃까지 응답하지 않아 걸린다
(TimeoutError 로 재현 확인). 고친 뒤엔 노드 내부의 deps.guardrail_timeout_s 안에서 스스로
끝나야 하고(바깥 타임아웃보다 훨씬 여유 있게), 그 타임아웃이 조용히 통과로 섞이지 않고 **차단**
+ 사용자에게 도달하는 안내 문구로 이어지는지 확인한다(#338 — 판정 불가는 안전 판정이 아니다).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_guardrail_wait_for.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import graphs.plan_execute.nodes as nodes_module  # noqa: E402
from core.config import Settings  # noqa: E402
from graphs.plan_execute.deps import _GraphDeps  # noqa: E402
from graphs.plan_execute.nodes import _guardrail_node  # noqa: E402
from langchain_core.messages import HumanMessage  # noqa: E402
from services.agent.guardrail import GUARDRAIL_UNAVAILABLE_MESSAGE  # noqa: E402

_OUTER_BOUND_S = 1.0  # 테스트 자체가 무기한 걸리지 않기 위한 안전판(재현 실패 시에도 CI 가 안 멈춤)
_NODE_TIMEOUT_S = 0.2  # deps.guardrail_timeout_s — 노드가 이 안에서 스스로 끝나야 함


async def _hanging_guardrail_fn(query, llm, enabled=True, config=None):
    """프로바이더가 응답하지 않는 상황의 스텁 — 영원히 끝나지 않는 코루틴."""
    await asyncio.Future()  # 누구도 resolve 하지 않음


class _Verdict:
    is_safe = True


async def _instant_safe_guardrail_fn(query, llm, enabled=True, config=None):
    return _Verdict()


def _make_deps(guardrail_fn, guardrail_timeout_s: float) -> _GraphDeps:
    return _GraphDeps(
        planner=None,
        clarifier=None,
        replanner=None,
        generator_llm=None,
        guardrail_llm=None,
        guardrail_fn=guardrail_fn,
        writer_llm=None,
        agents={},
        agent_timeout=5.0,
        agent_max_retries=0,
        agent_retry_delay=0.0,
        react_recursion_limit=8,
        plan_system="",
        replan_system="",
        plan_timeout_s=5.0,
        answer_timeout_s=5.0,
        clarify_timeout_s=5.0,
        guardrail_timeout_s=guardrail_timeout_s,
        map_timeout_s=5.0,
        history_max_chars=8000,
        enable_clarify=True,
        enable_guardrail=True,
        max_replan=2,
        map_reduce_domain_threshold=3,
        map_concurrency=2,
        reduce_mode="full",
    )


async def test_hanging_guardrail_resolves_within_node_timeout() -> str:
    """행 걸린 프로바이더 → 노드가 deps.guardrail_timeout_s 안에서 스스로 끝나고 **차단**한다(#338).

    통과가 아니라 차단이어야 한다 — 판정 불가는 안전 판정이 아니다. 안내 문구가
    final_answer/messages 로 사용자에게 도달하는지까지 함께 확인한다.
    """
    deps = _make_deps(_hanging_guardrail_fn, guardrail_timeout_s=_NODE_TIMEOUT_S)
    state = {"messages": [HumanMessage(content="질문")]}

    errors: list[str] = []
    original_error = nodes_module.logger.error

    def _capture_error(msg, *args, **kwargs):
        errors.append(msg % args if args else msg)
        return original_error(msg, *args, **kwargs)

    nodes_module.logger.error = _capture_error
    try:
        t0 = time.monotonic()
        out = await asyncio.wait_for(_guardrail_node(deps, state, config={}), timeout=_OUTER_BOUND_S)
        elapsed = time.monotonic() - t0
    finally:
        nodes_module.logger.error = original_error

    assert elapsed < _OUTER_BOUND_S, f"노드가 바깥 타임아웃({_OUTER_BOUND_S}s)까지 안 끝남 — wait_for 미적용"
    assert elapsed >= _NODE_TIMEOUT_S * 0.9, f"노드 타임아웃보다 너무 빨리 끝남(우연 성공 의심): {elapsed}s"
    assert out["guardrail_blocked"] is True, f"타임아웃은 차단(fail-closed)이어야 함(#338): {out}"
    assert out["final_answer"] == out["refusal_message"], out
    assert "다시 시도" in out["refusal_message"], (
        f"사용자에게 무엇이 일어났는지·무엇을 하면 되는지 안내해야 함: {out['refusal_message']!r}"
    )
    assert out["messages"][0].content == out["refusal_message"], "안내 문구가 messages 로도 전달돼야 함"
    assert any("응답 지연" in e or "지연" in e for e in errors), (
        f"타임아웃이 조용히 통과로 섞임 — 로그 신호 없음: {errors}"
    )
    return "test_hanging_guardrail_resolves_within_node_timeout"


async def test_normal_safe_path_unaffected() -> str:
    """정상 SAFE 응답 경로는 wait_for 도입 후에도 그대로 통과 (회귀 방향)."""
    deps = _make_deps(_instant_safe_guardrail_fn, guardrail_timeout_s=5.0)
    state = {"messages": [HumanMessage(content="삼성전자 시세 알려줘")]}
    out = await _guardrail_node(deps, state, config={})
    assert out == {"guardrail_blocked": False}, out
    return "test_normal_safe_path_unaffected"


async def test_nonpositive_guardrail_timeout_rejected_at_startup() -> str:
    """MA_GUARDRAIL_TIMEOUT_S<=0 → 기동 시점 fail-fast (#338 리뷰 지적).

    fail-closed 전환 후 0·음수는 asyncio.wait_for(timeout<=0)가 매 요청을 즉시 타임아웃시켜
    전체 채팅이 상시 차단되는 오설정이다 — JWT_SECRET·AUTH_DEV_BYPASS 와 같은 자리(config.py)에
    같은 fail-fast 패턴으로 잡는다.
    """
    for bad in (0, -1, -0.5):
        try:
            Settings(APP_ENV="development", MA_GUARDRAIL_TIMEOUT_S=bad)
        except ValueError as e:
            assert "MA_GUARDRAIL_TIMEOUT_S" in str(e), f"오설정값 {bad} 의 에러 메시지가 원인을 안 가리킴: {e}"
        else:
            raise AssertionError(f"MA_GUARDRAIL_TIMEOUT_S={bad} 가 기동을 통과함 — fail-fast 미작동")
    Settings(APP_ENV="development", MA_GUARDRAIL_TIMEOUT_S=15.0)  # 정상값은 그대로 통과(회귀 방향)
    return "test_nonpositive_guardrail_timeout_rejected_at_startup"


async def test_unavailable_message_lockstep_with_guardrail_module() -> str:
    """nodes.py::_TimeoutVerdict.refusal_message 는 guardrail.py::GUARDRAIL_UNAVAILABLE_MESSAGE 의
    로컬 복제다(graphs 는 services 를 import 하지 않는 경계라 import 로 못 묶는다, #338 리뷰 지적).

    두 문자열이 텍스트로 중복되므로 한쪽만 고치면 조용히 갈라진다 — 동일성을 여기서 강제한다.
    """
    assert nodes_module._TimeoutVerdict.refusal_message == GUARDRAIL_UNAVAILABLE_MESSAGE, (
        f"nodes.py 의 _TimeoutVerdict.refusal_message 가 guardrail.py 의 "
        f"GUARDRAIL_UNAVAILABLE_MESSAGE 와 갈라졌다 — 양쪽 다 고쳐야 한다.\n"
        f"nodes.py:      {nodes_module._TimeoutVerdict.refusal_message!r}\n"
        f"guardrail.py:  {GUARDRAIL_UNAVAILABLE_MESSAGE!r}"
    )
    return "test_unavailable_message_lockstep_with_guardrail_module"


async def _main() -> int:
    tests = [
        test_hanging_guardrail_resolves_within_node_timeout,
        test_normal_safe_path_unaffected,
        test_nonpositive_guardrail_timeout_rejected_at_startup,
        test_unavailable_message_lockstep_with_guardrail_module,
    ]
    passed = 0
    for tc in tests:
        name = await tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
