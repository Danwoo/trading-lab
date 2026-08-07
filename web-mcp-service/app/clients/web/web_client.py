"""Tavily Web Search API 연결 (transport) — api_key 본문 인증, JSON 응답. 단일 POST + 재시도, 연결 풀 재사용.

기본은 MOCK(인메모리 샘플 결과)라 키 없이 즉시 기동·응답한다. USE_REAL_API=true + TAVILY_API_KEY 일 때만
실제 Tavily 를 호출한다. 데이터 접근(score 필터·필드 트리밍)은 repositories/web 의 WebRepository 담당.
이 클래스는 SQL 엔진·Milvus 연결처럼 '연결(또는 mock store)'만 제공한다.
"""

import httpx
from utils.common.retry_utils import is_http_retryable, retry


class WebClient:
    def __init__(self, config, timeout: float = 30.0):
        self.base_url = "https://api.tavily.com"
        self._api_key = config.TAVILY_API_KEY
        self._use_real = bool(getattr(config, "USE_REAL_API", False) and config.TAVILY_API_KEY)
        self.exclude_domains = ["instagram.com", "facebook.com", "tiktok.com"]
        self._timeout = httpx.Timeout(timeout, connect=5.0)
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    @staticmethod
    def _mock_search(query: str, max_results: int, include_images: bool) -> dict:
        """키 없이 동작하는 canned 검색 결과 — Tavily 응답 형태(results·images·answer)로 돌려준다.

        실검색 결과가 아니라 데모/부팅용 합성 샘플이며, 외부 링크는 example.com 플레이스홀더다.
        """
        results = [
            {
                "title": f"{query} — 개요",
                "content": (
                    f"'{query}' 에 대한 목업 검색 결과입니다. 실데이터는 USE_REAL_API=true 와 "
                    "TAVILY_API_KEY 설정 시 Tavily 로 대체됩니다."
                ),
                "url": "https://example.com/search/overview",
                "score": 0.92,
                "published_date": None,
            },
            {
                "title": f"{query} — 관련 동향",
                "content": f"'{query}' 관련 동향 요약(목업). 정보 제공 목적이며 투자 조언이 아닙니다.",
                "url": "https://example.com/search/trend",
                "score": 0.71,
                "published_date": None,
            },
        ]
        return {
            "query": query,
            "answer": f"'{query}' 관련 목업 요약입니다 (키 없이 동작하는 샘플 응답).",
            "results": results[: max(max_results, 1)],
            "images": ["https://example.com/img/sample1.jpg"] if include_images else [],
        }

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced",
        include_images: bool = True,
    ) -> dict:
        """POST {base}/search → JSON dict. 일시 오류(502·503·504·네트워크) 재시도. mock 모드면 canned 결과."""
        if not self._use_real:
            return self._mock_search(query, max_results, include_images)

        async def _do() -> httpx.Response:
            resp = await self._http().post(
                f"{self.base_url}/search",
                json={
                    "api_key": self._api_key,
                    "query": query,
                    "search_depth": search_depth,
                    "include_images": include_images,
                    "max_results": min(max_results, 10),
                    "exclude_domains": self.exclude_domains,
                },
            )
            if resp.status_code in (502, 503, 504):
                resp.raise_for_status()
            return resp

        response = await retry(_do, base_delay=0.5, retryable=is_http_retryable)
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
