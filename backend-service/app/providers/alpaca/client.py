"""Alpaca Market Data v2 HTTP 클라이언트 — 인증·페이지네이션·한도가 끝나는 자리.

**미검증**: 키 발급에 이메일 가입이 필요하고 에이전트는 가입하지 않는다(#2 리드 결정,
2026-08-04). 엔드포인트·파라미터·응답 필드는 공개 문서 기준이며 실호출 대조는 키가 들어온
뒤의 일이다.

한도는 무료 플랜 200요청/분(#2 코멘트). 페이지네이션은 `next_page_token` 커서 방식이라
페이지 번호가 아니라 토큰을 이어 붙인다 — 그 사정이 이 클래스 밖으로 나가지 않는다.
"""

from typing import Any

import httpx
from utils.common.retry_utils import is_http_retryable, retry

BASE_URL = "https://data.alpaca.markets/v2"

# 응답당 최대 캔들 수 — 문서상 상한.
PAGE_LIMIT = 10000


class AlpacaClient:
    def __init__(self, api_key: str, timeout: float = 30.0, connect_timeout: float = 5.0):
        self.key_id, _, self.secret = api_key.partition(":")
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)

    @property
    def credentials_well_formed(self) -> bool:
        """`"<KEY_ID>:<SECRET>"` 형식인가. 형식이 깨진 키를 그대로 보내면 401 이 "키가 틀렸다"인지
        "형식이 틀렸다"인지 구분되지 않는다."""
        return bool(self.key_id and self.secret)

    def _headers(self) -> dict[str, str]:
        return {"APCA-API-KEY-ID": self.key_id, "APCA-API-SECRET-KEY": self.secret}

    async def bars(self, symbol: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """`/stocks/{symbol}/bars` 를 `next_page_token` 이 없어질 때까지 이어 받는다."""
        collected: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            query = {"limit": PAGE_LIMIT, **params}
            if page_token:
                query["page_token"] = page_token

            async def _do(q: dict[str, Any] = query) -> httpx.Response:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(f"{BASE_URL}/stocks/{symbol}/bars", params=q, headers=self._headers())
                if response.status_code in (429, 502, 503, 504):
                    response.raise_for_status()
                return response

            response = await retry(_do, base_delay=1.0, retryable=is_http_retryable)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise httpx.DecodingError("Alpaca 응답 최상위가 객체가 아닙니다")
            collected.extend(body.get("bars") or [])
            page_token = body.get("next_page_token")
            if not page_token:
                return collected

    async def latest_bars(self, symbols: list[str]) -> dict[str, Any]:
        """`/stocks/bars/latest` — 다종목 최신 캔들 일괄 조회. 갈래 3(일괄 조회)의 소스다."""

        async def _do() -> httpx.Response:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{BASE_URL}/stocks/bars/latest",
                    params={"symbols": ",".join(symbols)},
                    headers=self._headers(),
                )
            if response.status_code in (429, 502, 503, 504):
                response.raise_for_status()
            return response

        response = await retry(_do, base_delay=1.0, retryable=is_http_retryable)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise httpx.DecodingError("Alpaca 응답 최상위가 객체가 아닙니다")
        return body.get("bars") or {}
