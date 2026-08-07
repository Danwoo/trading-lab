from typing import Literal

from pydantic import BaseModel, Field


class NewsPageParams(BaseModel):
    page_no: int = Field(default=1, description="페이지 번호")
    num_of_rows: int = Field(default=10, ge=1, le=30, description="페이지당 결과 수")


class NewsSearchIn(NewsPageParams):
    keyword: str | None = Field(default=None, description="검색 키워드 (기사 제목·본문 매칭)")
    category: str | None = Field(default=None, description="뉴스 카테고리 (예: 실적, 공시, 시장, M&A, 거시)")


class NewsCompanyIn(NewsPageParams):
    ticker: str | None = Field(default=None, description="종목 코드 (예: 005930, AAPL)")
    company_name: str | None = Field(default=None, description="종목명 (예: 삼성전자, Apple)")
    category: str | None = Field(default=None, description="뉴스 카테고리 필터 (선택)")


class NewsDetailIn(NewsPageParams):
    article_id: str = Field(description="기사 ID ('N' + 9자리 숫자, 예: N000012345)")


class NewsSentimentIn(NewsPageParams):
    ticker: str | None = Field(default=None, description="종목 코드 (예: 005930, AAPL)")
    company_name: str | None = Field(default=None, description="종목명 (예: 삼성전자, Apple)")


class NewsDisclosureIn(NewsPageParams):
    ticker: str | None = Field(default=None, description="종목 코드 (예: 005930, AAPL)")
    company_name: str | None = Field(default=None, description="종목명 (예: 삼성전자, Apple)")
    disclosure_type: Literal["실적", "배당", "지분", "M&A", "유상증자", "기타"] | None = Field(
        default=None, description="공시 유형 필터. 미지정 시 전체"
    )


class NewsDataOut(BaseModel):
    data: list[dict] = Field(default_factory=list, description="뉴스 검색 결과 목록")
    total_count: int = Field(default=0, description="전체 결과 수")
