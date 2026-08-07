"""#276 — ANSWER_SYSTEM 이 운영정보 마스킹 문구를 데이터 부재 상황에도 쓰게 유도하던 문제 (LLM 호출 0회).

프롬프트 문구는 눈으로 판정하는 것이라(LLM 평가 없이) 문장 자체가 근거다. 이 테스트는 LLM 판정이
아니라 **회귀 방지용 문자열 계약**이다 — 마스킹 문구("해당 부분 데이터 일시 수집 불가")를
운영정보(API 키·IP·서비스 원문 코드) 전용으로 못 박는 구분 문구가 살아있는지, 그리고 이전의
모호한 단일 절 형태로 되돌아가지 않았는지 확인한다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_answer_system_masking_scope.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from graphs.system import ANSWER_SYSTEM  # noqa: E402

# #204 실측 — 이 문구가 살아있으면 데이터 부재 상황에도 마스킹 문구를 쓰라고 유도한다 (회귀 대상).
_OLD_AMBIGUOUS_FRAGMENT = '항목은 모두 다룸(없으면 "일반적으로…"로 채움). API 키'

_MASKING_PHRASE = "해당 부분 데이터 일시 수집 불가"


def test_masking_phrase_scoped_away_from_missing_data() -> str:
    """자료 부재 절에 '마스킹 문구를 쓰지 않는다'는 명시적 배제가 있다."""
    assert "아래 마스킹 문구는 쓰지 않음" in ANSWER_SYSTEM, (
        f"자료 부재 상황에서 마스킹 문구 사용을 명시적으로 배제하는 문구가 없음: {ANSWER_SYSTEM!r}"
    )
    return "test_masking_phrase_scoped_away_from_missing_data"


def test_masking_phrase_still_reserved_for_operational_info() -> str:
    """마스킹 문구 자체는 남아있되(운영정보 전용) 조건이 '운영정보'로 명시된다."""
    assert _MASKING_PHRASE in ANSWER_SYSTEM, "운영정보 마스킹 문구 자체가 사라짐 — 운영정보 노출 위험"
    assert "운영정보" in ANSWER_SYSTEM, "마스킹 문구의 적용 범위(운영정보)가 명시되지 않음"
    return "test_masking_phrase_still_reserved_for_operational_info"


def test_old_ambiguous_single_clause_not_reintroduced() -> str:
    """#204 가 관측한 모호한 단일 절 형태(자료부재·운영정보 미분리)로 되돌아가지 않았다."""
    assert _OLD_AMBIGUOUS_FRAGMENT not in ANSWER_SYSTEM, "모호한 구버전 문구로 회귀함 (#276 재발)"
    return "test_old_ambiguous_single_clause_not_reintroduced"


def _main() -> int:
    tests = [
        test_masking_phrase_scoped_away_from_missing_data,
        test_masking_phrase_still_reserved_for_operational_info,
        test_old_ambiguous_single_clause_not_reintroduced,
    ]
    passed = 0
    for tc in tests:
        print(f"PASS {tc()}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
