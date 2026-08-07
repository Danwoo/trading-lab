from typing import Literal

from pydantic import BaseModel, Field


class WebSearchIn(BaseModel):
    query: str = Field(description="검색어")
    max_results: int = Field(default=5, ge=1, le=10, description="최대 결과 수")
    search_depth: Literal["basic", "advanced"] = Field(
        default="advanced", description="검색 깊이 (basic=빠름, advanced=깊음)"
    )
    include_images: bool = Field(default=True, description="이미지 포함 여부")


class SearchResultOut(BaseModel):
    title: str = Field(description="제목")
    content: str = Field(description="내용 (500자 제한)")
    url: str = Field(description="URL")
    score: float = Field(description="관련도 점수")
    published_date: str | None = Field(default=None, description="발행일")


class WebSearchOut(BaseModel):
    query: str = Field(description="원본 검색어")
    results: list[SearchResultOut] = Field(description="검색 결과 목록")
    total_results: int = Field(description="전체 결과 수")
    answer: str | None = Field(default=None, description="Tavily 생성 답변")
    images: list[str] = Field(default_factory=list, description="이미지 URL 목록")
