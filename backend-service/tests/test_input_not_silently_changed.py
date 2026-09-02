"""#434 — 돈이 지나가는 입력이 조용히 바뀌거나 검증 없이 통과하지 않는지.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행형으로 쓴다:
    uv run python tests/test_input_not_silently_changed.py

저장 컬럼은 `avg_price`·`target_price` = Numeric(18,2), `weight` = Numeric(6,2),
`quantity` = integer 다. 스키마가 막지 않으면 두 방향으로 샌다:

  (1) **조용히 바뀐다** — 셋째 자리 아래가 저장 시 반올림돼 사용자가 넣은 값이 아닌 것이
      보드에 남는다. 아무도 안 알려준다.
  (2) **검증 없이 통과한다** — 음수 수량·컬럼 상한 초과가 스키마를 지나 DB 에서 터진다.
      사용자가 받는 것은 「무엇이 왜 잘못됐다」가 아니라 500 이다.

둘 다 「보드를 믿는다」를 깨므로 스키마 층에서 **거부하고 사유를 말한다.**
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from pydantic import ValidationError  # noqa: E402
from schemas.bot.bot_schema import BotStrategyIn  # noqa: E402
from schemas.portfolio.portfolio_schema import Holding  # noqa: E402
from schemas.watchlist.watchlist_schema import WatchlistCreateIn  # noqa: E402


def _rejects(fn, *, expect_in: str | None = None) -> str:
    try:
        fn()
    except ValidationError as e:
        if expect_in and expect_in not in str(e):
            raise AssertionError(f"사유에 {expect_in!r} 이 없다: {e}") from None
        return "거부"
    raise AssertionError("거부되지 않고 통과했다")


def test_음수_수량은_거부된다() -> str:
    _rejects(lambda: Holding(holding_nm="삼성전자", quantity=-5))
    return "음수 수량은 거부된다"


def test_integer_상한을_넘는_수량은_거부된다() -> str:
    _rejects(lambda: Holding(holding_nm="삼성전자", quantity=2_147_483_648))
    return "integer 상한을 넘는 수량은 거부된다"


def test_정상_수량은_그대로_통과한다() -> str:
    assert Holding(holding_nm="삼성전자", quantity=10).quantity == 10
    return "정상 수량은 그대로 통과한다"


def test_셋째_자리_아래는_반올림하지_않고_거부한다() -> str:
    for value in (70123.456, 0.001, 1.005):
        _rejects(lambda v=value: Holding(holding_nm="삼성전자", avg_price=v), expect_in="소수점")
    return "셋째 자리 아래는 반올림하지 않고 거부한다"


def test_둘째_자리까지는_그대로_통과한다() -> str:
    assert Holding(holding_nm="삼성전자", avg_price=70123.45).avg_price == 70123.45
    return "둘째 자리까지는 그대로 통과한다"


def test_목표가와_알림가도_같은_규칙을_받는다() -> str:
    _rejects(lambda: WatchlistCreateIn(ticker="005930", target_price=70123.456), expect_in="소수점")
    _rejects(lambda: WatchlistCreateIn(ticker="005930", alert_price=70123.456), expect_in="소수점")
    return "목표가와 알림가도 같은 규칙을 받는다"


def test_저장_한도를_넘는_평단은_거부된다() -> str:
    _rejects(lambda: Holding(holding_nm="삼성전자", avg_price=1e16))
    return "저장 한도를 넘는 평단은 거부된다"


def test_가중치는_컬럼_상한을_넘지_못한다() -> str:
    _rejects(lambda: BotStrategyIn(strategy_key="sma_cross", weight=10_000))
    return "가중치는 컬럼 상한을 넘지 못한다"


def test_컬럼_안의_가중치는_통과한다() -> str:
    assert BotStrategyIn(strategy_key="sma_cross", weight=1.5).weight == 1.5
    return "컬럼 안의 가중치는 통과한다"


def _main() -> int:
    tests = [
        test_음수_수량은_거부된다,
        test_integer_상한을_넘는_수량은_거부된다,
        test_정상_수량은_그대로_통과한다,
        test_셋째_자리_아래는_반올림하지_않고_거부한다,
        test_둘째_자리까지는_그대로_통과한다,
        test_목표가와_알림가도_같은_규칙을_받는다,
        test_저장_한도를_넘는_평단은_거부된다,
        test_가중치는_컬럼_상한을_넘지_못한다,
        test_컬럼_안의_가중치는_통과한다,
    ]
    passed = 0
    failed = []
    for tc in tests:
        try:
            name = tc()
        except AssertionError as e:
            failed.append(f"FAIL {tc.__name__}: {e}")
            print(failed[-1])
            continue
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
