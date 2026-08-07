from repositories.news.news_repository import NewsRepository
from schemas.news.news_schema import (
    NewsCompanyIn,
    NewsDataOut,
    NewsDetailIn,
    NewsDisclosureIn,
    NewsSearchIn,
    NewsSentimentIn,
)
from utils.common.staged_search import staged_search


class NewsService:
    """금융 뉴스 검색·종목 뉴스·센티먼트·공시연계 조회 (순수 뉴스 데이터, LLM 없음)."""

    def __init__(self, news_repository: NewsRepository):
        self.repository = news_repository

    async def news_search(self, params: NewsSearchIn) -> NewsDataOut:
        # 단계적 검색: 전체 조건 → 0건이면 핵심 키워드(keyword)만 남기고 카테고리 완화
        relaxed = params.model_copy(update={"category": None})
        stages = [lambda: self.repository.news_search(params)]
        if relaxed.model_dump() != params.model_dump():
            stages.append(lambda: self.repository.news_search(relaxed))
        return await staged_search(stages)

    async def news_company(self, params: NewsCompanyIn) -> NewsDataOut:
        # 단계적 검색: 전체 조건 → 0건이면 카테고리 필터를 풀어 종목 전체 뉴스로 완화
        relaxed = params.model_copy(update={"category": None})
        stages = [lambda: self.repository.news_company(params)]
        if relaxed.model_dump() != params.model_dump():
            stages.append(lambda: self.repository.news_company(relaxed))
        return await staged_search(stages)

    async def news_detail(self, params: NewsDetailIn) -> NewsDataOut:
        return await self.repository.news_detail(params)

    async def news_sentiment(self, params: NewsSentimentIn) -> NewsDataOut:
        return await self.repository.news_sentiment(params)

    async def news_disclosure(self, params: NewsDisclosureIn) -> NewsDataOut:
        # 단계적 검색: 전체 조건 → 0건이면 공시 유형 필터를 풀어 종목 전체 공시연계 뉴스로 완화
        relaxed = params.model_copy(update={"disclosure_type": None})
        stages = [lambda: self.repository.news_disclosure(params)]
        if relaxed.model_dump() != params.model_dump():
            stages.append(lambda: self.repository.news_disclosure(relaxed))
        return await staged_search(stages)
