"""브로커리지/포트폴리오 데이터 접근 (계좌·보유·거래·주문·활동 store). PortfolioClient 연결을 주입받아 조회 담당.

MOCK 모드(기본): client 의 in-memory 픽스처를 읽는다. REAL 모드(USE_REAL_API=true): client.get() 으로 외부
브로커리지 REST API 를 호출한다. 어느 경로든 동일한 dict 형태를 service 로 돌려줘 service/util 은 모드를 모른다.
"""

import asyncio

from clients.portfolio.portfolio_client import PortfolioClient
from core.logger import logger
from utils.portfolio.portfolio_utils import timestamp_in_range


class PortfolioRepository:
    def __init__(self, portfolio_client: PortfolioClient):
        self.broker = portfolio_client

    async def list_accounts(self, workspace_id: int | None = None) -> list[dict]:
        """계좌 목록 (account_no 포함 — service 가 마스킹). workspace_id 지정 시 그 테넌트 소유만.

        workspace_id=None 은 스코핑 없음(요청 밖/내부 용도) — service 는 항상 require_workspace_id 로 값을 실어 호출한다.
        """
        if self.broker.use_real:
            params = {"workspace_id": workspace_id} if workspace_id is not None else None
            resp = await self.broker.get("/accounts", params)
            resp.raise_for_status()
            return resp.json()
        accounts = self.broker.mock_accounts()
        if workspace_id is not None:
            accounts = [a for a in accounts if a.get("workspace_id") == workspace_id]
        return accounts

    async def list_holdings(self, account_id: str) -> list[dict]:
        """단일 계좌의 보유종목. 미존재 계좌는 빈 리스트."""
        if self.broker.use_real:
            resp = await self.broker.get(f"/accounts/{account_id}/holdings")
            if resp.status_code == 404:
                logger.warning(f"보유종목 없음(계좌 미존재): {account_id}")
                return []
            resp.raise_for_status()
            return resp.json()
        return self.broker.mock_holdings(account_id)

    async def list_transactions(self, account_id: str, since: str, until: str) -> list[dict]:
        """단일 계좌의 거래를 [since, until] 범위로 조회."""
        if self.broker.use_real:
            resp = await self.broker.get(f"/accounts/{account_id}/transactions", {"since": since, "until": until})
            if resp.status_code == 404:
                logger.warning(f"거래 없음(계좌 미존재): {account_id}")
                return []
            resp.raise_for_status()
            return resp.json()
        rows = self.broker.mock_transactions(account_id)
        return [t for t in rows if timestamp_in_range(t.get("trade_date"), since, until)]

    async def list_orders(self, account_id: str, since: str, until: str) -> list[dict]:
        """단일 계좌의 주문을 [since, until] 범위(접수일 기준)로 조회."""
        if self.broker.use_real:
            resp = await self.broker.get(f"/accounts/{account_id}/orders", {"since": since, "until": until})
            if resp.status_code == 404:
                logger.warning(f"주문 없음(계좌 미존재): {account_id}")
                return []
            resp.raise_for_status()
            return resp.json()
        rows = self.broker.mock_orders(account_id)
        return [o for o in rows if timestamp_in_range(o.get("placed_at"), since, until)]

    async def find_account(self, account_id: str, workspace_id: int | None = None) -> dict | None:
        """account_id → 계좌 (활동 조회 전 존재 확인용). workspace_id 지정 시 그 테넌트 소유 계좌만 매칭."""
        accounts = await self.list_accounts(workspace_id)
        for a in accounts:
            if a.get("account_id") == account_id:
                return a
        return None

    async def list_holdings_many(self, account_ids: list[str], concurrency: int = 6) -> dict[str, list[dict]]:
        """여러 계좌 보유종목을 동시 조회 (개별 실패는 건너뜀). {account_id: holdings}."""
        sem = asyncio.Semaphore(concurrency)

        async def one(account_id: str) -> tuple[str, list[dict]]:
            async with sem:
                return account_id, await self.list_holdings(account_id)

        results = await asyncio.gather(*(one(a) for a in account_ids), return_exceptions=True)
        out: dict[str, list[dict]] = {}
        for r in results:
            if isinstance(r, BaseException):
                logger.warning(f"보유종목 병렬 조회 실패: {r}")
                continue
            account_id, holdings = r
            out[account_id] = holdings
        return out

    async def list_transactions_many(
        self, account_ids: list[str], since: str, until: str, concurrency: int = 6
    ) -> dict[str, list[dict]]:
        """여러 계좌 거래를 동시 조회. {account_id: transactions}."""
        sem = asyncio.Semaphore(concurrency)

        async def one(account_id: str) -> tuple[str, list[dict]]:
            async with sem:
                return account_id, await self.list_transactions(account_id, since, until)

        results = await asyncio.gather(*(one(a) for a in account_ids), return_exceptions=True)
        out: dict[str, list[dict]] = {}
        for r in results:
            if isinstance(r, BaseException):
                logger.warning(f"거래 병렬 조회 실패: {r}")
                continue
            account_id, txs = r
            out[account_id] = txs
        return out

    async def list_orders_many(
        self, account_ids: list[str], since: str, until: str, concurrency: int = 6
    ) -> dict[str, list[dict]]:
        """여러 계좌 주문을 동시 조회. {account_id: orders}."""
        sem = asyncio.Semaphore(concurrency)

        async def one(account_id: str) -> tuple[str, list[dict]]:
            async with sem:
                return account_id, await self.list_orders(account_id, since, until)

        results = await asyncio.gather(*(one(a) for a in account_ids), return_exceptions=True)
        out: dict[str, list[dict]] = {}
        for r in results:
            if isinstance(r, BaseException):
                logger.warning(f"주문 병렬 조회 실패: {r}")
                continue
            account_id, orders = r
            out[account_id] = orders
        return out
