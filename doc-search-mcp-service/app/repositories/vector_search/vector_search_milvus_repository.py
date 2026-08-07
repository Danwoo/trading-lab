"""Milvus 토픽/이미지 컬렉션 검색 접근 (Milvus = 벡터 store, 연결 주입). 컬렉션별 3개 벡터장 sync search."""

from pymilvus import MilvusClient

TEXT_OUTPUT_FIELDS = [
    "text",
    "source",
    "book_id",
    "file_nm",
    "primary_l1",
    "primary_code",
    "topic_codes",
    "l1l2_codes",
    "header_chain",
    "chunk_idx",
    "question",
    "answer",
    "v3_v4",
]

IMAGE_OUTPUT_FIELDS = [
    "text",
    "book_id",
    "seq",
    "file_url",
    "file_nm",
    "primary_l1",
    "primary_code",
    "topic_codes",
    "l1l2_codes",
    "summary_caption",
    "detailed_caption",
]

# 인덱싱 스키마와 동일 metric — dense HNSW/COSINE, sparse SPARSE_INVERTED_INDEX/IP
_FIELD_SEARCH_PARAMS = {
    "dense_vector": {"metric_type": "COSINE", "params": {"ef": 200}},
    "document_sparse_vector": {"metric_type": "IP", "params": {}},
    "metadata_sparse_vector": {"metric_type": "IP", "params": {}},
}


class VectorSearchMilvusRepository:
    def __init__(self, milvus_client: MilvusClient | None):
        self.milvus = milvus_client

    def _search_field(
        self,
        collection: str,
        anns_field: str,
        vector: list[float] | dict[int, float],
        output_fields: list[str],
        limit: int,
        expr: str = "",
    ) -> list[dict]:
        res = self.milvus.search(
            collection_name=collection,
            data=[vector],
            anns_field=anns_field,
            search_params=_FIELD_SEARCH_PARAMS[anns_field],
            limit=limit,
            filter=expr,
            output_fields=output_fields,
        )
        return [{"score": float(hit["distance"]), "pk": hit["pk"], **dict(hit.get("entity") or {})} for hit in res[0]]

    def _search_three_fields(
        self,
        collection: str,
        dense_vector: list[float],
        doc_sparse_vector: dict[int, float],
        meta_sparse_vector: dict[int, float],
        output_fields: list[str],
        per_field_limit: int,
        expr: str = "",
    ) -> tuple[list[dict], list[dict], list[dict]]:
        if self.milvus is None:
            raise ConnectionError("Milvus 벡터DB에 연결할 수 없습니다.")
        self.milvus.load_collection(collection)
        return (
            self._search_field(collection, "dense_vector", dense_vector, output_fields, per_field_limit, expr),
            self._search_field(
                collection, "document_sparse_vector", doc_sparse_vector, output_fields, per_field_limit, expr
            ),
            self._search_field(
                collection, "metadata_sparse_vector", meta_sparse_vector, output_fields, per_field_limit, expr
            ),
        )

    def search_text(
        self,
        collection: str,
        dense_vector: list[float],
        doc_sparse_vector: dict[int, float],
        meta_sparse_vector: dict[int, float],
        source: str | None = None,
        per_field_limit: int = 30,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """text 컬렉션(topic_*) 3 벡터장 검색 → (dense_hits, doc_sparse_hits, meta_sparse_hits)."""
        expr = f'source == "{source}"' if source else ""
        return self._search_three_fields(
            collection, dense_vector, doc_sparse_vector, meta_sparse_vector, TEXT_OUTPUT_FIELDS, per_field_limit, expr
        )

    def search_image(
        self,
        collection: str,
        dense_vector: list[float],
        doc_sparse_vector: dict[int, float],
        meta_sparse_vector: dict[int, float],
        per_field_limit: int = 30,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """image 컬렉션(image_*) 3 벡터장 검색 → (dense_hits, doc_sparse_hits, meta_sparse_hits)."""
        return self._search_three_fields(
            collection, dense_vector, doc_sparse_vector, meta_sparse_vector, IMAGE_OUTPUT_FIELDS, per_field_limit
        )
