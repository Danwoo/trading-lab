from repositories.web.web_repository import WebRepository
from schemas.web.web_schema import WebSearchIn, WebSearchOut


class WebService:
    """Tavily 웹 검색 (순수 검색 데이터, LLM 없음)."""

    def __init__(self, web_repository: WebRepository):
        self.repository = web_repository

    async def search(self, params: WebSearchIn) -> WebSearchOut:
        return await self.repository.search(params)
