# services/disclosure/disclosure_service.py
from repositories.disclosure.disclosure_repository import DisclosureRepository
from schemas.disclosure.disclosure_schema import (
    CompanySearchIn,
    DisclosureDataOut,
    DisclosureDetailIn,
    DisclosureListIn,
    DividendIn,
    FinancialsIn,
    MajorShareholderIn,
)
from utils.common.staged_search import staged_search


class DisclosureService:
    """기업 전자공시·재무제표·배당·최대주주 조회 (순수 데이터, LLM 없음)."""

    def __init__(self, disclosure_repository: DisclosureRepository):
        self.disclosure_repo = disclosure_repository

    async def search_company(self, params: CompanySearchIn) -> DisclosureDataOut:
        return await self.disclosure_repo.search_company(params)

    async def get_financials(self, params: FinancialsIn) -> DisclosureDataOut:
        # 단계적 조회: 요청 보고서 → 0건이면 사업보고서(연간)·연결로 완화해 재시도
        relaxed = params.model_copy(update={"report_code": "11011", "fs_type": "CFS"})
        stages = [lambda: self.disclosure_repo.get_financials(params)]
        if relaxed.model_dump() != params.model_dump():
            stages.append(lambda: self.disclosure_repo.get_financials(relaxed))
        return await staged_search(stages)

    async def list_disclosures(self, params: DisclosureListIn) -> DisclosureDataOut:
        # 단계적 조회: 요청 조건 → 0건이면 유형·기간 한정을 풀어(전체 유형·기간 무제한) 재시도
        relaxed = params.model_copy(update={"disclosure_type": "ALL", "start_date": None, "end_date": None})
        stages = [lambda: self.disclosure_repo.list_disclosures(params)]
        if relaxed.model_dump() != params.model_dump():
            stages.append(lambda: self.disclosure_repo.list_disclosures(relaxed))
        return await staged_search(stages)

    async def get_disclosure_detail(self, params: DisclosureDetailIn) -> DisclosureDataOut:
        return await self.disclosure_repo.get_disclosure_detail(params)

    async def get_dividend(self, params: DividendIn) -> DisclosureDataOut:
        return await self.disclosure_repo.get_dividend(params)

    async def get_major_shareholder(self, params: MajorShareholderIn) -> DisclosureDataOut:
        return await self.disclosure_repo.get_major_shareholder(params)
