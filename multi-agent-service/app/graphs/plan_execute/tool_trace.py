"""sub-agent 내부 ReAct 의 tool 호출 input/output 캡처 콜백 + 출력 텍스트 추출."""

from __future__ import annotations

import json
import time
from typing import Any

from core.logger import logger
from langchain_core.callbacks.base import AsyncCallbackHandler


def _tool_output_text(output: Any) -> str:
    """MCP content-block / ToolMessage 출력에서 실제 텍스트(JSON)를 추출 — repr 저장 시 묻히는 내부 JSON 복원.

    grounding·extract_media·trace 가 파싱 가능한 raw 를 받도록, 콜백이 str(output)(repr) 대신 이걸 쓴다.
    """
    if isinstance(output, str):
        return output
    content = getattr(output, "content", output)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif block.get("type") == "json" and block.get("json") is not None:
                    parts.append(json.dumps(block["json"], ensure_ascii=False))
            elif isinstance(block, str):
                parts.append(block)
        if parts:
            return "\n".join(parts)
    if isinstance(content, str):
        return content
    return str(output)


class _ToolTraceCallback(AsyncCallbackHandler):
    """sub-agent 내부 ReAct 의 tool 호출 input/output 캡처.

    on_tool_start/on_tool_end 페어로 호출당 1개 dict 를 sink 에 누적.
    stream_writer 가 주어지면 tool 호출 시작/끝/실패 시 즉시 custom stream 에 push —
    서비스가 이를 SSE step event 로 변환해 사용자가 실시간 진행을 본다.
    """

    def __init__(self, agent_name: str, sink: list[dict[str, Any]], stream_writer: Any = None) -> None:
        self.agent_name = agent_name
        self.sink = sink
        self.stream_writer = stream_writer
        self._pending: dict[str, dict[str, Any]] = {}  # run_id → start info

    def _push(self, payload: dict[str, Any]) -> None:
        if self.stream_writer is None:
            return
        try:
            self.stream_writer(payload)
        except Exception as e:
            logger.debug("[_ToolTraceCallback] stream_writer push 실패: %s", e)

    async def on_tool_start(  # type: ignore[override]
        self, serialized: dict[str, Any], input_str: str, *, run_id: Any, **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name") if isinstance(serialized, dict) else str(serialized)
        self._pending[str(run_id)] = {
            "agent": self.agent_name,
            "tool": tool_name,
            "input": input_str[:2000] if isinstance(input_str, str) else str(input_str)[:2000],
            "started_at": time.monotonic(),
        }
        self._push({"event": "tool_call_started", "agent": self.agent_name, "tool": tool_name})

    async def on_tool_end(self, output: Any, *, run_id: Any, **kwargs: Any) -> None:  # type: ignore[override]
        rec = self._pending.pop(str(run_id), None)
        if rec is None:
            return
        rec["output"] = _tool_output_text(output)[:8000]  # media(sources/images) JSON 파싱 위해 충분히
        rec["latency_s"] = round(time.monotonic() - rec.pop("started_at", time.monotonic()), 2)
        rec["status"] = "ok"
        self.sink.append(rec)
        self._push(
            {
                "event": "tool_call_completed",
                "agent": self.agent_name,
                "tool": rec["tool"],
                "latency_s": rec["latency_s"],
                "status": "ok",
            }
        )

    async def on_tool_error(self, error: BaseException, *, run_id: Any, **kwargs: Any) -> None:  # type: ignore[override]
        rec = self._pending.pop(str(run_id), None)
        if rec is None:
            return
        rec["output"] = f"{type(error).__name__}: {error}"[:3000]
        rec["latency_s"] = round(time.monotonic() - rec.pop("started_at", time.monotonic()), 2)
        rec["status"] = "error"
        self.sink.append(rec)
        self._push(
            {
                "event": "tool_call_failed",
                "agent": self.agent_name,
                "tool": rec["tool"],
                "latency_s": rec["latency_s"],
                "error_type": type(error).__name__,
            }
        )
