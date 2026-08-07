"""Plan-Execute 코어 노드 — 진입 게이트·계획·실행·재계획·답변.

각 노드는 (deps, state, config) 시그니처의 top-level async 함수다. build_plan_execute_graph()
가 functools.partial 로 deps 를 바인딩해 StateGraph 에 등록한다 (원래 클로저 캡처의 명시적 파라미터화).
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from core.logger import logger
from graphs.results import AgentResult
from graphs.system import (
    ANSWER_SYSTEM,
    ANSWER_USER_TEMPLATE,
    CLARIFY_SYSTEM,
    REPLAN_USER_TEMPLATE,
    SYNTHESIS_SYSTEM,
    SYNTHESIS_USER_TEMPLATE,
)
from langchain_core.runnables import RunnableConfig
from utils.agent.prompting import build_node_messages

from .compliance import _ensure_disclaimer
from .context import (
    _build_history_ctx,
    _extract_query,
    _format_all_results_for_answer,
    _format_prior_stage_results,
    _message_text,
)
from .deps import _GraphDeps
from .invocation import _invoke_agent_safe
from .schemas import ClarifyDecision, ExecutionPlan, PlanExecuteState, StageTask
from .topology import _normalize_stages

# 문서 의도 백스톱 어휘 (#204) — 명사군 1개 이상 AND 동사군 1개 이상일 때만 발동.
# 발동·비발동 문항 표는 tests/test_plan_status_and_backstop.py 와 lockstep (평가셋 정본 05 §E-204).
_DOC_INTENT_NOUNS = ("업로드", "문서", "보고서", "리포트", "자료", "노트", "pdf", "파일")
_DOC_INTENT_VERBS = ("요약", "정리", "검색", "찾아")

# plan LLM 실패 시 정직 안내문 — 기존 실패 문구 계열(_answer_node 예외 문구)과 정렬 (#204)
_PLAN_FAILURE_NOTICE = "현재 요청이 많아 계획 수립에 실패했습니다. 잠시 후 다시 시도해주세요."

_SEC_FAILCLOSED_TIMEOUT_MARKER = "<!-- SEC_FAILCLOSED_TIMEOUT -->"


class _TimeoutVerdict:
    """asyncio.wait_for 타임아웃 전용 차단 판정(#338).

    services.agent.guardrail.GuardrailVerdict 와 같은 인터페이스(is_safe/category/refusal_message)를
    이 그래프 계층에 국소적으로 복제한다 — graphs 는 services 를 import 하지 않는다(역의존 회피,
    builder.py 의 guardrail_fn 주입 방식과 동일한 경계).

    ⚠️ refusal_message 는 services.agent.guardrail.GUARDRAIL_UNAVAILABLE_MESSAGE 의 리터럴 복제다.
    import 로 묶을 수 없어(위 경계) 텍스트로 중복되므로, 한쪽만 고치면 조용히 갈라진다 —
    tests/test_guardrail_wait_for.py::test_unavailable_message_lockstep_with_guardrail_module 이
    두 문자열의 동일성을 검사한다. 문구를 바꾸면 그 테스트도 함께 통과하는지 확인할 것.
    """

    is_safe = False
    category = "unavailable"
    reason = "timeout"
    refusal_message = "보안 점검이 지금 응답하지 않아 요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요."


def _has_doc_intent(query: str) -> bool:
    q = (query or "").lower()
    return any(n in q for n in _DOC_INTENT_NOUNS) and any(v in q for v in _DOC_INTENT_VERBS)


async def _guardrail_node(deps: _GraphDeps, state: PlanExecuteState, config: RunnableConfig) -> dict:
    """보안 게이트(첫 노드) — 프롬프트 인젝션·유해 요청 차단. fail-closed.

    ⚠️ 히스토리 격리: 현재 질문만 검사한다(state messages 의 누적 대화 미전달) —
    멀티턴 사회공학("아까 허락했잖아") 인젝션을 막기 위한 불변. clarify(히스토리 참조)와 정반대 계약.

    ⚠️ 타임아웃: clarify·plan 노드와 동일하게 wait_for 로 감싼다(#275) — guardrail_fn(check_guardrail)
    은 LLM 예외(429 등)는 자체 try/except 로 fail-closed 하지만, 프로바이더가 응답 자체를 멈추면(행)
    그 await 는 영원히 끝나지 않아 이 노드가 그래프 첫 노드라 스트림 첫 응답까지 무기한 막힌다.
    타임아웃도 fail-closed 정책과 일관되게 차단한다(#338, guardrail.py check_guardrail 의 예외
    fail-closed 와 동일 방향) — 판정 불가는 안전 판정이 아니다. 대가: 가드레일 프로바이더 장애가
    채팅 전체 장애가 된다 — 그 대가를 알고 고른 결정이라 재시도로 통과시키지 않는다.
    """
    from langchain_core.messages import AIMessage

    if not deps.enable_guardrail or deps.guardrail_fn is None:
        return {"guardrail_blocked": False}

    query = _extract_query(state["messages"])
    try:
        verdict = await asyncio.wait_for(
            deps.guardrail_fn(query, deps.guardrail_llm, enabled=True, config={**config, "run_name": "보안 검사"}),
            timeout=deps.guardrail_timeout_s,
        )
    except TimeoutError:
        logger.error(
            "[guardrail] %s 응답 지연(%.0fs 초과) → fail-closed 차단",
            _SEC_FAILCLOSED_TIMEOUT_MARKER,
            deps.guardrail_timeout_s,
        )
        verdict = _TimeoutVerdict()
    if verdict.is_safe:
        return {"guardrail_blocked": False}

    refusal = verdict.refusal_message
    logger.info("[guardrail] 차단 (category=%s)", verdict.category or "?")
    return {
        "guardrail_blocked": True,
        "refusal_message": refusal,
        "messages": [AIMessage(content=refusal)],
        "final_answer": refusal,
    }


async def _clarify_node(deps: _GraphDeps, state: PlanExecuteState, config: RunnableConfig) -> dict:
    """쿼리의 금융·투자 도메인 적합성·모호성·논리적 가능성을 판단."""
    from langchain_core.messages import AIMessage

    query = _extract_query(state["messages"])
    history_ctx = _build_history_ctx(state["messages"], k=20, max_total_chars=deps.history_max_chars)

    refused_topics = state.get("refused_topics") or []
    refused_ctx = ""
    if refused_topics:
        refused_ctx = f"\n\n[이전 거절 주제]\n{', '.join(refused_topics)}\n동일 컨텍스트 후속 질의는 refuse 유지."

    user_part = (
        (f"[이전 대화]\n{history_ctx}\n\n" if history_ctx else "")
        + (refused_ctx.strip() + "\n\n" if refused_ctx else "")
        + f"[현재 질문]\n{query}"
    )

    try:
        decision: ClarifyDecision = await asyncio.wait_for(
            deps.clarifier.ainvoke(
                build_node_messages(CLARIFY_SYSTEM, user=user_part),
                config={**config, "run_name": "보충질문 판단"},
            ),
            timeout=deps.clarify_timeout_s,
        )
    except Exception as e:
        logger.warning("clarify_node 실패 — proceed로 폴백: %s", e)
        return {"clarify_intent": "proceed", "clarification_question": None, "refusal_message": None}

    intent = decision.intent.lower().strip()
    if intent not in ("proceed", "clarify", "refuse"):
        logger.warning("clarify_node 알 수 없는 intent '%s' — proceed로 폴백", intent)
        return {"clarify_intent": "proceed", "clarification_question": None, "refusal_message": None}

    if intent == "clarify":
        question = decision.question.strip() or "질문을 좀 더 구체적으로 알려주실 수 있을까요?"
        logger.info("[clarify] 명확화 요청: %s", question[:100])
        return {
            "clarify_intent": "clarify",
            "clarification_question": question,
            "refusal_message": None,
            "messages": [AIMessage(content=question)],
            "final_answer": question,
        }

    if intent == "refuse":
        parts = [decision.refusal_reason.strip()]
        if decision.suggestion.strip():
            parts.append(decision.suggestion.strip())
        refusal = "\n".join(p for p in parts if p) or "죄송하지만 이 질문은 금융·투자 리서치 답변 범위를 벗어납니다."
        logger.info("[clarify] 거절: %s", refusal[:100])
        prev_refused = state.get("refused_topics") or []
        new_refused = list(prev_refused) + [query[:120]]
        return {
            "clarify_intent": "refuse",
            "clarification_question": None,
            "refusal_message": refusal,
            "messages": [AIMessage(content=refusal)],
            "final_answer": refusal,
            "refused_topics": new_refused,
        }

    logger.debug("[clarify] proceed — plan으로 전달")
    return {"clarify_intent": "proceed", "clarification_question": None, "refusal_message": None}


async def _plan_node(deps: _GraphDeps, state: PlanExecuteState, config: RunnableConfig) -> dict:
    """LLM → ExecutionPlan 구조화 출력."""
    query = _extract_query(state["messages"])
    history_ctx = _build_history_ctx(state["messages"], k=20, max_total_chars=deps.history_max_chars)

    user_part = (f"[이전 대화]\n{history_ctx}\n\n" if history_ctx else "") + f"[현재 질문]\n{query}"

    plan_status = "ok"
    try:
        plan: ExecutionPlan = await asyncio.wait_for(
            deps.planner.ainvoke(
                build_node_messages(deps.plan_system, user=user_part),
                config={**config, "run_name": "계획 수립"},
            ),
            timeout=deps.plan_timeout_s,
        )
    except Exception as e:
        logger.error("plan_node 실패 [%s]: %r", type(e).__name__, e)
        plan = ExecutionPlan(stages=[])
        plan_status = "error"

    normalized = _normalize_stages(plan.stages)
    if len(normalized) != len(plan.stages):
        logger.info("[plan] stage 위상 정렬: planner=%d → normalized=%d", len(plan.stages), len(normalized))
    if plan_status == "ok" and not normalized:
        plan_status = "empty"
    if plan_status == "empty" and "financials_domain" in deps.agents and _has_doc_intent(query):
        # 정당한 빈 계획이지만 문서 의도가 명확 — 결정론 백스톱 1-stage 주입 (#204).
        # financials_domain 미활성(도메인 토글)이면 발동하지 않는다.
        backstop = StageTask(
            agent_name="financials_domain",
            task=f"업로드 문서에서 {query} 관련 내용 검색·요약: {query}",
        )
        plan = ExecutionPlan(stages=[[backstop]])
        normalized = _normalize_stages(plan.stages)
        plan_status = "backstop"
        logger.info("[plan] 문서 의도 백스톱 발동 → financials_domain 1-stage 주입")
    logger.info("[plan] stages=%d status=%s", len(normalized), plan_status)
    return {
        "plan": plan,
        "plan_status": plan_status,
        "stage_results": [],
        "agent_calls": [],
        "tool_calls": [],
        "pending_stages": normalized,
        "replan_count": 0,
    }


async def _run_stage_node(deps: _GraphDeps, state: PlanExecuteState, config: RunnableConfig) -> dict:
    """pending_stages 큐에서 stage 1개만 pop 해 실행 (stage 내 tasks 는 asyncio.gather 병렬).

    실행·계획 분리: 이 노드는 '실행'만 담당하고, 다음 stage 유무·재배정 판단은 _replan_node 가 한다.
    결과는 stage_results 에 누적하고, 남은 큐는 pending_stages 로 돌려 그래프 edge 가 루프를 돈다.
    """
    try:
        from langgraph.config import get_stream_writer

        sa_stream_writer = get_stream_writer()
    except Exception:
        sa_stream_writer = None

    pending: list = list(state.get("pending_stages") or [])
    all_results: list[dict] = list(state.get("stage_results") or [])
    agent_calls: list[str] = list(state.get("agent_calls") or [])
    tool_calls_sink: list[dict[str, Any]] = list(state.get("tool_calls") or [])

    if not pending:
        return {
            "stage_results": all_results,
            "agent_calls": agent_calls,
            "tool_calls": tool_calls_sink,
            "pending_stages": [],
        }

    stage_tasks = pending.pop(0)
    stage_idx = len(all_results)
    original_query = _extract_query(state["messages"])
    prior_ctx = _format_prior_stage_results(all_results, tool_calls_sink)

    coros = []
    valid_tasks = []
    for task_item in stage_tasks:
        agent = deps.agents.get(task_item.agent_name)
        if agent is None:
            logger.warning("알 수 없는 에이전트: %s", task_item.agent_name)
            continue
        # 원본 쿼리를 항상 포함 — 플래너가 짧은 task 를 생성해도 도메인 에이전트가 검색 맥락 확보
        enriched_task = f"[원래 질문]\n{original_query}\n\n[이 단계 작업]\n{task_item.task}"
        if prior_ctx:
            enriched_task += f"\n\n[이전 단계 결과 참고]\n{prior_ctx}"
        coros.append(
            _invoke_agent_safe(
                agent,
                enriched_task,
                task_item.agent_name,
                timeout=deps.agent_timeout,
                max_retries=deps.agent_max_retries,
                retry_delay=deps.agent_retry_delay,
                react_recursion_limit=deps.react_recursion_limit,
                tool_trace_sink=tool_calls_sink,
                stream_writer=sa_stream_writer,
                parent_config=config,
            )
        )
        valid_tasks.append(task_item)
        agent_calls.append(task_item.agent_name)

    if not coros:
        return {
            "stage_results": all_results,
            "agent_calls": agent_calls,
            "tool_calls": tool_calls_sink,
            "pending_stages": pending,
        }

    outputs: list[Any] = await asyncio.gather(*coros, return_exceptions=True)
    results_list: list[dict] = []
    for t, o in zip(valid_tasks, outputs, strict=False):
        if isinstance(o, AgentResult):
            rec = o.to_legacy_dict()
        elif isinstance(o, Exception):
            rec = AgentResult.exception(agent=t.agent_name, task=t.task, exc=o).to_legacy_dict()
        else:  # 방어: 구버전 str 반환 호환
            rec = {
                "agent": t.agent_name,
                "task": t.task,
                "output": str(o),
                "status": "ok",
                "error_type": "",
                "elapsed_s": 0.0,
                "group": -1,
            }
        # enriched(원본질문+이전결과 포함) 대신 계획 task 원문을 보존 — trace 가독 + 재계획 중복 판정 키
        rec["task"] = t.task
        results_list.append(rec)
    all_results.append({"stage": stage_idx, "results": results_list})
    success_domains = [r["agent"] for r in results_list if r.get("status") == "ok"]
    failed_domains = [f"{r['agent']}({r.get('status')})" for r in results_list if r.get("status") != "ok"]
    logger.info(
        "[execute] stage %d 완료: 성공=%s 실패=%s (남은 큐 %d)",
        stage_idx,
        success_domains,
        failed_domains or "(없음)",
        len(pending),
    )

    return {
        "stage_results": all_results,
        "agent_calls": agent_calls,
        "tool_calls": tool_calls_sink,
        "pending_stages": pending,
    }


async def _replan_node(deps: _GraphDeps, state: PlanExecuteState, config: RunnableConfig) -> dict:
    """별도 '재계획' 노드 — 직전 결과를 보고 순차 의존 후속 stage 를 동적으로 추가한다.

    pending_stages 가 남아 있으면(계획된 stage) LLM 호출 없이 통과. 비어 있고 상한 미만일 때만
    직전 결과+팀별 역량을 router LLM 으로 판단해, 새 식별자 기반 후속 조사를 적합한 팀에 배정한다.
    상한 3중: ReplanDecision.done + replan_count<max_replan + 중복 (agent, task) 차단.
    """
    try:
        from langgraph.config import get_stream_writer

        _stream_writer = get_stream_writer()
    except Exception:
        _stream_writer = None

    def _signal_done() -> dict:
        """실행 종료(더 이상 stage 없음) 신호 — 서비스가 media·답변시작 이벤트를 이 시점에 flush."""
        if _stream_writer is not None:
            try:
                _stream_writer({"event": "execution_complete"})
            except Exception as exc:
                logger.debug("[replan] execution_complete push 실패: %s", exc)
        return {}

    pending = state.get("pending_stages") or []
    if pending:
        return {}  # 계획된 stage 가 남음 — 그대로 다음 실행으로 통과 (실행 종료 아님)

    replan_count = state.get("replan_count") or 0
    stage_results = state.get("stage_results") or []
    if replan_count >= deps.max_replan:
        logger.info("[replan] 상한 도달 (count=%d, max=%d) — 종료", replan_count, deps.max_replan)
        return _signal_done()
    if not stage_results:
        return _signal_done()  # 실행 결과 없음 — 재계획 무의미

    tool_calls = state.get("tool_calls") or []
    prior_ctx = _format_prior_stage_results(stage_results, tool_calls)
    if not prior_ctx:
        return _signal_done()  # 성공 결과 없음 — 추가 조사 근거 없음

    query = _extract_query(state["messages"])
    executed_keys = {(r.get("agent"), r.get("task")) for st in stage_results for r in st.get("results", [])}
    executed_agents = sorted({r.get("agent") for st in stage_results for r in st.get("results", []) if r.get("agent")})
    user_part = REPLAN_USER_TEMPLATE.format(
        query=query, executed=", ".join(executed_agents) or "(없음)", prior=prior_ctx
    )

    try:
        decision = await asyncio.wait_for(
            deps.replanner.ainvoke(
                build_node_messages(deps.replan_system, user=user_part),
                config={**config, "run_name": "재계획 판단"},
            ),
            timeout=deps.plan_timeout_s,
        )
    except Exception as e:
        logger.warning("[replan] 판단 실패 — 종료로 폴백: %s", e)
        return _signal_done()

    if decision.done or not decision.next_stage:
        logger.info("[replan] done=%s — 종료 (%s)", decision.done, (decision.reason or "")[:80])
        return _signal_done()

    valid = []
    for t in decision.next_stage:
        if t.agent_name not in deps.agents:
            logger.warning("[replan] 알 수 없는 에이전트 %s 무시", t.agent_name)
            continue
        if (t.agent_name, t.task) in executed_keys:
            logger.info("[replan] 중복 stage (%s) 무시", t.agent_name)
            continue
        valid.append(t)
    if not valid:
        logger.info("[replan] 추가할 신규 task 없음 — 종료")
        return _signal_done()

    # 실행 완료 에이전트를 충족된 의존성으로 시딩 — 미시딩 시 직전 결과 의존이 순환으로 오판돼 정렬 무력화
    normalized = _normalize_stages([valid], completed=set(executed_agents))
    logger.info(
        "[replan] 추가 stage: %s (replan_count %d→%d, %s)",
        [t.agent_name for t in valid],
        replan_count,
        replan_count + 1,
        (decision.reason or "")[:80],
    )
    return {"pending_stages": normalized, "replan_count": replan_count + 1}


async def _answer_node(deps: _GraphDeps, state: PlanExecuteState, config: RunnableConfig) -> dict:
    """수집된 결과로 최종 답변 생성. stage_results 가 비어있으면 history 기반 종합."""
    from langchain_core.messages import AIMessage

    query = _extract_query(state["messages"])
    stage_results = state.get("stage_results") or []

    if state.get("plan_status") == "error" and not stage_results:
        # plan 실패를 빈 계획으로 위장하지 않는다 — generator 호출 없이 정직한 혼잡 안내
        # (429 폭주 중 무근거 generator 호출 1회 절약 — #204·#207 정합)
        return {"final_answer": _PLAN_FAILURE_NOTICE, "messages": [AIMessage(content=_PLAN_FAILURE_NOTICE)]}

    context = _format_all_results_for_answer(stage_results)

    history_ctx = _build_history_ctx(state["messages"], k=20, max_total_chars=deps.history_max_chars)

    refused_topics = state.get("refused_topics") or []
    refused_str = ", ".join(refused_topics) if refused_topics else "(없음)"

    if not stage_results and history_ctx:
        messages = build_node_messages(
            SYNTHESIS_SYSTEM, user_template=SYNTHESIS_USER_TEMPLATE, query=query, history=history_ctx
        )
    elif history_ctx:
        merged = f"[이전 턴 누적 컨텍스트]\n{history_ctx}\n\n[현재 턴 신규 수집 결과]\n{context}"
        messages = build_node_messages(
            ANSWER_SYSTEM,
            user_template=ANSWER_USER_TEMPLATE,
            query=query,
            context=merged,
            refused_topics=refused_str,
        )
    else:
        messages = build_node_messages(
            ANSWER_SYSTEM,
            user_template=ANSWER_USER_TEMPLATE,
            query=query,
            context=context,
            refused_topics=refused_str,
        )

    try:
        ans = await asyncio.wait_for(
            deps.generator_llm.ainvoke(messages, config={**config, "run_name": "답변 작성"}),
            timeout=deps.answer_timeout_s,
        )
        final_answer = _ensure_disclaimer(_message_text(ans))
    except Exception as e:
        logger.error("answer_node 실패: %s", e)
        final_answer = "답변 생성 중 일시 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

    # env-gated answer_node 진단 로깅
    if os.getenv("MA_TRACE_ANSWER_NODE", "").lower() == "true":
        trace = {
            "query": query,
            "stage_results_count": len(stage_results),
            "prompt_context_preview": context[:500],
            "final_answer_preview": final_answer[:500],
        }
        logger.info("MA_TRACE_ANSWER_NODE: %s", json.dumps(trace, ensure_ascii=False))

    return {"final_answer": final_answer, "messages": [AIMessage(content=final_answer)]}
