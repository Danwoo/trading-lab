"""E-ALL — 전 파이프라인 6 시나리오 사후 측정 (#207 목표 판정, Tier 1: 실 LLM+MCP 호출).

⚠️ 이 스크립트는 실 LLM API 와 로컬 MCP 서버들을 호출한다. CI 에서 절대 실행 금지.
   `--confirm-budget` 없이 실행하면 예산 문구만 출력하고 종료한다 (명시 동의 게이트).
   사전 상한: 라우터 8만 토큰 — 누적 초과 조짐 시 즉시 중단하고 그때까지의 표를 보고한다.

산출: T1(usage_tracker) 수집치로 시나리오별 라우터·generator 토큰 표 (요약 평균만 제출 금지).
베이스라인: 이슈 실측 1만~1.3만/질문 — 동일 조건 재측정이 불가한 사후 비교임을 명기한다.
합격: 라우터 토큰 중앙값 ≤ 6.5k AND 전 시나리오 정상 종료 (05-evalset §E-ALL).

멀티턴 시나리오는 DB 대신 고정 히스토리 스텁을 쓴다 (재현성 — 좌표를 코드에 고정).
usage 필드가 근사(estimated=true)로 수집되면 표에 그대로 표기한다 — 근사로 합격 주장 금지.

사용: cd multi-agent-service && APP_ENV=development uv run python evals/run_e2e_measure.py --confirm-budget
      (MCP 서버들 기동 상태에서 — 데모와 같은 날 실행 금지)
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import os
import statistics
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

_ROUTER_TOKEN_HARD_CAP = 80_000  # 사전 상한 — 초과 조짐 시 중단 (05-evalset §E-ALL)
_PASS_ROUTER_MEDIAN = 6_500  # 베이스라인(이슈 실측 1만~1.3만)의 ~50%

# 라우터 모델이 지는 run_name — usage by_node 를 라우터/generator 로 분류 (00-cluster-analysis §1)
_ROUTER_LABELS = frozenset(
    {"보안 검사", "보충질문 판단", "계획 수립", "에이전트 선택", "결과 평가", "답변 합성", "인자 생성", "재계획 판단"}
)

_SCENARIOS = [
    ("단순 시세", "삼성전자 현재가 알려줘", 1),
    ("단일 도메인 재무", "삼성전자 최근 분기 실적 분석해줘", 1),
    ("업로드 문서 요약 (#204 재현)", "업로드한 리서치 보고서 요약해줘", 1),
    ("4도메인 종합", "삼성전자 재무·밸류·리스크·시장 모두 정리해줘", 1),
    ("멀티턴 후속 (히스토리 캡 경로)", "그 종목의 배당 정책은 어때?", 2),
    ("도메인 외 거절", "다음 주 날씨 알려줘", 1),
]

# 멀티턴 시나리오(gid=2)용 고정 히스토리 — 히스토리 캡 경로를 태우기 위한 장문 3턴
_MULTITURN_HISTORY = [
    {"question": "삼성전자 최근 분기 실적 알려줘", "answer": "삼성전자 2026년 2분기 매출은 …" + "상세 분석 " * 300},
    {"question": "그 실적에서 반도체 부문 비중은?", "answer": "반도체(DS) 부문은 …" + "부문 상세 " * 300},
    {"question": "경쟁사와 비교하면 어때?", "answer": "경쟁사 대비 …" + "비교 상세 " * 300},
]


def _require_budget_confirmation() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="E-ALL 전 파이프라인 6 시나리오 사후 측정 (실 LLM+MCP 호출)")
    parser.add_argument("--confirm-budget", action="store_true", help="예산 문구를 확인했고 실행에 동의")
    args = parser.parse_args()
    if not args.confirm_budget:
        print("이 실행기는 실 LLM API 예산을 소모합니다. 아래 예산을 확인한 뒤 --confirm-budget 로 동의하세요:")
        print(f"  - E-ALL: 파이프라인 6회 실행, 라우터 목표 ~4만 토큰, 사전 상한 {_ROUTER_TOKEN_HARD_CAP:,} 토큰")
        print("  - 실행 제약: 1일 라우터 10만 토큰 이하, 데모와 같은 날 금지, MCP 서버 기동 필요 (05-evalset §3)")
        sys.exit(2)
    return args


class _StubHistoryRepo:
    """멀티턴 시나리오용 고정 히스토리 — gid=2 만 3턴 반환, 그 외 빈 목록 (DB 불요·재현 고정)."""

    async def select_history(self, email: str, gid: int) -> list[dict]:
        return list(_MULTITURN_HISTORY) if gid == 2 else []


async def _main() -> int:
    _require_budget_confirmation()

    from clients.llm.llm_client import get_evaluator_llm, get_generator_llm, get_planner_llm, get_router_llm
    from clients.mcp.mcp_client import get_mcp_client
    from core.config import settings
    from services.agent.agent_service import AgentService
    from services.agent.response_cache import ResponseCache
    from utils.agent.mcp_classify import ALL_MCP_SERVICES

    service = AgentService(
        config=settings,
        mcp_client=get_mcp_client(settings),
        router_llm=get_router_llm(settings),
        planner_llm=get_planner_llm(settings),
        generator_llm=get_generator_llm(settings),
        evaluator_llm=get_evaluator_llm(settings),
        chat_history_repository=_StubHistoryRepo(),
        response_cache=ResponseCache(settings),  # 기본 비활성 — 캐시 hit 로 측정이 비는 것 방지
    )
    await service.initialize()

    rows: list[dict] = []
    router_total_accum = 0
    for name, question, gid in _SCENARIOS:
        usage_payload: dict = {}
        answer_len = 0
        error = ""
        async for event in service.stream_query(
            question, email="eval@local", gid=gid, enabled_mcps=set(ALL_MCP_SERVICES)
        ):
            if event.get("type") == "text":
                answer_len += len(event.get("content") or "")
            elif event.get("type") == "error":
                error = event.get("content") or "error"
            elif event.get("type") == "trace":
                usage_payload = (event.get("metadata") or {}).get("usage") or {}
        by_node = usage_payload.get("by_node") or {}
        router_tokens = sum(
            v.get("input_tokens", 0) + v.get("output_tokens", 0) for k, v in by_node.items() if k in _ROUTER_LABELS
        )
        other_tokens = sum(
            v.get("input_tokens", 0) + v.get("output_tokens", 0) for k, v in by_node.items() if k not in _ROUTER_LABELS
        )
        other_labels = sorted(k for k in by_node if k not in _ROUTER_LABELS)
        rows.append(
            {
                "scenario": name,
                "router_tokens": router_tokens,
                "other_tokens": other_tokens,
                "other_labels": other_labels,
                "calls": (usage_payload.get("total") or {}).get("calls", 0),
                "estimated": usage_payload.get("estimated", False),
                "answer_len": answer_len,
                "error": error,
            }
        )
        r = rows[-1]
        print(
            f"[{name}] router={r['router_tokens']} 기타(gen 포함)={r['other_tokens']} calls={r['calls']} "
            f"estimated={r['estimated']} answer_len={r['answer_len']}{' ERROR=' + error if error else ''}"
        )
        router_total_accum += router_tokens
        if router_total_accum > _ROUTER_TOKEN_HARD_CAP:
            print(f"\n중단: 라우터 누적 {router_total_accum:,} > 사전 상한 {_ROUTER_TOKEN_HARD_CAP:,} — 재승인 필요")
            return 1

    medians = statistics.median([r["router_tokens"] for r in rows])
    all_ok = all(not r["error"] and r["answer_len"] > 0 for r in rows)
    any_estimated = any(r["estimated"] for r in rows)
    print(f"\n라우터 토큰 중앙값: {medians:,.0f} (합격선 ≤ {_PASS_ROUTER_MEDIAN:,}) · 전 시나리오 정상 종료: {all_ok}")
    print("베이스라인: 이슈 실측 1만~1.3만/질문 — 동일 조건 재측정 불가한 사후 비교임")
    print(
        f"재현 조건: 실행일={datetime.date.today().isoformat()} router={settings.ROUTER_LLM_MODEL} "
        f"generator={settings.GENERATOR_LLM_MODEL} APP_ENV={os.environ.get('APP_ENV')}"
    )
    if any_estimated:
        print("판정: 보류 — usage 가 근사(estimated)로 수집됨. 근사로는 합격을 주장하지 않는다 (실측 경로 확인 필요)")
        return 1
    passed = medians <= _PASS_ROUTER_MEDIAN and all_ok
    print("판정: " + ("합격" if passed else "불합격 — 관측 데이터로 다음 절감 대상 재명세 (추측 기반 추가 절감 금지)"))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
