"""#434 (F4) — 없는 포트폴리오에 보유종목이 들어가지 않는지.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행형으로 쓴다:
    uv run python tests/test_holding_needs_its_portfolio.py

저장소에 외래키가 하나도 없다(`0001_baseline.py` 에 `ForeignKey` 0건). 그래서 참조 무결성은
전적으로 애플리케이션 층의 몫인데, `insert_holding` 은 중복만 보고 **부모가 있는지는 안 봤다.**
없는 포트폴리오 번호로 보유종목을 넣으면 201 이 돌아오고, 그 행은 어느 목록에도 안 잡히면서
API 로 지울 수도 없다 — 조회 경로가 전부 부모를 끼고 도는 탓이다.

DB 없이 도는 가짜 저장소로, 서비스가 다음을 지키는지 본다:

  (1) 부모가 없으면 **거부**한다 (고아 행이 안 생긴다).
  (2) 부모가 없으면 INSERT 자체가 시도되지 않는다 — 「거부했다」와 「넣고 나서 지웠다」는 다르다.
  (3) 부모가 있으면 종전대로 들어간다 — 막는 범위가 넓어지지 않았다.
  (4) 부모가 있고 이미 같은 종목이 있으면 종전대로 중복 거부다 — 새 검사가 이것을 가리지 않는다.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from core.auth_context import set_auth_context  # noqa: E402
from core.exceptions import ConflictError, NotFoundError  # noqa: E402
from services.portfolio.portfolio_service import PortfolioService  # noqa: E402

WORKSPACE_ID = 7


class FakeRepository:
    """부모·자식 존재 여부만 흉내 내고, INSERT 가 불렸는지 기록한다."""

    def __init__(self, *, portfolio: dict | None, holding: dict | None = None):
        self._portfolio = portfolio
        self._holding = holding
        self.inserted: list[dict] = []

    def select_portfolio(self, args: dict) -> dict | None:
        return self._portfolio

    def select_holding(self, args: dict) -> dict | None:
        return self._holding

    def insert_holding(self, args: dict) -> tuple:
        self.inserted.append(dict(args))
        return (1,)


def _service(repo: FakeRepository) -> PortfolioService:
    set_auth_context(user_id="u", email="u@x", role="operator", workspace_id=WORKSPACE_ID)
    return PortfolioService(portfolio_repository=repo)


def _args() -> dict:
    return {"portfolio_id": 999, "ticker": "005930", "holding_nm": "삼성전자", "quantity": 10}


def test_부모가_없으면_거부한다() -> str:
    repo = FakeRepository(portfolio=None)
    try:
        _service(repo).insert_holding(_args())
    except NotFoundError as e:
        assert "포트폴리오" in str(e), f"어느 칸이 문제인지 안 말한다: {e}"
        return "부모가 없으면 거부한다"
    raise AssertionError("고아 행이 201 로 들어갔다")


def test_부모가_없으면_INSERT_가_시도되지_않는다() -> str:
    repo = FakeRepository(portfolio=None)
    try:
        _service(repo).insert_holding(_args())
    except NotFoundError:
        pass
    assert repo.inserted == [], f"거부했다면서 INSERT 를 불렀다: {repo.inserted}"
    return "부모가 없으면 INSERT 가 시도되지 않는다"


def test_부모가_있으면_종전대로_들어간다() -> str:
    repo = FakeRepository(portfolio={"portfolio_id": 999})
    assert _service(repo).insert_holding(_args()) == (1,)
    assert len(repo.inserted) == 1
    return "부모가 있으면 종전대로 들어간다"


def test_중복_거부는_그대로다() -> str:
    repo = FakeRepository(portfolio={"portfolio_id": 999}, holding={"ticker": "005930"})
    try:
        _service(repo).insert_holding(_args())
    except ConflictError:
        assert repo.inserted == []
        return "중복 거부는 그대로다"
    raise AssertionError("중복이 통과했다")


def _main() -> int:
    tests = [
        test_부모가_없으면_거부한다,
        test_부모가_없으면_INSERT_가_시도되지_않는다,
        test_부모가_있으면_종전대로_들어간다,
        test_중복_거부는_그대로다,
    ]
    passed = 0
    for tc in tests:
        try:
            name = tc()
        except AssertionError as e:
            print(f"FAIL {tc.__name__}: {e}")
            continue
        print(f"PASS {name}")
        passed += 1
    print(f"\n검사한 단언 {len(tests)}건 중 {passed}건 통과")
    print("판정: 보유종목은 자기 포트폴리오 없이는 저장되지 않는다")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
