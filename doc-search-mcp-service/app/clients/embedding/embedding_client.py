"""OpenAI 호환 임베딩 API(bge-m3) 호출 — persistent AsyncClient + 일시 오류(502·503·504·네트워크) 재시도."""

import httpx
from utils.common.retry_utils import is_http_retryable, retry

# 임베딩 요청 1건에 실어 보내는 입력(청크) 수. 이 경로에서 가장 낮은 상한을 그대로 쓴다:
# text-embeddings-inference(TEI — 자체 호스팅 OpenAI 호환 서버) 의 `--max-client-batch-size`
# 기본값 **32** ("Control the maximum number of inputs that a client can send in a single request",
# https://huggingface.co/docs/text-embeddings-inference/cli_arguments). 초과분은 서버가 요청 자체를
# 거절하므로 클라이언트가 나눠 보내야 한다.
# 다른 후보 프로바이더의 상한은 이보다 느슨하거나 없어서, 32 면 양쪽 모두 안전하다:
# - Jina Embeddings API(CONTEXT.md 2026-07-27 데모 서빙 후보): "There is no batch size limit for
#   either the Embeddings or Reranker APIs" (https://jina.ai/embeddings/) — 대신 분당 토큰(TPM)
#   과금·제한이라 요청당 개수 상한이 없다. 32 × 청크 1024자 ≈ 최대 3.3만 토큰/요청으로 free tier
#   100K TPM 안에 든다.
# - TEI `--payload-limit` 기본 2MB 대비: 32 × 1024자 × (UTF-8 한글 3바이트) ≈ 98KB 로 여유.
_EMBED_BATCH_SIZE = 32


class EmbeddingClient:
    def __init__(self, config, timeout: float = 30.0):
        self.base_url = config.OPENAI_EMBEDDING_URL.rstrip("/")
        self.model = config.OPENAI_EMBEDDING_MODEL_NAME
        self._api_key = config.OPENAI_EMBEDDING_API_KEY
        self._timeout = httpx.Timeout(timeout, connect=5.0)
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
            )
        return self._client

    async def embed_query(self, text: str) -> list[float]:
        async def _do() -> httpx.Response:
            resp = await self._http().post(f"{self.base_url}/embeddings", json={"model": self.model, "input": [text]})
            if resp.status_code in (502, 503, 504):
                resp.raise_for_status()
            return resp

        resp = await retry(_do, base_delay=0.5, retryable=is_http_retryable)
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """문서 청크 배치 임베딩 (인제스트용) — embed_query 와 동일 엔드포인트·재시도. 반환은 입력 순서 보존.

        입력이 아무리 많아도 요청 1건에는 `_EMBED_BATCH_SIZE` 개까지만 싣고 순차로 나눠 보낸다
        (서버 입력 개수 상한 초과 거절 방지). 배치를 동시에 던지지 않는 것은 의도다 — 색인 1건이
        임베딩 서버를 독점해 검색 경로(embed_query)를 굶기지 않게 한다.
        """
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH_SIZE):
            embeddings.extend(await self._embed_batch(texts[start : start + _EMBED_BATCH_SIZE]))
        return embeddings

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """요청 1건 — OpenAI 호환 응답의 data 는 순서 보장이 없어 각 항목의 index 로 재정렬한다."""

        async def _do() -> httpx.Response:
            resp = await self._http().post(f"{self.base_url}/embeddings", json={"model": self.model, "input": texts})
            if resp.status_code in (502, 503, 504):
                resp.raise_for_status()
            return resp

        resp = await retry(_do, base_delay=0.5, retryable=is_http_retryable)
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
