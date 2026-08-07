"""Hierarchical Map-Reduce 노드 — 도메인별 sub-answer(Map) → 통합 답변(Reduce).

활성 도메인이 임계 이상일 때 _route_after_execute 가 이 경로로 보낸다. Map 은 도메인별 병렬 LLM
호출(완료 즉시 SSE chunk push), Reduce 는 sub-answer 들을 단일 통합 답변으로 합친다.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from core.logger import logger
from graphs.shared import _WRITER_SYSTEM, _WRITER_USER_TEMPLATE, join_tool_evidence
from graphs.system import (
    ANSWER_SYSTEM,
    ANSWER_USER_TEMPLATE,
    MAP_DOMAIN_SYSTEM,
    MAP_DOMAIN_USER_TEMPLATE,
    REDUCE_SYSTEM,
    REDUCE_USER_TEMPLATE,
)
from langchain_core.runnables import RunnableConfig
from utils.agent.prompting import build_node_messages
from utils.redaction.redactor import redact_operational_info

from .compliance import _ensure_disclaimer
from .context import _build_history_ctx, _extract_query, _format_all_results_for_answer, _message_text
from .deps import _GraphDeps
from .domains_map import _DOMAIN_LABELS, _classify_domain, _format_domain_results, _group_results_by_domain
from .schemas import PlanExecuteState


def _emit_map_completed(stream_writer: Any, result: dict[str, Any]) -> None:
    """도메인 sub-answer 완료 SSE chunk push (best-effort). OK·FAILED 공통."""
    if stream_writer is None:
        return
    try:
        stream_writer(
            {
                "event": "map_domain_completed",
                "domain": result["domain"],
                "domain_label": result["domain_label"],
                "narrative": result["narrative"],
                "status": result["status"],
            }
        )
    except Exception as e:
        logger.debug("[map] stream_writer push 실패 (%s)", e)


def _make_map_failed(domain: str, domain_label: str, reason: str, agent_count: int) -> dict[str, Any]:
    """Map 실패 stub. reason='timeout'|'exception' — Reduce 가 자연어로 흡수."""
    suffix = " (timeout)" if reason == "timeout" else ""
    return {
        "status": "FAILED",
        "domain": domain,
        "domain_label": domain_label,
        "stub": f"[DOMAIN_FAILED:{domain}:{reason}]",
        "narrative": f"<{domain_label} 도메인 정보 일시 수집 불가{suffix}>",
        "agent_count": agent_count,
    }


async def _map_domain_answer(
    deps: _GraphDeps,
    domain: str,
    domain_items: list[dict],
    query: str,
    config: RunnableConfig,
    semaphore: asyncio.Semaphore,
    stream_writer: Any = None,
    tool_calls_for_domain: list[dict] | None = None,
) -> dict[str, Any]:
    """단일 도메인 sub-answer 생성. Semaphore 로 동시성 제한. 실패 시 메타 stub 반환."""
    tool_calls_for_domain = tool_calls_for_domain or []
    async with semaphore:
        domain_label = _DOMAIN_LABELS.get(domain, domain)
        domain_results_text = _format_domain_results(domain_items)

        # Writer-as-Map: writer_llm 주입 시 항상 활성. MA_WRITER_AS_MAP=false 로 비상 우회.
        use_writer = deps.writer_llm is not None and os.getenv("MA_WRITER_AS_MAP", "true").lower() != "false"
        if use_writer:
            # tool 출력은 LLM context 진입 직전 결정론 redaction — context.py 소비 경로와 동일 계약
            domain_evidence_blocks = [
                f"[tool={tc.get('tool', '?')}] input={tc.get('input', '')}"
                f"\noutput=\n{redact_operational_info(str(tc.get('output', '')))}"
                for tc in tool_calls_for_domain
            ]
            tool_evidence = join_tool_evidence(domain_evidence_blocks)
            writer_task = (
                f"투자 리서치 도메인 답변 작성 — 분야: {domain_label}\n\n"
                f"사용자 질문: {query}\n\n"
                f"이전 sub-agent들의 도메인 답변 (참고):\n{domain_results_text}\n\n"
                f"위 사용자 질문에 대해 {domain_label} 분야 관점에서 800-1500자 자연 narrative로 답변. "
                "헤더·메타 표현 없이 자연스럽게 시작."
            )
            messages = build_node_messages(
                _WRITER_SYSTEM, user_template=_WRITER_USER_TEMPLATE, task=writer_task, tool_evidence=tool_evidence
            )
            llm_to_use = deps.writer_llm
        else:
            messages = build_node_messages(
                MAP_DOMAIN_SYSTEM.format(domain_name=domain_label),
                user_template=MAP_DOMAIN_USER_TEMPLATE,
                query=query,
                domain_results=domain_results_text,
            )
            llm_to_use = deps.generator_llm

        t0 = time.monotonic()
        try:
            ans = await asyncio.wait_for(
                llm_to_use.ainvoke(messages, config={**config, "run_name": "도메인 답변 작성"}),
                timeout=deps.map_timeout_s,
            )
            narrative = _message_text(ans)
            elapsed = round(time.monotonic() - t0, 2)
            logger.info("[map] %s 완료 (%ss, %d자)", domain, elapsed, len(narrative))
            result = {
                "status": "OK",
                "domain": domain,
                "domain_label": domain_label,
                "narrative": narrative,
                "elapsed_s": elapsed,
                "agent_count": len(domain_items),
            }
            _emit_map_completed(stream_writer, result)
            return result
        except TimeoutError:
            logger.warning("[map] %s 타임아웃 (%.1fs)", domain, deps.map_timeout_s)
            result = _make_map_failed(domain, domain_label, "timeout", len(domain_items))
            _emit_map_completed(stream_writer, result)
            return result
        except Exception as e:
            logger.error("[map] %s 실패: %s", domain, e)
            result = _make_map_failed(domain, domain_label, "exception", len(domain_items))
            _emit_map_completed(stream_writer, result)
            return result


async def _map_answer_node(deps: _GraphDeps, state: PlanExecuteState, config: RunnableConfig) -> dict:
    """Map 단계: 도메인별 sub-answer 를 병렬 LLM 호출로 생성 (완료 즉시 SSE chunk push)."""
    try:
        from langgraph.config import get_stream_writer

        stream_writer = get_stream_writer()
    except Exception:
        stream_writer = None

    query = _extract_query(state["messages"])
    stage_results = state.get("stage_results") or []

    grouped = _group_results_by_domain(stage_results)
    # 4 도메인만 대상. 'other'는 reduce 가 별도 처리하지 않음 (stage_results 원본 보존).
    target_domains = [(domain, items) for domain, items in grouped.items() if domain in _DOMAIN_LABELS and items]
    if not target_domains:
        logger.warning("[map] 대상 도메인 없음 — answer_node 폴백 필요")
        return {"domain_answers": {}}

    if stream_writer is not None:
        try:
            stream_writer({"event": "map_started", "domains": [d for d, _ in target_domains]})
        except Exception:
            pass

    semaphore = asyncio.Semaphore(deps.map_concurrency)

    # Writer-as-Map: tool_calls trace 를 도메인별로 그룹핑하여 전달
    tool_calls_state = state.get("tool_calls") or []
    tool_calls_by_domain: dict[str, list[dict]] = {}
    for tc in tool_calls_state:
        tc_domain = _classify_domain(tc.get("agent", ""))
        if tc_domain:
            tool_calls_by_domain.setdefault(tc_domain, []).append(tc)

    coros = [
        _map_domain_answer(
            deps,
            domain,
            items,
            query,
            config,
            semaphore,
            stream_writer,
            tool_calls_for_domain=tool_calls_by_domain.get(domain, []),
        )
        for domain, items in target_domains
    ]
    results = await asyncio.gather(*coros, return_exceptions=False)

    domain_answers: dict[str, dict[str, Any]] = {r["domain"]: r for r in results}
    logger.info(
        "[map] 완료: %d 도메인 (OK=%d, FAILED=%d)",
        len(domain_answers),
        sum(1 for r in results if r["status"] == "OK"),
        sum(1 for r in results if r["status"] == "FAILED"),
    )
    return {"domain_answers": domain_answers}


def _build_sub_answers_section(domain_answers: dict[str, dict]) -> str:
    """도메인별 sub-answer 를 메타 마크업 없이 빈 줄로 분리해 사용자 응답 본문으로 포맷."""
    domain_order = ["instrument", "financials", "risk", "market"]
    ordered = sorted(
        domain_answers.items(),
        key=lambda kv: domain_order.index(kv[0]) if kv[0] in domain_order else 99,
    )
    return _ensure_disclaimer("\n\n".join(ans.get("narrative", "") for _, ans in ordered))


def _build_brief_summaries(domain_answers: dict[str, dict]) -> str:
    """Reduce LLM 입력용 — 영역별 sub-answer 풀텍스트 전달 (truncation 없음)."""
    lines = []
    for domain, ans in domain_answers.items():
        label = ans.get("domain_label") or _DOMAIN_LABELS.get(domain, domain)
        status = ans.get("status", "OK")
        narrative = ans.get("narrative", "")
        if status == "OK":
            lines.append(f"[{label}]\n{narrative}")
        else:
            lines.append(f"[{label}] (수집 실패)\n{narrative}")
    return "\n\n".join(lines)


async def _reduce_node(deps: _GraphDeps, state: PlanExecuteState, config: RunnableConfig) -> dict:
    """Full Reduce: 도메인 sub-answer 들을 input 으로 단일 통합 답변 생성.

    sub-answer 는 internal state 로만 활용 — final_answer 가 사용자에게 보일 유일한 답변.
    Reduce LLM 실패 시 sub-answer concat 폴백 (응답 0자 방지).
    """
    from langchain_core.messages import AIMessage

    query = _extract_query(state["messages"])
    domain_answers = state.get("domain_answers") or {}

    if not domain_answers:
        # _map_answer_node 가 빈 결과 반환했거나 라우팅 오류 — single answer 폴백.
        logger.warning("[reduce] domain_answers 비어있음 — single answer 폴백")
        stage_results = state.get("stage_results") or []
        context = _format_all_results_for_answer(stage_results)
        history_ctx = _build_history_ctx(state["messages"], k=20, max_total_chars=deps.history_max_chars)
        refused_str = ", ".join(state.get("refused_topics") or []) or "(없음)"
        if history_ctx:
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
                deps.generator_llm.ainvoke(messages, config={**config, "run_name": "답변 통합"}),
                timeout=deps.answer_timeout_s,
            )
            fallback_answer = _ensure_disclaimer(_message_text(ans))
        except Exception as e:
            logger.error("[reduce] 폴백 single answer 실패: %s", e)
            fallback_answer = "답변 생성 중 일시 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        return {"final_answer": fallback_answer, "messages": [AIMessage(content=fallback_answer)]}

    if deps.reduce_mode == "disabled":
        final_answer = _build_sub_answers_section(domain_answers)
        logger.info("[reduce] mode=disabled — sub-answer concat만")
        return {"final_answer": final_answer, "messages": [AIMessage(content=final_answer)]}

    sub_answers_input = _build_brief_summaries(domain_answers)
    reduce_messages = build_node_messages(
        REDUCE_SYSTEM, user_template=REDUCE_USER_TEMPLATE, query=query, domain_summaries_brief=sub_answers_input
    )
    try:
        ans = await asyncio.wait_for(
            deps.generator_llm.ainvoke(reduce_messages, config={**config, "run_name": "답변 통합"}),
            timeout=deps.answer_timeout_s,  # full reduce 는 sub-answer 들을 합치므로 answer_timeout 공유
        )
        final_answer = _ensure_disclaimer(_message_text(ans))
        logger.info("[reduce] 통합 답변 완료 (%d자)", len(final_answer))
    except Exception as e:
        logger.warning("[reduce] 통합 실패 — sub-answer concat 폴백: %s", e)
        final_answer = _build_sub_answers_section(domain_answers)

    return {"final_answer": final_answer, "messages": [AIMessage(content=final_answer)]}
