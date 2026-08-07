"""보충질문·거절 응답이 최종 답변 취급을 받지 않는지 검증 (#364) — fail-closed.

## 왜 있나

clarify(보충질문)·refuse(도메인 밖 거절) 분기에서 그 문구를 `answer_text_full` 에 담았는데,
이 변수의 소비처가 넷이라 되물음이 **최종 답변처럼** 취급됐다:

  · `_response_cache.set` → **같은 질문을 다시 하면 캐시 히트로 보충질문이 답변으로 반환된다**
  · 컴플라이언스 고지 append → 되물음 뒤에 「투자 조언이 아닙니다」가 붙어 나간다
  · 미근거 수치 주석 → 되물음에 수치 주석이 붙는다
  · `_gen_title` / `_gen_follow_up` → 되물음 턴마다 LLM 호출 2회가 더 발생한다

처방은 **히스토리 적재용 텍스트를 별도 변수(`history_text`)로 분리**해, 캐시·고지·후속질문
생성이 최종 답변에만 걸리게 하는 것이다. 히스토리 적재는 되물음도 대상이다 — 그래야 다음 턴
컨텍스트에서 AI 되물음이 사라지지 않는다(#357 리뷰 [E]).

## 무엇을 검사하나 (native `stream_query` · example-ai `stream_query_example_ai` 양쪽)

  (1) clarify 턴 — 캐시에 아무것도 저장되지 않는다
  (2) clarify 턴 — 같은 질문 재요청이 캐시 히트가 아니라 그래프를 다시 탄다
  (3) clarify 턴 — 되물음 문구에 컴플라이언스 고지가 붙지 않는다
  (4) clarify 턴 — 되물음이 `ai_chat_history` 에는 그대로 적재된다(#357 리뷰 [E] 회귀 방지)
  (5) refuse 턴 — (1)~(4)와 동일
  (6) 가드레일 차단 턴 — 캐시에 저장되지 않는다. 저장되면 다음 재질문이 캐시 히트로 들어와
      「차단 턴은 적재하지 않는다」(#357 리뷰 [F])가 캐시 경로로 우회된다
  (7) 대조군 — 정상 최종 답변 턴은 여전히 캐시되고, 고지가 붙고, 히스토리에 적재된다
      (수정이 정상 경로를 죽이지 않았다는 증거)
  (8) example-ai — 되물음 턴에서 title/follow_up LLM 호출이 0회다

검증 경계: 실제 LLM·MCP·그래프는 스텁이다. 확인 대상은 **그래프 노드 출력 → 캐시/고지/
히스토리로 갈라지는 서비스 계층의 분기**다. 그래프가 실제로 그 노드 출력을 내는지는 범위 밖
(`verify_stage_topology.py`·`verify_plan_execute_refactor.py` 소관).

`uv run python scripts/verify_clarify_not_cached.py` (cwd=multi-agent-service).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from graphs.plan_execute import COMPLIANCE_DISCLAIMER  # noqa: E402
from langchain_core.messages import AIMessageChunk  # noqa: E402
from services.agent.agent_service import AgentService  # noqa: E402
from services.agent.response_cache import ResponseCache  # noqa: E402
from utils.agent.events import MSG_CACHE_HIT  # noqa: E402

CLARIFY_TEXT = "어느 계좌를 말씀하시는지 알려주세요."
REFUSE_TEXT = "투자 리서치 범위 밖 질문이라 답변드릴 수 없습니다."
GUARDRAIL_TEXT = "안전 정책상 답변할 수 없습니다."
ANSWER_TEXT = "삼성전자 종가는 74,500원입니다."


class _FakeGraph:
    """지정한 (모드, 청크) 시퀀스를 그대로 흘리는 그래프 스텁. 호출 횟수를 센다."""

    def __init__(self, chunks: list[tuple[str, dict]]):
        self._chunks = chunks
        self.astream_calls = 0

    async def astream(self, inputs, config=None, stream_mode=None):
        self.astream_calls += 1
        for mode, chunk in self._chunks:
            yield mode, chunk


class _FakeHistoryRepo:
    def __init__(self):
        self.rows: list[dict] = []

    async def select_history(self, email: str, gid: int) -> list[dict]:
        return [r for r in self.rows if r["email"] == email and r["gid"] == gid]

    async def insert_turn(self, email: str, gid: int, question: str, answer: str) -> None:
        self.rows.append({"email": email, "gid": gid, "question": question, "answer": answer})


class _CountingLLM:
    """title/follow_up 생성 LLM 스텁 — 호출 횟수만 센다."""

    def __init__(self):
        self.calls = 0

    async def ainvoke(self, prompt, config=None):
        self.calls += 1
        return SimpleNamespace(content="제목")


def _config():
    return SimpleNamespace(
        MA_RESPONSE_CACHE_ENABLED=True,
        MA_RESPONSE_CACHE_MAX_ENTRIES=32,
        MA_RESPONSE_CACHE_TTL_S=600,
        MA_TRACE_TOKEN_USAGE=False,
    )


def _service(graph: _FakeGraph, repo: _FakeHistoryRepo, llm: _CountingLLM) -> AgentService:
    cfg = _config()
    svc = AgentService(
        config=cfg,
        mcp_client=None,
        router_llm=llm,
        planner_llm=llm,
        generator_llm=llm,
        evaluator_llm=llm,
        chat_history_repository=repo,
        response_cache=ResponseCache(cfg),
    )

    async def _stub_build_graph(enabled_mcps):
        return graph

    svc._build_graph = _stub_build_graph  # 실제 그래프 컴파일(LLM·MCP 필요) 대체
    return svc


async def _drain(agen) -> list[dict]:
    return [event async for event in agen]


CLARIFY_CHUNK = ("updates", {"보충질문확인": {"clarify_intent": "clarify", "clarification_question": CLARIFY_TEXT}})
REFUSE_CHUNK = ("updates", {"보충질문확인": {"clarify_intent": "refuse", "refusal_message": REFUSE_TEXT}})
GUARDRAIL_CHUNK = ("updates", {"보안검사": {"guardrail_blocked": True, "refusal_message": GUARDRAIL_TEXT}})

# 최종 답변이 흘러 들어오는 자리가 경로마다 다르다 — native 는 updates 의 답변통합 노드,
# example-ai 는 messages 모드의 답변 노드 토큰.
ANSWER_CHUNK = {
    "native": ("updates", {"답변통합": {"final_answer": ANSWER_TEXT}}),
    "example-ai": ("messages", (AIMessageChunk(content=ANSWER_TEXT), {"langgraph_node": "답변통합"})),
}


async def _scenario(path: str, chunks: list[tuple[str, dict]], question: str):
    """한 시나리오를 두 번 실행한다 — 두 번째 실행이 캐시 히트인지 보려고."""
    graph, repo, llm = _FakeGraph(chunks), _FakeHistoryRepo(), _CountingLLM()
    svc = _service(graph, repo, llm)
    run = svc.stream_query if path == "native" else svc.stream_query_example_ai
    first = await _drain(run(question, "u1@example.com", 1001, set()))
    second = await _drain(run(question, "u1@example.com", 1001, set()))
    return graph, repo, llm, first, second


def _texts(events: list[dict]) -> str:
    """이벤트에서 사용자에게 나간 본문만 이어 붙인다 (native: text / example-ai: response_chunk)."""
    return "".join(e.get("content") or "" for e in events if e.get("type") in ("text", "response_chunk"))


def _has_cache_hit(events: list[dict]) -> bool:
    return MSG_CACHE_HIT in repr(events)


# 최종 답변에만 걸려야 하는 후처리의 흔적 — 경로마다 다른 것이 붙는다.
#   native      : 근거 없음 caveat step (`grounding`/`no_evidence`)
#   example-ai  : 컴플라이언스 고지 append
def _final_answer_post_processing(path: str, events: list[dict]) -> str:
    if path == "native":
        marks = [e for e in events if e.get("type") == "step" and e.get("phase") == "grounding"]
        return repr(marks) if marks else ""
    return COMPLIANCE_DISCLAIMER if COMPLIANCE_DISCLAIMER in _texts(events) else ""


async def main() -> int:
    problems: list[str] = []
    checks = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal checks
        checks += 1
        if not cond:
            problems.append(f"{name} — {detail}" if detail else name)

    for path in ("native", "example-ai"):
        # (1)~(5) 되물음·거절 — 캐시 금지, 재요청은 그래프 재실행, 고지 미부착, 히스토리는 적재
        for label, chunk, text in (
            ("clarify", CLARIFY_CHUNK, CLARIFY_TEXT),
            ("refuse", REFUSE_CHUNK, REFUSE_TEXT),
        ):
            graph, repo, llm, first, second = await _scenario(path, [chunk], f"{label} 질문")
            check(f"[{path}/{label}] 재요청이 캐시 히트가 아니다", not _has_cache_hit(second), repr(second)[:300])
            check(
                f"[{path}/{label}] 재요청이 그래프를 다시 탄다",
                graph.astream_calls == 2,
                f"astream {graph.astream_calls}회",
            )
            marker = _final_answer_post_processing(path, first)
            check(f"[{path}/{label}] 되물음에 최종답변 후처리가 안 붙는다", marker == "", marker[:200])
            check(
                f"[{path}/{label}] 되물음이 히스토리에는 적재된다",
                [r["answer"] for r in repo.rows] == [text, text],
                str(repo.rows),
            )
            if path == "example-ai":
                # (8) title/follow_up 은 최종 답변에만 — 되물음 턴에서는 LLM 을 부르지 않는다
                check(f"[{path}/{label}] title/follow_up LLM 호출 0회", llm.calls == 0, f"{llm.calls}회")

        # (6) 가드레일 차단 — 캐시 금지 (캐시되면 「차단 턴 미적재」가 캐시 경로로 우회된다)
        graph, repo, llm, first, second = await _scenario(path, [GUARDRAIL_CHUNK], "차단 질문")
        check(f"[{path}/guardrail] 재요청이 캐시 히트가 아니다", not _has_cache_hit(second), repr(second)[:300])
        check(f"[{path}/guardrail] 히스토리 미적재 유지(#357 [F])", repo.rows == [], str(repo.rows))

        # (7) 대조군 — 정상 최종 답변은 캐시·고지·적재가 그대로다
        graph, repo, llm, first, second = await _scenario(path, [ANSWER_CHUNK[path]], "정상 질문")
        check(f"[{path}/answer] 재요청이 캐시 히트다", _has_cache_hit(second), repr(second)[:300])
        check(
            f"[{path}/answer] 재요청은 그래프를 안 탄다", graph.astream_calls == 1, f"astream {graph.astream_calls}회"
        )
        check(
            f"[{path}/answer] 최종 답변에는 후처리가 그대로 붙는다",
            _final_answer_post_processing(path, first) != "",
            _texts(first)[:200],
        )
        check(
            f"[{path}/answer] 최종 답변이 히스토리에 적재된다",
            len(repo.rows) == 2 and repo.rows[0]["answer"].startswith(ANSWER_TEXT),
            str(repo.rows)[:300],
        )

    if checks == 0:
        print("FAIL: 검사 0건 — 시나리오가 하나도 안 돌았다")
        return 1
    if problems:
        print("FAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"PASS: 보충질문·거절이 최종 답변 취급을 받지 않는다 (경로 2개 × 시나리오 4개 · 검사 {checks}건)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
