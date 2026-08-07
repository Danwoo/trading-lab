"""그래프 노드가 공유하는 해결된 의존성 묶음 + 동적 라우팅 스키마 팩토리.

원래 build_plan_execute_graph() 가 클로저로 캡처하던 LLM·타임아웃·플래그를 한 곳에 모은다.
노드/라우터는 top-level 함수가 되고 이 _GraphDeps 를 첫 인자로 받아(functools.partial 바인딩)
그래프 구조(topology)는 그대로 유지하면서 클로저 캡처만 명시적 파라미터화한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from .schemas import ExecutionPlan, ReplanDecision, StageTask


@dataclass(frozen=True, kw_only=True)
class _GraphDeps:
    """노드/라우터가 참조하는 해결된(=기본값·폴백이 적용된) 의존성.

    필드는 원래 클로저가 캡처하던 로컬 변수와 1:1 대응 (동작 보존).

    kw_only=True + 기본값 (#284) — 이전엔 전 필드가 위치 인자 가능한 필수값이라, 새 필드를
    하나 추가할 때마다 모든 생성처(테스트·스크립트의 직접 `_GraphDeps(...)` 포함)를 함께 고쳐야
    했다(#275 의 guardrail_timeout_s 추가가 실측: builder.py 포함 4곳). 값에 안전한 기본값이
    있는 "튜닝 노브"(타임아웃·재시도·플래그·임계값)는 build_plan_execute_graph() 파라미터
    기본값과 동일하게 여기에도 기본값을 둔다 — 새 노브를 추가해도 기존 생성처(기본값을 원하는
    한)는 고칠 필요가 없다. 안전한 기본값이 없는 핵심 배선(LLM·콜러블·agents·프롬프트)은
    의도적으로 필수로 남긴다 — 그것까지 기본값을 주면 "빠뜨렸는데 조용히 동작"하는 쪽이 더
    위험하다.
    """

    # 구조화 출력이 바인딩된 LLM — 안전한 기본값 없음 (필수)
    planner: Any
    clarifier: Any
    replanner: Any
    # 원본 LLM / 콜러블 — 안전한 기본값 없음 (필수)
    generator_llm: Any
    guardrail_llm: Any
    guardrail_fn: Any
    writer_llm: Any
    # 에이전트 레지스트리 — 안전한 기본값 없음 (필수)
    agents: dict
    # 프롬프트 — 안전한 기본값 없음 (필수, agent_descriptions 유무로 호출부가 결정)
    plan_system: str
    replan_system: str
    # 호출 파라미터 — build_plan_execute_graph() 기본값과 lockstep
    agent_timeout: float = 90.0
    agent_max_retries: int = 0
    agent_retry_delay: float = 1.0
    react_recursion_limit: int = 20
    # 타임아웃 — build_plan_execute_graph() 기본값과 lockstep
    plan_timeout_s: float = 60.0
    answer_timeout_s: float = 180.0
    clarify_timeout_s: float = 15.0
    guardrail_timeout_s: float = 15.0
    map_timeout_s: float = 50.0
    # 히스토리 프롬프트 주입 총량 상한(문자) — _build_history_ctx 소비 노드 4곳에 전달 (#207)
    history_max_chars: int = 8000
    # 분기 플래그·임계값 — build_plan_execute_graph() 기본값과 lockstep
    enable_clarify: bool = True
    enable_guardrail: bool = True
    max_replan: int = 2
    map_reduce_domain_threshold: int = 3
    map_concurrency: int = 2
    reduce_mode: str = "full"


def _build_dynamic_schemas(agent_names_str: str) -> tuple[type[BaseModel], type[BaseModel], type[BaseModel]]:
    """schemas.py 정적 모델을 상속해 agent_name 에 유효 에이전트 목록을 주입한 LLM 라우팅 스키마 3종.

    런타임 Literal 생성은 불안정해 str + description 으로 유효 이름을 안내한다.
    agent_name 외 필드 문안은 base 의 model_fields 에서 끌어와 정적/동적 표류를 구조적으로 차단
    (회귀 검증: scripts/verify_schema_parity.py).
    반환: (StageTask, ExecutionPlan, ReplanDecision) — planner/replanner 구조화 출력용.
    """

    class _StageTask(StageTask):
        agent_name: str = Field(description=f"호출할 에이전트 이름. 반드시 다음 중 하나: {agent_names_str}")

    class _ExecutionPlan(ExecutionPlan):
        # base 는 폴백 ExecutionPlan(stages=[]) 용 optional — LLM 은 근거를 반드시 산출
        reasoning: str = Field(description=ExecutionPlan.model_fields["reasoning"].description)
        stages: list[list[_StageTask]] = Field(description=ExecutionPlan.model_fields["stages"].description)

    class _ReplanDecision(ReplanDecision):
        next_stage: list[_StageTask] = Field(
            default_factory=list,
            description=ReplanDecision.model_fields["next_stage"].description,
        )

    return _StageTask, _ExecutionPlan, _ReplanDecision
