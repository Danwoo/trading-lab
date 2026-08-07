"""금융 뉴스 데이터 연결 (transport) — 기본은 인메모리 목업, USE_REAL_API=true 시 뉴스 벤더 HTTP 호출.

데이터 접근(items 추출·정규화)은 repositories/news 의 NewsRepository 담당.
이 클래스는 SQL 엔진·Milvus 연결처럼 '연결'만 제공한다 — 목업 경로는 외부 의존 0이라 API 키 없이 즉시 동작하고,
실데이터 경로는 단일 GET + 재시도 + 연결 풀 재사용으로 뉴스 벤더 API 를 감싼다.
"""

from __future__ import annotations

import httpx
from clients.news import news_fixtures as fx
from utils.common.retry_utils import is_http_retryable, retry


class NewsClient:
    def __init__(self, config, timeout: float = 30.0):
        self.use_real_api = bool(getattr(config, "USE_REAL_API", False))
        self.base_url = (config.NEWS_API_BASE_URL or "").rstrip("/")
        self._api_key = config.NEWS_API_KEY or ""
        self._timeout = httpx.Timeout(timeout, connect=5.0)
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    @staticmethod
    def _envelope(items: list[dict], total: int | None = None) -> dict:
        """repository._parse_items 가 읽는 공통 응답 봉투 — 실/목업 경로 동일 형태."""
        return {
            "response": {
                "body": {
                    "totalCount": total if total is not None else len(items),
                    "items": {"item": items},
                }
            }
        }

    @staticmethod
    def _page(items: list[dict], page_no: int, num_of_rows: int) -> list[dict]:
        size = min(num_of_rows, 30)
        start = max(page_no - 1, 0) * size
        return items[start : start + size]

    @staticmethod
    def _map_article(a: dict) -> dict:
        """벤더 기사 한 건 → 목업과 동일 필드 스키마로 정규화 (원본 키는 보존)."""
        if not isinstance(a, dict):
            return {}
        src = a.get("source")
        if isinstance(src, dict):
            src = src.get("name") or src.get("title") or ""
        return {
            **a,
            "article_id": a.get("article_id") or a.get("id") or a.get("uuid") or "",
            "title": a.get("title") or "",
            "summary": a.get("summary") or a.get("description") or a.get("content") or "",
            "url": a.get("url") or a.get("link") or "",
            "source": src or a.get("press") or "",
            "published_at": a.get("published_at") or a.get("publishedAt") or a.get("pubDate") or "",
            "company_name": a.get("company_name") or a.get("company") or "",
        }

    @classmethod
    def _wrap_vendor(cls, raw: dict) -> dict:
        """벤더 원본 JSON → repository._parse_items 가 읽는 _envelope 형태로 정규화.

        벤더별 상이한 items/total 키를 흡수해(articles·items·results·data / totalResults·totalCount·total)
        실데이터가 조용히 빈 결과로 흘러가는 것을 막는다.
        """
        items: list = []
        total: int | None = None
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            for key in ("articles", "items", "results", "data", "article"):
                val = raw.get(key)
                if isinstance(val, dict):  # {"item": [...]} 래퍼 또는 단건 기사 오브젝트
                    val = val.get("item", val) if "item" in val else [val]
                if isinstance(val, list):
                    items = val
                    break
            if not items and (raw.get("title") or raw.get("id") or raw.get("article_id")):
                items = [raw]  # 상세 단건이 최상위 기사 오브젝트로 오는 벤더
            for tkey in ("totalResults", "totalCount", "total"):
                if raw.get(tkey) is not None:
                    total = int(raw[tkey] or 0)
                    break
        mapped = [cls._map_article(a) for a in items if isinstance(a, dict)]
        return cls._envelope(mapped, total if total is not None else len(mapped))

    async def _get(self, endpoint: str, params: dict) -> dict:
        """GET {base}/{endpoint} → JSON dict. 일시 오류(502·503·504·네트워크) 재시도.

        실데이터 경로 전용 — 벤더별 응답 키 매핑은 NewsRepository 가 _envelope 형태로 정규화한다.
        """
        query = {k: v for k, v in params.items() if v is not None}
        if self._api_key:
            query["apiKey"] = self._api_key

        async def _do() -> httpx.Response:
            resp = await self._http().get(f"{self.base_url}/{endpoint}", params=query)
            if resp.status_code in (502, 503, 504):
                resp.raise_for_status()
            return resp

        response = await retry(_do, base_delay=0.5, retryable=is_http_retryable)
        response.raise_for_status()
        return response.json()

    async def news_search(
        self,
        keyword: str | None = None,
        category: str | None = None,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> dict:
        if self.use_real_api:
            raw = await self._get(
                "search", {"q": keyword, "category": category, "page": page_no, "pageSize": num_of_rows}
            )
            return self._wrap_vendor(raw)
        items = fx.all_articles()
        if keyword:
            kw = keyword.lower()
            items = [a for a in items if kw in a["title"].lower() or kw in a["summary"].lower()]
        if category:
            items = [a for a in items if a.get("category") == category]
        return self._envelope(self._page(items, page_no, num_of_rows), total=len(items))

    async def news_company(
        self,
        ticker: str | None = None,
        company_name: str | None = None,
        category: str | None = None,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> dict:
        if self.use_real_api:
            raw = await self._get(
                "company",
                {
                    "ticker": ticker,
                    "name": company_name,
                    "category": category,
                    "page": page_no,
                    "pageSize": num_of_rows,
                },
            )
            return self._wrap_vendor(raw)
        tk = fx.resolve_ticker(ticker, company_name)
        items = fx.articles_for(tk) if tk else []
        if category:
            items = [a for a in items if a.get("category") == category]
        return self._envelope(self._page(items, page_no, num_of_rows), total=len(items))

    async def news_detail(
        self,
        article_id: str,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> dict:
        if self.use_real_api:
            raw = await self._get("article", {"id": article_id})
            return self._wrap_vendor(raw)
        article = fx.article_by_id(article_id)
        items = [article] if article else []
        return self._envelope(items, total=len(items))

    async def news_sentiment(
        self,
        ticker: str | None = None,
        company_name: str | None = None,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> dict:
        if self.use_real_api:
            raw = await self._get(
                "sentiment", {"ticker": ticker, "name": company_name, "page": page_no, "pageSize": num_of_rows}
            )
            return self._wrap_vendor(raw)
        tk = fx.resolve_ticker(ticker, company_name)
        articles = fx.articles_for(tk) if tk else []
        items = [
            {
                "article_id": a["article_id"],
                "title": a["title"],
                "company_name": a["company_name"],
                "published_at": a["published_at"],
                "sentiment": a["sentiment"],
                "sentiment_label": a["sentiment_label"],
                "price_impact_pct": a["price_impact_pct"],
                "source": a["source"],
                "url": a["url"],
            }
            for a in articles
        ]
        if items:
            avg = round(sum(a["sentiment"] for a in items) / len(items), 3)
            label = "긍정" if avg > 0.15 else "부정" if avg < -0.15 else "중립"
            summary = {
                "ticker": tk,
                "company_name": items[0]["company_name"],
                "avg_sentiment": avg,
                "avg_sentiment_label": label,
                "article_count": len(items),
                "is_summary": True,
            }
            items = [summary, *items]
        return self._envelope(self._page(items, page_no, num_of_rows), total=len(items))

    async def news_disclosure(
        self,
        ticker: str | None = None,
        company_name: str | None = None,
        disclosure_type: str | None = None,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> dict:
        if self.use_real_api:
            raw = await self._get(
                "disclosure",
                {
                    "ticker": ticker,
                    "name": company_name,
                    "type": disclosure_type,
                    "page": page_no,
                    "pageSize": num_of_rows,
                },
            )
            return self._wrap_vendor(raw)
        tk = fx.resolve_ticker(ticker, company_name)
        pool = fx.articles_for(tk) if tk else fx.all_articles()
        items = [a for a in pool if a.get("disclosure_linked")]
        if disclosure_type:
            items = [a for a in items if a.get("disclosure_type") == disclosure_type]
        return self._envelope(self._page(items, page_no, num_of_rows), total=len(items))

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
