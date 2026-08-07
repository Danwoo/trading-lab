"""#207 T1 — UsageTracker 의 run_name 별 usage 합산·근사 폴백·요약 검증 (LLM 호출 0회).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_usage_tracker.py
pytest 가 도입되면 test_* async 함수가 그대로 수집된다(pytest-asyncio 필요).
"""

from __future__ import annotations

import ast
import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

# app 소스 루트(절대 import)와 dev 설정을 app 모듈 import 전에 준비한다.
os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from graphs.pipeline_subagent import _RUN_NAME_PARAM, _RUN_NAME_WRITER, build_pipeline_subagent  # noqa: E402
from langchain_core.language_models import BaseChatModel  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langchain_core.outputs import ChatGeneration, ChatResult, LLMResult  # noqa: E402
from langchain_core.tools import StructuredTool  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from utils.agent.usage_tracker import UsageTracker  # noqa: E402


def _result_with_usage_metadata(input_tokens: int, output_tokens: int) -> LLMResult:
    msg = AIMessage(
        content="답변",
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    )
    return LLMResult(generations=[[ChatGeneration(message=msg)]])


def _result_with_llm_output(prompt_tokens: int, completion_tokens: int) -> LLMResult:
    msg = AIMessage(content="답변")
    return LLMResult(
        generations=[[ChatGeneration(message=msg)]],
        llm_output={"token_usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}},
    )


def _result_without_usage(text: str) -> LLMResult:
    return LLMResult(generations=[[ChatGeneration(message=AIMessage(content=text))]])


async def test_nested_run_resolves_parent_run_name() -> str:
    """구조화 출력 경로: 체인 run(run_name='계획 수립') 하위 LLM run 의 usage 가 부모 라벨로 합산."""
    tracker = UsageTracker()
    chain_id, llm_id = uuid4(), uuid4()
    await tracker.on_chain_start({}, {}, run_id=chain_id, name="계획 수립")
    await tracker.on_chat_model_start({}, [[HumanMessage(content="질문")]], run_id=llm_id, parent_run_id=chain_id)
    await tracker.on_llm_end(_result_with_usage_metadata(100, 20), run_id=llm_id)
    assert tracker.by_node == {"계획 수립": {"input_tokens": 100, "output_tokens": 20, "calls": 1}}, tracker.by_node
    assert tracker.estimated is False
    return "test_nested_run_resolves_parent_run_name"


async def test_direct_run_name_and_llm_output_fallback() -> str:
    """직접 run_name 지정 LLM(예: '답변 작성') + llm_output.token_usage 경로 합산."""
    tracker = UsageTracker()
    llm_id = uuid4()
    await tracker.on_chat_model_start({}, [[HumanMessage(content="질문")]], run_id=llm_id, name="답변 작성")
    await tracker.on_llm_end(_result_with_llm_output(50, 10), run_id=llm_id)
    assert tracker.by_node == {"답변 작성": {"input_tokens": 50, "output_tokens": 10, "calls": 1}}, tracker.by_node
    return "test_direct_run_name_and_llm_output_fallback"


async def test_accumulates_same_run_name() -> str:
    """같은 run_name 의 복수 호출은 합산되고 calls 가 는다."""
    tracker = UsageTracker()
    for _ in range(3):
        llm_id = uuid4()
        await tracker.on_chat_model_start({}, [[HumanMessage(content="q")]], run_id=llm_id, name="보안 검사")
        await tracker.on_llm_end(_result_with_usage_metadata(10, 5), run_id=llm_id)
    assert tracker.by_node == {"보안 검사": {"input_tokens": 30, "output_tokens": 15, "calls": 3}}, tracker.by_node
    totals = tracker.totals()
    assert totals == {"input_tokens": 30, "output_tokens": 15, "calls": 3}, totals
    return "test_accumulates_same_run_name"


async def test_estimation_fallback_marks_estimated() -> str:
    """usage 부재 응답 → 문자수/4 근사 + estimated=true (근사·실측 혼동 금지)."""
    tracker = UsageTracker()
    llm_id = uuid4()
    prompt = "가" * 400  # 400자 → 100 토큰 근사
    output = "나" * 80  # 80자 → 20 토큰 근사
    await tracker.on_chat_model_start({}, [[HumanMessage(content=prompt)]], run_id=llm_id, name="보충질문 판단")
    await tracker.on_llm_end(_result_without_usage(output), run_id=llm_id)
    assert tracker.estimated is True
    slot = tracker.by_node["보충질문 판단"]
    assert slot == {"input_tokens": 100, "output_tokens": 20, "calls": 1}, slot
    assert "estimated=true" in tracker.summary_line(), tracker.summary_line()
    return "test_estimation_fallback_marks_estimated"


async def test_generic_framework_names_not_used_as_labels() -> str:
    """프레임워크 기본 run 이름(RunnableSequence 등)은 라벨로 쓰지 않고 조상으로 거슬러 오른다."""
    tracker = UsageTracker()
    outer, seq, llm_id = uuid4(), uuid4(), uuid4()
    await tracker.on_chain_start({}, {}, run_id=outer, name="재계획 판단")
    await tracker.on_chain_start({}, {}, run_id=seq, parent_run_id=outer, name="RunnableSequence")
    await tracker.on_chat_model_start({}, [[HumanMessage(content="q")]], run_id=llm_id, parent_run_id=seq)
    await tracker.on_llm_end(_result_with_usage_metadata(7, 3), run_id=llm_id)
    assert list(tracker.by_node) == ["재계획 판단"], tracker.by_node
    return "test_generic_framework_names_not_used_as_labels"


async def test_unresolved_falls_back_to_langgraph_node_metadata() -> str:
    """이름 있는 조상이 없으면 langgraph_node metadata 로 귀속 (그마저 없으면 '(미분류)')."""
    tracker = UsageTracker()
    llm_id = uuid4()
    await tracker.on_chat_model_start(
        {}, [[HumanMessage(content="q")]], run_id=llm_id, metadata={"langgraph_node": "다음판단"}
    )
    await tracker.on_llm_end(_result_with_usage_metadata(5, 2), run_id=llm_id)
    assert list(tracker.by_node) == ["다음판단"], tracker.by_node
    return "test_unresolved_falls_back_to_langgraph_node_metadata"


async def test_summary_line_shape() -> str:
    """summary_line 은 총계·estimated·노드별 내역을 1줄로 담는다 ([usage] 로그 계약)."""
    tracker = UsageTracker()
    llm_id = uuid4()
    await tracker.on_chat_model_start({}, [[HumanMessage(content="q")]], run_id=llm_id, name="계획 수립")
    await tracker.on_llm_end(_result_with_usage_metadata(11, 4), run_id=llm_id)
    line = tracker.summary_line()
    for fragment in ("total_in=11", "total_out=4", "calls=1", "estimated=false", "계획 수립"):
        assert fragment in line, f"{fragment!r} 누락: {line}"
    payload = tracker.trace_payload()
    assert payload["total"]["input_tokens"] == 11 and payload["by_node"]["계획 수립"]["calls"] == 1, payload
    return "test_summary_line_shape"


# ── 관측 사각 그물 (#207) — run_name 없는 LLM 호출이 하나라도 있으면 실패 ──────────────
#
# 배경: usage tracker 는 run_name 으로만 노드를 가른다. run_name 이 없으면 가장 가까운 이름
# 있는 조상으로 흡수되는데, sub-agent 서브트리에서는 그 조상이 sub-agent 명이라 **라우터 모델
# 호출(인자 생성)이 generator 와 한 바구니**에 들어갔다. 관측 사각 위에서 절감 판정을 하면
# 판정 자체가 성립하지 않는다.
#
# 그래서 두 층으로 막는다:
#   ① 정적 전수 조사 — app/ 의 모든 invoke 호출을 AST 로 훑어 LLM 호출마다 run_name 확인.
#      분류표에 없는 새 수신자가 나오면 통과가 아니라 실패다 (사람이 분류해야 한다).
#   ② 실경로 확인 — 콜백이 실제로 발화하는 BaseChatModel 로 sub-agent 파이프라인을 돌려,
#      라우터·generator 가 서로 다른 라벨로 잡히는지 본다 (스텁 자칭 라벨이 아니라 실 배선).

_INVOKE_METHODS = frozenset({"ainvoke", "invoke", "astream", "astream_events", "abatch", "batch", "stream"})
# 이 수신자에 대한 invoke 는 LLM 호출 — run_name 이 반드시 붙어야 한다 (usage 귀속 대상).
_LLM_RECEIVERS = frozenset(
    {
        "bound",  # pipeline_subagent param (라우터) — bind_tools 결과
        "writer_llm",  # pipeline_subagent writer (generator)
        "structured",  # guardrail (라우터) — with_structured_output 결과
        "_router",  # res_pipeline 에이전트 선택 (라우터)
        "_evaluator",  # res_pipeline 결과 평가 (라우터)
        "router_llm",  # res_pipeline 답변 합성 (라우터)
        "deps.clarifier",
        "deps.planner",
        "deps.replanner",
        "deps.generator_llm",
        "llm_to_use",  # map_reduce 도메인 답변 작성
        "self._generator_llm",  # agent_service 제목·후속질문 생성
    }
)
# LLM 이 아닌 invoke — 도구 실행·서브그래프 호출. run_name 은 trace 가독용이라 강제하지 않는다.
_NON_LLM_RECEIVERS = frozenset({"tool", "agent", "graph"})
# fail-closed 핀 — 검사 0건이 초록이 되지 않게, 그리고 관측 지점이 조용히 줄지 않게 박는다.
_EXPECTED_LLM_CALL_SITES = 15


def _llm_call_sites() -> tuple[list[str], list[str], int]:
    """app/ 전수 AST 스캔 → (run_name 없는 LLM 호출, 분류표에 없는 수신자, 검사한 LLM 호출 수)."""
    unlabeled: list[str] = []
    unclassified: list[str] = []
    inspected = 0
    for path in sorted(_APP_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if node.func.attr not in _INVOKE_METHODS:
                continue
            receiver = ast.unparse(node.func.value)
            where = f"{path.relative_to(_APP_DIR.parent)}:{node.lineno} ({receiver}.{node.func.attr})"
            if receiver in _NON_LLM_RECEIVERS:
                continue
            if receiver not in _LLM_RECEIVERS:
                unclassified.append(where)
                continue
            inspected += 1
            if "run_name" not in ast.unparse(node):
                unlabeled.append(where)
    return unlabeled, unclassified, inspected


_EVAL_MEASURE_PATH = _APP_DIR.parent / "evals" / "run_e2e_measure.py"


def _eval_router_labels() -> set[str]:
    """evals/run_e2e_measure.py 의 _ROUTER_LABELS 리터럴 — import 하지 않고 소스에서 읽는다.

    그 모듈은 예산 확인 게이트가 붙은 실행기라 테스트가 import 할 대상이 아니다. AST 로 상수만
    떠 온다 (부작용·LLM import 0).
    """
    tree = ast.parse(_EVAL_MEASURE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_ROUTER_LABELS" for t in node.targets):
            continue
        value = node.value
        if isinstance(value, ast.Call) and value.args:  # frozenset({...})
            return set(ast.literal_eval(value.args[0]))
    raise AssertionError(f"_ROUTER_LABELS 리터럴을 찾지 못함: {_EVAL_MEASURE_PATH}")


async def test_router_label_lockstep_with_eval_classifier() -> str:
    """프로덕션 라벨 ↔ evals 라우터 분류표 lockstep — 주석이 아니라 기계로 확인한다.

    이 짝이 갈리면 라우터 호출이 generator 로 집계돼 절감 판정이 조용히 틀어진다. 문자열 하나
    (공백 유무 포함) 어긋나도 여기서 잡힌다.
    """
    labels = _eval_router_labels()
    assert labels, "evals 라우터 분류표가 비었다 — 분류가 통째로 죽는다"
    assert _RUN_NAME_PARAM in labels, (
        f"param(라우터) 라벨 {_RUN_NAME_PARAM!r} 이 evals 분류표에 없다 → 라우터 토큰이 generator 로 샌다: {labels}"
    )
    assert _RUN_NAME_WRITER not in labels, f"writer 는 generator 모델인데 라우터로 분류돼 있다: {_RUN_NAME_WRITER!r}"
    print(f"  라우터 분류표 {len(labels)}개와 lockstep 확인 (param={_RUN_NAME_PARAM!r})")
    return "test_router_label_lockstep_with_eval_classifier"


async def test_no_unlabeled_llm_call_site() -> str:
    """app/ 전수 — LLM 호출 지점 중 run_name 없는 곳이 0개 (관측 사각 0)."""
    unlabeled, unclassified, inspected = _llm_call_sites()
    assert not unclassified, (
        f"분류되지 않은 invoke 수신자 — LLM 인지 아닌지 사람이 판정해 표에 넣어야 한다: {unclassified}"
    )
    assert not unlabeled, f"run_name 없는 LLM 호출 = usage tracker 관측 사각: {unlabeled}"
    assert inspected == _EXPECTED_LLM_CALL_SITES, (
        f"LLM 호출 지점 수 변동: {inspected} != {_EXPECTED_LLM_CALL_SITES}. "
        "지점이 늘었으면 run_name 부착을 확인하고 핀을 올리고, 줄었으면 관측이 사라진 게 아닌지 확인하라."
    )
    print(f"  LLM 호출 지점 {inspected}개 전수 검사 — run_name 부재 0, 미분류 수신자 0")
    return "test_no_unlabeled_llm_call_site"


class _EmptyArgs(BaseModel):
    query: str = ""


class _FakeChatModel(BaseChatModel):
    """콜백이 실제로 발화하는 최소 BaseChatModel — 외부 API 호출 0회.

    스텁이 라벨을 자칭하는 테스트는 "프로덕션 트래커가 그 라벨로 잡는가"를 증명하지 못한다
    (이 PR 의 관측 사각이 정확히 그 틈에서 났다). 여기서는 langchain 의 콜백·run_name 배선을
    그대로 태워, 라벨이 실제로 usage 에 그렇게 찍히는지 본다.
    """

    replies: list = []

    @property
    def _llm_type(self) -> str:
        return "fake-chat"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return ChatResult(generations=[ChatGeneration(message=reply)])

    def bind_tools(self, tools, **kwargs):
        return self.bind(tools=tools, **kwargs)


def _msg(content: str, **kwargs) -> AIMessage:
    return AIMessage(
        content=content, usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110}, **kwargs
    )


async def test_subagent_router_and_writer_get_distinct_labels() -> str:
    """sub-agent 파이프라인 실경로 — param(라우터)·writer(generator)가 각자 라벨로 잡힌다.

    회귀 방향(실측): run_name 두 줄을 떼고 돌리면 by_node 가
    ``{'다음판단': …, '인자생성': …}`` 로 잡힌다 — langgraph 노드명 폴백이다. 공백 없는
    '인자생성' 은 evals 의 라우터 라벨('인자 생성')과 달라 라우터로 분류되지 않는다.
    조상 라벨(sub-agent 명) 흡수도 같은 결과이므로 그쪽 부재까지 함께 단언한다.
    """
    tool_name = "doc_search_topic_workspace"

    async def _run(query: str = "") -> str:
        return "검색 결과: 목표주가 128,000원"

    tool = StructuredTool.from_function(
        coroutine=_run, name=tool_name, description="내 워크스페이스 문서 검색", args_schema=_EmptyArgs
    )
    writer = _FakeChatModel(
        replies=[
            _msg(json.dumps({"enough": False, "next_tool": tool_name, "intent": "목표주가"}, ensure_ascii=False)),
            _msg(json.dumps({"enough": True, "answer": "목표주가는 128,000원"}, ensure_ascii=False)),
        ]
    )
    param = _FakeChatModel(
        replies=[
            _msg("", tool_calls=[{"name": tool_name, "args": {"query": "목표주가"}, "id": "p1", "type": "tool_call"}])
        ]
    )
    graph = build_pipeline_subagent(writer_llm=writer, param_llm=param, tools=[tool], base_prompt="t", footer="")

    tracker = UsageTracker()
    await graph.ainvoke(
        {"messages": [HumanMessage(content="업로드한 리포트에서 목표주가 찾아줘")]},
        # run_name=sub-agent 명 — graphs/shared.py 가 실제로 씌우는 조상 라벨을 재현한다
        config={"callbacks": [tracker], "run_name": "financials_sub"},
    )
    by_node = tracker.by_node
    print(f"  sub-agent 실경로 usage by_node={by_node}")
    assert _RUN_NAME_PARAM in by_node, f"라우터(인자 생성) 호출이 관측되지 않음 — 관측 사각: {by_node}"
    assert _RUN_NAME_WRITER in by_node, f"writer(generator) 호출이 관측되지 않음: {by_node}"
    assert "financials_sub" not in by_node, f"조상 라벨로 흡수됨 — 라우터/generator 분리 실패: {by_node}"
    assert by_node[_RUN_NAME_PARAM]["calls"] == 1, by_node
    assert by_node[_RUN_NAME_PARAM]["input_tokens"] > 0, "실측 usage 가 0 — 귀속은 됐으나 토큰이 안 잡힘"
    assert tracker.estimated is False, "usage_metadata 가 있는데 근사 폴백이 탔다"
    return "test_subagent_router_and_writer_get_distinct_labels"


async def _main() -> int:
    tests = [
        test_nested_run_resolves_parent_run_name,
        test_direct_run_name_and_llm_output_fallback,
        test_accumulates_same_run_name,
        test_estimation_fallback_marks_estimated,
        test_generic_framework_names_not_used_as_labels,
        test_unresolved_falls_back_to_langgraph_node_metadata,
        test_summary_line_shape,
        test_no_unlabeled_llm_call_site,
        test_router_label_lockstep_with_eval_classifier,
        test_subagent_router_and_writer_get_distinct_labels,
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
