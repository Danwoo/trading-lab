"""요청 스코프 LLM 토큰 사용량 관측 콜백 — run_name(노드)별 합산 (#207 관측 축).

usage 필드가 응답에 없으면 문자수/4 근사로 폴백하되 estimated 로 구분 표기한다 —
근사값을 실측처럼 쓰지 않기 위한 구분자다 (절감 주장은 실측 usage 로만 성립).
관측 콜백이 요청 스트림을 죽이면 안 되므로 내부 오류는 삼키고 debug 로그만 남긴다 (fail-open 관측).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core.logger import logger
from langchain_core.callbacks import AsyncCallbackHandler

# 프레임워크가 부여하는 기본 run 이름 — 노드 귀속 라벨로 쓰지 않는다.
# 이 앱의 유효 라벨은 노드 run_name(한글)·sub-agent 명(snake_case)뿐이다.
_GENERIC_NAME_PREFIXES = ("Runnable", "ChannelWrite", "ChannelRead", "ChatPromptTemplate", "Chat", "LangGraph")
_UNRESOLVED_LABEL = "(미분류)"
_ESTIMATE_CHARS_PER_TOKEN = 4
_MAX_PARENT_HOPS = 20


def _is_generic_name(name: str | None) -> bool:
    if not name:
        return True
    return name.startswith(_GENERIC_NAME_PREFIXES) or name.startswith("_")


class UsageTracker(AsyncCallbackHandler):
    """요청별 1개 인스턴스를 config callbacks 에 부착 — on_llm_end 의 usage 를 run_name 별 합산.

    라벨 해석: LLM run 자신 또는 가장 가까운 이름 있는 조상 run 의 run_name → 없으면
    langgraph 노드 metadata(langgraph_node) → 그래도 없으면 "(미분류)".
    """

    def __init__(self) -> None:
        super().__init__()
        self._parents: dict[UUID, UUID | None] = {}
        self._labels: dict[UUID, str] = {}
        self._graph_node: dict[UUID, str] = {}
        self._prompt_chars: dict[UUID, int] = {}
        self._by_node: dict[str, dict[str, int]] = {}
        self.estimated = False

    # ── 수집 훅 ──────────────────────────────────────────────────────────

    async def on_chain_start(
        self, serialized: Any, inputs: Any, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        try:
            self._parents[run_id] = parent_run_id
            name = kwargs.get("name")
            if not _is_generic_name(name):
                self._labels[run_id] = str(name)
        except Exception as e:  # 관측 실패가 요청을 죽이지 않게
            logger.debug("[usage] on_chain_start 무시: %s", e)

    async def on_chat_model_start(
        self,
        serialized: Any,
        messages: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            self._parents[run_id] = parent_run_id
            name = kwargs.get("name")
            if not _is_generic_name(name):
                self._labels[run_id] = str(name)
            node = (metadata or {}).get("langgraph_node")
            if node:
                self._graph_node[run_id] = str(node)
            chars = 0
            for batch in messages or []:
                for m in batch:
                    content = getattr(m, "content", m)
                    chars += len(content) if isinstance(content, str) else len(str(content))
            self._prompt_chars[run_id] = chars
        except Exception as e:
            logger.debug("[usage] on_chat_model_start 무시: %s", e)

    async def on_llm_start(
        self,
        serialized: Any,
        prompts: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            self._parents[run_id] = parent_run_id
            name = kwargs.get("name")
            if not _is_generic_name(name):
                self._labels[run_id] = str(name)
            node = (metadata or {}).get("langgraph_node")
            if node:
                self._graph_node[run_id] = str(node)
            self._prompt_chars[run_id] = sum(len(str(p)) for p in (prompts or []))
        except Exception as e:
            logger.debug("[usage] on_llm_start 무시: %s", e)

    async def on_llm_end(
        self, response: Any, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any
    ) -> None:
        try:
            usage = self._extract_usage(response)
            if usage is None:
                usage = self._estimate_usage(response, run_id)
                self.estimated = True
            input_tokens, output_tokens = usage
            label = self._resolve_label(run_id)
            slot = self._by_node.setdefault(label, {"input_tokens": 0, "output_tokens": 0, "calls": 0})
            slot["input_tokens"] += input_tokens
            slot["output_tokens"] += output_tokens
            slot["calls"] += 1
        except Exception as e:
            logger.debug("[usage] on_llm_end 무시: %s", e)

    # ── 내부 ────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_usage(response: Any) -> tuple[int, int] | None:
        """LLMResult 에서 (input_tokens, output_tokens) — 표준 usage_metadata 우선, OpenAI 호환 llm_output 폴백."""
        for gens in getattr(response, "generations", None) or []:
            for gen in gens:
                um = getattr(getattr(gen, "message", None), "usage_metadata", None)
                if um:
                    return int(um.get("input_tokens", 0)), int(um.get("output_tokens", 0))
        llm_output = getattr(response, "llm_output", None) or {}
        token_usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
        if token_usage:
            input_tokens = token_usage.get("prompt_tokens", token_usage.get("input_tokens", 0)) or 0
            output_tokens = token_usage.get("completion_tokens", token_usage.get("output_tokens", 0)) or 0
            if input_tokens or output_tokens:
                return int(input_tokens), int(output_tokens)
        return None

    def _estimate_usage(self, response: Any, run_id: UUID) -> tuple[int, int]:
        output_chars = 0
        for gens in getattr(response, "generations", None) or []:
            for gen in gens:
                output_chars += len(getattr(gen, "text", "") or "")
        input_chars = self._prompt_chars.get(run_id, 0)
        return input_chars // _ESTIMATE_CHARS_PER_TOKEN, output_chars // _ESTIMATE_CHARS_PER_TOKEN

    def _resolve_label(self, run_id: UUID) -> str:
        cursor: UUID | None = run_id
        for _ in range(_MAX_PARENT_HOPS):
            if cursor is None:
                break
            label = self._labels.get(cursor)
            if label:
                return label
            cursor = self._parents.get(cursor)
        return self._graph_node.get(run_id, _UNRESOLVED_LABEL)

    # ── 산출 ────────────────────────────────────────────────────────────

    @property
    def by_node(self) -> dict[str, dict[str, int]]:
        """{run_name: {"input_tokens": int, "output_tokens": int, "calls": int}} (복사본)."""
        return {k: dict(v) for k, v in self._by_node.items()}

    def totals(self) -> dict[str, int]:
        return {
            "input_tokens": sum(v["input_tokens"] for v in self._by_node.values()),
            "output_tokens": sum(v["output_tokens"] for v in self._by_node.values()),
            "calls": sum(v["calls"] for v in self._by_node.values()),
        }

    def trace_payload(self) -> dict[str, Any]:
        """trace_event metadata 합류용 — 총계 + 노드별 + estimated 구분자."""
        return {"total": self.totals(), "by_node": self.by_node, "estimated": self.estimated}

    def summary_line(self) -> str:
        total = self.totals()
        node_parts = ", ".join(
            f"{name}: in={v['input_tokens']} out={v['output_tokens']} calls={v['calls']}"
            for name, v in sorted(self._by_node.items())
        )
        return (
            f"total_in={total['input_tokens']} total_out={total['output_tokens']} "
            f"calls={total['calls']} estimated={str(self.estimated).lower()} by_node={{{node_parts}}}"
        )
