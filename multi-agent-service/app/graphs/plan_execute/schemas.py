"""Plan-Execute Pydantic 스키마 + State — 단일 SoT.

LLM 라우팅용 동적 스키마(deps._build_dynamic_schemas)는 여기 모델을 **상속**해
agent_name 필드만 agents.keys() 로 재정의한다. 필드 문안은 이 파일이 SoT.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

# 정적 에이전트 목록 — 타입 힌트용. LLM 스키마는 _build_dynamic_schemas 가
# agent_name 을 str + agents.keys() description 으로 재정의한다.
VALID_AGENTS = Literal[
    "instrument_domain",
    "financials_domain",
    "risk_domain",
    "market_domain",
]


class StageTask(BaseModel):
    """단일 에이전트 작업."""

    agent_name: VALID_AGENTS = Field(description="호출할 에이전트 이름")
    task: str = Field(
        description=(
            "에이전트에게 전달할 완전한 작업 지시문 (원래 질문의 구체적 맥락 포함, 30자 이상). "
            "financials_domain: 첫 단어에 조사 유형 표시 후 구체적 주제 서술. "
            "예) '재무 분석: 삼성전자 최근 분기 매출·영업이익 및 영업이익률 추이'. "
            "risk_domain: 첫 단어에 분석 유형 표시 후 종목·지표 서술. "
            "이전 stage 결과 활용 시 '이전 [에이전트명] 결과 기반으로' 형태로 연결."
        )
    )
    # 의미 기반 의존성 — execute_node 가 이 필드로 위상 정렬해 독립 tasks 를 같은 stage 로 병합
    depends_on_agents: list[str] = Field(
        default_factory=list,
        description="선행 에이전트 이름 리스트. 다른 에이전트 결과가 본 task 입력에 필요하면 명시. 독립 task는 [].",
    )


class ExecutionPlan(BaseModel):
    """LLM이 생성하는 실행 계획."""

    # optional 은 plan 실패 폴백 ExecutionPlan(stages=[]) 용 — LLM 스키마(_ExecutionPlan)는 필수로 재정의
    reasoning: str | None = Field(
        default=None,
        exclude=True,
        description="계획 수립 근거 (어떤 에이전트를 왜, 어떤 순서로 호출하는지)",
    )
    stages: list[list[StageTask]] = Field(
        description="실행 단계 목록. 각 stage 내 tasks는 병렬 실행, stages 간은 순차 실행. 도메인 외 질문이면 빈 리스트 []."
    )


class ReplanDecision(BaseModel):
    """재계획 노드 출력 — 직전 stage 결과를 보고 추가 조사 여부·내용을 결정."""

    done: bool = Field(description="지금까지 결과로 사용자 질문에 충분히 답할 수 있으면 True (종료)")
    reason: str = Field(description="판단 근거 한 문장 (trace 가독용)")
    next_stage: list[StageTask] = Field(
        default_factory=list,
        description=(
            "done=False 일 때만: 다음에 실행할 stage. 직전 결과에 담긴 식별자(공시 접수번호·종목코드·기관명 등)를 "
            "그 식별자에 맞는 도구를 가진 에이전트가 이어받아 조사하도록 task 를 작성. 보통 1개."
        ),
    )


class ClarifyDecision(BaseModel):
    """Clarification 노드의 LLM 출력 스키마."""

    intent: str = Field(
        description=(
            "판단 결과. "
            "'proceed'=충분히 명확한 금융·투자 질문, "
            "'clarify'=금융·투자 도메인이지만 너무 모호해 추가 정보 필요, "
            "'refuse'=도메인 외 질문이거나 논리적으로 불가능한 요구."
        )
    )
    question: str = Field(
        default="",
        description="intent='clarify'일 때만 사용. 사용자에게 정중하게 물을 한국어 질문 1~2문장.",
    )
    refusal_reason: str = Field(
        default="",
        description=(
            "intent='refuse'일 때만. 사용자에게 들려주듯 자연스러운 거절 1문장. "
            "'도메인 외', '가치사슬', '시스템 답변 범위' 같은 시스템 메타 표현 금지."
        ),
    )
    suggestion: str = Field(
        default="",
        description="intent='refuse'일 때만. 친근한 대안 안내 1문장.",
    )


class PlanExecuteState(TypedDict):
    messages: Annotated[list, add_messages]  # 사용자 쿼리 (멀티턴 히스토리 포함)
    plan: ExecutionPlan | None
    stage_results: list[dict[str, Any]]
    agent_calls: list[str]  # 실제 호출된 에이전트 순서
    final_answer: str
    guardrail_blocked: bool  # 보안검사 노드가 UNSAFE 차단 시 True (이후 END)
    clarify_intent: str | None  # "proceed" | "clarify" | "refuse"
    clarification_question: str | None
    refusal_message: str | None
    tool_calls: list[dict[str, Any]]  # [{agent, tool, input, output, latency_s, status}]
    refused_topics: list[str]  # 이전 turn 에서 거절한 주제 키워드 누적 (멀티턴 거절 일관성)
    domain_answers: dict[str, dict[str, Any]]  # Map-Reduce 경로의 도메인별 sub-answer
    pending_stages: list[list[StageTask]]  # 실행 대기 stage 큐 (계획수립이 채우고, 재계획이 추가, 단계실행이 pop)
    replan_count: int  # 재계획 횟수 (상한 MAX_REPLAN 체크용)
    plan_status: str  # "ok" | "empty" | "error" | "backstop" — plan 실패와 정당한 빈 계획의 구분자 (#204)
