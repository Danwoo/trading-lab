"""#269 — mock 시세·지수·환율의 기준시각(asof)이 조회 시점을 따라가는지 검증 (동작 기반 신선도).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_mock_freshness.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식 (#260 의 회귀 가드 — "현재가" 스냅샷의 asof 가 영구히 낡던 사고):
- quote·index·fx 모든 응답의 asof 가 '지금' 기준 7일 안이고 미래가 아니다
  (최근 거래일 마감 기준이라 최악이 주말+마감전 며칠 — 7일이면 여유 포함 상한).
- 위가 시계를 옮겨도 유지된다 — asof 가 소스에 박힌 상수면 여기서 깨진다.
- 응답 0건은 통과가 아니라 실패다 (fail-closed).
- **갈래(quote/index/fx)별로도 0건이면 실패다** (#289 — 총량이 남아 있어도 한 갈래가 통째로
  비면 그 갈래를 쓰는 화면·봇은 빈 응답을 받는다). 갈래 목록은 이 파일이 손으로 세는 것이
  아니라 `_asof_times()` 가 실제 호출하는 클라이언트 표면(quote/index/fx)에서 그대로 유도된다
  — 표면이 늘면 `_asof_times()` 의 `surfaces` 튜플에 한 줄 추가하는 것으로 검사도 함께 는다.

소스의 리터럴 형태는 보지 않는다 — 증상(낡음)만 본다. 렉시컬 보조 그물은 scripts/verify_no_absolute_dates.py.
시각 의존 검증은 클라이언트 모듈의 now_kst 를 갈아끼워(조회 시점 호출) 가짜 '지금'으로 돌린다
(선례: disclosure-mcp-service/tests/test_bsns_year_bounds.py).
"""

from __future__ import annotations

import asyncio
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

import clients.market.market_client as client_module  # noqa: E402

_KST = ZoneInfo("Asia/Seoul")
WINDOW_DAYS = 7  # 최근 거래일 마감(asof)의 정당한 최대 지연(주말+마감전 며칠)에 여유를 더한 상한


class _FrozenClock:
    """클라이언트 모듈의 now_kst 를 가짜 '지금'으로 바꾼다 (asof 계산이 조회 시점이라 교체가 그대로 먹는다)."""

    def __init__(self, fake: datetime.datetime) -> None:
        self._fake = fake
        self._original = getattr(client_module, "now_kst", None)

    def __enter__(self) -> _FrozenClock:
        assert self._original is not None, (
            "클라이언트가 now_kst 를 쓰지 않는다 — asof 가 시계를 안 본다는 뜻 (절대 시각으로 낡는 구조)"
        )
        client_module.now_kst = lambda: self._fake
        return self

    def __exit__(self, *exc_info) -> None:
        client_module.now_kst = self._original


def _client() -> client_module.MarketClient:
    return client_module.MarketClient(
        SimpleNamespace(MARKET_API_URL="http://mock.invalid", MARKET_API_KEY="", USE_REAL_API=False)
    )


def _asof_times() -> dict[str, list[tuple[str, datetime.datetime]]]:
    """quote·index·fx 전 픽스처 키를 실제 조회 경로로 읽어 갈래별로 (라벨, asof) 수집."""

    async def _collect() -> dict[str, list[tuple[str, datetime.datetime]]]:
        client = _client()
        surfaces = [
            ("quote", client.quote, sorted(client_module._MOCK_QUOTES)),
            ("index", client.index, sorted(client_module._MOCK_INDEX)),
            ("fx", client.fx, sorted(client_module._MOCK_FX)),
        ]
        by_surface: dict[str, list[tuple[str, datetime.datetime]]] = {name: [] for name, _, _ in surfaces}
        for surface, call, keys in surfaces:
            for key in keys:
                for row in (await call(key))["items"]:
                    by_surface[surface].append((f"{surface} {key}", datetime.datetime.fromisoformat(row["asof"])))
        return by_surface

    return asyncio.run(_collect())


def _assert_fresh(by_surface: dict[str, list[tuple[str, datetime.datetime]]], now: datetime.datetime) -> None:
    records = [record for rows in by_surface.values() for record in rows]
    assert records, "응답 0건 — 아무것도 검사하지 않았다 (픽스처 소실이면 초록이 아니라 빨강이어야 한다)"
    empty_surfaces = sorted(name for name, rows in by_surface.items() if not rows)
    assert not empty_surfaces, (
        f"0건 갈래: {empty_surfaces} — 총량은 남아 있어도 이 갈래를 쓰는 화면·봇은 빈 응답을 받는다 (#289)"
    )
    stale = {label: (now - asof).days for label, asof in records if (now - asof).days > WINDOW_DAYS}
    assert not stale, f"기준시각이 {WINDOW_DAYS}일 밖으로 낡음: {stale} — asof 가 시계를 안 따라간다"
    future = [label for label, asof in records if asof > now]
    assert not future, f"미래 기준시각: {future}"


def test_asof_fresh_now() -> str:
    """실제 지금 기준 — 절대 asof 픽스처가 낡아 있던 #260 의 그 자리."""
    by_surface = _asof_times()
    _assert_fresh(by_surface, datetime.datetime.now(_KST))
    print(f"  (검사 응답 {sum(len(rows) for rows in by_surface.values())}건, 갈래 {sorted(by_surface)})")
    return "test_asof_fresh_now"


def test_freshness_follows_the_clock() -> str:
    """시계를 옮겨도 신선하다 — 주중·주말 아침(마감 전) 포함, 어떤 '지금'에서도 최근 거래일 마감이어야 한다."""
    for fake in (
        datetime.datetime(2027, 1, 29, 12, 0, tzinfo=_KST),  # 약 +6개월 (금요일 장중)
        datetime.datetime(2028, 2, 14, 8, 30, tzinfo=_KST),  # 월요일 개장 전 — 지연 최악 케이스
        datetime.datetime(2031, 7, 1, 9, 30, tzinfo=_KST),  # 약 +5년
    ):
        with _FrozenClock(fake):
            _assert_fresh(_asof_times(), fake)
    return "test_freshness_follows_the_clock"


def _main() -> int:
    tests = [test_asof_fresh_now, test_freshness_follows_the_clock]
    passed = 0
    for tc in tests:
        name = tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
