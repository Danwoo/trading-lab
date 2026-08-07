"""Redis 의 BM25 sparse 모델(pickle) 로드·캐싱 + Kiwi 명사 정규화 → 쿼리 sparse 인코딩 (전부 sync — 호출측이 run_in_threadpool).

모델은 인덱싱 파이프라인(example-ai-lab topic_db)이 `preprocess.BM25Wrapper` 인스턴스로 저장 — 동일 인터페이스의
`Bm25Wrapper` 로 매핑해 unpickle 한다 (fn=milvus_model BM25EmbeddingFunction 은 패키지 동일 경로라 그대로 복원).
"""

import io
import pickle
from pathlib import Path

from core.logger import logger
from kiwipiepy import Kiwi
from milvus_model.sparse.bm25 import BM25EmbeddingFunction
from redis import Redis

TEXT_DOC_PREFIX = "topic_document_sparse_embedding_"
TEXT_META_PREFIX = "topic_metadata_sparse_embedding_"
IMAGE_DOC_PREFIX = "topic_image_document_sparse_embedding_"
IMAGE_META_PREFIX = "topic_image_metadata_sparse_embedding_"

# 인덱싱 측과 동일 금융 용어 사용자 사전 — 누락 시 BM25 vocabulary 불일치로 sparse 품질 저하
KIWI_DICT = Path(__file__).resolve().parent / "finance.dict"


class Bm25Wrapper:
    """인덱싱 측 BM25Wrapper 와 동일 attribute/메서드 시그니처 — unpickle 복원 대상."""

    fn: BM25EmbeddingFunction

    def embed_query(self, q: str) -> dict[int, float]:
        m = self.fn.encode_queries([q])
        return self._to_dict(m, 0)

    @staticmethod
    def _to_dict(csr, row_idx: int) -> dict[int, float]:
        # Milvus SPARSE_FLOAT_VECTOR 는 음수 거부 — 양수 가중치만 유지
        start, end = int(csr.indptr[row_idx]), int(csr.indptr[row_idx + 1])
        indices = csr.indices[start:end]
        data = csr.data[start:end]
        return {int(i): float(v) for i, v in zip(indices, data, strict=False) if v > 0}


class _Bm25Unpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if name == "BM25Wrapper":
            return Bm25Wrapper
        return super().find_class(module, name)


class Bm25Client:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self._models: dict[str, Bm25Wrapper] = {}
        self._kiwi: Kiwi | None = None

    def _get_kiwi(self) -> Kiwi:
        if self._kiwi is None:
            kiwi = Kiwi()
            kiwi.space_tolerance = 2
            if KIWI_DICT.exists():
                kiwi.load_user_dictionary(str(KIWI_DICT))
            else:
                logger.warning(f"Kiwi 금융 용어 사용자 사전 없음 — sparse 검색 품질 저하 위험: {KIWI_DICT}")
            self._kiwi = kiwi
        return self._kiwi

    def normalize_text(self, text: str) -> str:
        """명사 POS(NNG/NNP/SL/SN)만 추출해 공백 결합 — 인덱싱 측 normalize_text 와 동일해야 vocabulary 가 맞는다."""
        if not text:
            return ""
        tokens = self._get_kiwi().tokenize(text)
        return " ".join(t.form for t in tokens if t.tag in ("NNG", "NNP", "SL", "SN"))

    def _latest_key(self, prefix: str) -> str | None:
        """`prefix*` 중 timestamp 가장 큰 key (인덱싱이 timestamp suffix 로 버전 적재)."""
        keys = [k.decode() if isinstance(k, bytes) else k for k in self.redis.scan_iter(match=f"{prefix}*", count=200)]
        return max(keys) if keys else None

    def _load_model(self, prefix: str) -> Bm25Wrapper:
        if prefix in self._models:
            return self._models[prefix]
        key = self._latest_key(prefix)
        if key is None:
            raise RuntimeError(
                f"Redis 에 BM25 모델이 없습니다 (prefix={prefix}) — 인덱싱 파이프라인을 먼저 실행하세요."
            )
        raw = self.redis.get(key)
        if raw is None:
            raise RuntimeError(f"Redis BM25 모델 key 가 사라졌습니다: {key}")
        model = _Bm25Unpickler(io.BytesIO(raw)).load()
        self._models[prefix] = model
        logger.info(f"BM25 모델 로드: {key}")
        return model

    def embed_text_query(self, query: str) -> tuple[dict[int, float], dict[int, float]]:
        """text 컬렉션용 (document_sparse, metadata_sparse) 쿼리 벡터."""
        q = self.normalize_text(query) or query
        return self._load_model(TEXT_DOC_PREFIX).embed_query(q), self._load_model(TEXT_META_PREFIX).embed_query(q)

    def embed_image_query(self, query: str) -> tuple[dict[int, float], dict[int, float]]:
        """image 컬렉션용 (document_sparse, metadata_sparse) 쿼리 벡터 — 별도 fit corpus (`topic_image_*`)."""
        q = self.normalize_text(query) or query
        return self._load_model(IMAGE_DOC_PREFIX).embed_query(q), self._load_model(IMAGE_META_PREFIX).embed_query(q)
