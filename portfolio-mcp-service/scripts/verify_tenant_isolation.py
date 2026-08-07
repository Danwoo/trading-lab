"""테넌트 격리 회귀 검증 (#35) — 요청자 워크스페이스(workspace_id) 밖 계좌 데이터가 절대 새지 않음을 새 입력으로 공격.

계약:
  (1) list_accounts/list_holdings/search_* 는 요청자 테넌트 소유 계좌만 반환 — 타 워크스페이스 계좌·보유·거래·주문 불가시.
  (2) account_id 를 **직접** 타 테넌트 계좌로 지정해도 fail-closed — 빈 결과 / found=False (존재 오라클 차단).
  (3) 자기 소유 account_id 는 정상 조회.
  (4) 테넌트 미상(workspace_id=None: 요청 밖·순수 서비스 토큰) 이면 5개 조회 전부 UnauthorizedError — fail-closed.

조회는 기간 인자 없이(기본 조회창=최근 30일) 한다. 창을 절대 날짜로 박으면 mock 픽스처가 창 밖으로
빠지는 날 교차 조회가 "격리돼서 0건" 이 아니라 "볼 게 없어서 0건" 이 되어 검사가 조용히 무력해진다.
그래서 자기 계좌 조회가 0건이 아님을 먼저 확인(대조군)한 뒤 교차 조회의 0건을 주장한다.

mock 소유: 워크스페이스 1 = ACC-1001(KRW)·ACC-1002(USD), 워크스페이스 2 = ACC-1003(연금). 실제 PortfolioService 를 그대로 써
검사 — DB/LLM/외부 API 불필요. `uv run python scripts/verify_tenant_isolation.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "verify-secret")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from core.auth_context import set_auth_context  # noqa: E402
from core.container import Container  # noqa: E402
from core.exceptions import UnauthorizedError  # noqa: E402

problems: list[str] = []


def check(name: str, cond: bool) -> None:
    if not cond:
        problems.append(name)


class _StubFx:
    """FX 환산은 격리 검사와 무관 — 네트워크(market-data-mcp) 없이 hermetic 하게 빈 환율만 반환."""

    async def fetch_rates(self, pairs: set[str]) -> dict[str, dict]:
        return {}


def as_tenant(workspace_id: int | None) -> None:
    set_auth_context(user_id="verify", role="admin", workspace_id=workspace_id)


async def run_checks() -> None:
    svc = Container().portfolio_service()
    svc.fx_client = _StubFx()  # 격리 검사는 FX 값과 무관 — 네트워크 제거

    # (1) 계좌 목록이 테넌트로 스코핑 — 워크스페이스 1 은 ACC-1001·1002 만, 워크스페이스 2 는 ACC-1003 만.
    as_tenant(1)
    ids_1 = {a["account_id"] for a in await svc.list_accounts()}
    check("워크스페이스1 계좌 = {ACC-1001, ACC-1002}", ids_1 == {"ACC-1001", "ACC-1002"})
    check("워크스페이스1 은 ACC-1003(타 테넌트)을 못 본다", "ACC-1003" not in ids_1)

    as_tenant(2)
    ids_2 = {a["account_id"] for a in await svc.list_accounts()}
    check("워크스페이스2 계좌 = {ACC-1003}", ids_2 == {"ACC-1003"})
    check("워크스페이스2 는 ACC-1001·1002(타 테넌트)를 못 본다", not (ids_2 & {"ACC-1001", "ACC-1002"}))

    # (1) 보유종목 합산도 내 계좌만 — 워크스페이스 2 결과에 워크스페이스 1 종목(삼성·AAPL)이 절대 없어야.
    as_tenant(2)
    h2 = await svc.list_holdings()
    accs_in_h2 = set(h2["accounts"])
    check("워크스페이스2 보유합산은 ACC-1003 만", accs_in_h2 <= {"ACC-1003"})
    tickers_2 = {r["ticker"] for r in h2["holdings"]}
    check(
        "워크스페이스2 보유에 워크스페이스1 종목(005930·AAPL) 미유출",
        not (tickers_2 & {"005930", "AAPL", "MSFT", "000660"}),
    )

    # (3) 대조군 먼저 — 자기 계좌는 기본 조회창에서 실제로 데이터가 나온다. 이게 0건이면 아래 교차 0건은 무의미.
    as_tenant(2)
    owner_t = await svc.search_transactions(account_id="ACC-1003")
    check("대조군: 워크스페이스2→ACC-1003 자기 거래 있음", owner_t["transaction_count"] > 0)
    owner_o = await svc.search_orders(account_id="ACC-1003")
    check("대조군: 워크스페이스2→ACC-1003 자기 주문 있음", owner_o["order_count"] > 0)
    owner_a = await svc.get_account_activity(account_id="ACC-1003")
    check("대조군: 워크스페이스2→ACC-1003 자기 활동 있음", owner_a["found"] is True and owner_a["count"] > 0)

    # (2) 타 테넌트 account_id 직접 지정 → fail-closed (빈 결과 / found=False). 존재를 노출하지 않는다.
    as_tenant(1)  # 워크스페이스 1 이 워크스페이스 2 계좌(ACC-1003)를 직접 노린다 — 대조군과 같은 계좌·같은 조회창
    cross_h = await svc.list_holdings(account_id="ACC-1003")
    check("교차: 워크스페이스1→ACC-1003 보유 0건", cross_h["holding_count"] == 0 and cross_h["accounts"] == [])
    cross_t = await svc.search_transactions(account_id="ACC-1003")
    check("교차: 워크스페이스1→ACC-1003 거래 0건", cross_t["transaction_count"] == 0)
    cross_o = await svc.search_orders(account_id="ACC-1003")
    check("교차: 워크스페이스1→ACC-1003 주문 0건", cross_o["order_count"] == 0)
    cross_a = await svc.get_account_activity(account_id="ACC-1003")
    check("교차: 워크스페이스1→ACC-1003 활동 found=False (존재 오라클 차단)", cross_a["found"] is False)

    as_tenant(2)  # 반대 방향도 — 워크스페이스 2 가 워크스페이스 1 계좌(ACC-1001)를 직접 노린다
    rev_h = await svc.list_holdings(account_id="ACC-1001")
    check("교차: 워크스페이스2→ACC-1001 보유 0건", rev_h["holding_count"] == 0)
    rev_a = await svc.get_account_activity(account_id="ACC-1001")
    check("교차: 워크스페이스2→ACC-1001 활동 found=False", rev_a["found"] is False)

    # (3) 자기 소유 account_id 는 정상 — 격리가 자기 데이터까지 막지는 않음.
    as_tenant(1)
    own_h = await svc.list_holdings(account_id="ACC-1001")
    check("정상: 워크스페이스1→ACC-1001 보유 있음", own_h["holding_count"] > 0 and own_h["accounts"] == ["ACC-1001"])
    own_a = await svc.get_account_activity(account_id="ACC-1001")
    check("정상: 워크스페이스1→ACC-1001 활동 있음", own_a["found"] is True and own_a["count"] > 0)

    # (4) 테넌트 미상(workspace_id=None — 요청 밖·순수 서비스 토큰) → 5개 조회 전부 fail-closed(UnauthorizedError).
    as_tenant(None)

    async def raises_unauth(coro) -> bool:
        try:
            await coro
            return False
        except UnauthorizedError:
            return True

    check("fail-closed: list_accounts", await raises_unauth(svc.list_accounts()))
    check("fail-closed: list_holdings", await raises_unauth(svc.list_holdings()))
    check("fail-closed: search_transactions", await raises_unauth(svc.search_transactions()))
    check("fail-closed: search_orders", await raises_unauth(svc.search_orders()))
    check(
        "fail-closed: get_account_activity",
        await raises_unauth(svc.get_account_activity(account_id="ACC-1001")),
    )


def main() -> int:
    asyncio.run(run_checks())
    if problems:
        print("테넌트 격리 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        "테넌트 격리 OK — 계좌·보유·거래·주문·활동이 요청자 워크스페이스로 스코핑, 교차 account_id fail-closed, 무테넌트 401"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
