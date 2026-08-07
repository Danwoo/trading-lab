"""#121 회귀 방지 — 에이전트 재시도 시 tool-trace sink 중복 적재가 없음을 확인.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_invocation_retry_sink.py
pytest 가 도입되면 test_* async 함수가 그대로 수집된다(pytest-asyncio 필요).

검증 대상: `_invoke_agent_safe` 의 "시도별 임시 버퍼 → 성공한 시도만 공유 sink 로 승격" 동작.
실제 LLM/ReAct 대신 콜백 경로(_ToolTraceCallback)만 정밀 재현하는 테스트 더블을 쓴다.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

# app 소스 루트(core/graphs 절대 import)와 dev 설정을 app 모듈 import 전에 준비한다.
os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from graphs.plan_execute.invocation import _invoke_agent_safe  # noqa: E402
from graphs.results import AgentStatus  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402


class _FakeAgent:
    """스크립트대로 도구 콜백을 구동하고 시도별 결과를 반환하는 테스트 더블.

    script[i] = (outcome, n_tools): i 번째 시도에서 n_tools 개 도구를 성공 실행(sink append 유발)한 뒤
    outcome("ok"|"empty"|"timeout"|"raise")대로 종료한다. 각 도구 출력에 attempt 번호를 심어
    "sink 에 남은 기록이 어느 시도의 것인지"를 검증할 수 있게 한다.
    """

    def __init__(self, script: list[tuple[str, int]], interleave: bool = False) -> None:
        self.script = script
        self.interleave = interleave
        self.calls = 0

    async def ainvoke(self, inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        idx = self.calls
        self.calls += 1
        outcome, n_tools = self.script[idx]
        callbacks = (config or {}).get("callbacks") or []
        for cb in callbacks:
            for t in range(n_tools):
                run_id = f"{cb.agent_name}-att{idx}-tool{t}"
                await cb.on_tool_start({"name": f"tool_{t}"}, f"q{t}", run_id=run_id)
                if self.interleave:
                    await asyncio.sleep(0)  # 병렬 형제와 버퍼 append 를 실제로 교차시킨다
                await cb.on_tool_end(f'{{"attempt": {idx}, "tool": {t}}}', run_id=run_id)
        if outcome == "timeout":
            raise TimeoutError
        if outcome == "raise":
            raise RuntimeError("boom")
        if outcome == "empty":
            return {"messages": [AIMessage(content="")]}
        return {"messages": [AIMessage(content=f"answer-att{idx}")]}


async def test_first_try_success_unchanged() -> str:
    """성공 경로(재시도 없이 1번에 성공): 실행한 도구 기록이 그대로 sink 에 들어간다(무변경 논증)."""
    sink: list[dict[str, Any]] = []
    agent = _FakeAgent([("ok", 3)])
    result = await _invoke_agent_safe(
        agent, task="t", agent_name="MKT", timeout=5.0, max_retries=1, retry_delay=0.0, tool_trace_sink=sink
    )
    assert result.status == AgentStatus.OK, result.status
    assert agent.calls == 1, f"재시도가 발생하면 안 됨: calls={agent.calls}"
    assert len(sink) == 3, f"기대 3, 실제 {len(sink)}: {sink}"
    return "test_first_try_success_unchanged"


async def test_retry_promotes_only_successful_attempt() -> str:
    """부분성공→빈응답(실패)→재시도→성공: 공유 sink 에 최종 성공 시도 기록만 남는다.

    수정 전이라면 len(sink)==4 (실패 시도 2 + 성공 시도 2)로 중복 적재. 수정 후엔 성공 시도 2 만.
    """
    sink: list[dict[str, Any]] = []
    agent = _FakeAgent([("empty", 2), ("ok", 2)])
    result = await _invoke_agent_safe(
        agent, task="t", agent_name="RES", timeout=5.0, max_retries=1, retry_delay=0.0, tool_trace_sink=sink
    )
    assert result.status == AgentStatus.OK, result.status
    assert len(sink) == 2, f"중복 적재 — 기대 2, 실제 {len(sink)}: {sink}"
    assert all('"attempt": 1' in rec["output"] for rec in sink), f"성공(2번째) 시도 기록만 남아야 함: {sink}"
    return "test_retry_promotes_only_successful_attempt"


async def test_shared_sink_parallel_sibling_not_clobbered() -> str:
    """병렬 형제가 같은 sink 를 공유 + 한쪽이 재시도: 실패 시도 폐기가 형제 기록을 지우지 않는다.

    이것이 "길이 스냅샷 후 절단" 대신 "버퍼→성공 시 승격"을 택한 이유의 회귀 방지다.
    절단 방식이면 B 가 실패 시 자기 스냅샷 길이로 sink 를 자르며 그 사이 A 가 append 한 기록까지 지운다.
    """
    sink: list[dict[str, Any]] = []
    agent_ok = _FakeAgent([("ok", 2)], interleave=True)  # 1번에 성공, 2 도구
    agent_retry = _FakeAgent([("timeout", 2), ("ok", 2)], interleave=True)  # 실패(타임아웃) 후 성공
    await asyncio.gather(
        _invoke_agent_safe(
            agent_ok, task="t", agent_name="A", timeout=5.0, max_retries=1, retry_delay=0.0, tool_trace_sink=sink
        ),
        _invoke_agent_safe(
            agent_retry, task="t", agent_name="B", timeout=5.0, max_retries=1, retry_delay=0.0, tool_trace_sink=sink
        ),
    )
    assert len(sink) == 4, f"기대 4 (A 2 + B 최종 2), 실제 {len(sink)}: {sink}"
    a_recs = [r for r in sink if r["agent"] == "A"]
    b_recs = [r for r in sink if r["agent"] == "B"]
    assert len(a_recs) == 2, f"A 형제 기록이 훼손됨: {a_recs}"
    assert len(b_recs) == 2, f"B 는 성공 시도 2 만: {b_recs}"
    assert all('"attempt": 1' in r["output"] for r in b_recs), f"B 실패 시도가 남음: {b_recs}"
    return "test_shared_sink_parallel_sibling_not_clobbered"


async def _main() -> int:
    tests = [
        test_first_try_success_unchanged,
        test_retry_promotes_only_successful_attempt,
        test_shared_sink_parallel_sibling_not_clobbered,
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
