"""#197 — 강제검색 폴백의 결정론적 도구 선택 (E-197 Tier 0, LLM 호출 0회 — 이 이슈는 Tier 0 만으로 판정 완결).

표 기반 단위 테스트 + 스텁 파이프라인 통합: writer 스텁이 예외를 던지는 첫 진입에서
문서 의도 task 가 workspace 도구 강제 검색으로 이어지는지 검증한다.
도구 설명은 실제 MCP 라우터(disclosure_router·vector_search_router·workspace_router)의
docstring 발췌 — 표가 현실 설명 기준으로 성립함을 보장한다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_pipeline_fallback_tool.py
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from graphs import pipeline_subagent  # noqa: E402
from graphs.pipeline_subagent import _fallback_scores, _fallback_tool_for, build_pipeline_subagent  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langchain_core.tools import StructuredTool  # noqa: E402
from pydantic import BaseModel  # noqa: E402


class _NamedTool:
    """_fallback_tool_for 는 name/description 만 읽는다 — 표 검증용 경량 더블."""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description


# financials_sub 스펙 순서 그대로 (agents/domains/financials.py) — 설명은 실제 MCP 라우터 발췌
_T_FIN = _NamedTool(
    "disclosure_financials",
    "단일 발행사의 재무제표 핵심 계정(매출액·영업이익·당기순이익·자산/부채/자본총계)을 "
    "사업연도·보고서 종류·연결/별도 기준으로 조회한다 — 수익성·성장성·재무건전성 분석의 1차 근거.",
)
_T_COM = _NamedTool(
    "disclosure_company",
    "회사명·종목코드(6자리)·고유번호(corp_code)로 공시 대상 발행사를 찾는다 — "
    "재무·공시·배당·최대주주 도구를 호출하기 전 발행사를 정확히 식별하는 진입점.",
)
_T_EARN = _NamedTool(
    "doc_search_topic_earnings",
    "실적 분야 금융 문서 텍스트 검색. 실적발표·어닝콜 스크립트·IR 자료·실적 리뷰 리포트 본문/Q&A 청크를 반환.",
)
_T_WS = _NamedTool(
    "doc_search_topic_workspace",
    "내 워크스페이스(사용자 업로드) 문서 텍스트 검색. 사용자가 올린 리포트·문서를 청크로 색인한 "
    "개인/회사 전용 코퍼스에서 관련 청크를 반환한다.",
)
_ALL4 = [_T_FIN, _T_COM, _T_EARN, _T_WS]


def test_doc_task_full_toolset_picks_workspace() -> str:
    """업로드 문서 task + 전체 4종 → workspace (#197 핵심 결함 방향)."""
    picked = _fallback_tool_for("업로드한 리서치 보고서에서 목표주가 찾아줘", _ALL4)
    assert picked == "doc_search_topic_workspace", f"기대 workspace, 실제 {picked}"
    return "test_doc_task_full_toolset_picks_workspace"


def test_doc_task_partial_binding_picks_workspace() -> str:
    """#197 관측 환경 재현 — disclosure 2종 미바인딩(earnings+workspace만)에서도 workspace."""
    picked = _fallback_tool_for("업로드한 리서치 보고서에서 목표주가 찾아줘", [_T_EARN, _T_WS])
    assert picked == "doc_search_topic_workspace", f"기대 workspace, 실제 {picked}"
    return "test_doc_task_partial_binding_picks_workspace"


def test_earnings_task_not_pushed_to_workspace() -> str:
    """실적 task + 전체 4종 → earnings 또는 disclosure_* (workspace 아님 — 역회귀 방지)."""
    picked = _fallback_tool_for("삼성전자 분기 실적 요약", _ALL4)
    assert picked in ("doc_search_topic_earnings", "disclosure_financials", "disclosure_company"), picked
    assert picked != "doc_search_topic_workspace", "실적 질문이 workspace 로 밀림 (역회귀)"
    scores = _fallback_scores("삼성전자 분기 실적 요약", _ALL4)
    assert scores["doc_search_topic_workspace"] == 0, f"workspace 는 문서 신호 없이 0점이어야 함: {scores}"
    assert scores[picked] > 0, f"선택 도구가 무점수 — 신호를 못 읽음: {scores}"
    return "test_earnings_task_not_pushed_to_workspace"


def test_no_signal_task_keeps_spec_order_first() -> str:
    """신호 없는 task(전원 0점) → 첫 도구 (현행 스펙 순서 동작 보존)."""
    scores = _fallback_scores("이 종목 어때", _ALL4)
    assert all(v == 0 for v in scores.values()), f"전원 0점 전제 깨짐: {scores}"
    picked = _fallback_tool_for("이 종목 어때", _ALL4)
    assert picked == "disclosure_financials", f"기대 첫 도구, 실제 {picked}"
    return "test_no_signal_task_keeps_spec_order_first"


def test_single_and_empty_toolset_edges() -> str:
    """경계 — 도구 1개면 그 도구(신호 무관), 0개면 None."""
    assert _fallback_tool_for("아무 질문", [_T_WS]) == "doc_search_topic_workspace"
    assert _fallback_tool_for("아무 질문", [_T_EARN]) == "doc_search_topic_earnings"
    assert _fallback_tool_for("아무 질문", []) is None
    return "test_single_and_empty_toolset_edges"


# ── 어휘 목록 의존 결함 (리뷰 실측 반례) ──────────────────────────────────────
# 신호를 단일 한국어 목록으로 읽던 판은 아래 질의에서 workspace 0점 → 스펙 순서 첫 도구로
# 떨어졌다. 조합 판정(명시 A / 문서명사 C + 소유·지시 B|제공행위 A2)이 이 부류를 받는다.

_EN_DOC_QUERIES = (
    "find the target price in my uploaded report",  # A(upload) · B(my)+C(report) 이중 성립
    "summarize the document I attached",  # A(attach) · C(document)
    "what does my report say about the target price",  # A 없음 — B+C 만으로 성립
)
_KO_UNLISTED_SYNONYM_QUERIES = (
    "올려둔 파일에서 목표주가 찾아줘",  # A(올려) — 어미 변화 흡수
    "제출한 리포트 정리해줘",  # A2(제출한)+C(리포트)
    "붙인 자료 요약해줘",  # A2(붙인)+C(자료)
    "우리가 제출한 자료 요약",  # 제3자 주어 표지가 A2 를 막아도 B(우리)+C 가 받는다
)


def test_english_doc_task_picks_workspace() -> str:
    """영문 업로드 문서 질의 → workspace (한국어 어휘 목록에 묶여 뚫렸던 구간)."""
    for q in _EN_DOC_QUERIES:
        picked = _fallback_tool_for(q, _ALL4)
        assert picked == "doc_search_topic_workspace", f"{q!r} → 기대 workspace, 실제 {picked}"
    return "test_english_doc_task_picks_workspace"


def test_unlisted_korean_synonyms_pick_workspace() -> str:
    """미등재 한국어 동의어(올려둔·제출한·붙인) → workspace."""
    for q in _KO_UNLISTED_SYNONYM_QUERIES:
        picked = _fallback_tool_for(q, _ALL4)
        assert picked == "doc_search_topic_workspace", f"{q!r} → 기대 workspace, 실제 {picked}"
    return "test_unlisted_korean_synonyms_pick_workspace"


@contextmanager
def _factor_removed(attr: str):
    """신호 요소 하나를 통째로 비운다 — 목록 의존도 측정용 (원복 보장)."""
    original = getattr(pipeline_subagent, attr)
    setattr(pipeline_subagent, attr, ((), re.compile(r"(?!x)x")))  # 절대 매칭 안 되는 패턴
    try:
        yield
    finally:
        setattr(pipeline_subagent, attr, original)


def test_signal_survives_single_factor_removal() -> str:
    """목록 의존도 — 요소 하나를 통째로 비워도 영문 질의는 남은 조합으로 성립한다.

    어휘를 넓히기만 하면 항목 하나가 빠질 때 그대로 뚫린다. 조합 판정이라 A 를 비우면 B+C 가,
    B 를 비우면 A 가 받는다 — 이 중복성이 처방의 근거다 (한국어 A2 경로는 아래 한계 참조).
    """
    q = "find the target price in my uploaded report"
    with _factor_removed("_SIG_EXPLICIT"):  # A 제거 → B(my)+C(report) 로 성립
        assert _fallback_tool_for(q, _ALL4) == "doc_search_topic_workspace", "A 제거 시 B+C 가 못 받음"
    with _factor_removed("_SIG_POSSESSIVE"):  # B 제거 → A(upload) 로 성립
        assert _fallback_tool_for(q, _ALL4) == "doc_search_topic_workspace", "B 제거 시 A 가 못 받음"
    with _factor_removed("_SIG_DOC_NOUN"):  # C 제거 → A 로 성립
        assert _fallback_tool_for(q, _ALL4) == "doc_search_topic_workspace", "C 제거 시 A 가 못 받음"
    return "test_signal_survives_single_factor_removal"


def test_compound_words_do_not_fake_doc_signal() -> str:
    """과확장 차단 — 짧은 신호 어휘가 합성어 안쪽에 먹혀 오탐하지 않는다.

    신호를 넓히면 반대 방향 결함(실적·공시 질문이 workspace 로 밀림)이 생긴다. 아래는 넓히는
    과정에서 실제로 뚫렸던 합성어들이다: 국내/안내(→"내 "), 우리금융(→"우리"),
    끌어올린(→"올린"), 덧붙인(→"붙인"), 파일럿(→"파일").
    """
    for q in (
        "국내 증권사 보고서 요약해줘",
        "우리금융 실적 자료 알려줘",
        "주가를 끌어올린 요인 리포트로 정리해줘",
        "파일럿 사업 관련 국내 자료 찾아줘",
        "안내문서 어디 있어",
        "덧붙인 설명 말고 원문 보고서 보여줘",
    ):
        scores = _fallback_scores(q, _ALL4)
        assert scores["doc_search_topic_workspace"] == 0, f"{q!r} 가 업로드 신호로 오탐: {scores}"
    return "test_compound_words_do_not_fake_doc_signal"


def test_first_person_subject_is_not_third_party() -> str:
    """제3자 주어 상쇄가 1인칭 주어(내가·제가·우리가)까지 잡아먹지 않는다."""
    for q in ("내가 제출한 리포트 정리해줘", "제가 등록한 자료 요약", "우리가 제출한 자료 요약"):
        picked = _fallback_tool_for(q, _ALL4)
        assert picked == "doc_search_topic_workspace", f"{q!r} → 기대 workspace, 실제 {picked}"
    return "test_first_person_subject_is_not_third_party"


def test_third_party_submission_stays_disclosure() -> str:
    """제3자가 제출한 공시 문서는 업로드 신호가 아니다 — A2 확장이 부른 역회귀 차단."""
    for q in ("삼성전자가 금감원에 제출한 사업보고서 요약해줘", "삼성전자가 공시한 사업보고서 요약해줘"):
        scores = _fallback_scores(q, _ALL4)
        assert scores["doc_search_topic_workspace"] == 0, f"{q!r} 가 업로드 신호로 읽힘: {scores}"
        assert _fallback_tool_for(q, _ALL4) != "doc_search_topic_workspace", q
    return "test_third_party_submission_stays_disclosure"


def test_unrecognized_phrasing_still_falls_to_spec_order() -> str:
    """남는 한계를 명시 고정 — 결정론 폴백은 미등재 표현을 원리적으로 다 덮지 못한다.

    이 경로는 LLM 실패 시 도는 폴백이라 의도 분류를 LLM 에 물을 수 없다. 아래처럼 어떤 요소도
    안 걸리는 표현은 여전히 스펙 순서 첫 도구로 떨어진다 — 없앤 것이 아니라 **관측 대상으로
    돌린 것**이다(전원 0점이면 writer_node 가 task 를 warning 으로 남긴다). 이 케이스가
    깨지면(=workspace 로 붙으면) 신호가 과하게 넓어진 것이므로 그 방향도 여기서 잡는다.
    """
    q = "네가 갖고 있는 그거 정리해줘"
    scores = _fallback_scores(q, _ALL4)
    assert all(v == 0 for v in scores.values()), f"전원 0점 전제 깨짐: {scores}"
    assert _fallback_tool_for(q, _ALL4) == "disclosure_financials", "0점 폴백의 스펙 순서 보존이 깨짐"
    return "test_unrecognized_phrasing_still_falls_to_spec_order"


# ── 스텁 파이프라인 통합 — writer 예외 → 강제 검색이 실제 도구 호출로 이어지는가 ──


class _RaisingWriter:
    """writer LLM 스텁 — 항상 예외 (429 소진 상황 재현)."""

    async def ainvoke(self, messages: list, config: dict | None = None):
        raise RuntimeError("rate limited (스텁)")


class _StubParam:
    """param LLM 스텁 — tool_choice 도구를 빈 인자로 호출하는 tool_calls 반환."""

    def bind_tools(self, tools: list, tool_choice: str | None = None):
        self._choice = tool_choice or tools[0].name
        return self

    async def ainvoke(self, messages: list, config: dict | None = None):
        return AIMessage(
            content="", tool_calls=[{"name": self._choice, "args": {}, "id": "call-1", "type": "tool_call"}]
        )


class _EmptyArgs(BaseModel):
    query: str = ""


def _stub_tool(name: str, description: str, called: list[str]) -> StructuredTool:
    async def _run(query: str = "") -> str:
        called.append(name)
        return f"{name} 검색 결과: 목표주가 128,000원 관련 청크"

    return StructuredTool.from_function(coroutine=_run, name=name, description=description, args_schema=_EmptyArgs)


async def test_pipeline_writer_failure_forces_workspace_search() -> str:
    """문서 의도 task 에서 writer 첫 진입 예외 → workspace 도구가 실제 호출됐는지.

    한국어·영문 두 질의로 돌린다 — 종전 케이스가 한국어만 덮어 영문 구간이 회귀 그물 밖이었다.
    """
    for question in ("업로드한 리서치 보고서에서 목표주가 찾아줘", "find the target price in my uploaded report"):
        called: list[str] = []
        tools = [_stub_tool(t.name, t.description, called) for t in _ALL4]
        graph = build_pipeline_subagent(
            writer_llm=_RaisingWriter(), param_llm=_StubParam(), tools=tools, base_prompt="테스트", footer=""
        )
        out = await graph.ainvoke({"messages": [HumanMessage(content=question)]})
        assert called, f"폴백이 어떤 도구도 호출하지 않음 (그물 자체가 안 돌았음): {question!r}"
        assert called[0] == "doc_search_topic_workspace", f"{question!r} → 기대 workspace, 실제 {called}"
        assert out.get("messages"), "파이프라인이 메시지를 반환하지 않음"
    return "test_pipeline_writer_failure_forces_workspace_search"


async def _main() -> int:
    sync_tests = [
        test_doc_task_full_toolset_picks_workspace,
        test_doc_task_partial_binding_picks_workspace,
        test_earnings_task_not_pushed_to_workspace,
        test_no_signal_task_keeps_spec_order_first,
        test_single_and_empty_toolset_edges,
        test_english_doc_task_picks_workspace,
        test_unlisted_korean_synonyms_pick_workspace,
        test_signal_survives_single_factor_removal,
        test_compound_words_do_not_fake_doc_signal,
        test_first_person_subject_is_not_third_party,
        test_third_party_submission_stays_disclosure,
        test_unrecognized_phrasing_still_falls_to_spec_order,
    ]
    passed = 0
    for tc in sync_tests:
        print(f"PASS {tc()}")
        passed += 1
    print(f"PASS {await test_pipeline_writer_failure_forces_workspace_search()}")
    passed += 1
    total = len(sync_tests) + 1
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
