"""stage 위상 정렬 회귀 검증 — topology._normalize_stages 의 정렬·안전망·completed 시딩 계약.

계약:
  (1) 독립 tasks 는 같은 stage 로 병합, 배치 내 의존성은 stage 분리로 순서 보존
  (2) 진짜 순환 의존성은 남은 tasks 를 마지막 stage 에 일괄 배치 (안전망)
  (3) completed 시딩: 이미 실행 완료된 에이전트에 대한 의존은 충족으로 취급 —
      재계획 배치가 직전 결과 의존을 순환으로 오판해 정렬이 무력화되던 결함의 회귀 방지
  (4) completed 미지정 시 기존(계획 시점) 동작과 동일 (하위호환)

import 체인이 Settings() 를 인스턴스화하므로 env 없는 실행(CI)용 placeholder 를 setdefault.
`uv run python scripts/verify_stage_topology.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from graphs.plan_execute.topology import _normalize_stages  # noqa: E402


def _t(agent: str, deps: list[str] | None = None) -> dict:
    return {"agent_name": agent, "depends_on_agents": deps or []}


def _shape(stages: list[list[dict]], completed: set[str] | None = None) -> list[list[str]]:
    return [[t["agent_name"] for t in st] for st in _normalize_stages(stages, completed)]


def main() -> int:
    problems: list[str] = []

    def check(name: str, got, want) -> None:
        if got != want:
            problems.append(f"{name}: got={got} want={want}")

    check("빈 입력", _shape([]), [])
    check("독립 tasks 병합", _shape([[_t("a")], [_t("b")]]), [["a", "b"]])
    check("배치 내 의존 분리", _shape([[_t("a"), _t("b", ["a"])]]), [["a"], ["b"]])
    check(
        "다단 체인",
        _shape([[_t("a")], [_t("b", ["a"]), _t("c", ["a"])], [_t("d", ["b"])]]),
        [["a"], ["b", "c"], ["d"]],
    )
    check("순환 안전망 (마지막 stage 일괄)", _shape([[_t("a", ["b"]), _t("b", ["a"])]]), [["a", "b"]])

    # completed 시딩 — 재계획 배치의 직전 실행 결과 의존
    check(
        "실행완료 의존 단일 (시딩)",
        _shape([[_t("financials", ["instrument"])]], completed={"instrument"}),
        [["financials"]],
    )
    check(
        "혼합 의존 순서 보존 (시딩)",
        _shape([[_t("financials", ["instrument"]), _t("risk", ["financials"])]], completed={"instrument"}),
        [["financials"], ["risk"]],
    )
    check(
        "혼합 의존 순서 보존 (미시딩=회귀 감지)",
        _shape([[_t("financials", ["instrument"]), _t("risk", ["financials"])]]),
        [["financials", "risk"]],
    )

    if problems:
        print("stage topology 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("stage topology OK — 병합·분리·순환 안전망·completed 시딩 계약 전부 성립")
    return 0


if __name__ == "__main__":
    sys.exit(main())
