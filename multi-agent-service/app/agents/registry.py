"""도메인 모듈 수집 — 활성 도메인 목록으로 SUBAGENT/DOMAIN 레지스트리 구성.

settings 직접 import 없이 호출자(AgentService)가 config.MULTI_AGENT_DOMAINS 를 넘긴다
(container 가 유일한 settings 경계 유지).

새 도메인 추가 절차:
    ① agents/domains/ 에 모듈 1개 — SUBAGENT_SPECS + DOMAIN_SPEC + register()
       (domain_key 는 "<도메인>_domain" 컨벤션)
    ② 아래 _DOMAIN_MODULES 에 {"<도메인>": 모듈} 등록
    ③ config.MULTI_AGENT_DOMAINS 에 키 추가 (core/config.py 기본값 또는 env)
    ④ graphs/plan_execute/domains_map.py — _DOMAIN_LABELS 에 라벨 1줄 + _build_subagent_domain_map()
       의 SUBAGENT_SPECS import 목록에 추가 (Map-Reduce 도메인 분류·라벨)
    ⑤ utils/agent/events.py — DOMAIN_KO_LABEL 에 "<도메인>_domain" 라벨 (UI step 이벤트)
플래너 프롬프트·plan 스키마는 DOMAIN_REGISTRY 에서 동적 구성되므로 별도 수정 불필요.
"""

from __future__ import annotations

from agents.domains import financials, instrument, market, risk
from agents.specs import DomainSpec, SubAgentSpec
from core.logger import logger

_DOMAIN_MODULES = {
    "instrument": instrument,
    "financials": financials,
    "risk": risk,
    "market": market,
}


def load_domain_registry(domains: list[str]) -> tuple[dict[str, SubAgentSpec], dict[str, DomainSpec]]:
    """활성 도메인 목록 → (SUBAGENT_REGISTRY, DOMAIN_REGISTRY)."""
    subagent_registry: dict[str, SubAgentSpec] = {}
    domain_registry: dict[str, DomainSpec] = {}

    for domain_name in domains:
        module = _DOMAIN_MODULES.get(domain_name)
        if module is None:
            logger.warning("[registry] 알 수 없는 도메인: %s (MULTI_AGENT_DOMAINS 확인)", domain_name)
            continue
        reg = module.register()
        subagent_registry.update(reg["sub_agents"])
        domain_registry[reg["domain_key"]] = reg["domain_spec"]
        logger.debug("[registry] 로드: %s → %s", domain_name, reg["domain_key"])

    return subagent_registry, domain_registry
