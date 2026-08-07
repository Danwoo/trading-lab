"""기업 전자공시·재무제표 연결 (transport) — DART OpenAPI(crtfc_key) 또는 내장 mock.

기본은 USE_REAL_API=false → API 키 없이 in-memory mock 공시/재무 데이터로 동작한다.
USE_REAL_API=true 이고 DISCLOSURE_API_KEY 가 있을 때만 실제 DART OpenAPI 를 호출한다.
mock 데이터는 잘 알려진 공개 발행사 몇 곳의 손익·재무상태·현금흐름·공시목록·배당·최대주주 샘플이다
(공개 시장 발행사 정보는 비밀이 아님).

응답은 실/mock 경로 모두 `{"data": [...], "total_count"?}` 봉투로 정규화해 돌려준다 — DART 네이티브 `list` 키를
여기(producer)에서 `data` 로 흡수해 repositories/disclosure·multi-agent 인용 계약과 맞춘다.
이 클래스는 SQL 엔진·HTTP 게이트웨이처럼 '연결'만 제공한다.
"""

import io
import zipfile
from xml.etree import ElementTree as ET

import httpx
from clients.disclosure.mock_fixtures import (
    MOCK_COMPANIES,
    mock_dividends,
    mock_filings,
    mock_financials,
    mock_shareholders,
)
from core.logger import logger
from utils.common.retry_utils import is_http_retryable, retry
from utils.common.time_utils import now_kst

# DART 응답 status — 000=정상, 013=조회 데이터 없음(정상적 빈 결과). 그 외는 오류로 간주.
_DART_OK_STATUSES = {"000", "013"}


class CorpCodeIndex:
    """회사명·종목코드(6)·고유번호(8) → corp_code(8) 매핑. 실API 키가 있으면 DART corpCode.xml 로
    전체 상장 발행사를 적재하고, 없거나 적재 실패 시 내장 픽스처(MOCK_COMPANIES)로 폴백한다."""

    def __init__(self) -> None:
        self._companies: list[dict] = [dict(c) for c in MOCK_COMPANIES]
        self._by_name: dict[str, str] = {c["corp_name"].lower(): c["corp_code"] for c in MOCK_COMPANIES}
        self._by_stock: dict[str, str] = {c["stock_code"]: c["corp_code"] for c in MOCK_COMPANIES}
        self._by_code: set[str] = {c["corp_code"] for c in MOCK_COMPANIES}
        self._loaded = False

    async def ensure_loaded(self, fetch) -> None:
        """corpCode.xml(zip) 을 한 번만 적재 (fail-soft — 실패 시 픽스처 유지)."""
        if self._loaded:
            return
        try:
            self._ingest_zip(await fetch())
        except Exception as exc:  # noqa: BLE001 — 적재 실패는 폴백으로 흡수(조용한 무한 재시도 방지)
            logger.warning("corpCode.xml 적재 실패 — 내장 픽스처로 폴백: %s", exc)
        finally:
            self._loaded = True

    def _ingest_zip(self, content: bytes) -> None:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            name = next((n for n in zf.namelist() if n.lower().endswith(".xml")), None)
            if not name:
                return
            xml_bytes = zf.read(name)
        root = ET.fromstring(xml_bytes)
        for node in root.iter("list"):
            code = (node.findtext("corp_code") or "").strip()
            corp_name = (node.findtext("corp_name") or "").strip()
            stock = (node.findtext("stock_code") or "").strip()
            if not code:
                continue
            self._by_code.add(code)
            if corp_name:
                self._by_name.setdefault(corp_name.lower(), code)
            if stock:  # 상장 발행사(종목코드 보유)만 검색 목록에 담아 메모리 억제
                self._by_stock.setdefault(stock, code)
                self._companies.append({"corp_code": code, "corp_name": corp_name, "stock_code": stock})

    def resolve(self, corp: str) -> str:
        """무엇이 오든 corp_code(8) 로 정규화. 미상이면 입력 원문 반환."""
        key = (corp or "").strip()
        if key in self._by_code:
            return key
        if key in self._by_stock:
            return self._by_stock[key]
        return self._by_name.get(key.lower(), key)

    def search(self, query: str | None) -> list[dict]:
        q = (query or "").strip().lower()
        if not q:
            return list(self._companies)
        return [
            c for c in self._companies if q in c["corp_name"].lower() or q == c.get("stock_code") or q == c["corp_code"]
        ]


