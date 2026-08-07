import asyncio

import httpx
from clients.bm25.bm25_client import Bm25Client
from clients.embedding.embedding_client import EmbeddingClient
from clients.reranker.reranker_client import RerankerClient
from core.logger import logger
from fastapi.concurrency import run_in_threadpool
from repositories.vector_search.vector_search_milvus_repository import VectorSearchMilvusRepository
from schemas.vector_search.vector_search_schema import (
    ImageSearchIn,
    ImageSearchItem,
    ImageSearchOut,
    TopicSearchIn,
    TopicSearchItem,
    TopicSearchOut,
)
from utils.common.staged_search import staged_search
from utils.vector_search.mock_data import mock_image_out, mock_topic_out
from utils.vector_search.score_utils import (
    clean_file_url,
    image_hit_key,
    merge_weighted_hits,
    text_hit_key,
    to_plain_list,
)

PER_FIELD_LIMIT = 30
RERANK_POOL = 30
RERANK_DOC_CHARS = 2000
# (dense, doc_sparse, meta_sparse) — 원본 가중치 튜닝 결과 (meta_sparse 약화로 라우팅 정확도 개선)
WEIGHTS = (0.4, 0.5, 0.1)

# MOCK 폴백을 유발하는 인프라 장애 — Milvus/Redis/임베딩/리랭커 미가용 시 이 예외들로 표면화된다.
_INFRA_ERRORS = (ConnectionError, RuntimeError, httpx.HTTPError, OSError, TimeoutError)


