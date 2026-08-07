"""정적/동적 스키마 parity 검증 — schemas.py ↔ deps._build_dynamic_schemas.

계약: LLM 라우팅용 동적 스키마 3종(_StageTask/_ExecutionPlan/_ReplanDecision)은
schemas.py 정적 모델의 **서브클래스**이고, 필드 문안(description)·필수 여부는 base 와
동일해야 한다. 의도된 분기는 2개뿐:
  (1) agent_name — str + agents.keys() 목록 주입 (런타임 Literal 생성 불안정 우회)
  (2) _ExecutionPlan.reasoning 필수화 — base 는 plan 실패 폴백 ExecutionPlan(stages=[]) 용 optional
표류 시 증상이 crash 가 아니라 LLM 라우팅 품질 저하(어긋난 문안이 조용히 프롬프트에 실림)라
정적 검사가 유일한 회귀 방어선이다.

pydantic import 필요 (stdlib 불가) — `uv run python scripts/verify_schema_parity.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# app import 체인이 Settings() 를 인스턴스화 — env 없는 실행(CI 등)에서 JWT_SECRET fail-fast 우회
os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from graphs.plan_execute.deps import _build_dynamic_schemas  # noqa: E402
from graphs.plan_execute.schemas import ExecutionPlan, ReplanDecision, StageTask  # noqa: E402

_NAMES = "financials_domain, instrument_domain, market_domain, risk_domain"
# (base 모델명, 필드명) — description·필수 여부 비교에서 제외되는 의도된 분기
_INTENDED = {("StageTask", "agent_name"), ("ExecutionPlan", "reasoning")}


def main() -> int:
    dyn_st, dyn_ep, dyn_rd = _build_dynamic_schemas(_NAMES)
    problems: list[str] = []

    for dyn, base in ((dyn_st, StageTask), (dyn_ep, ExecutionPlan), (dyn_rd, ReplanDecision)):
        if not issubclass(dyn, base):
            problems.append(f"{dyn.__name__} 가 {base.__name__} 의 서브클래스가 아님")
            continue
        for fname, dfield in dyn.model_fields.items():
            bfield = base.model_fields.get(fname)
            if bfield is None:
                problems.append(f"{dyn.__name__}.{fname}: base {base.__name__} 에 없는 필드")
                continue
            if (base.__name__, fname) in _INTENDED:
                continue
            if dfield.description != bfield.description:
                problems.append(f"{dyn.__name__}.{fname}: description 이 base 와 표류")
            if dfield.is_required() != bfield.is_required():
                problems.append(f"{dyn.__name__}.{fname}: 필수 여부가 base 와 표류")

    # agent_name 목록 주입이 중첩 스키마($defs 의 _StageTask)까지 실제 도달하는지
    for dyn in (dyn_ep, dyn_rd):
        if _NAMES not in str(dyn.model_json_schema()):
            problems.append(f"{dyn.__name__}: agents 목록이 LLM JSON 스키마에 미반영")

    if problems:
        print("schema parity 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("schema parity OK — 동적 3종 모두 정적 서브클래스, 문안·필수 여부 동일 (의도 분기: agent_name, reasoning)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
