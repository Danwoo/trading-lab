"""#235 — mock 픽스처가 스키마 기본값과 같은 사업연도를 덮는지(= 인자 없이 불러도 0건이 아닌지) 검증.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_mock_fixture_freshness.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식:
- 인자 없이(스키마 기본값) 부른 재무·배당이 수록 발행사 전부에서 0건이 아니다.
- 시계를 옮겨도 같다 — 픽스처의 사업연도가 상수가 아니라 '지금'의 함수다 (매년 사람이 올릴 필요 없음).
- 픽스처가 붙이는 연도 라벨이 스키마 기본값과 일치한다 (라벨만 다른 해를 가리키는 조용한 어긋남 차단).
- 재무·배당·지분 행의 인용 근거(rcept_no)가 공시 목록에 실제로 존재한다 (인용이 떠도는 번호가 아님).
- 소스에 연도·접수일 리터럴이 남아 있지 않다 — 다음 해에 조용히 낡는 값을 다시 들이지 않기 위한 가드.

시각 의존 검증은 로드된 모듈들의 now_kst 를 갈아끼워(호출 시점 계산이라 교체가 그대로 먹는다) 가짜 '오늘'로 돌린다.
"""

from __future__ import annotations

import asyncio
import datetime
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

# import 체인이 Settings() 를 인스턴스화 — env 없는 실행(CI 등)에서 JWT_SECRET fail-fast 우회
os.environ.setdefault("JWT_SECRET", "test-freshness-secret")

import clients.disclosure.mock_fixtures as fixtures  # noqa: E402
import schemas.disclosure.disclosure_schema as schema  # noqa: E402
from clients.disclosure.disclosure_client import DisclosureClient  # noqa: E402

_KST = ZoneInfo("Asia/Seoul")
_FIXTURE_SOURCE = _APP_DIR / "clients" / "disclosure" / "mock_fixtures.py"
_FAKE_YEARS = (2027, 2031, 2040)
_CORPS = [c["corp_name"] for c in fixtures.MOCK_COMPANIES]

# mock 전용 클라이언트 — USE_REAL_API=False 라 DART 를 부르지 않는다(네트워크 없음).
_MOCK_CONFIG = SimpleNamespace(
    DISCLOSURE_API_BASE_URL="https://opendart.fss.or.kr/api", DISCLOSURE_API_KEY="", USE_REAL_API=False
)


class _FrozenClock:
    """now_kst 를 쓰는 모든 모듈을 가짜 '오늘'로 바꾼다 (호출 시점 계산이라 교체가 그대로 먹는다)."""

    def __init__(self, year: int, month: int = 7, day: int = 1) -> None:
        self._fake = datetime.datetime(year, month, day, tzinfo=_KST)
        self._originals: dict[str, object] = {}

    def __enter__(self) -> _FrozenClock:
        for name, module in list(sys.modules.items()):
            if module is not None and callable(getattr(module, "now_kst", None)):
                self._originals[name] = module.now_kst
                module.now_kst = lambda _f=self._fake: _f
        assert self._originals, "now_kst 를 쓰는 모듈이 없다 — 픽스처·스키마가 시계를 안 본다는 뜻"
        return self

    def __exit__(self, *exc_info) -> None:
        for name, original in self._originals.items():
            sys.modules[name].now_kst = original


def _rows(coro) -> list[dict]:
    return asyncio.run(coro)["data"]


def _financials(corp: str) -> list[dict]:
    """인자 없이 부른 재무 — 사업연도·보고서·연결 구분은 전부 스키마 기본값."""
    params = schema.FinancialsIn(corp=corp)
    client = DisclosureClient(_MOCK_CONFIG)
    return _rows(
        client.get_financials(
            corp=params.corp, year=params.year, report_code=params.report_code, fs_type=params.fs_type
        )
    )


def _dividend(corp: str) -> list[dict]:
    params = schema.DividendIn(corp=corp)
    return _rows(DisclosureClient(_MOCK_CONFIG).get_dividend(corp=params.corp, year=params.year))