class VectorSearchService:
    """hybrid 검색 오케스트레이션 — dense+sparse 인코딩 → Milvus 3 벡터장 검색 → 가중합 병합 → rerank.

    `USE_REAL_API=false`(기본) 또는 실 인프라 연결 실패 시 in-memory MOCK 금융 문서 스냅샷으로 폴백해
    API 키·Milvus·Redis 없이도 28개 tool 이 단독 동작한다 (mock_data.py).
    """

    def __init__(
        self,
        vector_search_repository: VectorSearchMilvusRepository,
        embedding_client: EmbeddingClient,
        reranker_client: RerankerClient,
        bm25_client: Bm25Client,
        use_real_api: bool = False,
    ):
        self.repository = vector_search_repository
        self.embedding = embedding_client
        self.reranker = reranker_client
        self.bm25 = bm25_client
        self.use_real_api = use_real_api

    async def topic_search(self, collection: str, params: TopicSearchIn) -> TopicSearchOut:
        if not self.use_real_api:
            return mock_topic_out(collection, params.source, params.top_k)
        # 단계적 검색: 전체 → 0건이면 핵심(query)만 남기고 source 필터를 통합(None)으로 완화
        relaxed = params.model_copy(update={"source": None})
        stages = [lambda: self._topic_search(collection, params)]
        if relaxed.model_dump() != params.model_dump():
            stages.append(lambda: self._topic_search(collection, relaxed))
        try:
            return await staged_search(stages)
        except _INFRA_ERRORS as e:
            logger.warning("topic_search 인프라 장애 — MOCK 폴백 (%s): %s", collection, e)
            return mock_topic_out(collection, params.source, params.top_k)

    async def _topic_search(self, collection: str, params: TopicSearchIn) -> TopicSearchOut:
        dense_vec, (doc_vec, meta_vec) = await asyncio.gather(
            self.embedding.embed_query(params.query),
            run_in_threadpool(self.bm25.embed_text_query, params.query),
        )
        d_hits, s_hits, m_hits = await run_in_threadpool(
            self.repository.search_text, collection, dense_vec, doc_vec, meta_vec, params.source, PER_FIELD_LIMIT
        )
        candidates = merge_weighted_hits(d_hits, s_hits, m_hits, WEIGHTS, text_hit_key)[:RERANK_POOL]
        ranked = await self._rerank(params.query, candidates, params.top_k)
        items = [
            TopicSearchItem(
                score=round(c["final_score"], 4),
                rerank=round(c["rerank_score"], 4) if c["rerank_score"] is not None else None,
                hybrid=round(c["hybrid_score"], 4),
                dense=round(c["dense_score"], 3),
                doc_sparse_score=round(c["doc_sparse_score"], 3),
                meta_sparse_score=round(c["meta_sparse_score"], 3),
                source=c.get("source"),
                book_id=c.get("book_id"),
                primary_code=c.get("primary_code"),
                topic_codes=to_plain_list(c.get("topic_codes")),
                l1l2_codes=to_plain_list(c.get("l1l2_codes")),
                file_nm=c.get("file_nm"),
                header_chain=c.get("header_chain"),
                text=(c.get("text") or "")[:800],
                question=(c.get("question") or "")[:300],
                answer=(c.get("answer") or "")[:1000],
            )
            for c in ranked
        ]
        return TopicSearchOut(data=items, total_count=len(items))

    async def image_search(self, collection: str, params: ImageSearchIn) -> ImageSearchOut:
        if not self.use_real_api:
            return mock_image_out(collection, params.top_k)
        try:
            return await self._image_search(collection, params)
        except _INFRA_ERRORS as e:
            logger.warning("image_search 인프라 장애 — MOCK 폴백 (%s): %s", collection, e)
            return mock_image_out(collection, params.top_k)

    async def _image_search(self, collection: str, params: ImageSearchIn) -> ImageSearchOut:
        dense_vec, (doc_vec, meta_vec) = await asyncio.gather(
            self.embedding.embed_query(params.query),
            run_in_threadpool(self.bm25.embed_image_query, params.query),
        )
        d_hits, s_hits, m_hits = await run_in_threadpool(
            self.repository.search_image, collection, dense_vec, doc_vec, meta_vec, PER_FIELD_LIMIT
        )
        candidates = merge_weighted_hits(d_hits, s_hits, m_hits, WEIGHTS, image_hit_key)[:RERANK_POOL]
        ranked = await self._rerank(params.query, candidates, params.top_k)
        items = [
            ImageSearchItem(
                score=round(c["final_score"], 4),
                rerank=round(c["rerank_score"], 4) if c["rerank_score"] is not None else None,
                hybrid=round(c["hybrid_score"], 4),
                book_id=c.get("book_id"),
                seq=c.get("seq"),
                file_url=clean_file_url(c.get("file_url")),
                file_nm=c.get("file_nm"),
                primary_code=c.get("primary_code"),
                topic_codes=to_plain_list(c.get("topic_codes")),
                summary_caption=(c.get("summary_caption") or "")[:500],
                detailed_caption=(c.get("detailed_caption") or "")[:1500],
            )
            for c in ranked
        ]
        return ImageSearchOut(data=items, total_count=len(items))

    async def _rerank(self, query: str, candidates: list[dict], top_k: int) -> list[dict]:
        """후보를 reranker 로 재정렬 — 실패(HTTP 오류·timeout) 시 hybrid 점수 폴백 (검색 자체는 살린다)."""
        if not candidates:
            return []
        docs = [(c.get("text") or "")[:RERANK_DOC_CHARS] for c in candidates]
        try:
            results = await self.reranker.rerank(query, docs, top_n=top_k)
        except httpx.HTTPError as e:
            logger.warning(f"rerank 실패 — hybrid 점수 폴백: {e}")
            results = []
        if not results:
            for c in candidates:
                c["final_score"] = c["hybrid_score"]
            return candidates[:top_k]
        ranked: list[dict] = []
        for r in results:
            idx = r.get("index")
            if idx is None or idx >= len(candidates):
                continue
            c = candidates[idx]
            c["rerank_score"] = float(r.get("relevance_score", 0.0))
            c["final_score"] = c["rerank_score"]
            ranked.append(c)
        return ranked[:top_k]
