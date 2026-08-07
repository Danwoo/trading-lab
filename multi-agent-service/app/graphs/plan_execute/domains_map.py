"""도메인 라벨·분류 + Hierarchical Map-Reduce 그룹핑 헬퍼.

★ 새 도메인 추가 시 이 파일을 손댄다 — _DOMAIN_LABELS 에 라벨 1줄 +
_build_subagent_domain_map() 의 SUBAGENT_SPECS import 목록에 추가 (Map-Reduce 도메인 분류·라벨).
"""

from __future__ import annotations

from core.logger import logger
from utils.redaction.redactor import redact_operational_info

_DOMAIN_LABELS: dict[str, str] = {
    "instrument": "종목·시세",
    "financials": "재무·공시",
    "risk": "리스크·밸류",
    "market": "시장·뉴스·매크로",
}


def _build_subagent_domain_map() -> dict[str, str]:
    """전체 도메인 모듈의 (sub_agent_name → domain) 매핑 빌드 (활성 도메인과 무관 — 분류 전용)."""
    mapping: dict[str, str] = {}
    try:
        from agents.domains.financials import SUBAGENT_SPECS as FINANCIALS_SPECS
        from agents.domains.instrument import SUBAGENT_SPECS as INSTRUMENT_SPECS
        from agents.domains.market import SUBAGENT_SPECS as MARKET_SPECS
        from agents.domains.risk import SUBAGENT_SPECS as RISK_SPECS

        for spec_set in (INSTRUMENT_SPECS, FINANCIALS_SPECS, RISK_SPECS, MARKET_SPECS):
            for name, spec in spec_set.items():
                mapping[name] = spec.domain
    except Exception as exc:
        logger.warning("[plan_execute] SUBAGENT_SPECS 로드 실패: %s — 이름 prefix 휴리스틱만 사용", exc)
    return mapping


_SUBAGENT_DOMAIN_MAP: dict[str, str] = _build_subagent_domain_map()


def _classify_domain(agent_name: str) -> str | None:
    """agent 이름 → 4 도메인 분류. SUBAGENT_SPECS 의 domain 필드 우선, 그 외 이름 prefix."""
    if not agent_name:
        return None
    if agent_name in _SUBAGENT_DOMAIN_MAP:
        return _SUBAGENT_DOMAIN_MAP[agent_name]
    for domain in _DOMAIN_LABELS:
        if agent_name == f"{domain}_domain" or agent_name.startswith(f"{domain}_"):
            return domain
    return None


def _group_results_by_domain(all_results: list[dict]) -> dict[str, list[dict]]:
    """stage_results 를 도메인별로 그룹화. 미분류 agent 는 'other'."""
    grouped: dict[str, list[dict]] = {}
    for stage_data in all_results:
        for item in stage_data.get("results", []):
            agent = item.get("agent", "")
            domain = _classify_domain(agent) or "other"
            grouped.setdefault(domain, []).append(item)
    return grouped


def _count_active_domains(all_results: list[dict]) -> int:
    """stage_results 에서 실제 호출된 도메인(4 카테고리) 개수. 'other'·빈 stage 제외."""
    grouped = _group_results_by_domain(all_results)
    return sum(1 for domain, items in grouped.items() if domain in _DOMAIN_LABELS and items)


def _format_domain_results(items: list[dict]) -> str:
    """단일 도메인의 sub-agent 결과를 Map prompt 입력 텍스트로 포맷."""
    parts = []
    for item in items:
        agent = item.get("agent", "unknown")
        status = item.get("status", "ok")
        if status == "ok":
            output = redact_operational_info(str(item.get("output", "")))
            parts.append(f"### {agent}\n{output}")
        else:
            err_detail = redact_operational_info(str(item.get("output", "")) or f"({status})")
            parts.append(f"### {agent}\n[{agent}_데이터수집실패: {status}] {err_detail}")
    return "\n\n".join(parts) if parts else "(이 도메인 수집 결과 없음)"
