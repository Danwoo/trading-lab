"""#226 — **답변이 무슨 모델로 만들어지도록 설정됐는지**를 화면이 알 수 있다 (LLM 호출 0회).

설정에 제공자 축이 없고 모델명만 있어, 받은 사람은 자기 키가 어느 제공자 것인지에 따라
무엇을 적어야 하는지 모른다. 잘못 적어도 **기동은 되고 질문할 때 터진다.**

제공자를 고르는 화면은 키 저장 방침이 정해져야 만든다(#225 결정 대기). 그 전에도 「지금 무슨
모델로 답하도록 돼 있나」는 낼 수 있고, 그것만으로 「내가 넣은 설정이 실제로 쓰였나」가 확인된다.

**이 검사가 지키는 것 둘**:
  ① 값이 비어도 화면에 낼 문자열이 나온다 — 빈 문자열은 「없음」과 「모름」을 뭉갠다
  ② 게이트웨이 URL 로 제공자를 **추정하지 않는다** — 사내 게이트웨이는 어느 제공자든 감싸므로
     추정이 틀리면 화면이 거짓을 말한다

이 레포는 아직 pytest 를 도입하지 않았으므로 standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_model_identity.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from utils.agent.model_identity import UNKNOWN, model_identity  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def main() -> int:
    # ── 설정한 대로 나온다 ────────────────────────────────────────────────
    configured = SimpleNamespace(
        ROUTER_LLM_MODEL="gpt-4o-mini",
        GENERATOR_LLM_MODEL="claude-sonnet-4",
        ROUTER_LLM_BASE_URL="https://gateway.internal/v1",
        GENERATOR_LLM_BASE_URL="https://gateway.internal/v1",
    )
    identity = model_identity(configured)
    check("계획 모델", identity["planner"], "gpt-4o-mini")
    check("답변 모델", identity["generator"], "claude-sonnet-4")

    # ── 비어 있으면 「모름」이 나온다 — 빈 문자열로 뭉개지 않는다 ─────────
    empty = SimpleNamespace(ROUTER_LLM_MODEL="", GENERATOR_LLM_MODEL="")
    blank = model_identity(empty)
    check("안 넣으면 계획도 모름", blank["planner"], UNKNOWN)
    check("안 넣으면 답변도 모름", blank["generator"], UNKNOWN)

    # ── 설정 항목 자체가 없어도 죽지 않는다 ──────────────────────────────
    missing = model_identity(SimpleNamespace())
    check("항목이 없어도 모름", missing["planner"], UNKNOWN)

    # ── 제공자를 추정하지 않는다 — 같은 게이트웨이 뒤의 서로 다른 모델 ──
    check("계획과 답변이 따로 온다", identity["planner"] != identity["generator"], True)
    check("키는 둘뿐이다 — 추정한 제공자 항목이 없다", sorted(identity), ["generator", "planner"])

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 7:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 무슨 모델로 답하도록 설정됐는지가 화면에 낼 수 있는 형태로 나온다 (#226)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
