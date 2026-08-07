"""trace 이벤트 metadata 빌더 (순수함수, IO 없음).

stream_query 가 누적한 호출/결과 리스트를 UI 신뢰도·출처 표시 + 디버깅용 dict 로 종합한다.
모든 운영 정보(API 키·IP·실패 사유 등)는 redact_operational_info 로 sanitize.
"""

from __future__ import annotations

from collections import Counter

from utils.agent.grounding import compute_grounding
from utils.redaction.redactor import redact_operational_info


def build_trace_metadata(
    agent_calls: list[str],
    stage_results: list[dict],
    elapsed_s: float,
    answer_text: str,
    *,
    trace_enabled: bool,
    tool_calls: list[dict] | None = None,
    domain_answers: dict | None = None,
) -> dict:
    """trace 이벤트용 custom metadata. trace_enabled=False 면 빈 dict."""
    if not trace_enabled:
        return {}

    domain_hits = dict(Counter(agent_calls))

    flat_results = []
    for st in stage_results:
        flat_results.extend(st.get("results") or [])
    total = len(flat_results)
    success = sum(1 for r in flat_results if r.get("status") == "ok")
    failure = total - success
    error_rate = round(failure / total, 4) if total > 0 else 0.0

    # composite_score: 간이 휴리스틱 (답변 길이 + 성공률 가중합)
    length_score = min(1.0, len(answer_text) / 1000.0)
    success_score = success / total if total > 0 else 0.0
    composite = round(0.6 * length_score + 0.4 * success_score, 4)

    base_metadata: dict = {
        "sub_agent_calls": len(agent_calls),
        "domain_hits": domain_hits,
        "success_count": success,
        "failure_count": failure,
        "error_rate": error_rate,
        "elapsed_s": elapsed_s,
        "answer_len": len(answer_text),
        "composite_score": composite,
        "grounding": compute_grounding(tool_calls or []),
    }

    stage_results_detail = []
    for st in stage_results:
        stage_items = []
        for r in st.get("results") or []:
            stage_items.append(
                {
                    "agent": r.get("agent"),
                    "task": redact_operational_info(str(r.get("task", "")))[:300],
                    "status": r.get("status"),
                    "elapsed_s": r.get("elapsed_s"),
                    "group": r.get("group"),
                    "output_preview": redact_operational_info(str(r.get("output", "")))[:500],
                }
            )
        stage_results_detail.append({"stage": st.get("stage"), "results": stage_items})
    base_metadata["stage_results_detail"] = stage_results_detail

    if domain_answers:
        base_metadata["domain_answers_detail"] = {
            domain: {
                "domain_label": ans.get("domain_label"),
                "status": ans.get("status"),
                "narrative": redact_operational_info(str(ans.get("narrative", ""))),
                "elapsed_s": ans.get("elapsed_s"),
                "agent_count": ans.get("agent_count"),
            }
            for domain, ans in domain_answers.items()
        }

    if tool_calls:
        base_metadata["tool_calls"] = [
            {
                "agent": tc.get("agent"),
                "tool": tc.get("tool"),
                "input": redact_operational_info(str(tc.get("input", "")))[:500],
                "output": redact_operational_info(str(tc.get("output", "")))[:1000],
                "latency_s": tc.get("latency_s"),
                "status": tc.get("status"),
            }
            for tc in tool_calls
        ]

    return base_metadata
