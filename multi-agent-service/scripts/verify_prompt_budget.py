"""시스템 프롬프트 토큰 예산 실측·핀 — E-207 Tier 0 (LLM 호출 0회, 오프라인 토크나이저).

계약 (평가셋 정본 05 §1 E-207):
  - 대상 전수: guardrail(+구조화 스키마)·CLARIFY·PLAN(동적 카탈로그+동적 스키마)·REPLAN(동적)·
    ANSWER·MAP·REDUCE·_WRITER_SYSTEM 2종(shared·pipeline_subagent)
  - 문자수 + 토큰수 표 출력, 선언된 예산(_BUDGET_TOKENS) 초과 시 exit 1 — 프롬프트 비대화 회귀 핀
  - 이 스크립트가 #207 이슈의 "guardrail ~5.7k 토큰" 주장을 실측으로 확정/기각한다

토크나이저: tiktoken o200k_harmony (gpt-oss 계열 공개 인코딩 — 라우터 모델 openai/gpt-oss-120b 와
동계열, 오프라인). generator 모델 토크나이저는 미확정이므로 generator 소비 프롬프트(ANSWER·MAP·
REDUCE·writer)의 토큰수는 근사다 — 표의 값은 전부 o200k_harmony 기준임을 명기한다.

fail-closed: 대상 프롬프트가 비었거나(import 경로 붕괴 포함) 행 수가 기대와 다르면 실패.
사용: `APP_ENV=development uv run python scripts/verify_prompt_budget.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# app import 체인이 Settings() 를 인스턴스화 — env 없는 실행(CI 등)에서 JWT_SECRET fail-fast 우회
os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import tiktoken  # noqa: E402
from agents.registry import load_domain_registry  # noqa: E402
from agents.specs import _SECURITY_FOOTER  # noqa: E402
from agents.sub_agents import get_domain_descriptions  # noqa: E402
from graphs.pipeline_subagent import _WRITER_SYSTEM as PIPELINE_WRITER_SYSTEM  # noqa: E402
from graphs.plan_execute.deps import _build_dynamic_schemas  # noqa: E402
from graphs.shared import _WRITER_SYSTEM as SHARED_WRITER_SYSTEM  # noqa: E402
from graphs.system import (  # noqa: E402
    ANSWER_SYSTEM,
    CLARIFY_SYSTEM,
    MAP_DOMAIN_SYSTEM,
    PLAN_SYSTEM_TEMPLATE,
    REDUCE_SYSTEM,
    REPLAN_SYSTEM_TEMPLATE,
)
from services.agent.guardrail import _GuardrailOutput, create_guardrail_system_prompt  # noqa: E402

_ENCODING = "o200k_harmony"

# 토큰 예산 핀 — 2026-07-30 실측값에 +10% 내림 여유. 초과 = 프롬프트 비대화 회귀(빨간불).
# 값을 올리려면 그 변경 자체가 리뷰 대상이다 (#207 회귀 방향: 프롬프트가 조용히 자라는 것).
# guardrail 은 T6(축약, 별도 승인) 반영 시 ~50% 로 내려 다시 핀 한다.
_BUDGET_TOKENS = {
    "guardrail": 1130,  # 실측 1022 — 이슈의 "~5.7k" 주장은 프롬프트 단독 기준으로는 기각
    "guardrail 구조화 스키마(JSON)": 70,  # 실측 61
    "CLARIFY": 1270,  # 실측 1150
    "PLAN (동적 카탈로그)": 1240,  # 실측 1125
    "PLAN 동적 스키마(JSON)": 480,  # 실측 435
    "REPLAN (동적 카탈로그)": 710,  # 실측 643
    "ANSWER": 1060,  # 실측 955
    "MAP": 780,  # 실측 705
    "REDUCE": 820,  # 실측 739
    "WRITER (shared — 정적)": 850,  # 실측 769
    "WRITER (pipeline_subagent — 대표 구성)": 1250,  # 실측 1129 (catalog 설명 제외 하한)
}


def _build_rows() -> list[tuple[str, str]]:
    """(이름, 프롬프트 텍스트) 행 — 동적 프롬프트는 실제 4도메인 registry 로 구성한다."""
    _, domain_registry = load_domain_registry(["instrument", "financials", "risk", "market"])
    descriptions = get_domain_descriptions(domain_registry)
    agents_section = "\n".join(f"- {name:<22}: {desc}" for name, desc in descriptions.items())
    agent_names = ", ".join(sorted(descriptions.keys()))
    _, execution_plan_cls, _ = _build_dynamic_schemas(agent_names)

    # pipeline writer 는 대표 구성(financials_sub base + 도구 이름 4종 catalog)으로 측정 —
    # 실제 catalog 설명은 MCP 런타임 주입이라 오프라인 측정은 하한이다 (표 비고 참조).
    from agents.domains.financials import SUBAGENT_SPECS

    fin_spec = SUBAGENT_SPECS["financials_sub"]
    representative_catalog = "\n".join(f"- {name}: (MCP 런타임 설명)" for name in fin_spec.mcp_tools)
    pipeline_writer = PIPELINE_WRITER_SYSTEM.format(
        base=fin_spec.prompt,
        catalog=representative_catalog,
        footer=_SECURITY_FOOTER,
        data_start="<<<UNTRUSTED_TOOL_DATA>>>",
        data_end="<<<END_UNTRUSTED_TOOL_DATA>>>",
    )

    return [
        ("guardrail", create_guardrail_system_prompt()),
        ("guardrail 구조화 스키마(JSON)", json.dumps(_GuardrailOutput.model_json_schema(), ensure_ascii=False)),
        ("CLARIFY", CLARIFY_SYSTEM),
        ("PLAN (동적 카탈로그)", PLAN_SYSTEM_TEMPLATE.format(agents_section=agents_section)),
        ("PLAN 동적 스키마(JSON)", json.dumps(execution_plan_cls.model_json_schema(), ensure_ascii=False)),
        ("REPLAN (동적 카탈로그)", REPLAN_SYSTEM_TEMPLATE.format(agents_section=agents_section)),
        ("ANSWER", ANSWER_SYSTEM),
        ("MAP", MAP_DOMAIN_SYSTEM.format(domain_name="재무")),
        ("REDUCE", REDUCE_SYSTEM),
        ("WRITER (shared — 정적)", SHARED_WRITER_SYSTEM),
        ("WRITER (pipeline_subagent — 대표 구성)", pipeline_writer),
    ]


def main() -> int:
    enc = tiktoken.get_encoding(_ENCODING)
    rows = _build_rows()

    problems: list[str] = []
    if set(_BUDGET_TOKENS) != {name for name, _ in rows}:
        problems.append("예산 표와 측정 행이 불일치 — 대상 추가/삭제 시 두 곳을 함께 고쳐라")

    print(f"시스템 프롬프트 토큰 예산 (토크나이저: tiktoken {_ENCODING} — gpt-oss 계열, 오프라인)")
    print(f"{'프롬프트':<42} {'문자수':>8} {'토큰수':>8} {'예산':>8}  판정")
    total_tokens = 0
    for name, text in rows:
        if not text or not text.strip():
            problems.append(f"{name}: 프롬프트가 비어 있음 (import·구성 경로 붕괴)")
            continue
        tokens = len(enc.encode(text))
        total_tokens += tokens
        budget = _BUDGET_TOKENS.get(name)
        verdict = "-"
        if budget is not None:
            verdict = "OK" if tokens <= budget else "초과"
            if tokens > budget:
                problems.append(f"{name}: {tokens} 토큰 > 예산 {budget} (프롬프트 비대화 회귀)")
        print(f"{name:<42} {len(text):>8} {tokens:>8} {budget if budget is not None else '-':>8}  {verdict}")
    print(f"\n검사 행 수: {len(rows)} (기대 {len(_BUDGET_TOKENS)}) · 토큰 합계: {total_tokens}")
    print("비고: generator 소비 프롬프트(ANSWER·MAP·REDUCE·WRITER)의 토큰수는 o200k_harmony 근사.")
    print("비고: WRITER(pipeline) 는 catalog 설명이 MCP 런타임 주입이라 오프라인 측정은 하한.")

    if len(rows) != len(_BUDGET_TOKENS) or len(rows) == 0:
        problems.append(f"검사 행 수 {len(rows)} ≠ 기대 {len(_BUDGET_TOKENS)} — fail-closed")

    if problems:
        print("\n예산 위반/구성 오류:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nprompt budget OK — 전 행 예산 이내")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
