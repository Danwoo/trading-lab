"""에이전트 호출 결과 구조화 타입.

오류 문자열("(타임아웃 300s)" 등)이 dict 평탄화로 다음 stage 의 prior_ctx 에 그대로 주입되어
LLM 이 "오류 메시지를 이전 결과로 해석"하는 silent corruption 을 막기 위해
status / payload / error 정보 / 지연을 분리 보관한다.

계약:
    - payload 는 성공 시에만 str 로 비어 있지 않음. 그 외 None.
    - error_message 는 실패 시에만 비어 있지 않음. 사용자 노출용 짧은 한국어.
    - status 로 성공/실패 분기 — 문자열 prefix 매칭 절대 금지.
    - status != OK 결과는 LLM 프롬프트 context 에서 제외 (Fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AgentStatus(StrEnum):
    """에이전트 호출 결과 상태. OK 만 downstream context 로 흘려보낸다."""

    OK = "ok"
    TIMEOUT = "timeout"
    RECURSION = "recursion"
    LIMIT_SOFT = "limit_soft"  # max_calls 초과이나 과거 성공 데이터 있음
    LIMIT_HARD = "limit_hard"  # max_calls 초과이고 과거 성공 없음
    EXCEPTION = "exception"
    MISSING_TOOL = "missing_tool"
    EMPTY = "empty"  # 응답 구조 정상이나 content 비어있음


SUCCESS_STATUSES: frozenset[AgentStatus] = frozenset({AgentStatus.OK})


@dataclass(slots=True)
class AgentResult:
    """에이전트 호출 결과."""

    agent: str
    task: str
    status: AgentStatus
    payload: str | None = None
    error_message: str = ""
    error_type: str = ""
    elapsed_s: float = 0.0
    group: int = -1
    call_idx: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status in SUCCESS_STATUSES

    def to_legacy_dict(self) -> dict:
        """stage_results 등 dict 기반 소비 코드와의 호환 평탄화."""
        if self.is_success:
            output = self.payload or ""
        else:
            output = self.error_message or f"({self.status.value})"
        return {
            "agent": self.agent,
            "task": self.task,
            "group": self.group,
            "output": output,
            "status": self.status.value,
            "error_type": self.error_type,
            "elapsed_s": self.elapsed_s,
        }

    @classmethod
    def ok(cls, *, agent: str, task: str, payload: str, elapsed_s: float = 0.0, group: int = -1) -> AgentResult:
        return cls(agent=agent, task=task, status=AgentStatus.OK, payload=payload, elapsed_s=elapsed_s, group=group)

    @classmethod
    def timeout(
        cls, *, agent: str, task: str, timeout_s: float, elapsed_s: float = 0.0, group: int = -1
    ) -> AgentResult:
        return cls(
            agent=agent,
            task=task,
            status=AgentStatus.TIMEOUT,
            error_message=f"(타임아웃 {timeout_s:.0f}s)",
            elapsed_s=elapsed_s,
            group=group,
        )

    @classmethod
    def exception(
        cls, *, agent: str, task: str, exc: BaseException, elapsed_s: float = 0.0, group: int = -1
    ) -> AgentResult:
        return cls(
            agent=agent,
            task=task,
            status=AgentStatus.EXCEPTION,
            error_message=f"(오류: {type(exc).__name__}: {str(exc)[:200]})",
            error_type=type(exc).__name__,
            elapsed_s=elapsed_s,
            group=group,
        )

    @classmethod
    def missing_tool(cls, *, agent: str, task: str, group: int = -1) -> AgentResult:
        return cls(
            agent=agent,
            task=task,
            status=AgentStatus.MISSING_TOOL,
            error_message=f"({agent} 도구 없음)",
            group=group,
        )

    @classmethod
    def empty(cls, *, agent: str, task: str, elapsed_s: float = 0.0, group: int = -1) -> AgentResult:
        return cls(
            agent=agent,
            task=task,
            status=AgentStatus.EMPTY,
            error_message="(응답 없음)",
            elapsed_s=elapsed_s,
            group=group,
        )
