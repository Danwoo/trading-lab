"""운영 규약 C절 — **주문 계열 호출이 코드 레벨에서 막히는지** (네트워크 없음).

실계좌 자격증명으로 주문 API 를 호출하지 않는다 — 예외 없다. 이 그물이 잠그는 것:

  ① 기본 상태(변수 없음)에서 주문 경로가 예외로 막힌다
  ② "true" 가 아닌 어떤 값("True"·"1"·"yes")도 열지 못한다 — 정확 일치만
  ③ 계좌 조회는 명시 플래그 없이 막힌다 (C절 — 리드가 요청한 세션에서만)
  ④ 조회 경로는 가드를 그냥 지난다
  ⑤ 가드가 클라이언트의 유일한 관문(request)에 실제로 배선돼 있다
  ⑥ 자격증명·토큰이 예외 문구에 실리지 않는다
  ⑦ 경로 문자열(`..`·`//`·쿼리)로 가드를 돌아가지 못한다 — 정규화 후 판정

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_toss_order_guard.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# 설정을 세우고 나서 import 한다 — client 가 redaction → core.config 를 물고 들어온다.
# `test_data_source_key_leak.py` 와 같은 관용구다. 값은 쓰이지 않고 존재만 필요하다.
os.environ["APP_ENV"] = "toss-guard-test"
for _name, _value in {
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
    os.environ.setdefault(_name, _value)

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from providers.toss.client import TossClient  # noqa: E402
from providers.toss.live_guard import (  # noqa: E402
    AccountReadBlocked,
    TradingLiveDisabled,
    assert_path_allowed,
)

FAILURES: list[str] = []
CHECKED = 0

SECRET = "toss-secret-CANARY-000"


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def blocked(path: str, **kwargs) -> str | None:
    """가드가 막으면 예외 클래스 이름, 통과하면 None."""
    try:
        assert_path_allowed(path, **kwargs)
        return None
    except (TradingLiveDisabled, AccountReadBlocked) as exc:
        return type(exc).__name__


def main() -> int:
    os.environ.pop("TRADING_LIVE_ENABLED", None)

    # ── ① 기본은 닫힘 ────────────────────────────────────────────────────
    check("주문 — 변수 없음", blocked("/api/v1/orders"), "TradingLiveDisabled")
    check("조건주문 — 변수 없음", blocked("/api/v1/conditional-orders/123"), "TradingLiveDisabled")

    # ── ② 정확 일치만 연다 ───────────────────────────────────────────────
    for value in ("false", "True", "TRUE", "1", "yes", " true", ""):
        os.environ["TRADING_LIVE_ENABLED"] = value
        check(f"주문 — {value!r} 는 못 연다", blocked("/api/v1/orders"), "TradingLiveDisabled")
    os.environ["TRADING_LIVE_ENABLED"] = "true"
    check("주문 — 정확히 true 만 연다", blocked("/api/v1/orders"), None)
    os.environ.pop("TRADING_LIVE_ENABLED", None)

    # ── ③ 계좌는 명시 플래그 ─────────────────────────────────────────────
    check("계좌 — 기본 차단", blocked("/api/v1/accounts/me"), "AccountReadBlocked")
    check("계좌 — 명시 플래그로만", blocked("/api/v1/accounts/me", allow_account_read=True), None)

    # ── ④ 조회는 지나간다 ────────────────────────────────────────────────
    for path in ("/api/v1/candles", "/api/v1/prices", "/api/v1/stocks/all", "/api/v1/market-calendar/KR"):
        check(f"조회 통과 — {path}", blocked(path), None)

    # ── ⑤ 관문 배선 — request() 가 네트워크 전에 가드에서 막힌다 ─────────
    client = TossClient(f"client-id-x:{SECRET}")
    try:
        asyncio.run(client.request("/api/v1/orders", {}))
        check("request 가 가드를 태운다", "통과됨", "TradingLiveDisabled")
    except TradingLiveDisabled as exc:
        check("request 가 가드를 태운다", True, True)
        check("⑥ 예외에 시크릿이 없다", SECRET in str(exc), False)
    except Exception as exc:  # noqa: BLE001 — 네트워크 예외가 나면 가드보다 늦게 막힌 것이다
        check("request 가 가드를 태운다", type(exc).__name__, "TradingLiveDisabled")

    # 경로 문자열로 가드를 우회하려는 시도 — httpx 는 보내기 직전에 dot-segment 를 접는다.
    # 접기 전 문자열로 판정하면 아래가 전부 주문으로 나간다.
    for sneaky in (
        "/api/v1/candles/../orders",
        "/api/v1/./orders",
        "/api/v1//orders",
        "/api/v1/a/b/../../orders",
        "/api/v1/orders?symbol=005930",
        "/api/v1/candles/../conditional-orders",
    ):
        try:
            assert_path_allowed(sneaky)
            check(f"우회 차단: {sneaky}", "통과함", "차단")
        except TradingLiveDisabled:
            check(f"우회 차단: {sneaky}", "차단", "차단")

    # 정상 조회 경로는 정규화 뒤에도 그대로 지난다
    for benign in ("/api/v1/candles", "/api/v1/stocks/all", "/api/v1/prices?symbols=005930"):
        try:
            assert_path_allowed(benign)
            check(f"조회는 지난다: {benign}", "통과", "통과")
        except Exception as exc:  # noqa: BLE001
            check(f"조회는 지난다: {benign}", type(exc).__name__, "통과")

    # 가드 우회 경로가 없는지 — 클라이언트에 request 밖의 공개 HTTP 진입점이 없다
    public = [n for n in dir(client) if not n.startswith("_") and callable(getattr(client, n))]
    check("공개 진입점이 관문 셋뿐이다", sorted(public), ["candles", "request", "stocks_all"])

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 15:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 주문은 코드 레벨에서 막히고, true 정확 일치만 연다 (운영 규약 C절)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
