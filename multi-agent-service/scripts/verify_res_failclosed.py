"""RES 파이프라인 fail-closed 회귀 검증 — 실패 sub-agent 의 강제 retry + synthesize 배제 계약.

계약 (graphs/results.py: "status != OK 결과는 LLM 프롬프트 context 에서 제외"):
  (1) status != ok 인 sub-agent 는 LLM verdict 유무·판정과 무관하게 tier1 강제 retry 로 실제 재실행된다.
  (2) retry 후에도 실패한 결과는 synthesize 프롬프트 context 에서 제외된다 (오류 문자열 미유입).
  (3) retry 로 회복(ok)된 결과는 synthesize context 에 정상 유입된다.
  (4) 회귀 감지: 전부 ok 면 강제 retry·배제가 일어나지 않는다.

실제 build_res_domain_graph 를 FakeLLM/FakeTool 로 end-to-end 구동한다. 이슈(#74)가 돌린
"LLM 이 실패 agent 의 verdict 를 미반환" 경로에 더해, LLM 이 실패 agent 를 accept 로 반환하는 경로·
retry 성공 회복 경로·reject 혼합 경로 등 새 입력으로 공격한다.

import 체인이 Settings() 를 인스턴스화하므로 env 없는 실행(CI)용 placeholder 를 setdefault.
`uv run python scripts/verify_res_failclosed.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from graphs.res_pipeline import (  # noqa: E402
    _ExecuteEvaluation,
    _ResultVerdict,
    _SubAgentCall,
    _SubAgentPlan,
    build_res_domain_graph,
)
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

_FAIL = object()  # ainvoke 호출 시 예외를 던지라는 센티널


class _FakeTool:
    """StructuredTool 대역 — 호출마다 behaviors 를 소비. str=성공 payload, _FAIL=예외."""

    def __init__(self, name: str, behaviors: list) -> None:
        self.name = name
        self.description = f"{name} 도메인 도구"
        self._behaviors = list(behaviors)
        self.call_count = 0

    async def ainvoke(self, args: dict, config=None) -> str:
        self.call_count += 1
        behavior = self._behaviors.pop(0) if self._behaviors else self._behaviors_default()
        if behavior is _FAIL:
            raise RuntimeError(f"{self.name} 도구 호출 강제 실패")
        return behavior

    def _behaviors_default(self):
        # behaviors 소진 후에는 마지막 지정 동작을 반복 (테스트 단순화)
        return _FAIL


class _StructuredLLM:
    """with_structured_output 이 돌려주는 대역 — 고정 구조체 반환."""

    def __init__(self, value) -> None:
        self._value = value

    async def ainvoke(self, messages, config=None):
        return self._value


class _FakeRouterLLM:
    """router_llm 대역. route/evaluate 는 structured, synthesize 는 base ainvoke(캡처)."""

    def __init__(self, plan: _SubAgentPlan, evaluation: _ExecuteEvaluation) -> None:
        self._plan = plan
        self._evaluation = evaluation
        self.synth_inputs: list[str] = []  # synthesize HumanMessage content 캡처

    def with_structured_output(self, schema):
        if schema is _SubAgentPlan:
            return _StructuredLLM(self._plan)
        if schema is _ExecuteEvaluation:
            return _StructuredLLM(self._evaluation)
        raise AssertionError(f"예상치 못한 structured schema: {schema}")

    async def ainvoke(self, messages, config=None):
        # build_node_messages → [SystemMessage, HumanMessage]; results_text 는 HumanMessage 에 있다.
        self.synth_inputs.append(str(messages[-1].content))
        return AIMessage(content="[SYNTH]")


_ERROR_MARKERS = ("(오류", "타임아웃", "도구 없음", "(응답 없음)", "강제 실패", "RuntimeError")


async def _run_case(
    *,
    tools: list[_FakeTool],
    plan_calls: list[_SubAgentCall],
    verdicts: list[_ResultVerdict],
) -> tuple[str, dict[str, _FakeTool]]:
    """그래프를 end-to-end 구동, synthesize 입력 텍스트와 tool 맵 반환."""
    llm = _FakeRouterLLM(_SubAgentPlan(calls=plan_calls), _ExecuteEvaluation(verdicts=verdicts))
    graph = build_res_domain_graph(
        domain_name="verify",
        router_llm=llm,
        domain_tools=tools,
        domain_prompt="테스트 도메인",
        sub_agent_timeout=5.0,
    )
    await graph.ainvoke({"messages": [HumanMessage(content="테스트 작업 지시")]})
    assert llm.synth_inputs, "synthesize LLM 이 호출되지 않음 (fast-path 로 우회됐을 수 있음)"
    return llm.synth_inputs[-1], {t.name: t for t in tools}


def main() -> int:
    problems: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        if not ok:
            problems.append(f"{name}: {detail}")

    def call(name: str, task: str, group: int = 0) -> _SubAgentCall:
        return _SubAgentCall(agent=name, task=task, group=group)

    def verdict(agent: str, v: str, refined: str = "") -> _ResultVerdict:
        return _ResultVerdict(agent=agent, verdict=v, refined_task=refined)

    # ── Case 1: 이슈 핵심 — LLM 이 실패 agent 의 verdict 를 미반환 (append 분기) ──
    ok_tool = _FakeTool("market", ["시세 요약: 정상 데이터 " + "x" * 40])
    fail_tool = _FakeTool("news", [_FAIL, _FAIL])  # 초기 + retry 모두 실패
    synth, tmap = asyncio.run(
        _run_case(
            tools=[ok_tool, fail_tool],
            plan_calls=[call("market", "시세 조회"), call("news", "뉴스 조회")],
            verdicts=[verdict("market", "accept")],  # 성공 agent 만 verdict (LLM 은 ok 만 봄)
        )
    )
    check("C1 실패 agent retry 실제 수행", tmap["news"].call_count == 2, f"news call_count={tmap['news'].call_count}")
    check("C1 synthesize 에 오류 마커 없음", not any(m in synth for m in _ERROR_MARKERS), f"synth={synth[:200]!r}")
    check("C1 실패 agent 결과 배제", "[news]" not in synth, f"synth={synth[:200]!r}")
    check("C1 성공 agent 결과 유입", "[market]" in synth, f"synth={synth[:200]!r}")

    # ── Case 2: 새 입력 — LLM 이 실패 agent 를 accept 로 반환 (mutate 분기, 이슈 미검증) ──
    ok2 = _FakeTool("market", ["시세 요약: 정상 " + "y" * 40])
    fail2 = _FakeTool("news", [_FAIL, _FAIL])
    synth2, tmap2 = asyncio.run(
        _run_case(
            tools=[ok2, fail2],
            plan_calls=[call("market", "시세 조회"), call("news", "뉴스 조회")],
            verdicts=[verdict("market", "accept"), verdict("news", "accept")],  # 실패인데 accept 로 옴
        )
    )
    check("C2 accept→강제 retry 수행", tmap2["news"].call_count == 2, f"news call_count={tmap2['news'].call_count}")
    check("C2 synthesize 에 오류 마커 없음", not any(m in synth2 for m in _ERROR_MARKERS), f"synth={synth2[:200]!r}")
    check("C2 실패 agent 결과 배제", "[news]" not in synth2, f"synth={synth2[:200]!r}")

    # ── Case 3: 새 입력 — retry 가 성공하면 회복된 payload 가 synthesize 에 유입 ──
    ok3 = _FakeTool("market", ["시세 요약: 정상 " + "z" * 40])
    recover = _FakeTool("news", [_FAIL, "뉴스 요약: 회복된 정상 데이터 " + "w" * 30])  # 초기 실패 → retry 성공
    synth3, tmap3 = asyncio.run(
        _run_case(
            tools=[ok3, recover],
            plan_calls=[call("market", "시세 조회"), call("news", "뉴스 조회")],
            verdicts=[verdict("market", "accept")],
        )
    )
    check("C3 retry 수행", tmap3["news"].call_count == 2, f"news call_count={tmap3['news'].call_count}")
    check("C3 회복 결과 유입", "[news]" in synth3 and "회복된 정상 데이터" in synth3, f"synth={synth3[:250]!r}")
    check("C3 synthesize 에 오류 마커 없음", not any(m in synth3 for m in _ERROR_MARKERS), f"synth={synth3[:250]!r}")

    # ── Case 4: 새 입력 — reject(ok) + 실패 혼합, 둘 다 배제 ──
    ok4 = _FakeTool("market", ["시세 요약: 정상 " + "a" * 40])
    junk4 = _FakeTool("disc", ["무관한 잡음 데이터 " + "b" * 40])  # ok 지만 reject 판정
    fail4 = _FakeTool("news", [_FAIL, _FAIL])
    synth4, tmap4 = asyncio.run(
        _run_case(
            tools=[ok4, junk4, fail4],
            plan_calls=[call("market", "시세"), call("disc", "공시"), call("news", "뉴스")],
            verdicts=[verdict("market", "accept"), verdict("disc", "reject")],
        )
    )
    check("C4 reject 결과 배제", "[disc]" not in synth4, f"synth={synth4[:250]!r}")
    check("C4 실패 결과 배제", "[news]" not in synth4, f"synth={synth4[:250]!r}")
    check("C4 정상 결과 유입", "[market]" in synth4, f"synth={synth4[:250]!r}")
    check("C4 synthesize 에 오류 마커 없음", not any(m in synth4 for m in _ERROR_MARKERS), f"synth={synth4[:250]!r}")

    # ── Case 5: 회귀 감지 — 전부 ok 면 강제 retry·배제 없음 (전원 유입) ──
    a5 = _FakeTool("market", ["시세 " + "c" * 40])
    b5 = _FakeTool("disc", ["공시 " + "d" * 40])
    c5 = _FakeTool("news", ["뉴스 " + "e" * 40])
    synth5, tmap5 = asyncio.run(
        _run_case(
            tools=[a5, b5, c5],
            plan_calls=[call("market", "시세"), call("disc", "공시"), call("news", "뉴스")],
            verdicts=[verdict("market", "accept"), verdict("disc", "accept"), verdict("news", "accept")],
        )
    )
    no_retry = tmap5["market"].call_count == 1 and tmap5["disc"].call_count == 1 and tmap5["news"].call_count == 1
    check("C5 전부 ok → retry 없음", no_retry, "call_count 가 1 이 아님 (불필요한 retry)")
    all_in = "[market]" in synth5 and "[disc]" in synth5 and "[news]" in synth5
    check("C5 전원 synthesize 유입", all_in, f"synth={synth5[:300]!r}")

    if problems:
        print("RES fail-closed 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        "RES fail-closed OK — 강제 retry 실제 수행(verdict 미반환·accept 오판 양쪽) + "
        "실패/reject synthesize 배제 + retry 회복 유입 + 전부 ok 회귀 무영향 전부 성립"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
