"""정적 동등성 증명 하네스 — plan_execute 리팩터 전/후 비교.

LLM/MCP 키 없이 그래프를 '실행'하지 못하므로 실행 대신 3축으로 동등성을 증명한다:
  (1) getsource  — 이동한 심볼의 소스 텍스트가 byte-identical (= 재작성 없음 증명)
  (2) behavior   — 순수 함수를 결정론적 입력으로 호출해 출력 비교
  (3) topology   — mock LLM/agent 로 그래프를 빌드(빌더는 LLM 을 호출하지 않음)해
                   compile 된 StateGraph 의 노드/엣지/조건분기 매핑을 덤프

개발 도구 — 프로덕션 패키지(app/) 밖 scripts/ 에 위치해 Docker 이미지에 실리지 않는다.
사용: `uv run python scripts/verify_plan_execute_refactor.py` (cwd=서비스 루트) → stdout 에 JSON 1개.
`--against <ref>` 를 주면 ref 를 임시 워크트리로 꺼내 그쪽 하네스 덤프와 현재 트리 덤프를 비교해
축별 MATCH/MISMATCH 를 출력한다 (워크트리 생성·정리는 스크립트 내부 처리, 전부 일치 시 exit 0).

`graphs.plan_execute.<name>` 네임스페이스로만 접근하는 이유: origin/main 은 plan_execute 가
단일 모듈(서브모듈 없음)이고 이 브랜치는 패키지(__init__ 재노출)다. 같은 스크립트가 양쪽에서
byte-identical 하게 돌아 동등성을 증명하려면 서브모듈 직접 import 가 아니라 이 공통 네임스페이스여야 한다.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

# app import 체인이 Settings() 를 인스턴스화 — env 없는 실행(CI 등)에서 JWT_SECRET fail-fast 우회
os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import graphs.plan_execute as pe  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

# 이동 대상 심볼 — top-level namespace 로 접근 (리팩터 후 __init__ 재노출로 동일 경로 유지)
_SOURCE_SYMBOLS = [
    "StageTask",
    "ExecutionPlan",
    "ReplanDecision",
    "ClarifyDecision",
    "PlanExecuteState",
    "_tool_output_text",
    "_ToolTraceCallback",
    "_extract_query",
    "_build_history_ctx",
    "_format_prior_stage_results",
    "_format_all_results_for_answer",
    "_ensure_disclaimer",
    "_build_subagent_domain_map",
    "_classify_domain",
    "_group_results_by_domain",
    "_count_active_domains",
    "_format_domain_results",
    "_normalize_stages",
    "_invoke_agent_safe",
    "build_plan_execute_graph",
]


def _dump_sources() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in _SOURCE_SYMBOLS:
        obj = getattr(pe, name)
        try:
            out[name] = inspect.getsource(obj)
        except (TypeError, OSError):
            out[name] = "<no-source>"
    return out


def _dump_constants() -> dict:
    return {
        "COMPLIANCE_DISCLAIMER": pe.COMPLIANCE_DISCLAIMER,
        "VALID_AGENTS": str(pe.VALID_AGENTS),
        "_DOMAIN_LABELS": pe._DOMAIN_LABELS,
        "_SUBAGENT_DOMAIN_MAP": dict(sorted(pe._SUBAGENT_DOMAIN_MAP.items())),
    }


def _obj(content):
    return types.SimpleNamespace(content=content)


def _stage(idx, results):
    return {"stage": idx, "results": results}


_SAMPLE_RESULTS = [
    _stage(
        0,
        [
            {
                "agent": "instrument_domain",
                "task": "t1",
                "output": "삼성전자 시세 조회 결과 email=a@b.com",
                "status": "ok",
            },
            {"agent": "financials_domain", "task": "t2", "output": "재무 실패", "status": "timeout"},
        ],
    ),
    _stage(
        1,
        [
            {"agent": "risk_domain", "task": "t3", "output": "리스크 평가 output", "status": "ok"},
            {"agent": "market_domain", "task": "t4", "output": "", "status": "ok"},
            {"agent": "weird_agent", "task": "t5", "output": "미분류", "status": "ok"},
        ],
    ),
]

_SAMPLE_TOOL_CALLS = [
    {"agent": "instrument_domain", "tool": "get_quote", "input": "삼성전자", "output": '{"code":"005930"}'},
    {"agent": "financials_domain", "tool": "get_fin", "input": "x", "output": ""},
]


def _dump_behavior() -> dict:
    b: dict = {}

    b["ensure_disclaimer"] = [
        pe._ensure_disclaimer(x) for x in ["", "투자 조언이 아닙니다 포함", "일반 텍스트", "  꼬리공백  \n"]
    ]

    b["tool_output_text"] = [
        pe._tool_output_text("plain string"),
        pe._tool_output_text(_obj([{"type": "text", "text": "블록텍스트"}, {"type": "json", "json": {"k": 1}}])),
        pe._tool_output_text(_obj([{"type": "other"}, "리터럴", 42])),
        pe._tool_output_text(_obj("content 문자열")),
        pe._tool_output_text(_obj(12345)),
        pe._tool_output_text(None),
    ]

    msgs = [
        HumanMessage(content="첫 질문"),
        AIMessage(content="첫 답변"),
        HumanMessage(content="  현재 질문  "),
    ]
    b["extract_query"] = pe._extract_query(msgs)
    b["extract_query_empty"] = pe._extract_query([AIMessage(content="no human")])
    b["build_history_ctx_k20"] = pe._build_history_ctx(msgs, 20)
    b["build_history_ctx_k1"] = pe._build_history_ctx(msgs, 1)
    b["build_history_ctx_single"] = pe._build_history_ctx([HumanMessage(content="only")], 20)

    b["format_prior_stage_results"] = pe._format_prior_stage_results(_SAMPLE_RESULTS, _SAMPLE_TOOL_CALLS)
    b["format_prior_stage_results_no_tc"] = pe._format_prior_stage_results(_SAMPLE_RESULTS, None)
    b["format_all_results_for_answer"] = pe._format_all_results_for_answer(_SAMPLE_RESULTS)
    b["format_all_results_empty"] = pe._format_all_results_for_answer([])

    b["classify_domain"] = {
        name: pe._classify_domain(name)
        for name in [
            "instrument_domain",
            "financials_domain",
            "risk_domain",
            "market_domain",
            "market_news",
            "unknown_thing",
            "",
            *list(pe._SUBAGENT_DOMAIN_MAP.keys())[:3],
        ]
    }

    grouped = pe._group_results_by_domain(_SAMPLE_RESULTS)
    b["group_results_by_domain"] = {k: [i.get("agent") for i in v] for k, v in sorted(grouped.items())}
    b["count_active_domains"] = pe._count_active_domains(_SAMPLE_RESULTS)
    b["format_domain_results"] = pe._format_domain_results(_SAMPLE_RESULTS[0]["results"])
    b["format_domain_results_empty"] = pe._format_domain_results([])

    # _normalize_stages — dict 및 pydantic 입력 모두, 순환 케이스 포함
    def _norm(stages):
        out = pe._normalize_stages(stages)
        return [[(getattr(t, "agent_name", None) or t.get("agent_name")) for t in stage] for stage in out]

    b["normalize_empty"] = _norm([])
    b["normalize_independent"] = _norm(
        [[{"agent_name": "a", "depends_on_agents": []}, {"agent_name": "b", "depends_on_agents": []}]]
    )
    b["normalize_chain"] = _norm(
        [
            [{"agent_name": "a", "depends_on_agents": []}],
            [{"agent_name": "b", "depends_on_agents": ["a"]}, {"agent_name": "c", "depends_on_agents": ["a"]}],
        ]
    )
    b["normalize_cycle"] = _norm(
        [[{"agent_name": "a", "depends_on_agents": ["b"]}, {"agent_name": "b", "depends_on_agents": ["a"]}]]
    )
    b["normalize_pydantic"] = _norm([[pe.StageTask(agent_name="instrument_domain", task="x", depends_on_agents=[])]])
    return b


class _MockLLM:
    """builder 가 with_structured_output / 저장만 하고 실행하지 않으므로 no-op 로 충분."""

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, *a, **k):  # pragma: no cover - 그래프 미실행
        raise AssertionError("mock LLM 은 빌드 전용")


def _edges(compiled) -> dict:
    g = compiled.get_graph()
    nodes = sorted(g.nodes.keys())
    edges = sorted(
        (
            f"{e.source}->{e.target}"
            + (" [cond]" if getattr(e, "conditional", False) else "")
            + (f" ({e.data})" if getattr(e, "data", None) not in (None, "") else "")
        )
        for e in g.edges
    )
    return {"nodes": nodes, "edges": edges}


def _dump_topology() -> dict:
    agents = {
        "instrument_domain": object(),
        "financials_domain": object(),
        "risk_domain": object(),
        "market_domain": object(),
    }
    descs = {k: f"{k} 설명" for k in agents}

    def build(**over):
        kw = dict(
            planner_llm=_MockLLM(),
            generator_llm=_MockLLM(),
            agents=agents,
            agent_descriptions=descs,
            writer_llm=_MockLLM(),
        )
        kw.update(over)
        return _edges(pe.build_plan_execute_graph(**kw))

    return {
        "clarify=T,guardrail=F": build(enable_clarify=True, enable_guardrail=False),
        "clarify=F,guardrail=F": build(enable_clarify=False, enable_guardrail=False),
        "clarify=T,guardrail=T": build(enable_clarify=True, enable_guardrail=True, guardrail_fn=lambda *a, **k: None),
        "clarify=F,guardrail=T": build(enable_clarify=False, enable_guardrail=True, guardrail_fn=lambda *a, **k: None),
        "no_descriptions": build(agent_descriptions=None),
    }


def _dump_all() -> dict:
    return {
        "constants": _dump_constants(),
        "behavior": _dump_behavior(),
        "topology": _dump_topology(),
        "sources": _dump_sources(),
    }


def _run_dump_at_ref(ref: str) -> dict:
    repo_root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
    ).stdout.strip()
    script_rel = Path(__file__).resolve().relative_to(repo_root)
    worktree = tempfile.mkdtemp(prefix="verify-plan-execute-")
    try:
        try:
            subprocess.run(
                ["git", "worktree", "add", "--detach", worktree, ref],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            sys.exit(f"error: ref '{ref}' 워크트리 생성 실패\n{e.stderr.strip()}")
        print(f"[against] {ref} 워크트리의 하네스 실행 중...", file=sys.stderr)
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            proc = subprocess.run(
                [sys.executable, str(Path(worktree) / script_rel)],
                cwd=Path(worktree) / script_rel.parent.parent,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        except subprocess.CalledProcessError as e:
            sys.exit(f"error: ref '{ref}' 의 하네스 실행 실패\n{e.stderr.strip()}")
        return json.loads(proc.stdout)
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", worktree], capture_output=True)
        shutil.rmtree(worktree, ignore_errors=True)


def _diff_keys(before: dict, after: dict) -> list[str]:
    return sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))


def _report(before: dict, after: dict) -> bool:
    ok = True
    for axis in ("topology", "constants", "behavior"):
        differ = _diff_keys(before.get(axis, {}), after.get(axis, {}))
        if differ:
            print(f"{axis}: MISMATCH (differ: {', '.join(differ)})")
            ok = False
        else:
            print(f"{axis}: MATCH")
    changed = _diff_keys(before.get("sources", {}), after.get("sources", {}))
    if changed:
        print(f"sources changed ({len(changed)}):")
        for name in changed:
            print(f"  - {name}")
        ok = False
    else:
        print(f"sources changed: 없음 ({len(after.get('sources', {}))} symbols 동일)")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="plan_execute 리팩터 전/후 정적 동등성 하네스")
    parser.add_argument(
        "--against",
        metavar="REF",
        help="비교할 git ref (예: origin/main) — 생략 시 현재 트리 덤프 JSON 만 출력",
    )
    args = parser.parse_args()

    current = _dump_all()
    if not args.against:
        print(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True))
        return

    before = _run_dump_at_ref(args.against)
    print(f"=== 비교: {args.against} vs 현재 트리 ===")
    ok = _report(before, current)
    print("RESULT: PASS" if ok else "RESULT: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
