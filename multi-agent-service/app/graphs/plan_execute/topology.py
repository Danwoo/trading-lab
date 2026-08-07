"""의존성 기반 stage 위상 정렬 (depends_on_agents → Kahn 변형)."""

from __future__ import annotations

from typing import Any

from core.logger import logger


def _normalize_stages(stages: list[list[Any]], completed: set[str] | None = None) -> list[list[Any]]:
    """planner output 을 depends_on_agents 기반 위상 정렬 (Kahn 변형).

    planner 의 stage 분할은 무시하고 depends_on_agents 만 신뢰 — 독립 tasks 는 같은
    stage 로 병합, 진짜 순차 의존성만 stage 분리 보존. 순환 의존성 발견 시 남은
    tasks 를 마지막 stage 에 일괄 배치 (안전망).

    completed: 이미 실행 완료된 에이전트 이름 집합 — 재계획 배치처럼 선행 stage 결과가
    이미 있는 컨텍스트에서 그 의존성을 충족된 것으로 취급 (미지정 시 계획 시점과 동일한 빈 집합).
    """
    all_tasks = [t for stage in stages for t in stage]
    if not all_tasks:
        return []

    def _deps_of(t: Any) -> list[str]:
        deps = getattr(t, "depends_on_agents", None)
        if deps is None and isinstance(t, dict):
            deps = t.get("depends_on_agents", [])
        return list(deps or [])

    def _agent_of(t: Any) -> str:
        return getattr(t, "agent_name", None) or (t.get("agent_name", "") if isinstance(t, dict) else "")

    pending = list(all_tasks)
    completed_agents: set[str] = set(completed or ())
    normalized: list[list[Any]] = []

    while pending:
        ready = [t for t in pending if all(d in completed_agents for d in _deps_of(t))]
        if not ready:
            logger.warning("[_normalize_stages] 순환 또는 미해결 의존성 — %d tasks를 마지막 stage로", len(pending))
            normalized.append(pending)
            break
        normalized.append(ready)
        for t in ready:
            completed_agents.add(_agent_of(t))
        pending = [t for t in pending if t not in ready]

    return normalized
