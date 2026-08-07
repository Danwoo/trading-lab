"""에이전트 안전 호출 — 타임아웃/예외 처리 + 지수 백오프 재시도."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from core.logger import logger
from graphs.results import AgentResult
from langchain_core.messages import HumanMessage

from .context import _message_text
from .tool_trace import _ToolTraceCallback


async def _invoke_agent_safe(
    agent,
    task: str,
    agent_name: str,
    timeout: float = 90.0,
    max_retries: int = 0,
    retry_delay: float = 1.0,
    group: int = -1,
    react_recursion_limit: int = 20,
    tool_trace_sink: list[dict[str, Any]] | None = None,
    stream_writer: Any = None,
    parent_config: dict[str, Any] | None = None,
) -> AgentResult:
    """에이전트 안전 호출 — 타임아웃/예외 처리 + 지수 백오프 재시도."""
    from langchain_core.messages import AIMessage

    last_result: AgentResult = AgentResult.exception(
        agent=agent_name, task=task, exc=RuntimeError("no attempt made"), group=group
    )

    for attempt in range(1 + max_retries):
        t0 = time.monotonic()
        # 시도별 임시 trace 버퍼 — 성공한 시도의 도구 기록만 공유 sink 로 승격한다(#121).
        # 실패(타임아웃/예외/빈응답) 시 이 버퍼를 그대로 버려, 부분성공 후 실패한 시도가 남긴 도구
        # 기록이 공유 sink 에 누적되지 않게 한다. 공유 sink 를 "길이 스냅샷 후 절단"하지 않는 이유:
        # 같은 sink 를 병렬 sub-agent 들이 공유(nodes.py `_run_stage_node`)하므로, 절단은 그 사이
        # 다른 형제 agent 가 append 한 기록까지 지운다. 버퍼→성공 시 extend 는 append-only 라 안전하다.
        attempt_trace: list[dict[str, Any]] = []
        try:
            # run_name=도메인명 — LangSmith/langfuse trace 트리에서 generic "LangGraph" 대신 도메인 식별
            invoke_config: dict[str, Any] = {"recursion_limit": react_recursion_limit, "run_name": agent_name}
            # 요청 스코프 configurable(delegate_runtime)을 도메인 그래프까지 명시 전달 — ambient 전파 비의존
            if parent_config and parent_config.get("configurable"):
                invoke_config["configurable"] = parent_config["configurable"]
            if tool_trace_sink is not None or stream_writer is not None:
                invoke_config["callbacks"] = [
                    _ToolTraceCallback(
                        agent_name=agent_name,
                        sink=attempt_trace,
                        stream_writer=stream_writer,
                    ),
                ]
            output = await asyncio.wait_for(
                agent.ainvoke({"messages": [HumanMessage(content=task)]}, config=invoke_config),
                timeout=timeout,
            )
            msgs = output.get("messages", [])
            ai_msgs = [m for m in reversed(msgs) if isinstance(m, AIMessage)]
            elapsed = round(time.monotonic() - t0, 2)
            payload = _message_text(ai_msgs[0]) if ai_msgs else ""
            if not payload:
                last_result = AgentResult.empty(agent=agent_name, task=task, elapsed_s=elapsed, group=group)
            else:
                if attempt > 0:
                    logger.info("[%s] 재시도 성공 (attempt %d)", agent_name, attempt + 1)
                # 성공한 시도의 도구 기록만 공유 sink 로 승격 — append-only 라 병렬 형제 sink 를 깨지 않음.
                if tool_trace_sink is not None:
                    tool_trace_sink.extend(attempt_trace)
                return AgentResult.ok(agent=agent_name, task=task, payload=payload, elapsed_s=elapsed, group=group)
        except TimeoutError:
            elapsed = round(time.monotonic() - t0, 2)
            last_result = AgentResult.timeout(
                agent=agent_name, task=task, timeout_s=timeout, elapsed_s=elapsed, group=group
            )
            logger.warning("[%s] 타임아웃 (attempt %d/%d)", agent_name, attempt + 1, 1 + max_retries)
        except Exception as e:
            elapsed = round(time.monotonic() - t0, 2)
            last_result = AgentResult.exception(agent=agent_name, task=task, exc=e, elapsed_s=elapsed, group=group)
            logger.warning("[%s] 오류 (attempt %d/%d): %s", agent_name, attempt + 1, 1 + max_retries, e)
        if attempt < max_retries:
            await asyncio.sleep(retry_delay * (2**attempt))

    return last_result
