"""data.go.kr 금융위 HTTP 클라이언트 — 인증(serviceKey)·페이지네이션·한도가 끝나는 자리.

**이 클라이언트는 실호출로 검증되지 않았다.** 키 발급에 가입이 필요하고 에이전트는 가입하지
않는다(#243 리드 결정, 2026-08-04). 엔드포인트·파라미터·응답 필드명은 공개 문서 기준으로
작성했고, 실제 값 대조(오더 3 T5 증명 의무)는 키가 들어온 뒤에 해야 한다 — 그때까지 이 소스의
`capabilities()` 는 `available=False` 다.

한도는 10,000 호출/일(#230). 국내는 날짜별 전종목 스냅샷이라 종목 수가 늘어도 호출 수가 늘지
않는다 — 10년 일봉 전체가 약 4,100 호출로 계산된다(#243 코멘트).
"""

from typing import Any

import httpx
from utils.common.retry_utils import is_http_retryable, retry

BASE_URL = "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService"
STOCK_PRICE_PATH = "/getStockPriceInfo"

# 한 페이지 최대 행 수. 국내 전 종목이 약 2,800 이라 하루치 스냅샷이 3페이지 안에 들어온다.
PAGE_SIZE = 1000


class DataGoKrClient:
    def __init__(self, service_key: str, timeout: float = 30.0, connect_timeout: float = 5.0):
        self.service_key = service_key
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = {"serviceKey": self.service_key, "resultType": "json", "numOfRows": PAGE_SIZE, **params}

        async def _do() -> httpx.Response:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{BASE_URL}{path}", params=query)
            if response.status_code in (429, 502, 503, 504):
                response.raise_for_status()
            return response

        response = await retry(_do, base_delay=1.0, retryable=is_http_retryable)
        response.raise_for_status()
        return response.json()

    async def stock_price_pages(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """`getStockPriceInfo` 를 끝까지 페이징해 item 배열을 이어 붙인다.

        페이지네이션이 어댑터 안에서 끝나는 것이 계약이다(구현설계 §5.2 #4) — 호출부는 `pageNo`
        를 모른다.
        """
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            body = await self._get(STOCK_PRICE_PATH, {**params, "pageNo": page})
            page_items, total = _extract_items(body)
            items.extend(page_items)
            if not page_items or len(items) >= total or page * PAGE_SIZE >= total:
                return items
            page += 1


def _extract_items(body: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """공공데이터포털 공통 응답 봉투(`response.body.items.item`)를 벗긴다. 봉투가 어긋나면
    빈 목록이 아니라 예외다 — 키 오류·서비스 점검도 200 + 오류 봉투로 오기 때문에, 조용히
    0건으로 처리하면 "데이터가 없는 날"과 구분되지 않는다."""
    response = body.get("response") if isinstance(body, dict) else None
    if not isinstance(response, dict):
        raise httpx.DecodingError("공공데이터 응답에 response 봉투가 없습니다")
    header = response.get("header") or {}
    code = header.get("resultCode")
    if code not in (None, "00"):
        raise httpx.DecodingError(f"공공데이터 응답 오류 코드 {code}: {header.get('resultMsg')}")
    payload = response.get("body") or {}
    items = (payload.get("items") or {}).get("item") or []
    if isinstance(items, dict):
        items = [items]
    return list(items), int(payload.get("totalCount") or len(items))
