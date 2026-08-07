"""E-196W — sub-agent writer 수치 보존 평가 실행기 (Tier 1: 실 generator 호출 — 예산 승인 후에만).

⚠️ 이 스크립트는 실 LLM API 를 호출한다. CI 에서 절대 실행 금지.
   `--confirm-budget` 없이 실행하면 예산 문구만 출력하고 종료한다 (명시 동의 게이트).
   선행 조건: generator 제공자·쿼터 확인 보고 (05-evalset §E-196W).

실행 방식 (호출 최소화 — 05-evalset §E-196W):
  build_pipeline_subagent 에 실 generator + 스텁 param/도구를 주입하고, messages 에 증거를
  사전 주입한 뒤 max_iters=0 (forced-answer 모드) 으로 돌려 문항·샘플당 writer 를 정확히
  1회만 호출한다. forced 모드는 "추가 검색 한도 도달" 문구가 붙는다는 점에서 첫-패스
  프롬프트와 다르다 — 보존 행동 판정에는 영향이 없다고 보고 채택 (재현 조건에 명기).

채점 (전부 결정론 — LLM 판정자 없음):
  재현: required_numbers 를 numeric_guard._norm 정규화 매칭 — 18샘플 중 >=15 AND 전 3샘플
        실패 문항 0. 회귀: 비거절 답변 AND find_ungrounded_numbers(answer, evidence) == [].

사용: cd multi-agent-service && APP_ENV=development uv run python evals/run_writer_numeric.py --confirm-budget
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "writer_numeric.json"
_K_SAMPLES = 3
_BUDGET_LINES = [
    "E-196W 예산: generator 36회 호출 (12문항 × K=3), 추정 6만~9만 토큰.",
    "선행 조건: generator 제공자·쿼터 확인 보고. 데모와 같은 날 실행 금지 (05-evalset §3).",
]


def _require_budget_confirmation() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E-196W writer 수치 보존 평가 (실 LLM 호출)")
    parser.add_argument("--confirm-budget", action="store_true", help="예산 문구를 확인했고 실행에 동의")
    args = parser.parse_args()
    if not args.confirm_budget:
        print("이 실행기는 실 LLM API 예산을 소모합니다. 아래 예산을 확인한 뒤 --confirm-budget 로 동의하세요:")
        for line in _BUDGET_LINES:
            print(f"  - {line}")
        sys.exit(2)
    return args


async def _main() -> int:
    _require_budget_confirmation()

    from agents.domains.financials import SUBAGENT_SPECS
    from agents.specs import _SECURITY_FOOTER
    from clients.llm.llm_client import get_generator_llm
    from core.config import settings
    from graphs.pipeline_subagent import build_pipeline_subagent
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel
    from utils.agent.numeric_guard import _ANY_NUM_RE, _norm, find_ungrounded_numbers
    from utils.agent.usage_tracker import UsageTracker

    fixture = json.loads(_FIXTURES.read_text(encoding="utf-8"))
    items = fixture["items"]
    if len(items) != 12:
        print(f"픽스처 문항 수 {len(items)} ≠ 12 — fail-closed (픽스처 변경은 명세 개정 사안)")
        return 1

    class _NeverParam:
        def bind_tools(self, tools, tool_choice=None):
            raise AssertionError("forced-answer 모드에서 param 이 호출되면 안 됨 (호출 예산 위반)")

    class _EmptyArgs(BaseModel):
        query: str = ""

    def _stub_tool(name: str) -> StructuredTool:
        async def _run(query: str = "") -> str:
            raise AssertionError("forced-answer 모드에서 도구가 호출되면 안 됨")

        return StructuredTool.from_function(coroutine=_run, name=name, description="스텁", args_schema=_EmptyArgs)

    fin_spec = SUBAGENT_SPECS["financials_sub"]
    generator = get_generator_llm(settings)
    tools = [_stub_tool(n) for n in fin_spec.mcp_tools]
    graph = build_pipeline_subagent(
        writer_llm=generator,
        param_llm=_NeverParam(),
        tools=tools,
        base_prompt=fin_spec.prompt,
        footer=_SECURITY_FOOTER,
        max_iters=0,  # forced-answer — 문항·샘플당 writer 정확히 1회
    )

    usage = UsageTracker()
    refusal_marker = "(검색 결과로 답변을 만들지 못했습니다.)"
    rows: list[dict] = []
    for item in items:
        evidence_calls = [{"tool": ev["tool"], "output": ev["output"]} for ev in item["evidence"]]
        messages: list = [HumanMessage(content=item["task"])]
        for i, ev in enumerate(item["evidence"]):
            call_id = f"ev-{item['id']}-{i}"
            messages.append(
                AIMessage(content="", tool_calls=[{"name": ev["tool"], "args": {}, "id": call_id, "type": "tool_call"}])
            )
            messages.append(ToolMessage(content=ev["output"], tool_call_id=call_id, name=ev["tool"]))
        for sample_idx in range(_K_SAMPLES):
            out = await graph.ainvoke({"messages": messages}, config={"callbacks": [usage]})
            answer = str(out["messages"][-1].content)
            answer_numbers = {_norm(tok) for tok in _ANY_NUM_RE.findall(answer)}
            if item["kind"] == "recall":
                missing = [n for n in item["required_numbers"] if _norm(n) not in answer_numbers]
                ok = not missing
                detail = f"누락={missing}" if missing else "보존"
            else:
                ungrounded = find_ungrounded_numbers(answer, evidence_calls)
                refused = refusal_marker in answer or len(answer.strip()) < 50
                ok = (not ungrounded) and (not refused)
                detail = f"미근거={ungrounded} 거절={refused}" if not ok else "정상"
            rows.append(
                {
                    "id": item["id"],
                    "kind": item["kind"],
                    "sample": sample_idx + 1,
                    "ok": ok,
                    "detail": detail,
                    "answer_len": len(answer),
                }
            )
            print(
                f"[{item['id']} s{sample_idx + 1}] {'PASS' if ok else 'FAIL'} — {detail} (len={rows[-1]['answer_len']})"
            )

    # 합격 판정 (요약 평균만 제출 금지 — 문항별 표 위에 출력 완료)
    recall_rows = [r for r in rows if r["kind"] == "recall"]
    regression_rows = [r for r in rows if r["kind"] == "regression"]
    recall_pass = sum(1 for r in recall_rows if r["ok"])
    all3_failed = [
        item_id
        for item_id in {r["id"] for r in recall_rows}
        if not any(r["ok"] for r in recall_rows if r["id"] == item_id)
    ]
    regression_bad = [r for r in regression_rows if not r["ok"]]

    print(
        f"\n재현: {recall_pass}/{len(recall_rows)} 샘플 보존 (합격선 >=15/18), 전 3샘플 실패 문항: {all3_failed or '없음'}"
    )
    print(f"회귀: 위반 {len(regression_bad)}건 (합격선 0)")
    print(f"usage: {usage.summary_line()}")
    print(
        f"재현 조건: 실행일={datetime.date.today().isoformat()} 모델={settings.GENERATOR_LLM_MODEL} "
        f"APP_ENV={os.environ.get('APP_ENV')} K={_K_SAMPLES} temp=0.3(팩토리) forced-answer 모드"
    )
    passed = recall_pass >= 15 and not all3_failed and not regression_bad
    print("판정: " + ("합격" if passed else "불합격 — iterate (기록을 이슈 코멘트로 축적 후 판단 요청)"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
