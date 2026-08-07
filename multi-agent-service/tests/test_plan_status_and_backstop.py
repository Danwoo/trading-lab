"""#204 — plan_status 3분기·문서 의도 백스톱·error 시 generator 미호출 (E-204 Tier 0, LLM 호출 0회).

- 스텁 플래너 3종(예외 raise / stages=[] / 정상 1-stage) → plan_status error/empty/ok
- plan error 시 _answer_node 가 generator 스텁을 호출하지 않고 고정 안내문 반환
- 백스톱 어휘 표: 발동 10문 / 비발동 10문 (회귀 방향: 비발동 10문이 백스톱에 걸리면 실패)
- financials_domain 미활성(도메인 토글) 시 백스톱 미발동

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_plan_status_and_backstop.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from graphs.plan_execute.deps import _GraphDeps  # noqa: E402
from graphs.plan_execute.nodes import _PLAN_FAILURE_NOTICE, _answer_node, _plan_node  # noqa: E402
from graphs.plan_execute.schemas import ExecutionPlan, StageTask  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

# 백스톱 발동 10문 — 명사군(업로드·문서·보고서·리포트·자료·노트·PDF·파일) AND 동사군(요약·정리·검색·찾아)
_BACKSTOP_FIRE = [
    "업로드한 리서치 보고서 요약해줘",
    "올린 PDF 정리해줘",
    "내 문서에서 목표주가 찾아줘",
    "업로드 파일 내용 요약 부탁해",
    "리서치 노트 검색해줘",
    "워크스페이스에 올린 리포트 정리해줘",
    "첨부한 자료 요약해줘",
    "사내 리서치 문서 검색해서 보여줘",
    "업로드된 보고서에서 투자의견 찾아줘",
    "pdf 파일 핵심만 정리해줘",
]

# 비발동 10문 — 도메인 외 / 일반 금융(정상 플랜 경로) / 명사군만·동사군만 경계문
_BACKSTOP_NO_FIRE = [
    "다음 주 날씨 알려줘",
    "삼성전자 실적 알려줘",
    "오늘 저녁 메뉴 추천해줘",
    "보고서 어디 있어",  # 명사군만
    "리서치 자료 좀",  # 명사군만
    "삼성전자 재무 요약해줘",  # 동사군만
    "시장 동향 정리해줘",  # 동사군만
    "이 종목 어때",
    "업로드 방법 알려줘",  # 명사군만
    "최근 뉴스 검색해줘",  # 동사군만
]


class _RaisingPlanner:
    async def ainvoke(self, messages, config=None):
        raise RuntimeError("429 rate limited (스텁)")


class _EmptyPlanner:
    async def ainvoke(self, messages, config=None):
        return ExecutionPlan(stages=[])


class _NormalPlanner:
    async def ainvoke(self, messages, config=None):
        return ExecutionPlan(
            stages=[[StageTask(agent_name="financials_domain", task="재무 분석: 삼성전자 최근 분기 실적 추이")]]
        )


class _CountingGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, messages, config=None):
        self.calls += 1
        return AIMessage(content="generator 답변")


def _make_deps(planner, generator=None, agents: dict | None = None) -> _GraphDeps:
    return _GraphDeps(
        planner=planner,
        clarifier=None,
        replanner=None,
        generator_llm=generator,
        guardrail_llm=None,
        guardrail_fn=None,
        writer_llm=None,
        agents=agents if agents is not None else {"financials_domain": object()},
        agent_timeout=5.0,
        agent_max_retries=0,
        agent_retry_delay=0.0,
        react_recursion_limit=8,
        plan_system="플래너",
        replan_system="재계획",
        plan_timeout_s=5.0,
        answer_timeout_s=5.0,
        clarify_timeout_s=5.0,
        guardrail_timeout_s=5.0,
        map_timeout_s=5.0,
        history_max_chars=8000,
        enable_clarify=True,
        enable_guardrail=True,
        max_replan=2,
        map_reduce_domain_threshold=3,
        map_concurrency=2,
        reduce_mode="full",
    )


async def _run_plan(planner, query: str, agents: dict | None = None) -> dict:
    deps = _make_deps(planner, agents=agents)
    return await _plan_node(deps, {"messages": [HumanMessage(content=query)]}, config={})


async def test_plan_status_three_way() -> str:
    """스텁 플래너 3종 → error / empty / ok."""
    out_err = await _run_plan(_RaisingPlanner(), "삼성전자 실적 알려줘")
    assert out_err["plan_status"] == "error", out_err["plan_status"]
    assert out_err["pending_stages"] == [], "error 인데 stage 가 주입됨"

    out_empty = await _run_plan(_EmptyPlanner(), "다음 주 날씨 알려줘")
    assert out_empty["plan_status"] == "empty", out_empty["plan_status"]
    assert out_empty["pending_stages"] == []

    out_ok = await _run_plan(_NormalPlanner(), "삼성전자 실적 알려줘")
    assert out_ok["plan_status"] == "ok", out_ok["plan_status"]
    assert len(out_ok["pending_stages"]) == 1
    return "test_plan_status_three_way"


async def test_error_with_doc_intent_stays_error() -> str:
    """plan 실패는 문서 의도 질문이어도 백스톱이 아니라 정직한 error — (A)/(B) 분리 계약."""
    out = await _run_plan(_RaisingPlanner(), "업로드한 리서치 보고서 요약해줘")
    assert out["plan_status"] == "error", out["plan_status"]
    assert out["pending_stages"] == [], "error 에 백스톱이 발동함 (분리 계약 위반)"
    return "test_error_with_doc_intent_stays_error"


async def test_backstop_fires_on_doc_intent_table() -> str:
    """발동 10문: 정당한 빈 계획 + 문서 의도 → financials_domain 1-stage 백스톱."""
    for query in _BACKSTOP_FIRE:
        out = await _run_plan(_EmptyPlanner(), query)
        assert out["plan_status"] == "backstop", f"{query!r}: 기대 backstop, 실제 {out['plan_status']}"
        stages = out["pending_stages"]
        assert len(stages) == 1 and len(stages[0]) == 1, f"{query!r}: 1-stage 1-task 아님"
        task = stages[0][0]
        assert task.agent_name == "financials_domain", f"{query!r}: {task.agent_name}"
        assert query in task.task, f"{query!r}: 원질문이 task 에 없음 — {task.task}"
    return "test_backstop_fires_on_doc_intent_table"


async def test_backstop_not_fired_on_regression_table() -> str:
    """비발동 10문: 백스톱에 걸리면 실패 (도메인 외 stages=0 유지 — 회귀 방향)."""
    for query in _BACKSTOP_NO_FIRE:
        out = await _run_plan(_EmptyPlanner(), query)
        assert out["plan_status"] == "empty", f"{query!r}: 기대 empty, 실제 {out['plan_status']} (오발동)"
        assert out["pending_stages"] == [], f"{query!r}: 비발동 문항에 stage 주입됨"
    return "test_backstop_not_fired_on_regression_table"


async def test_backstop_disabled_without_financials_domain() -> str:
    """financials_domain 미활성(도메인 토글) → 문서 의도여도 백스톱 미발동."""
    out = await _run_plan(_EmptyPlanner(), "업로드한 리서치 보고서 요약해줘", agents={"market_domain": object()})
    assert out["plan_status"] == "empty", out["plan_status"]
    assert out["pending_stages"] == []
    return "test_backstop_disabled_without_financials_domain"


async def test_answer_skips_generator_on_plan_error() -> str:
    """plan error + stage_results 비면: generator 미호출 + 고정 안내문 (무근거 호출 1회 절약)."""
    generator = _CountingGenerator()
    deps = _make_deps(_RaisingPlanner(), generator=generator)
    state = {
        "messages": [HumanMessage(content="업로드한 리서치 보고서 요약해줘")],
        "plan_status": "error",
        "stage_results": [],
    }
    out = await _answer_node(deps, state, config={})
    assert generator.calls == 0, f"generator 가 호출됨 ({generator.calls}회)"
    assert out["final_answer"] == _PLAN_FAILURE_NOTICE, out["final_answer"]
    return "test_answer_skips_generator_on_plan_error"


async def test_answer_normal_path_when_results_exist() -> str:
    """plan_status=error 라도 stage_results 가 있으면 기존 generator 경로 (조건은 AND — 계약 고정)."""
    generator = _CountingGenerator()
    deps = _make_deps(_RaisingPlanner(), generator=generator)
    state = {
        "messages": [HumanMessage(content="질문")],
        "plan_status": "error",
        "stage_results": [{"stage": 0, "results": [{"agent": "financials_domain", "status": "ok", "output": "결과"}]}],
    }
    out = await _answer_node(deps, state, config={})
    assert generator.calls == 1, f"generator 호출 기대 1, 실제 {generator.calls}"
    assert out["final_answer"] != _PLAN_FAILURE_NOTICE
    return "test_answer_normal_path_when_results_exist"


async def _main() -> int:
    tests = [
        test_plan_status_three_way,
        test_error_with_doc_intent_stays_error,
        test_backstop_fires_on_doc_intent_table,
        test_backstop_not_fired_on_regression_table,
        test_backstop_disabled_without_financials_domain,
        test_answer_skips_generator_on_plan_error,
        test_answer_normal_path_when_results_exist,
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
