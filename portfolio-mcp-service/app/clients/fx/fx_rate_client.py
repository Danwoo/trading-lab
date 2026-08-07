"""환율(FX) 조회 — market-data-mcp 의 /market/fx REST 를 호출한다 (환율 SoT 는 market-data-mcp).

portfolio-mcp 는 환율을 자체 보관하지 않는다. 기준통화 환산이 필요할 때만 이 클라이언트로 통화쌍 환율을
가져오고, 조회 실패·미존재 pair 는 fail-soft — 그 통화는 환산에서 제외해 호출측이 unconverted 로 정직 표기한다
(없는 환율을 역수·삼각환산으로 지어내지 않는다). market-data-mcp 는 기본 MOCK 환율을 반환하므로 dev 에서도
API 키 없이 동작한다. MCP tool 호출과 동일하게 매 요청 fresh 서비스 JWT(exp 1분)를 붙인다.
"""

import asyncio

import httpx
from core.logger import logger
from core.security import create_access_token


class _ServiceJwtAuth(httpx.Auth):
    """요청마다 fresh 서비스 JWT(exp 1분) 주입 — 정적 헤더는 만료 시 401."""

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {create_access_token()}"
        yield request


class FxRateClient:
    def __init__(self, config, timeout: float = 10.0):
        self.base_url = (getattr(config, "MARKET_DATA_MCP_URL", "") or "").rstrip("/")
        self._timeout = httpx.Timeout(timeout, connect=3.0)
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                auth=_ServiceJwtAuth(),
                headers={"Accept": "application/json"},
            )
        return self._client

    async def _fetch_one(self, pair: str) -> tuple[str, dict | None]:
        if not self.base_url:
            return pair, None
        try:
            resp = await self._http().post(f"{self.base_url}/market/fx", json={"pair": pair})
            resp.raise_for_status()
            rows = (resp.json() or {}).get("data") or []
            row = rows[0] if rows else None
            if row and row.get("rate") is not None:
                return pair, {"rate": float(row["rate"]), "asof": row.get("asof") or ""}
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"환율 조회 실패({pair}) — 환산 제외: {e}")
        return pair, None

    async def fetch_rates(self, pairs: set[str]) -> dict[str, dict]:
        """통화쌍 집합의 현재 환율을 동시 조회. {pair: {"rate", "asof"}} — 실패·미존재 pair 는 생략(fail-soft)."""
        if not pairs:
            return {}
        results = await asyncio.gather(*(self._fetch_one(p) for p in pairs))
        return {pair: row for pair, row in results if row is not None}

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
