from clients.disclosure.disclosure_client import DisclosureClient
from schemas.disclosure.disclosure_schema import (
    CompanySearchIn,
    DisclosureDataOut,
    DisclosureDetailIn,
    DisclosureListIn,
    DividendIn,
    FinancialsIn,
    MajorShareholderIn,
)


class DisclosureRepository:
    def __init__(self, disclosure_client: DisclosureClient):
        self.client = disclosure_client

    def _out(self, data: list[dict], total: int | None = None) -> DisclosureDataOut:
        # 출처(mock/real)는 client 가 단일 소유 — 응답마다 정직하게 라벨링
        return DisclosureDataOut(
            data=data, total_count=total if total is not None else len(data), source=self.client.source
        )

    @staticmethod
    def _as_list(raw: dict) -> list[dict]:
        # client 가 실/mock 공통으로 `data` 봉투로 정규화해 돌려준다 (DART 네이티브 `list` 아님)
        items = raw.get("data", [])
        return items if isinstance(items, list) else []

    async def search_company(self, params: CompanySearchIn) -> DisclosureDataOut:
        raw = await self.client.search_company(query=params.query)
        return self._out(self._as_list(raw))

    async def get_financials(self, params: FinancialsIn) -> DisclosureDataOut:
        raw = await self.client.get_financials(
            corp=params.corp, year=params.year, report_code=params.report_code, fs_type=params.fs_type
        )
        return self._out(self._as_list(raw))

    async def list_disclosures(self, params: DisclosureListIn) -> DisclosureDataOut:
        raw = await self.client.list_disclosures(
            corp=params.corp,
            disclosure_type=params.disclosure_type,
            start_date=params.start_date,
            end_date=params.end_date,
            page_no=params.page_no,
            page_count=params.page_count,
        )
        data = self._as_list(raw)
        total = raw.get("total_count", len(data))
        return self._out(data, total)

    async def get_disclosure_detail(self, params: DisclosureDetailIn) -> DisclosureDataOut:
        raw = await self.client.get_disclosure_detail(rcept_no=params.rcept_no)
        return self._out(self._as_list(raw))

    async def get_dividend(self, params: DividendIn) -> DisclosureDataOut:
        raw = await self.client.get_dividend(corp=params.corp, year=params.year)
        return self._out(self._as_list(raw))

    async def get_major_shareholder(self, params: MajorShareholderIn) -> DisclosureDataOut:
        raw = await self.client.get_major_shareholder(corp=params.corp)
        return self._out(self._as_list(raw))
