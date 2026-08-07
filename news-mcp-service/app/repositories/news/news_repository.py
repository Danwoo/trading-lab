"""금융 뉴스 데이터 접근 (news = 외부 검색 store). NewsClient 연결을 주입받아 조회 담당.

목업·실데이터 어느 경로든 client 가 동일한 응답 봉투를 돌려주므로 여기서는 items 추출·total_count 정규화만 한다.
"""

from clients.news.news_client import NewsClient
from schemas.news.news_schema import (
    NewsCompanyIn,
    NewsDataOut,
    NewsDetailIn,
    NewsDisclosureIn,
    NewsSearchIn,
    NewsSentimentIn,
)


class NewsRepository:
    def __init__(self, news_client: NewsClient):
        self.client = news_client

    @staticmethod
    def _parse_items(raw: dict) -> tuple[list[dict], int]:
        body = raw.get("response", {}).get("body", {}) or {}
        total = int(body.get("totalCount", 0) or 0)
        items_data = body.get("items", {}) or {}
        item = items_data.get("item", [])
        if isinstance(item, dict):
            item = [item]
        return item or [], total

    async def news_search(self, params: NewsSearchIn) -> NewsDataOut:
        raw = await self.client.news_search(
            keyword=params.keyword,
            category=params.category,
            page_no=params.page_no,
            num_of_rows=params.num_of_rows,
        )
        data, total = self._parse_items(raw)
        return NewsDataOut(data=data, total_count=total)

    async def news_company(self, params: NewsCompanyIn) -> NewsDataOut:
        raw = await self.client.news_company(
            ticker=params.ticker,
            company_name=params.company_name,
            category=params.category,
            page_no=params.page_no,
            num_of_rows=params.num_of_rows,
        )
        data, total = self._parse_items(raw)
        return NewsDataOut(data=data, total_count=total)

    async def news_detail(self, params: NewsDetailIn) -> NewsDataOut:
        raw = await self.client.news_detail(
            article_id=params.article_id,
            page_no=params.page_no,
            num_of_rows=params.num_of_rows,
        )
        data, total = self._parse_items(raw)
        return NewsDataOut(data=data, total_count=total)

    async def news_sentiment(self, params: NewsSentimentIn) -> NewsDataOut:
        raw = await self.client.news_sentiment(
            ticker=params.ticker,
            company_name=params.company_name,
            page_no=params.page_no,
            num_of_rows=params.num_of_rows,
        )
        data, total = self._parse_items(raw)
        return NewsDataOut(data=data, total_count=total)

    async def news_disclosure(self, params: NewsDisclosureIn) -> NewsDataOut:
        raw = await self.client.news_disclosure(
            ticker=params.ticker,
            company_name=params.company_name,
            disclosure_type=params.disclosure_type,
            page_no=params.page_no,
            num_of_rows=params.num_of_rows,
        )
        data, total = self._parse_items(raw)
        return NewsDataOut(data=data, total_count=total)
