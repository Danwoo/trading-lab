"""Tavily 웹 검색 데이터 접근 (web = 외부 검색 store). WebClient 연결을 주입받아 조회 담당."""

from clients.web.web_client import WebClient
from schemas.web.web_schema import SearchResultOut, WebSearchIn, WebSearchOut


class WebRepository:
    def __init__(self, web_client: WebClient):
        self.client = web_client

    async def search(self, params: WebSearchIn) -> WebSearchOut:
        raw = await self.client.search(
            query=params.query,
            max_results=params.max_results,
            search_depth=params.search_depth,
            include_images=params.include_images,
        )

        results = []
        for item in raw.get("results", []):
            score = item.get("score", 0)
            if score < 0.15:
                continue
            results.append(
                SearchResultOut(
                    title=item.get("title", "")[:150],
                    content=item.get("content", "")[:500],
                    url=item.get("url", ""),
                    score=score,
                    published_date=item.get("published_date"),
                )
            )

        images = []
        if params.include_images:
            images = raw.get("images", []) or []

        return WebSearchOut(
            query=params.query,
            results=results,
            total_results=len(results),
            answer=raw.get("answer") or None,
            images=images,
        )