def test_default_call_is_not_empty() -> str:
    """실제 오늘 기준 — 기본 사업연도가 전년도로 바뀌자 mock 이 0건이 됐던(#235) 그 자리."""
    for corp in _CORPS:
        assert _financials(corp), f"{corp}: 인자 없는 재무 조회가 0건 — 픽스처가 기본 사업연도를 못 덮는다"
        assert _dividend(corp), f"{corp}: 인자 없는 배당 조회가 0건 — 픽스처가 기본 사업연도를 못 덮는다"
    return "test_default_call_is_not_empty"


def test_default_call_follows_the_clock() -> str:
    """픽스처의 사업연도가 상수가 아니라 '지금'의 함수 — 해가 바뀌어도 사람 손 없이 따라 움직인다."""
    for fake_year in _FAKE_YEARS:
        with _FrozenClock(fake_year):
            for corp in _CORPS:
                assert _financials(corp), f"{fake_year}년 {corp}: 인자 없는 재무 조회가 0건 — 픽스처가 낡았다"
                assert _dividend(corp), f"{fake_year}년 {corp}: 인자 없는 배당 조회가 0건 — 픽스처가 낡았다"
    return "test_default_call_follows_the_clock"


def test_year_label_matches_schema_default() -> str:
    """픽스처가 붙이는 연도 라벨이 스키마 기본값과 같다 — 건수만 맞고 다른 해를 가리키는 어긋남 차단."""
    for fake_year in (None, *_FAKE_YEARS):
        clock = _FrozenClock(fake_year) if fake_year else None
        if clock:
            clock.__enter__()
        try:
            expected = schema.FinancialsIn(corp=_CORPS[0]).year
            for corp in _CORPS:
                report_nm = _financials(corp)[0]["report_nm"]
                assert f"({expected}.12)" in report_nm, (
                    f"{corp}: 재무 출처가 {report_nm} — 기본 사업연도({expected}) 아님"
                )
                bsns_year = _dividend(corp)[0]["bsns_year"]
                assert bsns_year == str(expected), f"{corp}: 배당 사업연도가 {bsns_year} — 기본값({expected}) 아님"
        finally:
            if clock:
                clock.__exit__()
    return "test_year_label_matches_schema_default"


def test_citation_rcept_no_exists_in_filings() -> str:
    """재무·배당·지분 행이 근거로 다는 접수번호가 공시 목록에 실제로 있다 — 떠도는 인용 번호 차단."""
    for fake_year in (None, *_FAKE_YEARS):
        clock = _FrozenClock(fake_year) if fake_year else None
        if clock:
            clock.__enter__()
        try:
            known = {f["rcept_no"] for f in fixtures.mock_filings()}
            client = DisclosureClient(_MOCK_CONFIG)
            for corp in _CORPS:
                for row in _financials(corp) + _dividend(corp) + _rows(client.get_major_shareholder(corp=corp)):
                    rcept_no = row["rcept_no"]
                    assert rcept_no in known, f"{corp}: 인용 접수번호 {rcept_no} 가 공시 목록에 없다"
                    assert _rows(client.get_disclosure_detail(rcept_no=rcept_no)), (
                        f"{corp}: 접수번호 {rcept_no} 로 공시 상세가 0건 — 인용을 따라갈 수 없다"
                    )
        finally:
            if clock:
                clock.__exit__()
    return "test_citation_rcept_no_exists_in_filings"


def test_no_year_literal_left_in_source() -> str:
    """소스에 연도·접수일 리터럴이 없다 — 다음 해에 조용히 낡을 값을 다시 들이는 것을 막는 가드.

    잡는 것은 두 형태다: 맨 4자리 20xx 연도, 그리고 20/21 로 시작하는 8자리 접수일(YYYYMMDD) 문자열.
    설립일(est_dt) 처럼 19xx 로 시작하는 과거 사실은 시간이 지나도 안 움직이므로 대상이 아니다.
    """
    lines = [
        line for line in _FIXTURE_SOURCE.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")
    ]
    hits = [line.strip() for line in lines if re.search(r"\b20\d{2}\b|[\"'](?:20|21)\d{6}", line)]
    assert not hits, f"연도·접수일 리터럴이 남아 있다 (해가 바뀌면 낡는다): {hits}"
    return "test_no_year_literal_left_in_source"


def _main() -> int:
    tests = [
        test_default_call_is_not_empty,
        test_default_call_follows_the_clock,
        test_year_label_matches_schema_default,
        test_citation_rcept_no_exists_in_filings,
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
