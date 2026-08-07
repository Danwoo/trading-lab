"""OpenAI 호환 reranker API(bge-reranker-v2-m3) 호출 — URL 은 /rerank suffix 포함 전체 endpoint.

실패 시 hybrid 점수 폴백은 service 책임 — 여기서는 예외를 그대로 전파한다.
"""

import httpx
from utils.common.retry_utils import is_http_retryable, retry


class RerankerClient:
    def __init__(self, config, timeout: float = 10.0):
        self.url = config.OPENAI_RERANKER_URL
        self.model = config.OPENAI_RERANKER_MODEL_NAME
        self._api_key = config.OPENAI_API_KEY
        self._timeout = httpx.Timeout(timeout, connect=5.0)
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
            )
        return self._client

    async def rerank(self, query: str, documents: list[str], top_n: int) -> list[dict]:
        """문서를 query 관련성 순으로 재정렬 — [{"index": int, "relevance_score": float, ...}]."""
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": top_n,
            "return_documents": True,
        }

        async def _do() -> httpx.Response:
            resp = await self._http().post(self.url, json=payload)
            if resp.status_code in (502, 503, 504):
                resp.raise_for_status()
            return resp

        resp = await retry(_do, base_delay=0.5, retryable=is_http_retryable)
        resp.raise_for_status()
        return resp.json().get("results") or []

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
