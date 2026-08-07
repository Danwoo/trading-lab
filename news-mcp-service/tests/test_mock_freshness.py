"""#269 — mock 기사 발행일이 조회 시점을 따라가는지 검증 (동작 기반 신선도).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_mock_freshness.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식 (#260 의 회귀 가드 — "최근 뉴스" 데모가 영구히 낡던 사고):
- 모든 기사의 published_at 이 '지금' 기준 30일 안이고 미래가 아니다.
- 가장 최근 기사는 7일 안이다 — 뉴스 데모는 "최근"이 살아 있어야 한다.
- 위 두 가지가 시계를 옮겨도 유지된다 — 발행일이 소스에 박힌 상수면 여기서 깨진다.
- 기사 0건은 통과가 아니라 실패다 (fail-closed).

소스의 리터럴 형태는 보지 않는다 — 증상(낡음)만 본다. 렉시컬 보조 그물은 scripts/verify_no_absolute_dates.py.
시각 의존 검증은 픽스처 모듈의 now_kst 를 갈아끼워(조회 시점 호출) 가짜 '지금'으로 돌린다
(선례: disclosure-mcp-service/tests/test_bsns_year_bounds.py).
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import clients.news.news_fixtures as fixtures  # noqa: E402

_KST = ZoneInfo("Asia/Seoul")
WINDOW_DAYS = 30  # 데모 픽스처가 "최근 한 달" 밖으로 낡으면 고장으로 본다
LATEST_MAX_DAYS = 7  # "최근 뉴스" 데모의 최신 기사 상한


class _FrozenClock:
    """픽스처 모듈의 now_kst 를 가짜 '지금'으로 바꾼다 (날짜 치환이 조회 시점이라 교체가 그대로 먹는다)."""

    def __init__(self, fake: datetime.datetime) -> None:
        self._fake = fake
        self._original = getattr(fixtures, "now_kst", None)

    def __enter__(self) -> _FrozenClock:
        assert self._original is not None, (
            "픽스처가 now_kst 를 쓰지 않는다 — 발행일이 시계를 안 본다는 뜻 (절대 날짜로 낡는 구조)"
        )
        fixtures.now_kst = lambda: self._fake
        return self

    def __exit__(self, *exc_info) -> None:
        fixtures.now_kst = self._original


def _published_times() -> list[tuple[str, datetime.datetime]]:
    return [
        (article["article_id"], datetime.datetime.fromisoformat(article["published_at"]))
        for article in fixtures.all_articles()
    ]


def _assert_fresh(records: list[tuple[str, datetime.datetime]], now: datetime.datetime) -> None:
    assert records, "기사 0건 — 아무것도 검사하지 않았다 (픽스처 소실이면 초록이 아니라 빨강이어야 한다)"
    ages = {label: (now - published).days for label, published in records}
    stale = {label: age for label, age in ages.items() if age > WINDOW_DAYS}
    assert not stale, f"{WINDOW_DAYS}일 밖으로 낡은 기사: {stale} — 발행일이 시계를 안 따라간다"
    future = [label for label, published in records if published > now]
    assert not future, f"미래 발행 기사: {future}"
    newest = min(ages.values())
    assert newest <= LATEST_MAX_DAYS, f"가장 최근 기사가 {newest}일 전 — '최근 뉴스' 데모가 낡는다"


def test_articles_fresh_now() -> str:
    """실제 지금 기준 — 절대 발행일 픽스처가 낡아 있던 #260 의 그 자리."""
    records = _published_times()
    _assert_fresh(records, datetime.datetime.now(_KST))
    print(f"  (검사 기사 {len(records)}건)")
    return "test_articles_fresh_now"


def test_freshness_follows_the_clock() -> str:
    """시계를 옮겨도 신선하다 — 오늘만 맞는 절대 날짜를 심으면 여기서 빨개진다."""
    for fake in (
        datetime.datetime(2027, 1, 29, 12, 0, tzinfo=_KST),  # 약 +6개월
        datetime.datetime(2031, 7, 1, 9, 30, tzinfo=_KST),  # 약 +5년
    ):
        with _FrozenClock(fake):
            _assert_fresh(_published_times(), fake)
    return "test_freshness_follows_the_clock"


def _main() -> int:
    tests = [test_articles_fresh_now, test_freshness_follows_the_clock]
    passed = 0
    for tc in tests:
        name = tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
