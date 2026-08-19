"""토스증권 Open API HTTP 클라이언트 — 인증·한도·주문 차단이 끝나는 자리.

사양 근거: openapi.tossinvest.com/openapi-docs (overview.md · openapi.json, 2026-08-19 확인).
자격증명은 `client_id:client_secret` 합성 한 줄로 받는다(alpaca 의 `KEYID:SECRET` 관례) —
갈라 쓰는 두 env 항목의 소유자는 `data_key_service` 다.

**실호출 미검증**: 자격증명 한쪽(client_id)이 아직 없어 토큰 발급을 실측하지 못했다.
엔드포인트·파라미터·응답 필드는 공식 사양 기준이고, 실호출 대조는 자격이 완성된 뒤의 일이다.

한도는 공식(overview.md: AUTH 5/s · MARKET_DATA 15/s · CHART 20/s)보다 보수적으로 잡는다 —
한도 초과는 일시 제한으로 이어진다.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from utils.common.retry_utils import is_http_retryable, retry
from utils.redaction.redactor import register_secret

from providers.toss.live_guard import assert_path_allowed

BASE_URL = "https://openapi.tossinvest.com"
TOKEN_PATH = "/oauth2/token"

#: 페이지당 캔들 상한 — 사양의 count 범위 1~200.
PAGE_LIMIT = 200

#: 카테고리별 최소 호출 간격(초) — 공식 한도의 1/3~1/5 수준.
THROTTLE_INTERVAL_S: dict[str, float] = {
    "AUTH": 1.0,
    "MARKET_DATA": 0.25,
    "MARKET_DATA_CHART": 0.25,
}

#: 토큰 만료 전 이만큼 남으면 재발급 — 경계에서 만료 응답을 받지 않게.
TOKEN_REFRESH_MARGIN_S = 60.0

#: 응답이 수명을 안 알려줄 때 쓰는 보수값 — 사양 기본(86,400)보다 짧게 잡아 늦어도 한 시간이면
#: 다시 받는다. 0 으로 두면 캐시가 죽어 매 호출이 재발급이 된다.
TOKEN_FALLBACK_LIFETIME_S = 3600.0


def _category(path: str) -> str:
    if path == TOKEN_PATH:
        return "AUTH"
    if path.startswith("/api/v1/candles"):
        return "MARKET_DATA_CHART"
    return "MARKET_DATA"


class TossClient:
    def __init__(self, api_key: str, timeout: float = 30.0, connect_timeout: float = 5.0):
        self.client_id, _, self.client_secret = (api_key or "").partition(":")
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._last_call_at: dict[str, float] = {}
        self._auth_lock = asyncio.Lock()
        # 시크릿은 로그 관문에 먼저 올린다 — 어떤 예외 문구에 실려도 가려지게.
        if self.client_secret:
            register_secret(self.client_secret)

    @property
    def credentials_well_formed(self) -> bool:
        """`"<CLIENT_ID>:<CLIENT_SECRET>"` 두 쪽이 다 있는가 — 한쪽만으로는 토큰이 안 나온다."""
        return bool(self.client_id and self.client_secret)

    async def _throttle(self, category: str) -> None:
        interval = THROTTLE_INTERVAL_S.get(category, 0.25)
        last = self._last_call_at.get(category)
        now = time.monotonic()
        if last is not None and now - last < interval:
            await asyncio.sleep(interval - (now - last))
        self._last_call_at[category] = time.monotonic()

    async def _access_token(self) -> str:
        """Client Credentials 토큰 — 캐시하고 만료 여유(60s) 전에 갱신한다. 값은 로그에 없다."""
        async with self._auth_lock:
            if self._token and time.monotonic() < self._token_expires_at - TOKEN_REFRESH_MARGIN_S:
                return self._token

            await self._throttle("AUTH")

            async def _do() -> httpx.Response:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{BASE_URL}{TOKEN_PATH}",
                        data={
                            "grant_type": "client_credentials",
                            "client_id": self.client_id,
                            "client_secret": self.client_secret,
                        },
                    )
                if response.status_code in (429, 502, 503, 504):
                    response.raise_for_status()
                return response

            response = await retry(_do, base_delay=1.0, retryable=is_http_retryable)
            response.raise_for_status()
            body = response.json()
            token = body.get("access_token")
            if not isinstance(token, str) or not token:
                raise httpx.DecodingError("토큰 응답에 access_token 이 없습니다")
            register_secret(token)
            self._token = token
            # `expires_in` 이 없으면 만료를 0 으로 두지 않는다 — 그러면 캐시가 영구 무효가 돼
            # 매 요청이 재발급을 부르고 AUTH 한도(1/s)에 직렬화된다. 짧은 보수값으로 떨어진다.
            lifetime = float(body.get("expires_in") or 0) or TOKEN_FALLBACK_LIFETIME_S
            self._token_expires_at = time.monotonic() + lifetime
            return token

    async def request(
        self, path: str, params: dict[str, Any] | None = None, *, allow_account_read: bool = False
    ) -> Any:
        """모든 조회가 지나는 단일 관문 — 주문·계좌 차단(live_guard) → 한도 → 토큰 → 재시도."""
        assert_path_allowed(path, allow_account_read=allow_account_read)
        await self._throttle(_category(path))
        token = await self._access_token()

        async def _do() -> httpx.Response:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{BASE_URL}{path}", params=params, headers={"Authorization": f"Bearer {token}"}
                )
            if response.status_code in (429, 502, 503, 504):
                response.raise_for_status()
            return response

        response = await retry(_do, base_delay=1.0, retryable=is_http_retryable)
        response.raise_for_status()
        return response.json()

    async def candles(self, symbol: str, interval: str, count: int = PAGE_LIMIT, before: str | None = None) -> dict:
        params: dict[str, Any] = {"symbol": symbol, "interval": interval, "count": count, "adjusted": "false"}
        if before:
            params["before"] = before
        body = await self.request("/api/v1/candles", params)
        result = (body or {}).get("result")
        if not isinstance(result, dict):
            raise httpx.DecodingError("candles 응답에 result 객체가 없습니다")
        return result

    async def stocks_all(self, market: str) -> list[dict]:
        body = await self.request("/api/v1/stocks/all", {"market": market})
        result = (body or {}).get("result")
        if isinstance(result, dict):
            for field in ("stocks", "items"):
                rows = result.get(field)
                if isinstance(rows, list):
                    return rows
            # 「종목 0개」와 「응답 모양이 다름」을 뭉개지 않는다 — 조용한 빈 목록은 적재를
            # 성공으로 기록하면서 아무것도 안 넣는다.
            raise httpx.DecodingError(f"stocks/all 응답에 종목 배열이 없습니다 (받은 키: {sorted(result)})")
        if isinstance(result, list):
            return result
        raise httpx.DecodingError("stocks/all 응답에 result 가 없습니다")
