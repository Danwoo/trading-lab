"""멀티 에이전트 서비스 — Plan-Execute(Centralized) 그래프 운용.

구조:
    planner_llm → 도메인 에이전트 중 필요한 것들을 순차/병렬 호출 계획
    → 각 도메인 에이전트(RES pipeline) 실행 → generator_llm 이 결과 종합해 최종 답변

초기화는 main.py lifespan 에서 1회 (MCP tool 수집 + 기본 그래프 프리웜).
그래프는 (enabled_mcps, tool_map 버전) 키로 메모이즈 — 컴파일이 순수 CPU 로 이벤트루프를
블록하므로 요청마다 재빌드하지 않는다 (#120).
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator

from agents.registry import load_domain_registry
from agents.sub_agents import create_domain_agents, create_sub_agents, get_domain_descriptions
from clients.mcp.mcp_client import get_cached_tools
from core.logger import logger
from graphs.plan_execute import COMPLIANCE_DISCLAIMER, build_plan_execute_graph
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from services.agent.guardrail import check_guardrail
from services.agent.response_cache import ResponseCache, make_cache_key
from utils.agent import example_ai_events as tex
from utils.agent.events import (
    DOMAIN_KO_LABEL,
    MSG_ANSWER_STARTED,
    MSG_CACHE_HIT,
    MSG_CLARIFY_REQUESTED,
    MSG_EXECUTE_COMPLETED,
    MSG_EXECUTE_STARTED,
    MSG_GUARDRAIL_BLOCKED,
    MSG_PLAN_COMPLETED,
    MSG_PLAN_STARTED,
    MSG_REFUSE_OUT_OF_DOMAIN,
    clarification_event,
    domain_label,
    error_event,
    step_event,
    text_event,
    trace_event,
)
from utils.agent.grounding import any_sourced, compute_grounding
from utils.agent.mcp_classify import ALL_MCP_SERVICES, filter_tool_map
from utils.agent.numeric_guard import annotate_ungrounded_numbers
from utils.agent.plan_utils import plan_domains
from utils.agent.trace_metadata import build_trace_metadata
from utils.agent.usage_tracker import UsageTracker


class AgentService:
    """4도메인 멀티 에이전트 서비스. initialize() 후 stream_query() 사용."""

    def __init__(
        self,
        config,
        mcp_client,
        router_llm,
        planner_llm,
        generator_llm,
        evaluator_llm,
        chat_history_repository,
        response_cache: ResponseCache,
    ):
        self._config = config
        self._mcp_client = mcp_client
        self._router_llm = router_llm
        self._planner_llm = planner_llm
        self._generator_llm = generator_llm
        self._evaluator_llm = evaluator_llm
        self._chat_history_repo = chat_history_repository
        self._response_cache = response_cache
        self._tool_map: dict = {}
        self._tool_map_version = 0
        self._graph_cache: dict[tuple[frozenset[str], int], object] = {}
        self._domain_registry = None
        self._subagent_registry = None
        self._langfuse_enabled = False

    async def initialize(self) -> None:
        """MCP tool 수집 + domain registry 캐싱 + 기본 그래프(전체 MCP enabled) 프리웜. lifespan 1회."""
        await self._refresh_tool_map()
        self._subagent_registry, self._domain_registry = load_domain_registry(self._config.MULTI_AGENT_DOMAINS)
        logger.info(
            "[AgentService] 캐싱 완료: MCP tools %d개, 도메인 %d개",
            len(self._tool_map),
            len(self._domain_registry),
        )
        await self._build_graph(set(ALL_MCP_SERVICES))
        self._init_langfuse()

    async def _refresh_tool_map(self) -> None:
        """MCP tool 을 재수집해 tool_map 을 갱신한다. 기동 시 다운됐던 서버가 살아나면
        다음 요청에서 tool 이 그래프에 반영되도록 _build_graph 가 매 요청 호출한다.

        get_cached_tools 는 서버별 캐시라 수집값이 늘거나 유지만 될 뿐 줄지 않으므로(플래핑 없음),
        전량 수집 후에는 네트워크 없이 캐시를 반환해 사실상 no-op 이다.

        tool 집합이 변하면(서버 복구 — 단조 증가) 버전을 올리고 그래프 캐시를 비워
        다음 _build_graph 가 새 tool 로 재빌드하게 한다."""
        try:
            tools = await get_cached_tools(self._mcp_client)
        except Exception as e:
            logger.warning("[AgentService] MCP tool 수집 실패 (%s) — 현 tool_map 유지", e)
            return
        new_map = {t.name: t for t in tools}
        if set(new_map) != set(self._tool_map):
            self._tool_map_version += 1
            self._graph_cache.clear()
        self._tool_map = new_map

    def _init_langfuse(self) -> None:
        """langfuse 키 3종이 모두 있으면 client 를 초기화한다 — 이후 graph 실행이 langfuse 로 trace 된다."""
        cfg = self._config
        if cfg.LANGFUSE_PUBLIC_KEY and cfg.LANGFUSE_SECRET_KEY and cfg.LANGFUSE_HOST:
            Langfuse(public_key=cfg.LANGFUSE_PUBLIC_KEY, secret_key=cfg.LANGFUSE_SECRET_KEY, host=cfg.LANGFUSE_HOST)
            self._langfuse_enabled = True
            logger.info("[AgentService] langfuse tracing 활성 (host=%s)", cfg.LANGFUSE_HOST)

    def _stream_callbacks(self) -> list:
        """langfuse 활성 시 요청별 CallbackHandler — astream config 의 callbacks 로 넘긴다."""
        return [CallbackHandler()] if self._langfuse_enabled else []

    async def _build_graph(self, enabled_mcps: set[str]):
        """enabled MCP 의 tool 만 바인딩한 Plan-Execute 그래프 반환 — (enabled_mcps, tool_map 버전) 키 메모이즈.

        컴파일(17개 StateGraph, 순수 CPU ~100ms)이 이벤트루프를 블록해 동시 SSE 스트림의 토큰
        전송을 멈추므로 재사용한다 (#120). 캐시 키 상한은 enabled_mcps 조합(2^5) × tool_map
        버전(버전업 시 clear) — eviction 불필요. 동시 miss 의 중복 빌드는 허용(결과 동일·기동
        직후에만 드물게 발생 — 락 비용이 더 큼). 공유 그래프의 요청별 상태는
        config["configurable"]["delegate_runtime"] 로 격리된다 (wrap_agent_as_tool 참조)."""
        await self._refresh_tool_map()  # 기동 시 다운됐던 MCP 서버 복구분을 반영 (전량 수집 후 no-op)
        cache_key = (frozenset(enabled_mcps), self._tool_map_version)
        cached_graph = self._graph_cache.get(cache_key)
        if cached_graph is not None:
            return cached_graph
        tool_map = filter_tool_map(self._tool_map, enabled_mcps)
        sub_agents = await create_sub_agents(
            router_llm=self._router_llm,
            generator_llm=self._generator_llm,
            tool_map=tool_map,
            subagent_registry=self._subagent_registry,
        )
        # 파이프라인 writer(generator)가 답을 내므로 wrap 의 별도 writer 분리는 두지 않는다 → 마지막 AIMessage 사용
        domain_agents, _ = await create_domain_agents(
            router_llm=self._router_llm,
            sub_agents=sub_agents,
            domain_registry=self._domain_registry,
            subagent_registry=self._subagent_registry,
            sub_agent_timeout=self._config.MA_SUB_AGENT_TIMEOUT_S,
            max_sub_calls=self._config.MA_DELEGATE_MAX_CALLS,
        )
        graph = build_plan_execute_graph(
            planner_llm=self._planner_llm,
            generator_llm=self._generator_llm,
            agents=domain_agents,
            agent_timeout=self._config.MA_AGENT_TIMEOUT_S,
            agent_max_retries=self._config.MA_AGENT_MAX_RETRIES,
            agent_descriptions=get_domain_descriptions(self._domain_registry),
            plan_timeout_s=self._config.MA_PLAN_TIMEOUT_S,
            answer_timeout_s=self._config.MA_ANSWER_TIMEOUT_S,
            react_recursion_limit=self._config.MA_REACT_RECURSION_LIMIT,
            clarifier_llm=self._router_llm,
            clarify_timeout_s=self._config.MA_CLARIFY_TIMEOUT_S,
            guardrail_fn=check_guardrail,
            guardrail_llm=self._router_llm,
            guardrail_timeout_s=self._config.MA_GUARDRAIL_TIMEOUT_S,
            enable_guardrail=self._config.MA_GUARDRAIL_ENABLED,
            replanner_llm=self._router_llm,
            max_replan=self._config.MA_MAX_REPLAN,
            map_reduce_domain_threshold=self._config.MA_MAP_REDUCE_DOMAIN_THRESHOLD,
            map_concurrency=self._config.MA_MAP_CONCURRENCY,
            map_timeout_s=self._config.MA_MAP_TIMEOUT_S,
            reduce_mode=self._config.MA_REDUCE_MODE,
            writer_llm=self._generator_llm,
            history_max_chars=self._config.MA_HISTORY_MAX_CHARS,
        )
        self._graph_cache[cache_key] = graph
        logger.info(
            "[AgentService] 그래프 빌드·캐시: enabled=%s, tool_map v%d (캐시 %d개)",
            sorted(enabled_mcps),
            self._tool_map_version,
            len(self._graph_cache),
        )
        return graph

    async def _initial_messages(self, email: str, gid: int, question: str) -> list:
        """ai_chat_history (email,gid) 조회 → [Human,AI,...] + 현재 질문. 실패 시 단일턴."""
        history = []
        try:
            rows = await self._chat_history_repo.select_history(email, gid)
        except Exception as e:
            logger.warning("[AgentService] 히스토리 조회 실패 (email=%s gid=%s): %s", email, gid, e)
            rows = []
        for row in rows:
            if row.get("question"):
                history.append(HumanMessage(content=row["question"]))
            if row.get("answer"):
                history.append(AIMessage(content=row["answer"]))
        history.append(HumanMessage(content=question))
        return history

    async def _persist_turn(self, email: str, gid: int, question: str, answer: str) -> None:
        """이번 턴을 ai_chat_history 에 적재 — 실패해도 스트림 응답 자체는 막지 않는다(best-effort).

        ⚠️ 여기서 저장하는 `question` 은 항상 **사용자가 실제로 입력한 원문**이어야 한다.
        `stream_query` 본문은 보충질문(clarify) 분기에서 지역변수 `question` 을 그래프가 만든
        되물음 문장으로 재대입하므로(그 지역 표시 목적), 호출부는 재대입 전에 캡처해 둔 원본을
        넘긴다 — 아니면 히스토리에 사용자 질문 대신 AI 되물음이 실려 다음 턴 컨텍스트가 뒤틀린다.
        """
        try:
            await self._chat_history_repo.insert_turn(email, gid, question, answer)
        except Exception as e:
            logger.warning("[AgentService] 히스토리 적재 실패 (email=%s gid=%s): %s", email, gid, e)

    async def stream_query(
        self, question: str, email: str, gid: int, enabled_mcps: set[str]
    ) -> AsyncGenerator[dict, None]:
        """쿼리를 멀티 에이전트로 처리하고 이벤트 dict 를 yield 한다 (라우터가 SSE 프레이밍).

        이벤트 유형 (utils/agent/events.py):
            step / text / trace / error / clarification
        """
        # 가드레일은 그래프 첫 노드(보안검사)에서 수행 — 차단 시 아래 스트림 루프에서 처리.
        # 히스토리 적재용 원본 보존 — 아래에서 `question` 이 재대입될 수 있다(_persist_turn 참고).
        original_question = question

        # 응답 캐시 hit 시 즉시 반환 — (email,gid,enabled_mcps,question) 조합 키로 교차 유출 차단
        cache_key = make_cache_key(email, gid, enabled_mcps, question)
        cached = self._response_cache.get(cache_key)
        if cached is not None:
            logger.info("[AgentService] 캐시 hit — gid=%s, len=%d", gid, len(cached))
            yield step_event("cache", "hit", message=MSG_CACHE_HIT)
            yield text_event(cached)
            yield trace_event({"reason": "cache_hit", "answer_len": len(cached)})
            await self._persist_turn(email, gid, original_question, cached)
            return

        yield step_event("plan", "started", message=MSG_PLAN_STARTED)

        graph = await self._build_graph(enabled_mcps)
        # 요청 스코프 토큰 사용량 관측 — 스트림 종료 시 [usage] 로그 + trace_event 합류 (#207)
        usage_tracker = UsageTracker()
        config = {
            "recursion_limit": 100,
            "callbacks": [*self._stream_callbacks(), usage_tracker],
            "run_name": "투자 리서치 멀티에이전트",
            # delegate_runtime: 요청 스코프 sub-agent 호출한도 계수 — 캐시 그래프 공유 시 요청 격리 축
            "configurable": {"delegate_runtime": {}},
            # [LangSmith 전용 관측] Threads 그룹핑 — (email, gid) 한 대화의 멀티턴 run 을 한 스레드로 묶음.
            # ⚠️ langfuse 전환 시: session_id metadata 는 LangSmith 컨벤션. langfuse 는 trace metadata 의
            #    session_id 를 자체 Sessions 로 인식하므로 키 유지 가능하나, 관측 백엔드 교체 시 동작 재확인 필요.
            "metadata": {"session_id": f"{email}:{gid}"},
        }

        t_start = time.monotonic()
        agent_calls_total: list[str] = []
        stage_results_total: list[dict] = []
        tool_calls_total: list[dict] = []
        domain_answers_total: dict[str, dict] = {}
        # answer_text_full 은 **최종 답변만** 담는다 — 캐시·근거고지·수치주석·후속질문이 이 변수를 본다.
        # 보충질문·거절은 최종 답변이 아니므로 history_text 로 갈라 담는다 (#364): 히스토리에는
        # 실려야 하지만(#357 리뷰 [E]) 캐시에 앉으면 재질문 시 되물음이 답변으로 돌아온다.
        answer_text_full = ""
        history_text = ""
        guardrail_blocked = False  # #357 리뷰 [F] — 차단된 턴은 finally 에서 적재하지 않는다
        announced_execute_start = False
        announced_answer_start = False
        emitted_stage_count = 0  # 재계획 루프로 도메인실행 노드가 여러 번 fire → domain_completed 중복 방지

        try:
            # custom stream 으로 Map 도메인별·tool 호출 progressive SSE
            async for mode, chunk in graph.astream(
                {"messages": await self._initial_messages(email, gid, question)},
                config=config,
                stream_mode=["updates", "custom"],
            ):
                if mode == "custom":
                    event = (chunk or {}).get("event")
                    if event == "map_started":
                        domains = chunk.get("domains") or []
                        yield step_event(
                            "map_answer",
                            "started",
                            domains=domains,
                            message=f"도메인 답변 생성 시작 ({len(domains)}개)",
                        )
                    elif event == "map_domain_completed":
                        domain = chunk.get("domain", "")
                        domain_label_str = chunk.get("domain_label", domain)
                        domain_status = chunk.get("status", "OK")
                        # sub-answer 본문은 internal state — step 이벤트만 흘려 UI 가 진행 chip 표시.
                        # 최종 통합 답변은 reduce 의 final_answer 1회만 사용자에게 stream 된다.
                        yield step_event(
                            "map_answer",
                            "domain_completed",
                            domain=domain,
                            domain_label=domain_label_str,
                            domain_status=domain_status,
                            message=f"{domain_label_str} 분석 완료",
                        )
                    elif event == "tool_call_started":
                        yield step_event(
                            "tool_call",
                            "started",
                            agent=chunk.get("agent", ""),
                            tool=chunk.get("tool", ""),
                            message=f"{chunk.get('agent', '')}: {chunk.get('tool', '')} 호출",
                        )
                    elif event == "tool_call_completed":
                        latency = chunk.get("latency_s")
                        yield step_event(
                            "tool_call",
                            "completed",
                            agent=chunk.get("agent", ""),
                            tool=chunk.get("tool", ""),
                            elapsed_s=latency,
                            message=f"{chunk.get('agent', '')}: {chunk.get('tool', '')} 완료 ({latency}s)",
                        )
                    elif event == "tool_call_failed":
                        err_type = chunk.get("error_type", "Error")
                        yield step_event(
                            "tool_call",
                            "failed",
                            agent=chunk.get("agent", ""),
                            tool=chunk.get("tool", ""),
                            error_type=err_type,
                            message=f"{chunk.get('agent', '')}: {chunk.get('tool', '')} 실패 ({err_type})",
                        )
                    elif event == "execution_complete":
                        # 재계획 종료(더 이상 stage 없음) — 모든 단계실행이 끝난 뒤 1회만 fire.
                        yield step_event("execute", "completed", message=MSG_EXECUTE_COMPLETED)
                        if not announced_answer_start:
                            yield step_event("answer", "started", message=MSG_ANSWER_STARTED)
                            announced_answer_start = True
                    continue

                for node_name, node_output in chunk.items():
                    if node_name == "보안검사" and node_output.get("guardrail_blocked"):
                        refusal = node_output.get("refusal_message") or MSG_GUARDRAIL_BLOCKED
                        history_text = refusal
                        guardrail_blocked = True
                        # message=refusal(카테고리별 실제 문구) — MSG_GUARDRAIL_BLOCKED 고정값을 쓰면
                        # unavailable(가드레일 응답불가)도 "위험 판정" 문구로 나가 사용자를 오도한다(#338 리뷰).
                        yield step_event("guardrail", "blocked", message=refusal)
                        yield text_event(refusal)

                    if node_name == "보충질문확인":
                        intent = node_output.get("clarify_intent") or "proceed"
                        if intent == "clarify":
                            question = node_output.get("clarification_question") or ""
                            history_text = question
                            yield step_event("clarify", "requested", message=MSG_CLARIFY_REQUESTED)
                            yield clarification_event(question)
                        elif intent == "refuse":
                            refusal = node_output.get("refusal_message") or MSG_REFUSE_OUT_OF_DOMAIN
                            history_text = refusal
                            yield step_event("clarify", "refused", message=MSG_REFUSE_OUT_OF_DOMAIN)
                            yield text_event(refusal)

                    if node_name == "계획수립":
                        plan_obj = node_output.get("plan")
                        stage_count = len(getattr(plan_obj, "stages", []) or [])
                        yield step_event("plan", "completed", stages=stage_count, message=MSG_PLAN_COMPLETED)
                        if not announced_execute_start:
                            yield step_event("execute", "started", message=MSG_EXECUTE_STARTED)
                            announced_execute_start = True

                    if node_name == "도메인실행":
                        # 노드가 stage_results·agent_calls·tool_calls 를 누적해 통째 반환 → 교체 (재계획 루프 중복 합산 방지)
                        agent_calls_total[:] = node_output.get("agent_calls", []) or []
                        new_stage_results = node_output.get("stage_results", []) or []
                        stage_results_total[:] = new_stage_results
                        tc = node_output.get("tool_calls")
                        if tc:
                            tool_calls_total[:] = tc
                        # 이번 fire 에서 새로 추가된 stage 만 domain_completed emit (이전 stage 재emit 방지)
                        for st in new_stage_results[emitted_stage_count:]:
                            for r in st.get("results") or []:
                                if r.get("status") == "ok":
                                    yield step_event(
                                        "execute",
                                        "domain_completed",
                                        domain=r.get("agent"),
                                        elapsed_s=r.get("elapsed_s"),
                                        message=f"{domain_label(r.get('agent', ''))} 도메인 조회 완료",
                                    )
                        emitted_stage_count = len(new_stage_results)

                    if node_name == "도메인별답변":
                        da = node_output.get("domain_answers")
                        if da:
                            domain_answers_total.update(da)

                    if node_name == "답변작성":
                        answer_text = ""
                        msgs = node_output.get("messages", [])
                        if msgs:
                            last = msgs[-1]
                            answer_text = getattr(last, "content", str(last))
                        elif "final_answer" in node_output:
                            answer_text = node_output["final_answer"]
                        if answer_text:
                            answer_text_full += answer_text
                            yield text_event(answer_text)

                    if node_name == "답변통합":
                        final_text = node_output.get("final_answer") or ""
                        if not final_text:
                            msgs = node_output.get("messages", [])
                            if msgs:
                                final_text = getattr(msgs[-1], "content", "")
                        if final_text:
                            answer_text_full += final_text
                            yield text_event(final_text)

            # 근거 없음 caveat — example-ai 경로와 일관되게 native 도 미근거 시 고지
            grounding = compute_grounding(tool_calls_total)
            if answer_text_full and not any_sourced(grounding):
                yield step_event("grounding", "no_evidence", message="검색 근거가 없어 일반 지식으로 답합니다.")

            # 미근거 수치 가드레일 — tool 출력에 없는 금융 수치를 결정론적으로 표기
            if answer_text_full:
                annotation, _ = annotate_ungrounded_numbers(answer_text_full, tool_calls_total)
                if annotation:
                    tail = f"\n\n{annotation}"
                    answer_text_full += tail
                    yield text_event(tail)

            elapsed_s = round(time.monotonic() - t_start, 2)
            metadata = build_trace_metadata(
                agent_calls_total,
                stage_results_total,
                elapsed_s,
                answer_text_full or history_text,  # trace 는 되물음 턴도 관측 대상이다
                trace_enabled=self._config.MA_TRACE_TOKEN_USAGE,
                tool_calls=tool_calls_total,
                domain_answers=domain_answers_total,
            )

            if answer_text_full:
                self._response_cache.set(cache_key, answer_text_full)

            logger.info("[usage] %s", usage_tracker.summary_line())
            trace_payload = metadata or {
                "reason": "metadata_disabled",
                "answer_len": len(answer_text_full or history_text),
            }
            trace_payload["usage"] = usage_tracker.trace_payload()
            yield trace_event(trace_payload)

        except Exception as e:
            logger.error("[AgentService] 스트리밍 오류: %s", e)
            yield error_event("멀티 에이전트 처리 중 오류가 발생했습니다.")
            yield trace_event({"reason": "exception", "error_type": type(e).__name__})
        finally:
            # 예외·정상 종료 모두 적재 — answer_text_full 은 중단 시 빈 문자열일 수 있다(테이블 설계 그대로).
            # 단, 가드레일이 차단한 턴은 적재하지 않는다(#357 리뷰 [F]) — 거부된 질문은 멀티턴
            # 컨텍스트로서 가치가 없고, 저장하면 다음 턴부터 `_build_history_ctx`(clarify/plan/
            # answer/map_reduce 4개 노드 프롬프트)에 원문이 재주입된다. #85 의 무력화 방어가 그
            # 자리에서 받아내긴 하지만, 애초에 안 적재하는 편이 더 싸고 근본적이다.
            if not guardrail_blocked:
                await self._persist_turn(email, gid, original_question, answer_text_full or history_text)

    async def stream_query_example_ai(
        self, question: str, email: str, gid: int, enabled_mcps: set[str]
    ) -> AsyncGenerator[dict, None]:
        """ai-chatbot 프론트 호환 SSE 이벤트 dict 를 yield (라우터가 newline-delimited JSON 프레이밍).

        기존 stream_query 와 별개 어댑터 — graph.astream 의 "messages" 모드 토큰을
        answer/reduce 노드에 한해 response_chunk 로 흘린다(타 노드 토큰은 답변 오염 차단).
        switch1-4(요청 body)는 planner 자동 선택이라 무시(호환용).
        이벤트 순서: start → step(routing) → routing → (tool_parameters) → step(tools)
                    → media → step(response) → response_chunk×N → title → follow_up → workflow_complete
        """
        yield tex.start_event(query=question)

        # 응답 캐시 — native 경로와 동일한 (email,gid,enabled_mcps,question) 키로 격리(교차 유출 차단).
        cache_key = make_cache_key(email, gid, enabled_mcps, question)
        cached = self._response_cache.get(cache_key)
        if cached is not None:
            logger.info("[AgentService] example-ai 캐시 hit — gid=%s, len=%d", gid, len(cached))
            yield tex.step_event("response", MSG_CACHE_HIT)
            yield tex.response_chunk_event(cached, 1, len(cached))
            yield tex.workflow_complete_event()
            await self._persist_turn(email, gid, question, cached)
            return

        # 가드레일은 그래프 첫 노드(보안검사)에서 수행 — 차단 시 아래 스트림 루프에서 처리.
        graph = await self._build_graph(enabled_mcps)
        # 요청 스코프 토큰 사용량 관측 — native stream_query 와 동일 부착 (#283, #207 관측 축).
        # 이 경로가 그동안 미부착이라 example-ai 트래픽의 토큰 소모가 [usage] 로그에 잡히지 않았다.
        usage_tracker = UsageTracker()
        config = {
            "recursion_limit": 100,
            "callbacks": [*self._stream_callbacks(), usage_tracker],
            "run_name": "투자 리서치 멀티에이전트",
            # delegate_runtime: 요청 스코프 sub-agent 호출한도 계수 — 캐시 그래프 공유 시 요청 격리 축
            "configurable": {"delegate_runtime": {}},
            # [LangSmith 전용 관측] Threads 그룹핑 — (email, gid) 한 대화의 멀티턴 run 을 한 스레드로 묶음.
            # ⚠️ langfuse 전환 시: session_id metadata 는 LangSmith 컨벤션. langfuse 는 trace metadata 의
            #    session_id 를 자체 Sessions 로 인식하므로 키 유지 가능하나, 관측 백엔드 교체 시 동작 재확인 필요.
            "metadata": {"session_id": f"{email}:{gid}"},
        }

        tool_calls_total: list[dict] = []
        # native 와 같은 분리 — answer_text_full 은 최종 답변만, 보충질문·거절은 history_text (#364)
        answer_text_full = ""
        history_text = ""
        guardrail_blocked = False  # #357 리뷰 [F] — 차단된 턴은 finally 에서 적재하지 않는다
        chunk_id = 0
        announced_tools_step = False
        announced_response_step = False
        media_sent = False

        yield tex.step_event("routing", MSG_PLAN_STARTED)

        try:
            async for mode, chunk in graph.astream(
                {"messages": await self._initial_messages(email, gid, question)},
                config=config,
                stream_mode=["updates", "custom", "messages"],
            ):
                if mode == "messages":
                    # (message_chunk, metadata) — 답변작성/답변통합 노드 토큰만 답변으로 흘린다.
                    message_chunk, metadata = chunk
                    if (metadata or {}).get("langgraph_node") not in ("답변작성", "답변통합"):
                        continue
                    # #72 최종답변 이중 전송 차단. messages 모드는 (a) LLM 토큰(AIMessageChunk)과
                    # (b) 노드가 state 에 쓴 완성 AIMessage 를 둘 다 emit 한다. 답변 노드가 disclaimer 를
                    # 붙여 새 id 의 AIMessage 를 반환 → LangGraph 의 id 기반 dedupe 실패 → 토큰 스트림에
                    # 뒤이어 완성본이 통째로 한 번 더 나간다. 정본은 토큰 스트림이므로, 이미 토큰을 흘린
                    # (answer_text_full 채워진) 뒤 도착하는 완성 AIMessage 는 버린다(누락된 disclaimer 는
                    # 아래 결정론적 백스톱이 보강). 단 토큰이 전혀 없던 경로(reduce disabled 등 LLM 미호출)는
                    # 이 완성본이 유일 전달이므로 통과시킨다.
                    if not isinstance(message_chunk, AIMessageChunk) and answer_text_full:
                        continue
                    delta = getattr(message_chunk, "content", "") or ""
                    if not isinstance(delta, str) or not delta:
                        continue
                    if not announced_response_step:
                        yield tex.step_event("response", MSG_ANSWER_STARTED)
                        announced_response_step = True
                    chunk_id += 1
                    answer_text_full += delta
                    yield tex.response_chunk_event(delta, chunk_id, len(answer_text_full))
                    continue

                if mode == "custom":
                    # 도구 호출 진행 — tool_parameters(키워드 있을 때) 또는 step.
                    event = (chunk or {}).get("event")
                    if event == "tool_call_started":
                        agent = chunk.get("agent", "")
                        tool = chunk.get("tool", "")
                        yield tex.step_event("tools", f"{domain_label(agent)}: {tool} 도구 호출 중")
                    elif event == "execution_complete" and not media_sent:
                        # 재계획 종료 — 모든 단계실행이 끝난 시점에 누적 tool_calls 로 media·grounding 산출(답변 전).
                        grounding = compute_grounding(tool_calls_total)
                        images, sources, summary = tex.extract_media(tool_calls_total)
                        summary["has_results"] = any_sourced(grounding)
                        if images or sources:
                            yield tex.media_event(images, sources, summary)
                        if not any_sourced(grounding):
                            yield tex.step_event("response", "검색 근거가 없어 일반 지식으로 답합니다.")
                        media_sent = True
                    continue

                # mode == "updates"
                for node_name, node_output in chunk.items():
                    # 게이트 차단/거절: response_chunk 로 전체 1회 emit. return 하지 않는다 —
                    # 차단 시 그래프는 END 로 가 astream 이 자연 종료되므로, early-return 으로 제너레이터를
                    # 버리면 LangSmith 가 루트 run 을 GeneratorExit 에러로 기록한다(trace 깨짐). post-loop 가
                    # workflow_complete 를 1회 emit (answer_text_full 비어 title/follow_up 자동 스킵).
                    if node_name == "보안검사" and node_output.get("guardrail_blocked"):
                        refusal = node_output.get("refusal_message") or MSG_GUARDRAIL_BLOCKED
                        guardrail_blocked = True  # #357 리뷰 [F] — finally 에서 적재하지 않는다
                        # answer_text_full 은 일부러 안 채운다 — post-loop 가 이 변수의 공백을 보고
                        # title/follow_up 생성을 건너뛴다(거부 문구로 제목·후속질문을 만들지 않기 위함).
                        # message=refusal — 위 astream(mode="messages") 경로와 동일 이유(#338 리뷰).
                        yield tex.step_event("routing", refusal)
                        yield tex.step_event("response", MSG_ANSWER_STARTED)
                        yield tex.response_chunk_event(refusal, 1, len(refusal))

                    if node_name == "보충질문확인":
                        intent = node_output.get("clarify_intent") or "proceed"
                        text = ""
                        if intent == "clarify":
                            text = node_output.get("clarification_question") or ""
                        elif intent == "refuse":
                            text = node_output.get("refusal_message") or MSG_REFUSE_OUT_OF_DOMAIN
                        if text:
                            # native(stream_query) 와 동일하게 히스토리에는 싣는다(#357 리뷰 [E])
                            # — 안 실으면 이 턴이 answer="" 로 적재돼 "보충질문 → 사용자 답변"
                            # 처럼 되물음이 꼭 필요한 멀티턴 시나리오에서 AI 되물음이 다음 턴
                            # 컨텍스트(`_initial_messages`)에서 사라진다. 다만 최종 답변은 아니므로
                            # answer_text_full 이 아니라 history_text 다 (#364).
                            history_text = text
                            yield tex.step_event("response", MSG_ANSWER_STARTED)
                            yield tex.response_chunk_event(text, 1, len(text))

                    if node_name == "계획수립":
                        plan_obj = node_output.get("plan")
                        selected_domains = plan_domains(plan_obj)
                        if selected_domains:
                            tool_info = [
                                {
                                    "name": DOMAIN_KO_LABEL.get(d, d),
                                    "description": f"{DOMAIN_KO_LABEL.get(d, d)} 조회 중",
                                }
                                for d in selected_domains
                            ]
                            yield tex.routing_event(selected_tools=selected_domains, tool_info=tool_info)
                        if not announced_tools_step:
                            yield tex.step_event("tools", MSG_EXECUTE_STARTED)
                            announced_tools_step = True

                    if node_name == "도메인실행":
                        # 노드가 tool_calls 를 누적 반환 → 통째 교체. media·grounding 은 execution_complete 시점에 산출.
                        tc = node_output.get("tool_calls")
                        if tc:
                            tool_calls_total[:] = tc

            # 컴플라이언스 고지 — 토큰 스트림이 결정론적 disclaimer 를 누락했으면 마지막 청크로 1회 보강.
            if answer_text_full.strip() and "투자 조언이 아닙니다" not in answer_text_full:
                tail = f"\n\n{COMPLIANCE_DISCLAIMER}"
                chunk_id += 1
                answer_text_full += tail
                yield tex.response_chunk_event(tail, chunk_id, len(answer_text_full))

            # 미근거 수치 가드레일 — tool 출력에 없는 금융 수치를 결정론적으로 표기 (native 경로와 동일).
            if answer_text_full.strip():
                annotation, _ = annotate_ungrounded_numbers(answer_text_full, tool_calls_total)
                if annotation:
                    tail = f"\n\n{annotation}"
                    chunk_id += 1
                    answer_text_full += tail
                    yield tex.response_chunk_event(tail, chunk_id, len(answer_text_full))

            # 답변 토큰 스트림 종료 후 title / follow_up (실패 시 생략 — 예외 전파 금지)
            # 그래프 trace 밖(post-loop)이라 run_name + session 부여해 generic 루트 대신 thread 에 귀속.
            # callbacks 에도 같은 tracker 를 물려 title/follow_up 토큰까지 [usage] 에 합류시킨다.
            post_cfg = {"metadata": {"session_id": f"{email}:{gid}"}, "callbacks": [usage_tracker]}
            if answer_text_full.strip():
                self._response_cache.set(cache_key, answer_text_full)
                title = await self._gen_title(question, answer_text_full, config=post_cfg)
                if title:
                    yield tex.title_event(title)
                follow_up = await self._gen_follow_up(question, answer_text_full, config=post_cfg)
                if follow_up:
                    yield tex.follow_up_question_event(follow_up)

            logger.info("[usage] example-ai %s", usage_tracker.summary_line())
            yield tex.workflow_complete_event()

        except Exception as e:
            logger.error("[AgentService] example-ai 스트리밍 오류: %s", e)
            yield tex.error_event("멀티 에이전트 처리 중 오류가 발생했습니다.")
            yield tex.workflow_complete_event()
        finally:
            # 예외·정상 종료 모두 적재 — answer_text_full 은 중단 시 빈 문자열일 수 있다(테이블 설계 그대로).
            # 단, 가드레일이 차단한 턴은 적재하지 않는다 — native(stream_query) 와 동일 이유(#357 리뷰 [F]).
            if not guardrail_blocked:
                await self._persist_turn(email, gid, question, answer_text_full or history_text)

    async def _gen_title(self, question: str, answer: str, config: dict | None = None) -> str:
        """답변에 어울리는 8자 이내 한국어 제목 1개. 실패 시 빈 문자열 (예외 전파 금지)."""
        prompt = (
            "다음 질문과 답변에 어울리는 한국어 제목을 8자 이내로 1개만 만들어라. "
            "따옴표·접두어·설명 없이 제목 텍스트만 출력.\n\n"
            f"[질문]\n{question}\n\n[답변]\n{answer[:1500]}"
        )
        try:
            ans = await self._generator_llm.ainvoke(prompt, config={**(config or {}), "run_name": "제목 생성"})
            title = (ans.content if hasattr(ans, "content") else str(ans)).strip()
            return title.strip("\"'“”「」 ")[:30]
        except Exception as e:
            logger.debug("[AgentService] title 생성 실패 (생략): %s", e)
            return ""

    async def _gen_follow_up(self, question: str, answer: str, config: dict | None = None) -> str:
        """후속 질문 3개를 JSON 배열 문자열로 반환. 실패 시 빈 문자열 (예외 전파 금지)."""
        prompt = (
            "다음 답변에 이어질 후속 질문 3개를 한국어로 만들어 JSON 배열로만 출력하라. "
            '예: ["질문1","질문2","질문3"]. 다른 텍스트·코드펜스 금지.\n\n'
            f"[질문]\n{question}\n\n[답변]\n{answer[:1500]}"
        )
        try:
            ans = await self._generator_llm.ainvoke(prompt, config={**(config or {}), "run_name": "후속질문 생성"})
            raw = (ans.content if hasattr(ans, "content") else str(ans)).strip()
            start, end = raw.find("["), raw.rfind("]")
            if start == -1 or end == -1 or end <= start:
                return ""
            items = json.loads(raw[start : end + 1])
            questions = [str(q) for q in items if isinstance(q, str | int | float)][:3]
            return json.dumps(questions, ensure_ascii=False) if questions else ""
        except Exception as e:
            logger.debug("[AgentService] follow_up 생성 실패 (생략): %s", e)
            return ""
