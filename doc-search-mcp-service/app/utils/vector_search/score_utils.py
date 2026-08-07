"""hybrid 점수·필드 순수함수 — log+min-max 정규화 / 3 벡터장 가중합 병합·중복제거 / 필드 정규화. IO 없음."""

import math
import re
from collections.abc import Callable


def log_minmax(scores: list[float]) -> list[float]:
    """log + min-max 정규화 (sparse 점수가 dense 를 압도하는 것 완화)."""
    if not scores:
        return []
    log_s = [math.log(max(s, 0) + 1.0) for s in scores]
    mn, mx = min(log_s), max(log_s)
    if mx - mn < 1e-9:
        return [0.0 for _ in log_s]
    return [(x - mn) / (mx - mn) for x in log_s]


def text_hit_key(h: dict) -> tuple:
    return (h.get("book_id"), h.get("chunk_idx"), h.get("source"), (h.get("text") or "")[:60])


def image_hit_key(h: dict) -> tuple:
    return (h.get("book_id"), h.get("seq"), (h.get("file_url") or "")[:60])


def merge_weighted_hits(
    dense_hits: list[dict],
    doc_sparse_hits: list[dict],
    meta_sparse_hits: list[dict],
    weights: tuple[float, float, float],
    key_fn: Callable[[dict], tuple],
) -> list[dict]:
    """벡터장별 결과를 정규화 → key 중복제거 + 가중합(hybrid_score) → 내림차순 정렬.

    각 항목에 dense_score/doc_sparse_score/meta_sparse_score(정규화값, 중복 시 max)
    + hybrid_score + rerank_score(None) + final_score(0.0) 필드를 부여한다.
    """
    w_d, w_s, w_m = weights
    merged: dict[tuple, dict] = {}
    for hits, w, field in (
        (dense_hits, w_d, "dense_score"),
        (doc_sparse_hits, w_s, "doc_sparse_score"),
        (meta_sparse_hits, w_m, "meta_sparse_score"),
    ):
        norm = log_minmax([h["score"] for h in hits])
        for h, n in zip(hits, norm, strict=False):
            k = key_fn(h)
            if k not in merged:
                merged[k] = {
                    **h,
                    "dense_score": 0.0,
                    "doc_sparse_score": 0.0,
                    "meta_sparse_score": 0.0,
                    "hybrid_score": 0.0,
                    "rerank_score": None,
                    "final_score": 0.0,
                }
            merged[k][field] = max(merged[k][field], n)
            merged[k]["hybrid_score"] += w * n
    return sorted(merged.values(), key=lambda x: -x["hybrid_score"])


def to_plain_list(v) -> list | None:
    """pymilvus 의 RepeatedScalarContainer 등 → JSON 직렬화 가능한 일반 list."""
    if v is None:
        return None
    try:
        return list(v)
    except TypeError:
        return v


_SRC_ATTR = re.compile(r"""src\s*=\s*["']?([^"'<>\s]+)""", re.IGNORECASE)


def clean_file_url(v: str | None) -> str | None:
    """Milvus 원본 file 컬럼의 HTML 조각(`src="..."`, 닫는 따옴표 누락 포함)에서 순수 URL/경로만 추출.

    원본 데이터는 손대지 않고 MCP 응답값만 정제한다. `src=` 없으면 양끝 따옴표/공백만 제거.
    """
    if not v:
        return v
    m = _SRC_ATTR.search(v)
    cleaned = (m.group(1) if m else v).strip().strip("\"'")
    return cleaned or None
