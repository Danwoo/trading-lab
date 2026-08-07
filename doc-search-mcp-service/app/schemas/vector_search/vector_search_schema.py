from typing import Literal

from pydantic import BaseModel, Field


class TopicSearchIn(BaseModel):
    query: str = Field(description="자연어 검색 쿼리 (한국어)")
    top_k: int = Field(default=5, ge=1, le=30, description="반환 결과 수")
    source: Literal["html", "label"] | None = Field(
        default=None, description="소스 필터 — html: 책 본문 청크, label: Q&A 라벨. 미지정 시 통합 검색"
    )


class ImageSearchIn(BaseModel):
    query: str = Field(description="자연어 검색 쿼리 (한국어)")
    top_k: int = Field(default=5, ge=1, le=30, description="반환 결과 수")


class TopicSearchItem(BaseModel):
    score: float = Field(description="최종 점수 — rerank 성공 시 relevance_score(0~1), 실패 시 hybrid 가중합 폴백")
    rerank: float | None = Field(default=None, description="reranker relevance_score. null 이면 rerank 미적용(폴백)")
    hybrid: float = Field(description="dense+sparse 가중합 점수 (정규화 후 0.4/0.5/0.1)")
    dense: float = Field(description="dense(bge-m3) 정규화 점수 기여")
    doc_sparse_score: float = Field(description="본문 BM25 sparse 정규화 점수 기여")
    meta_sparse_score: float = Field(description="메타데이터 BM25 sparse 정규화 점수 기여")
    source: str | None = Field(default=None, description="청크 출처 — html(책 본문) 또는 label(Q&A)")
    book_id: int | None = Field(default=None, description="책 ID (label 청크는 0)")
    primary_code: str | None = Field(default=None, description="주 토픽 분류 코드")
    topic_codes: list[str] | None = Field(default=None, description="토픽 분류 코드 목록")
    l1l2_codes: list[str] | None = Field(default=None, description="L1.L2 카테고리 코드 목록")
    file_nm: str | None = Field(default=None, description="원본 파일명(책 제목)")
    header_chain: str | None = Field(default=None, description="문서 내 헤더 경로 (장>절>항)")
    text: str = Field(default="", description="청크 본문 (최대 800자)")
    question: str = Field(default="", description="Q&A 질문 (label 청크 전용, 최대 300자)")
    answer: str = Field(default="", description="Q&A 답변 (label 청크 전용, 최대 1000자)")


class ImageSearchItem(BaseModel):
    score: float = Field(description="최종 점수 — rerank 성공 시 relevance_score(0~1), 실패 시 hybrid 가중합 폴백")
    rerank: float | None = Field(default=None, description="reranker relevance_score. null 이면 rerank 미적용(폴백)")
    hybrid: float = Field(description="dense+sparse 가중합 점수 (정규화 후 0.4/0.5/0.1)")
    book_id: int | None = Field(default=None, description="책 ID")
    seq: int | None = Field(default=None, description="책 내 이미지 순번")
    file_url: str | None = Field(default=None, description="이미지 URL")
    file_nm: str | None = Field(default=None, description="원본 파일명(책 제목)")
    primary_code: str | None = Field(default=None, description="주 토픽 분류 코드")
    topic_codes: list[str] | None = Field(default=None, description="토픽 분류 코드 목록")
    summary_caption: str = Field(default="", description="이미지 요약 캡션 (최대 500자)")
    detailed_caption: str = Field(default="", description="이미지 상세 캡션 (최대 1500자)")


class TopicSearchOut(BaseModel):
    data: list[TopicSearchItem] = Field(default_factory=list, description="검색 결과 목록 (score 내림차순)")
    total_count: int = Field(default=0, description="반환 결과 수")


class ImageSearchOut(BaseModel):
    data: list[ImageSearchItem] = Field(default_factory=list, description="검색 결과 목록 (score 내림차순)")
    total_count: int = Field(default=0, description="반환 결과 수")
