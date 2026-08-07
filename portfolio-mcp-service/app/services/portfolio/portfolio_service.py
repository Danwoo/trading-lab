# services/portfolio/portfolio_service.py
from clients.fx.fx_rate_client import FxRateClient
from core.auth_context import require_workspace_id
from repositories.portfolio.portfolio_repository import PortfolioRepository
from utils.common.time_utils import now_kst
from utils.portfolio.portfolio_utils import (
    assign_weights,
    convert_to_base,
    event_line,
    fx_pairs_for,
    holding_line,
    nav_by_currency,
    norm_since,
    norm_until,
    order_line,
    select_rates,
    sum_by_currency,
    sum_market_value_by_currency,
    timestamp_sort_key,
    tx_line,
)
from utils.redaction.redactor import redact_secrets

_MAX_RESULTS = 250  # 검색 결과 상한 (초과 시 최신쪽 유지)
_DEFAULT_BASE_CURRENCY = "KRW"


class PortfolioService:
    """브로커리지/포트폴리오 데이터 조회 (순수 포트폴리오 데이터, LLM 없음).

    숫자(평가금액·손익·비중)는 보유·체결 mock/공시 데이터에서 결정론적으로 계산하며 추정하지 않는다.
    통화가 섞이면 통화별 dict 로 분리하고, 기준통화 환산합(*_in_base)은 market-data-mcp 환율로만 낸다 —
    환율 없는 통화는 지어내지 않고 unconverted_currencies 로 정직 표기한다.
    """

    def __init__(self, portfolio_repository: PortfolioRepository, fx_rate_client: FxRateClient):
        self.portfolio_repo = portfolio_repository
        self.fx_client = fx_rate_client

    async def _tenant_target_ids(self, workspace_id: int, account_id: str | None) -> list[str]:
        """요청자 테넌트 소유 계좌로 스코핑한 대상 account_id 목록.

        account_id 미지정 → 내 계좌 전부. 지정 → 내 소유일 때만 그 하나, 아니면 빈 리스트(fail-closed —
        타 테넌트 계좌 id 를 직접 실어도 존재를 노출하지 않고 0건 반환).
        """
        accounts = await self.portfolio_repo.list_accounts(workspace_id)
        my_ids = [a["account_id"] for a in accounts]
        if account_id is None:
            return my_ids
        return [account_id] if account_id in my_ids else []

    async def list_accounts(self) -> list[dict]:
        """계좌 목록 (account_no 는 마스킹, NAV=현금+평가금액). 요청자 테넌트 소유 계좌만.

        nav_by_currency 는 환율 없는 통화별 분리, nav_in_base 는 계좌 기준통화(base_currency)로 환산 합산.
        """
        workspace_id = require_workspace_id()
        accounts = await self.portfolio_repo.list_accounts(workspace_id)
        account_ids = [a["account_id"] for a in accounts]
        holdings_by_acc = await self.portfolio_repo.list_holdings_many(account_ids)

        # 계좌별 통화별 NAV 를 먼저 내고, 환산에 필요한 통화쌍을 모아 한 번에 조회 (계좌마다 기준통화가 다를 수 있음)
        navs: dict[str, tuple[str, float, dict[str, float]]] = {}
        pairs: set[str] = set()
        for a in accounts:
            base_ccy = a.get("base_currency") or _DEFAULT_BASE_CURRENCY
            cash = float(a.get("cash_balance") or 0)
            nav_by_ccy = nav_by_currency(base_ccy, cash, holdings_by_acc.get(a["account_id"], []))
            navs[a["account_id"]] = (base_ccy, cash, nav_by_ccy)
            pairs |= fx_pairs_for(nav_by_ccy, base_ccy)
        fetched = await self.fx_client.fetch_rates(pairs)

        out = []
        for a in accounts:
            base_ccy, cash, nav_by_ccy = navs[a["account_id"]]
            rates, fx_used = select_rates(fetched, nav_by_ccy, base_ccy)
            nav_in_base, unconverted = convert_to_base(nav_by_ccy, base_ccy, rates)
            out.append(
                {
                    "account_id": a["account_id"],
                    "account_no": redact_secrets(a.get("account_no") or ""),
                    "account_name": a.get("account_name") or "",
                    "account_type": a.get("account_type") or "cash",
                    "base_currency": base_ccy,
                    "nav": nav_by_ccy[base_ccy],
                    "nav_by_currency": nav_by_ccy,
                    "nav_in_base": nav_in_base,
                    "fx_rates_used": fx_used,
                    "unconverted_currencies": unconverted,
                    "cash_balance": round(cash, 2),
                }
            )
        return sorted(out, key=lambda x: x["account_id"])

    async def _convert_by_currency(
        self, by_currency: dict[str, float], base_currency: str
    ) -> tuple[float, dict[str, dict], list[str]]:
        """통화별 합계를 기준통화로 환산 → (합계_in_base, fx_rates_used, unconverted). 환율은 fail-soft."""
        fetched = await self.fx_client.fetch_rates(fx_pairs_for(by_currency, base_currency))
        rates, fx_used = select_rates(fetched, by_currency, base_currency)
        total_in_base, unconverted = convert_to_base(by_currency, base_currency, rates)
        return total_in_base, fx_used, unconverted

    async def list_holdings(
        self,
        account_id: str | None = None,
        asset_class: str | None = None,
        ticker_keywords: list[str] | None = None,
        min_weight: float | None = None,
        base_currency: str | None = None,
    ) -> dict:
        """보유종목 조회 → 평가금액·손익·비중 계산된 구조화 보유분. NL 추출·LLM 요약은 호출자 몫.

        account_id 지정 시 그 계좌만, 미지정 시 (요청자 테넌트 소유) 전체 계좌 합산. 비중(weight)은 계좌별 평가자산 기준.
        total_market_value_in_base 는 base_currency(기본 KRW)로 환산 합산, 환율 없는 통화는 unconverted.
        """
        base = base_currency or _DEFAULT_BASE_CURRENCY
        workspace_id = require_workspace_id()
        target_ids = await self._tenant_target_ids(workspace_id, account_id)
        holdings_by_acc = await self.portfolio_repo.list_holdings_many(target_ids)

        rows: list[dict] = []
        for acc_id, holdings in holdings_by_acc.items():
            lines = [holding_line(acc_id, h) for h in holdings]
            assign_weights(lines)  # 계좌별 평가자산 기준 비중 (full precision)
            rows.extend(lines)

        kws = ticker_keywords or []
        rows = [
            r
            for r in rows
            if (not asset_class or r["asset_class"] == asset_class)
            and (not kws or any(k.lower() in r["ticker"].lower() or k.lower() in r["name"].lower() for k in kws))
            and (min_weight is None or r["weight"] >= min_weight)
        ]
        rows.sort(key=lambda r: r["market_value"], reverse=True)
        by_ccy = sum_market_value_by_currency(rows)
        total_in_base, fx_used, unconverted = await self._convert_by_currency(by_ccy, base)
        return {
            "holdings": rows,
            "holding_count": len(rows),
            "total_market_value_by_currency": by_ccy,
            "base_currency": base,
            "total_market_value_in_base": total_in_base,
            "fx_rates_used": fx_used,
            "unconverted_currencies": unconverted,
            "accounts": sorted({r["account_id"] for r in rows}),
        }

    async def search_transactions(
        self,
        account_id: str | None = None,
        tx_type: str | None = None,
        ticker_keywords: list[str] | None = None,
        since: str | None = None,
        until: str | None = None,
        base_currency: str | None = None,
    ) -> dict:
        """구조화 조건으로 거래 검색 → 필터·시간순 정렬된 구조화 거래. account_id 미지정 시 (요청자 테넌트 소유) 전체 계좌.

        net_amount_in_base 는 base_currency(기본 KRW)로 환산한 순현금흐름, 환율 없는 통화는 unconverted.
        """
        base = base_currency or _DEFAULT_BASE_CURRENCY
        now = now_kst()
        since = norm_since(since, now)
        until = norm_until(until, now)
        workspace_id = require_workspace_id()
        target_ids = await self._tenant_target_ids(workspace_id, account_id)
        tx_by_acc = await self.portfolio_repo.list_transactions_many(target_ids, since, until)

        kws = ticker_keywords or []
        # 표시 trade_date 는 날짜로 절단되지만 정렬은 원본 타임스탬프(있으면 시:분:초까지)로 해 당일 내 순서를 보존한다
        keyed = []
        for acc_id, txs in tx_by_acc.items():
            for t in txs:
                line = tx_line(acc_id, t)
                if tx_type and line["tx_type"] != tx_type:
                    continue
                if kws and not any(
                    k.lower() in line["ticker"].lower() or k.lower() in line["name"].lower() for k in kws
                ):
                    continue
                keyed.append((timestamp_sort_key(t.get("trade_date")), line))
        keyed.sort(key=lambda pair: pair[0])  # 시간순(오래된→최신)
        truncated = len(keyed) > _MAX_RESULTS
        rows = [line for _, line in (keyed[-_MAX_RESULTS:] if truncated else keyed)]
        net_by_ccy = sum_by_currency(rows, "amount")
        net_in_base, fx_used, unconverted = await self._convert_by_currency(net_by_ccy, base)
        return {
            "transactions": rows,
            "transaction_count": len(rows),
            "truncated": truncated,
            "period": f"{since[:10]} ~ {until[:10]}",
            "net_amount_by_currency": net_by_ccy,
            "base_currency": base,
            "net_amount_in_base": net_in_base,
            "fx_rates_used": fx_used,
            "unconverted_currencies": unconverted,
            "accounts": sorted({r["account_id"] for r in rows}),
        }

    async def search_orders(
        self,
        account_id: str | None = None,
        status: str | None = None,
        side: str | None = None,
        ticker_keywords: list[str] | None = None,
        since: str | None = None,
        until: str | None = None,
    ) -> dict:
        """구조화 조건으로 주문 검색 → 최신 접수순 구조화 주문. account_id 미지정 시 (요청자 테넌트 소유) 전체 계좌."""
        now = now_kst()
        since = norm_since(since, now)
        until = norm_until(until, now)
        workspace_id = require_workspace_id()
        target_ids = await self._tenant_target_ids(workspace_id, account_id)
        orders_by_acc = await self.portfolio_repo.list_orders_many(target_ids, since, until)

        kws = ticker_keywords or []
        # 표시 placed_at 은 날짜로 절단되지만 정렬은 원본 타임스탬프로 해 당일 내 순서를 보존한다
        keyed = []
        for acc_id, orders in orders_by_acc.items():
            for o in orders:
                line = order_line(acc_id, o)
                if status and line["status"] != status:
                    continue
                if side and line["side"] != side:
                    continue
                if kws and not any(
                    k.lower() in line["ticker"].lower() or k.lower() in line["name"].lower() for k in kws
                ):
                    continue
                keyed.append((timestamp_sort_key(o.get("placed_at")), line))
        keyed.sort(key=lambda pair: pair[0], reverse=True)  # 최신 접수순
        truncated = len(keyed) > _MAX_RESULTS
        rows = [line for _, line in keyed[:_MAX_RESULTS]]
        return {
            "orders": rows,
            "order_count": len(rows),
            "truncated": truncated,
            "period": f"{since[:10]} ~ {until[:10]}",
            "accounts": sorted({r["account_id"] for r in rows}),
        }

    async def get_account_activity(self, account_id: str, since: str | None = None, until: str | None = None) -> dict:
        """계좌(account_id)의 활동 이벤트(체결·주문·입출금·배당 통합, 최신순).

        account_id 미존재 시 예외 대신 found=False 로 graceful 반환 — 에이전트 스트림이 깨지지 않고
        '활동 없음(0건)' 과 '계좌 미존재' 를 구분해 답할 수 있게 한다. 타 테넌트 계좌 id 도 found=False
        로 취급 — 소유 여부를 노출하지 않는다(존재 오라클 차단).
        """
        now = now_kst()
        since = norm_since(since, now)
        until = norm_until(until, now)
        workspace_id = require_workspace_id()
        account = await self.portfolio_repo.find_account(account_id, workspace_id)
        if not account:
            return {
                "account_id": account_id,
                "events": [],
                "count": 0,
                "found": False,
                "period": f"{since[:10]} ~ {until[:10]}",
            }

        txs = await self.portfolio_repo.list_transactions(account_id, since, until)
        orders = await self.portfolio_repo.list_orders(account_id, since, until)
        raw: list[dict] = []
        for t in txs:
            line = tx_line(account_id, t)
            cash_types = {"deposit", "withdraw", "fee"}
            action = (
                "dividend" if line["tx_type"] == "dividend" else ("cash" if line["tx_type"] in cash_types else "trade")
            )
            label = line["name"] or line["tx_type"]
            qty = f" {line['quantity']:g}주" if line["quantity"] else ""
            raw.append(
                {
                    "date": t.get("trade_date") or "",  # 원본 타임스탬프로 정렬, event_line 이 표시용으로 절단
                    "action": action,
                    "detail": f"{line['tx_type']} {label}{qty} ({line['amount']:+,.0f} {line['currency']})",
                    "amount": line["amount"],
                }
            )
        for o in orders:
            line = order_line(account_id, o)
            raw.append(
                {
                    "date": o.get("placed_at") or "",
                    "action": "order",
                    "detail": f"{line['side']} {line['name']} {line['status']} ({line['filled_quantity']:g}/{line['quantity']:g})",
                    "amount": 0.0,
                }
            )

        raw.sort(key=lambda e: timestamp_sort_key(e["date"]), reverse=True)  # 최신순
        lines = [event_line(e) for e in raw]
        truncated = len(lines) > _MAX_RESULTS
        rows = lines[:_MAX_RESULTS]
        return {
            "account_id": account_id,
            "events": rows,
            "count": len(rows),
            "truncated": truncated,
            "found": True,
            "period": f"{since[:10]} ~ {until[:10]}",
        }