class DisclosureClient:
    def __init__(self, config, timeout: float = 30.0):
        self.base_url = config.DISCLOSURE_API_BASE_URL.rstrip("/")
        self._api_key = config.DISCLOSURE_API_KEY
        self._use_real = bool(config.USE_REAL_API and config.DISCLOSURE_API_KEY)
        self._timeout = httpx.Timeout(timeout, connect=5.0)
        self._client: httpx.AsyncClient | None = None
        self._corp_index = CorpCodeIndex()

    @property
    def source(self) -> str:
        """현재 데이터 출처 — 'real'(DART OpenAPI) 또는 'mock'(내장 샘플)."""
        return "real" if self._use_real else "mock"

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _fetch_corp_code_zip(self) -> bytes:
        """DART corpCode.xml(zip) 바이트 — 전체 발행사 고유번호 사전."""
        resp = await self._http().get(f"{self.base_url}/corpCode.xml", params={"crtfc_key": self._api_key})
        resp.raise_for_status()
        return resp.content

    async def _resolve(self, corp: str | None) -> str | None:
        """corp → corp_code(8). 실API 경로에서는 corpCode.xml 로 전체 사전을 확보한 뒤 해석."""
        if corp is None:
            return None
        if self._use_real:
            await self._corp_index.ensure_loaded(self._fetch_corp_code_zip)
        return self._corp_index.resolve(corp)

    async def _get(self, endpoint: str, params: dict) -> dict:
        """GET {base}/{endpoint}.json → `{"data": rows, "total_count"?}` 로 정규화 (실API 경로).

        일시 오류(502·503·504·네트워크)는 재시도하고, DART body `status` 를 검사해
        오류 상태(비-000·비-013)면 raise 한다 (조용한 빈 응답 방지).
        """
        query = {k: v for k, v in params.items() if v is not None}
        query["crtfc_key"] = self._api_key

        async def _do() -> httpx.Response:
            resp = await self._http().get(f"{self.base_url}/{endpoint}.json", params=query)
            if resp.status_code in (502, 503, 504):
                resp.raise_for_status()
            return resp

        response = await retry(_do, base_delay=0.5, retryable=is_http_retryable)
        response.raise_for_status()
        body = response.json()
        return self._normalize(body)

    @staticmethod
    def _normalize(body: dict) -> dict:
        """DART 응답 → `{"data": rows, "total_count"?}`. 오류 status 는 raise."""
        if not isinstance(body, dict):
            return {"data": []}
        status = str(body.get("status", "")).strip()
        if status and status not in _DART_OK_STATUSES:
            message = body.get("message") or "알 수 없는 오류"
            raise RuntimeError(f"DART 응답 오류입니다 (status={status}): {message}")
        rows = body.get("list", [])
        envelope: dict = {"data": rows if isinstance(rows, list) else []}
        if body.get("total_count") is not None:
            envelope["total_count"] = body["total_count"]
        return envelope

    async def search_company(self, query: str | None = None) -> dict:
        # 실API: corpCode.xml 전체 사전에서 검색 / mock: 내장 픽스처 검색 (동일 인터페이스)
        if self._use_real:
            await self._corp_index.ensure_loaded(self._fetch_corp_code_zip)
        return {"data": self._corp_index.search(query)}

    async def get_financials(self, corp: str, year: int, report_code: str, fs_type: str) -> dict:
        corp_code = await self._resolve(corp)
        if self._use_real:
            return await self._get(
                "fnlttSinglAcntAll",
                {
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": report_code,
                    "fs_div": fs_type,
                },
            )
        return {"data": mock_financials(corp_code, year, fs_type)}

    async def list_disclosures(
        self,
        corp: str | None,
        disclosure_type: str,
        start_date: str | None,
        end_date: str | None,
        page_no: int,
        page_count: int,
    ) -> dict:
        corp_code = await self._resolve(corp) if corp else None
        if self._use_real:
            return await self._get(
                "list",
                {
                    "corp_code": corp_code,
                    "pblntf_ty": None if disclosure_type == "ALL" else disclosure_type,
                    "bgn_de": start_date,
                    "end_de": end_date,
                    "page_no": page_no,
                    "page_count": min(page_count, 100),
                },
            )
        items = [
            f
            for f in mock_filings()
            if (corp_code is None or f["corp_code"] == corp_code)
            and (disclosure_type == "ALL" or f["pblntf_ty"] == disclosure_type)
            and (start_date is None or f["rcept_dt"] >= start_date)
            and (end_date is None or f["rcept_dt"] <= end_date)
        ]
        items.sort(key=lambda f: f["rcept_dt"], reverse=True)
        total = len(items)
        start = (page_no - 1) * page_count
        return {"data": items[start : start + page_count], "total_count": total}

    async def get_disclosure_detail(self, rcept_no: str) -> dict:
        # 실 DART 는 rcept_no 단건 메타 엔드포인트가 없어, 접수번호 앞 8자리(YYYYMMDD)로
        # list.json 을 조회해 해당 rcept_no 행을 찾아 본문 메타로 돌려준다.
        if self._use_real:
            match = await self._find_filing(rcept_no)
            return {"data": [match] if match else []}
        item = next((f for f in mock_filings() if f["rcept_no"] == rcept_no), None)
        return {"data": [item] if item else []}

    async def _find_filing(self, rcept_no: str) -> dict | None:
        """접수번호에 인코딩된 접수일로 list.json 을 페이지 조회해 해당 공시 한 건을 찾는다."""
        date = (rcept_no or "")[:8]
        if len(date) != 8 or not date.isdigit():
            return None
        for page_no in range(1, 11):  # 최대 10페이지(×100) 로 탐색 범위 제한
            raw = await self._get("list", {"bgn_de": date, "end_de": date, "page_no": page_no, "page_count": 100})
            rows = raw.get("data", [])
            match = next((r for r in rows if r.get("rcept_no") == rcept_no), None)
            if match:
                return match
            if len(rows) < 100:
                break
        return None

    async def get_dividend(self, corp: str, year: int) -> dict:
        corp_code = await self._resolve(corp)
        if self._use_real:
            return await self._get(
                "alotMatter",
                {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": "11011"},
            )
        return {"data": mock_dividends(corp_code, year)}

    async def get_major_shareholder(self, corp: str, bsns_year: int | None = None) -> dict:
        year = bsns_year or (now_kst().year - 1)  # 최신 확정 정기보고서는 통상 전년도 기준
        corp_code = await self._resolve(corp)
        if self._use_real:
            return await self._get(
                "hyslrSttus",
                {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": "11011"},
            )
        return {"data": mock_shareholders(corp_code)}

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
