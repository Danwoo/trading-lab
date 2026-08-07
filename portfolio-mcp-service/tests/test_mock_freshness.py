"""#269 — mock 거래·주문 날짜가 조회 시점을 따라가는지 검증 (동작 기반 신선도).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_mock_freshness.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식 (#260 의 회귀 가드 — 절대 날짜 픽스처가 조회창 밖으로 빠져 주간 리포트가 0건이 되던 사고):
- 모든 거래(trade_date)·주문(placed_at)이 '지금' 기준 조회창(30일) 안이고 미래가 아니다.
- 가장 최근 레코드는 7일 안이다 — 주간 활동 리포트 데모가 항상 볼 것이 있어야 한다.
- 위 두 가지가 시계를 옮겨도 유지된다 — 날짜가 소스에 박힌 상수면 여기서 깨진다.
- 레코드 0건은 통과가 아니라 실패다 (fail-closed — 검사 대상이 사라지면 초록이 아니라 빨강).

소스의 리터럴 형태는 보지 않는다 — 증상(낡음)만 본다. 렉시컬 보조 그물은 scripts/verify_no_absolute_dates.py.
시각 의존 검증은 클라이언트 모듈의 now_kst 를 갈아끼워(조회 시점 호출) 가짜 '지금'으로 돌린다
(선례: disclosure-mcp-service/tests/test_bsns_year_bounds.py).
"""

from __future__ import annotations

import datetime
import os
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

import clients.portfolio.portfolio_client as client_module  # noqa: E402

_KST = ZoneInfo("Asia/Seoul")
WINDOW_DAYS = 30  # 거래·주문 조회 기본창 (schemas: "미지정 시 최근 30일")
LATEST_MAX_DAYS = 7  # 주간 활동 리포트가 빈손이 되지 않는 상한


class _FrozenClock:
    """클라이언트 모듈의 now_kst 를 가짜 '지금'으로 바꾼다 (날짜 치환이 조회 시점이라 교체가 그대로 먹는다)."""

    def __init__(self, fake: datetime.datetime) -> None:
        self._fake = fake
        self._original = getattr(client_module, "now_kst", None)

    def __enter__(self) -> _FrozenClock:
        assert self._original is not None, (
            "클라이언트가 now_kst 를 쓰지 않는다 — 픽스처 날짜가 시계를 안 본다는 뜻 (절대 날짜로 낡는 구조)"
        )
        client_module.now_kst = lambda: self._fake
        return self

    def __exit__(self, *exc_info) -> None:
        client_module.now_kst = self._original


def _client() -> client_module.PortfolioClient:
    return client_module.PortfolioClient(SimpleNamespace(USE_REAL_API=False))


def _dated_records(client: client_module.PortfolioClient) -> list[tuple[str, datetime.date]]:
    """전 계좌의 (라벨, 날짜) 목록 — 거래는 trade_date, 주문은 placed_at."""
    records: list[tuple[str, datetime.date]] = []
    for account in client.mock_accounts():
        account_id = account["account_id"]
        for tx in client.mock_transactions(account_id):
            records.append((f"{account_id} 거래 {tx['tx_type']}", datetime.date.fromisoformat(tx["trade_date"])))
        for order in client.mock_orders(account_id):
            records.append((f"{account_id} 주문 {order['order_id']}", datetime.date.fromisoformat(order["placed_at"])))
    return records


def _assert_fresh(records: list[tuple[str, datetime.date]], today: datetime.date) -> None:
    assert records, "레코드 0건 — 아무것도 검사하지 않았다 (픽스처 소실이면 초록이 아니라 빨강이어야 한다)"
    stale = [(label, (today - day).days) for label, day in records if (today - day).days > WINDOW_DAYS]
    assert not stale, f"조회창({WINDOW_DAYS}일) 밖으로 낡은 레코드: {stale} — 날짜가 시계를 안 따라간다"
    future = [(label, day.isoformat()) for label, day in records if day > today]
    assert not future, f"미래 날짜 레코드: {future}"
    newest = min(today.toordinal() - day.toordinal() for _, day in records)
    assert newest <= LATEST_MAX_DAYS, (
        f"가장 최근 레코드가 {newest}일 전 — 주간 리포트({LATEST_MAX_DAYS}일 창)가 빈손이 된다"
    )


def test_records_fresh_now() -> str:
    """실제 오늘 기준 — 절대 날짜 픽스처가 30일 창 밖으로 빠져 조회가 0건이 되던 #260 의 그 자리."""
    records = _dated_records(_client())
    _assert_fresh(records, datetime.datetime.now(_KST).date())
    print(f"  (검사 레코드 {len(records)}건)")
    return "test_records_fresh_now"


def test_freshness_follows_the_clock() -> str:
    """시계를 옮겨도 신선하다 — 오늘만 맞는 절대 날짜를 심으면 여기서 빨개진다."""
    for fake in (
        datetime.datetime(2027, 1, 29, 12, 0, tzinfo=_KST),  # 약 +6개월
        datetime.datetime(2031, 7, 1, 9, 30, tzinfo=_KST),  # 약 +5년
    ):
        with _FrozenClock(fake):
            _assert_fresh(_dated_records(_client()), fake.date())
    return "test_freshness_follows_the_clock"


def _main() -> int:
    tests = [test_records_fresh_now, test_freshness_follows_the_clock]
    passed = 0
    for tc in tests:
        name = tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
