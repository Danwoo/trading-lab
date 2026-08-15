"""#2 — 시세 계층의 계약 불변식 검증 (키 0개 상태에서 도는 것).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행형으로 작성한다:
    cd backend-service && uv run python tests/test_market_data_contract.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식:
- **키가 없어도 어댑터가 만들어지고**, 못 하는 것이 `available=False` + 사유로 나온다 (FR-013·FR-021).
  키 없음이 예외로 기동을 막으면 "키 0개로 전 서비스가 기동된다"가 깨진다.
- **capability 사유에 다음 행동이 실린다** — "키가 없다"만으로는 리드가 무엇을 해야 할지 모른다.
- **캔들 조회는 provider 를 주입받지 않는다** (MD-AD-19). 생성자 시그니처로 확인한다.
- **없는 것은 빈 배열이 아니라 사유와 함께 빈 배열**이다 — 0건이 "거래가 없었다"인지 "소스가
  없다"인지 응답이 스스로 말한다.
- **`limit` 상한 초과는 조용히 잘리지 않고 400** — 잘린 캔들로 그린 차트는 틀린 차트다.
- **5분봉 합성은 정각 버킷**이고 1분봉을 직접 접은 값과 일치한다 (MD-AD-26 + NFR-006).
- **응답 내 중복 캔들 병합 규칙**(MD-AD-24)이 open=first·high=max·low=min·close=last·volume=max.
- **scope 형식 오류는 0건 적재 성공이 아니라 거절**이다.

외부 의존(DB·소스 HTTP)은 대역으로 두고 계약만 돌린다 — 이 파일은 네트워크·DB 없이 돈다.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from decimal import Decimal
from pathlib import Path

os.environ["APP_ENV"] = "market-contract-test"
for key, value in {
    "BACKEND_SQL_DB_DRIVER": "postgresql+psycopg",
    "BACKEND_SQL_DB_HOST": "localhost",
    "BACKEND_SQL_DB_PORT": "5432",
    "BACKEND_SQL_DB_NAME": "test",
    "BACKEND_SQL_DB_USER": "test",
    "BACKEND_SQL_DB_PASSWORD": "test",
    "SFTP_HOST": "localhost",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "test",
    "SFTP_PASSWORD": "test",
    "JWT_SECRET": "test-secret",
}.items():
    os.environ.setdefault(key, value)

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import inspect  # noqa: E402

from core.config import settings  # noqa: E402
from core.exceptions import BadRequestError  # noqa: E402
from providers import get_provider, list_sources  # noqa: E402
from providers.merge import merge_duplicate_bars  # noqa: E402
from providers.models import NormalizedBar  # noqa: E402
from services.bar.bar_service import MAX_BARS, BarService, synthesize_bars  # noqa: E402
from services.capability.capability_service import CapabilityService  # noqa: E402
from services.data_key.data_key_service import DataKeyService  # noqa: E402
from services.ingest.ingest_service import parse_scope  # noqa: E402

# 키가 있어야만 열리는 소스 — 이 목록이 비면 "키 없음" 축을 아무것도 검사하지 않은 것이므로
# 아래 테스트가 fail-closed 로 실패한다.
KEY_REQUIRED_SOURCES = ("data_go_kr", "alpaca")


class _StubBarRepository:
    """DB 대역 — 실 SQL 은 스크래치 DB 검증(PR 본문)에서 돌린다. 여기서는 서비스 로직만 본다."""

    def __init__(self, instrument: dict | None = None, daily: list[dict] | None = None, minute=None):
        self.instrument = instrument
        self.daily = daily or []
        self.minute = minute or []

    def select_instrument(self, args):
        return self.instrument

    def select_daily_bar_list(self, args):
        return self.daily[: args["limit"]], len(self.daily)

    def select_minute_bar_list(self, args):
        return self.minute[: args["limit"]], len(self.minute)

    def select_traded_dates(self, args):
        return []


def _bar_service(daily=None, minute=None, instrument=None) -> BarService:
    return BarService(
        bar_repository=_StubBarRepository(instrument=instrument, daily=daily, minute=minute),
        capability_service=CapabilityService(data_key_service=DataKeyService(config=settings)),
    )


def test_key_required_sources_build_without_key_and_explain_why() -> str:
    """키가 없어도 어댑터는 만들어지고, 못 하는 것이 사유와 함께 나온다 (FR-013)."""
    registered = list_sources()
    checked = [source for source in KEY_REQUIRED_SOURCES if source in registered]
    assert checked, f"키 필요 소스를 0건 검사했다 — 레지스트리: {registered} (fail-closed)"

    for source in checked:
        provider = get_provider(source, None)  # 예외가 나면 기동이 막힌다는 뜻이다
        caps = provider.capabilities()
        assert caps, f"{source} 의 capability 표가 비었다"
        assert not any(cap.available for cap in caps), f"{source} 가 키 없이 available=True 를 냈다"
        assert all(cap.reason for cap in caps if not cap.available), f"{source} 에 사유 없는 available=False 가 있다"
    return f"test_key_required_sources_build_without_key_and_explain_why (소스 {len(checked)}개)"


def test_capability_reason_carries_next_action() -> str:
    """사유에 "어디서 받아 어디에 넣는지"가 실린다 — 사유가 다음 행동을 담지 않으면 반쪽이다."""
    service = CapabilityService(data_key_service=DataKeyService(config=settings))
    rows = service.list_capabilities(workspace_id=1)
    assert rows, "capability 행을 0건 수집했다 (fail-closed)"

    key_rows = [row for row in rows if row["source"] in KEY_REQUIRED_SOURCES and not row["available"]]
    assert key_rows, "키 필요 소스의 available=False 행이 0건이다 (fail-closed)"
    with_hint = [row for row in key_rows if row["reason"] and "발급 경로" in row["reason"]]
    assert with_hint, f"발급 경로가 실린 사유가 없다: {key_rows[0]['reason']!r}"
    return f"test_capability_reason_carries_next_action (행 {len(rows)}개 중 키 사유 {len(key_rows)}개)"


def test_bar_service_is_not_wired_to_any_provider() -> str:
    """차트가 소스를 직접 부를 통로가 생성자에 없다 (MD-AD-19)."""
    params = set(inspect.signature(BarService.__init__).parameters) - {"self"}
    assert params == {"bar_repository", "capability_service"}, f"BarService 주입 인자가 바뀌었다: {params}"
    source = inspect.getsource(BarService)
    assert "get_provider" not in source, "BarService 가 provider 레지스트리를 직접 부른다"
    return "test_bar_service_is_not_wired_to_any_provider"


def test_empty_response_carries_reason_not_bare_zero() -> str:
    """소스가 없는 시장은 404 도 조용한 0건도 아니고, 200 + 사유다 (FR-021)."""
    service = _bar_service()
    out = service.select_daily_bar_list(
        {
            "market": "KOSPI",
            "symbol": "005930",
            "date_from": dt.date(2026, 1, 2),
            "date_to": dt.date(2026, 1, 31),
            "limit": None,
            "workspace_id": 1,
        }
    )
    assert out["items"] == [] and out["total_count"] == 0
    assert out["unavailable_reason"], "빈 응답에 사유가 없다"
    assert "키" in out["unavailable_reason"], (
        f"국내 일봉이 비어 있는 사유가 키 얘기가 아니다: {out['unavailable_reason']}"
    )
    # 사유가 「키가 아직 없다」뿐이면 코드도 함께 온다 — 화면은 이 코드로만 임시 데이터를 그린다
    # (문구로 가르면 문구만 바뀌어도 조용히 갈린다). 코드를 흘리면 화면은 영영 빈 채로 남는다.
    assert out["unavailable_code"] == "credential_missing", (
        f"사유는 키 얘기인데 코드가 {out['unavailable_code']!r} 다"
    )

    minute = _bar_service().select_minute_bar_list(
        {
            "market": "KOSPI",
            "symbol": "005930",
            "ts_from": dt.datetime(2026, 1, 2, 9, 0),
            "ts_to": dt.datetime(2026, 1, 2, 15, 30),
            "interval_min": 1,
            "limit": None,
            "workspace_id": 1,
        }
    )
    assert minute["unavailable_code"] == "credential_missing", (
        f"분봉 쪽만 코드를 흘린다: {minute['unavailable_code']!r}"
    )
    return "test_empty_response_carries_reason_not_bare_zero"


def test_every_bar_exit_carries_both_fields() -> str:
    """사유를 싣는 자리마다 코드가 같이 실린다 — 한쪽만 실은 출구가 하나라도 있으면 실패다.

    실측으로 잡힌 구멍이다: 종목 마스터가 비어 있는 갈래가 사유만 싣고 코드를 흘려, 화면이
    「키가 아직 없다」를 알 방법이 없어 빈 채로 남았다.
    """
    source = inspect.getsource(BarService)
    reasons = source.count('"unavailable_reason"')
    codes = source.count('"unavailable_code"')
    assert reasons > 0, "사유를 싣는 자리를 하나도 못 찾았다 (그물이 죽어 있다)"
    assert reasons == codes, f"사유 {reasons}자리 · 코드 {codes}자리 — 짝이 안 맞는다"

    # 코드를 안 주면 조용히 None 이 되는 기본값이 없어야 새 호출자가 같은 실수를 못 한다.
    code_param = inspect.signature(BarService._empty).parameters["code"]
    assert code_param.default is inspect.Parameter.empty, "_empty(code=) 에 기본값이 생겼다"
    return f"test_every_bar_exit_carries_both_fields (사유·코드 각 {reasons}자리)"


def test_limit_over_cap_is_rejected_not_truncated() -> str:
    service = _bar_service(instrument={"instrument_id": 1})
    try:
        service.select_daily_bar_list(
            {
                "market": "NASDAQ",
                "symbol": "AAPL",
                "date_from": dt.date(2026, 1, 2),
                "date_to": dt.date(2026, 1, 31),
                "limit": MAX_BARS + 1,
                "workspace_id": 1,
            }
        )
    except BadRequestError:
        return "test_limit_over_cap_is_rejected_not_truncated"
    raise AssertionError("상한을 넘는 limit 이 조용히 통과했다 — 잘린 캔들로 그린 차트는 틀린 차트다")


def test_five_minute_synthesis_matches_manual_fold() -> str:
    """5분봉 합성이 같은 구간 1분봉을 손으로 접은 값과 일치하고, 버킷 경계가 정각이다."""
    minute_bars = [
        {"time": "2026-08-06T09:31", "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 100},
        {"time": "2026-08-06T09:32", "open": 11.0, "high": 15.0, "low": 10.5, "close": 14.0, "volume": 200},
        {"time": "2026-08-06T09:34", "open": 14.0, "high": 14.5, "low": 8.0, "close": 9.5, "volume": 50},
        {"time": "2026-08-06T09:35", "open": 9.5, "high": 10.0, "low": 9.4, "close": 9.8, "volume": 70},
    ]
    out = synthesize_bars(minute_bars, 5)
    assert [row["time"] for row in out] == ["2026-08-06T09:30", "2026-08-06T09:35"], [r["time"] for r in out]
    first = out[0]
    assert first["open"] == 10.0, first  # first
    assert first["high"] == 15.0, first  # max
    assert first["low"] == 8.0, first  # min
    assert first["close"] == 9.5, first  # last
    assert first["volume"] == 350, first  # sum — 겹치지 않는 별개 거래다
    return "test_five_minute_synthesis_matches_manual_fold"


def test_duplicate_bars_in_one_response_merge_by_rule() -> str:
    """MD-AD-24 — 같은 타임스탬프가 두 번 온 응답이 결정론적으로 한 행이 된다."""
    ts = dt.datetime(2026, 8, 6, 0, 0)
    bars = [
        NormalizedBar(
            symbol="AAPL",
            market="NASDAQ",
            ts=ts,
            open=Decimal(10),
            high=Decimal(12),
            low=Decimal(9),
            close=Decimal(11),
            volume=100,
            adj_policy="raw",
        ),
        NormalizedBar(
            symbol="AAPL",
            market="NASDAQ",
            ts=ts,
            open=Decimal(99),
            high=Decimal(15),
            low=Decimal(8),
            close=Decimal(14),
            volume=80,
            adj_policy="raw",
        ),
    ]
    merged = merge_duplicate_bars(bars, source="test")
    assert len(merged) == 1, merged
    row = merged[0]
    assert row.open == Decimal(10), "open 은 first 여야 한다 (뒤 행의 99 가 이기면 안 된다)"
    assert row.high == Decimal(15) and row.low == Decimal(8)
    assert row.close == Decimal(14), "close 는 last"
    assert row.volume == 100, "volume 은 max — 합계(180)가 아니다"
    return "test_duplicate_bars_in_one_response_merge_by_rule"


def test_malformed_scope_is_rejected_not_silently_empty() -> str:
    """scope 오타가 "0건 적재 성공"으로 끝나면 아무도 눈치채지 못한다."""
    assert parse_scope("instrument_master", "nasdaq") == ("NASDAQ", [])
    assert parse_scope("daily_bar", "nasdaq:aapl, msft") == ("NASDAQ", ["AAPL", "MSFT"])
    for job_kind, scope in [("daily_bar", ""), ("daily_bar", "  "), ("instrument_master", "NASDAQ:AAPL")]:
        try:
            parse_scope(job_kind, scope)
        except BadRequestError:
            continue
        raise AssertionError(f"형식이 어긋난 scope 가 통과했다: {job_kind} {scope!r}")
    return "test_malformed_scope_is_rejected_not_silently_empty"


TESTS = [
    test_key_required_sources_build_without_key_and_explain_why,
    test_capability_reason_carries_next_action,
    test_bar_service_is_not_wired_to_any_provider,
    test_empty_response_carries_reason_not_bare_zero,
    test_every_bar_exit_carries_both_fields,
    test_limit_over_cap_is_rejected_not_truncated,
    test_five_minute_synthesis_matches_manual_fold,
    test_duplicate_bars_in_one_response_merge_by_rule,
    test_malformed_scope_is_rejected_not_silently_empty,
]


def _unregistered_tests() -> list[str]:
    """`TESTS` 는 손으로 적는 목록이라, 새 테스트를 안 적으면 **조용히 안 돈다** (실측으로 겪었다).

    등록을 잊은 것 자체를 실패로 만든다 — 목록이 모듈의 `test_*` 를 전부 덮어야 한다.
    """
    registered = {test.__name__ for test in TESTS}
    defined = {name for name, value in globals().items() if name.startswith("test_") and callable(value)}
    return sorted(defined - registered)


if __name__ == "__main__":
    missing = _unregistered_tests()
    if missing:
        print(f"  FAIL TESTS 목록에 없는 테스트: {', '.join(missing)}")
        sys.exit(1)
    failures = 0
    for test in TESTS:
        try:
            print(f"  PASS {test()}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {test.__name__}: {exc}")
    print(f"\n검사한 케이스 {len(TESTS)}개 중 {len(TESTS) - failures}개 통과, {failures}개 실패")
    sys.exit(1 if failures else 0)
