"""ExecutionPlan 파생 순수함수 (IO 없음)."""

from __future__ import annotations


def plan_domains(plan_obj) -> list[str]:
    """ExecutionPlan.stages 에서 호출 예정 도메인 에이전트 이름을 순서·중복제거하여 추출."""
    domains: list[str] = []
    for stage in getattr(plan_obj, "stages", []) or []:
        for task in stage or []:
            name = getattr(task, "agent_name", None)
            if name and name not in domains:
                domains.append(name)
    return domains
