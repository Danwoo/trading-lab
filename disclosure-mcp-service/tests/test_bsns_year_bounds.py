"""#228 — 재무·배당 조회의 사업연도 경계가 시계를 따라가는지 검증.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_bsns_year_bounds.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식:
- 오늘 기준 당해 연도가 거부되지 않는다 (상한 2025 하드코딩으로 2026 회계연도가 422 였던 #228 의 회귀 가드).
- 상한·기본값이 소스에 박힌 상수가 아니다 — 시계를 옮기면 둘 다 따라 움직인다(매년 사람이 올릴 필요 없음).
- 하한(DART 제공 최초 연도)과 명백한 오타 입력은 여전히 거부한다.
- 소스에 연도 리터럴이 남아 있지 않다 — 다음 해에 조용히 낡는 값을 다시 들이지 않기 위한 가드.

시각 의존 검증은 스키마 모듈의 now_kst 를 갈아끼워(검증 시점 호출) 가짜 '오늘'로 돌린다.
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import schemas.disclosure.disclosure_schema as schema  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from utils.common.time_utils import now_kst  # noqa: E402

_SCHEMA_SOURCE = _APP_DIR / "schemas" / "disclosure" / "disclosure_schema.py"
_KST = ZoneInfo("Asia/Seoul")
_YEAR_MODELS = (schema.FinancialsIn, schema.DividendIn)


class _FrozenClock:
    """스키마 모듈의 now_kst 를 가짜 '오늘'로 바꾼다 (검증 시점 호출이라 교체가 그대로 먹는다)."""

    def __init__(self, year: int, month: int = 7, day: int = 1) -> None:
        self._fake = datetime.datetime(year, month, day, tzinfo=_KST)
        self._original = getattr(schema, "now_kst", None)

    def __enter__(self) -> _FrozenClock:
        assert self._original is not None, "스키마가 now_kst 를 쓰지 않는다 — 경계가 시계를 안 본다는 뜻"
        schema.now_kst = lambda: self._fake
        return self

    def __exit__(self, *exc_info) -> None:
        schema.now_kst = self._original


def _accepts(model, year: int) -> bool:
    try:
        model(corp="삼성전자", year=year)
    except ValidationError:
        return False
    return True


def test_current_year_is_accepted() -> str:
    """실제 오늘 기준 당해 연도 — 상한이 2025 로 박혀 있어 2026 이 422 였던 그 자리."""
    this_year = now_kst().year
    for model in _YEAR_MODELS:
        assert _accepts(model, this_year), f"{model.__name__}: 당해 연도 {this_year} 가 거부됨 — 상한이 낡았다"
    return "test_current_year_is_accepted"


def test_upper_bound_follows_the_clock() -> str:
    """상한이 상수가 아니라 '지금'의 함수 — 해가 바뀌면 사람 손 없이 함께 올라간다."""
    for fake_year in (2026, 2031, 2040):
        with _FrozenClock(fake_year):
            for model in _YEAR_MODELS:
                assert _accepts(model, fake_year), f"{model.__name__}: {fake_year}년에 당해 연도가 거부됨"
                assert _accepts(model, fake_year + 1), (
                    f"{model.__name__}: {fake_year}년에 당해+1 이 거부됨 — 비12월 결산·연말 경계 여유가 없다"
                )
                assert not _accepts(model, fake_year + 2), (
                    f"{model.__name__}: {fake_year}년에 당해+2 가 통과됨 — 상한이 사실상 없다"
                )
    return "test_upper_bound_follows_the_clock"


def test_default_year_follows_the_clock() -> str:
    """인자 없이 부른 LLM 이 과거에 고정된 연도를 보지 않는다 — 기본값도 시계를 따라간다."""
    for fake_year in (2026, 2031, 2040):
        with _FrozenClock(fake_year):
            for model in _YEAR_MODELS:
                got = model(corp="삼성전자").year
                assert got == fake_year - 1, (
                    f"{model.__name__}: {fake_year}년 기본값이 {got} — 최근 확정 사업연도가 아니다"
                )
    return "test_default_year_follows_the_clock"


def test_lower_bound_and_nonsense_still_rejected() -> str:
    """상한을 풀었다고 아무 값이나 받지 않는다 — DART 제공 최초 연도 미만·자릿수 오타는 그대로 거부."""
    for model in _YEAR_MODELS:
        assert _accepts(model, schema.MIN_BSNS_YEAR), f"{model.__name__}: 하한 연도가 거부됨"
        assert not _accepts(model, schema.MIN_BSNS_YEAR - 1), f"{model.__name__}: 하한 미만이 통과됨"
        assert not _accepts(model, 99999), f"{model.__name__}: 자릿수 오타(99999)가 통과됨"
    return "test_lower_bound_and_nonsense_still_rejected"


def test_no_year_literal_left_in_source() -> str:
    """소스에 연도 리터럴이 없다 — 다음 해에 조용히 낡을 값을 다시 들이는 것을 막는 가드.

    하한(MIN_BSNS_YEAR)은 시간이 지나도 안 움직이는 업스트림 사실이라 유일한 예외다.
    """
    source = _SCHEMA_SOURCE.read_text(encoding="utf-8")
    lines = [
        line
        for line in source.splitlines()
        if not line.lstrip().startswith("#") and not line.startswith("MIN_BSNS_YEAR")
    ]
    hits = [line.strip() for line in lines if re.search(r"\b(19|20|21)\d{2}\b", line)]
    assert not hits, f"연도 리터럴이 남아 있다 (해가 바뀌면 낡는다): {hits}"
    return "test_no_year_literal_left_in_source"


def _main() -> int:
    tests = [
        test_current_year_is_accepted,
        test_upper_bound_follows_the_clock,
        test_default_year_follows_the_clock,
        test_lower_bound_and_nonsense_still_rejected,
        test_no_year_literal_left_in_source,
    ]
    passed = 0
    for tc in tests:
        name = tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
