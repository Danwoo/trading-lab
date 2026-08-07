# routers/disclosure/disclosure_router.py
from core.container import Container
from core.security import verify_access_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from schemas.disclosure.disclosure_schema import (
    CompanySearchIn,
    DisclosureDataOut,
    DisclosureDetailIn,
    DisclosureListIn,
    DividendIn,
    FinancialsIn,
    MajorShareholderIn,
)
from services.disclosure.disclosure_service import DisclosureService
from utils.common.few_shot import few_shot

# operation_id 가 MCP tool 이름의 SoT — multi-agent-service `agents/domains/*` 의 SUBAGENT_SPECS.mcp_tools
# 가 이 이름으로 바인딩 (변경 시 lockstep). docstring 이 tool description, Pydantic In/Out 이 tool 입출력 스키마.
router = APIRouter(prefix="/disclosure", dependencies=[Depends(verify_access_token)])


@router.post(
    "/company",
    operation_id="disclosure_company",
    openapi_extra=few_shot(
        [
            {"질문": "삼성전자 공시 발행사 정보 알려줘", "호출": {"query": "삼성전자"}},
            {"질문": "종목코드 000660 회사가 어디야", "호출": {"query": "000660"}},
            {"질문": "공시 대상 상장사 목록 보여줘", "호출": {}},
        ]
    ),
)
@inject
async def disclosure_company(
    body: CompanySearchIn,
    disclosure_service: DisclosureService = Depends(Provide[Container.disclosure_service]),
) -> DisclosureDataOut:
    """회사명·종목코드(6자리)·고유번호(corp_code)로 공시 대상 발행사를 찾는다 — 재무·공시·배당·최대주주 도구를 호출하기 전 발행사를 정확히 식별하는 진입점. 동명·약칭으로 corp 인자가 모호할 때 먼저 이 도구로 corp_code·종목코드를 확정한 뒤 다른 도구에 넘긴다. query 를 비우면 등록된 발행사 전체 목록을 돌려준다."""
    return await disclosure_service.search_company(body)


@router.post(
    "/financials",
    operation_id="disclosure_financials",
    openapi_extra=few_shot(
        [
            {
                "질문": "삼성전자 작년 연결 재무제표(매출·영업이익·순이익) 보여줘",
                "호출": {"corp": "삼성전자", "report_code": "11011", "fs_type": "CFS"},
            },
            {
                "질문": "SK하이닉스 최근 사업보고서 별도 재무제표",
                "호출": {"corp": "SK하이닉스", "fs_type": "OFS"},
            },
            {
                "질문": "현대자동차 반기보고서 재무",
                "호출": {"corp": "현대자동차", "report_code": "11012"},
            },
        ]
    ),
)
@inject
async def disclosure_financials(
    body: FinancialsIn,
    disclosure_service: DisclosureService = Depends(Provide[Container.disclosure_service]),
) -> DisclosureDataOut:
    """단일 발행사의 재무제표 핵심 계정(매출액·영업이익·당기순이익·자산/부채/자본총계·영업활동현금흐름)을 사업연도·보고서 종류·연결/별도 기준으로 조회한다 — 수익성·성장성·재무건전성 분석의 1차 근거. report_code 로 연간(11011)·반기(11012)·분기(11013/11014)를 고르고, fs_type 으로 연결(CFS)·별도(OFS)를 고른다(모호하면 CFS). thstrm_amount=당기·frmtrm_amount=전기 금액이라 YoY 비교에 쓴다. 발행사 식별이 모호하면 disclosure_company 로 먼저 corp 를 확정한다. 수치는 공시 근거이며, 단정적 투자 판단으로 확장하지 마라."""
    return await disclosure_service.get_financials(body)


@router.post(
    "/list",
    operation_id="disclosure_list",
    openapi_extra=few_shot(
        [
            {"질문": "삼성전자 최근 공시 목록 보여줘", "호출": {"corp": "삼성전자"}},
            {
                "질문": "현대자동차 정기공시만 골라 보여줘",
                "호출": {"corp": "현대자동차", "disclosure_type": "A"},
            },
            {"질문": "최근 주요사항보고 공시 전체", "호출": {"disclosure_type": "B"}},
        ]
    ),
)
@inject
async def disclosure_list(
    body: DisclosureListIn,
    disclosure_service: DisclosureService = Depends(Provide[Container.disclosure_service]),
) -> DisclosureDataOut:
    """발행사·유형·기간으로 공시 접수 목록을 조회한다 — 어떤 공시가 언제 들어왔는지 타임라인을 잡는 기본 도구. disclosure_type 으로 정기공시(A)·주요사항보고(B)·발행공시(C)·지분공시(D)를 좁히고(모호하면 ALL), start_date/end_date(YYYYMMDD)로 기간을 건다. corp 를 비우면 전체 발행사 최신 공시를 본다. 각 행의 rcept_no(접수번호 14자리)를 disclosure_detail 에 넘기면 그 공시의 본문 메타를 본다. 0건이면 유형·기간 한정을 풀어 자동 완화 재조회한다."""
    return await disclosure_service.list_disclosures(body)


@router.post(
    "/detail",
    operation_id="disclosure_detail",
    openapi_extra=few_shot(
        [
            {"질문": "이 공시 접수번호 20250314000123 내용 알려줘", "호출": {"rcept_no": "20250314000123"}},
            {"질문": "배당 결정 공시 20250131000045 상세", "호출": {"rcept_no": "20250131000045"}},
        ]
    ),
)
@inject
async def disclosure_detail(
    body: DisclosureDetailIn,
    disclosure_service: DisclosureService = Depends(Provide[Container.disclosure_service]),
) -> DisclosureDataOut:
    """단일 공시의 본문 메타·요약을 접수번호(rcept_no)로 조회한다 — 회사명·보고서명·접수일·공시유형 등 그 공시 한 건의 식별 정보를 돌려준다. rcept_no 는 disclosure_list 결과에서 얻는다(목록 없이 임의 번호를 만들지 마라). 재무 수치 자체는 disclosure_financials, 배당은 disclosure_dividend 가 맞다."""
    return await disclosure_service.get_disclosure_detail(body)


@router.post(
    "/dividend",
    operation_id="disclosure_dividend",
    openapi_extra=few_shot(
        [
            {"질문": "삼성전자 배당 알려줘 (주당배당금·배당성향)", "호출": {"corp": "삼성전자"}},
            {"질문": "현대자동차 배당수익률 알려줘", "호출": {"corp": "현대자동차"}},
        ]
    ),
)
@inject
async def disclosure_dividend(
    body: DividendIn,
    disclosure_service: DisclosureService = Depends(Provide[Container.disclosure_service]),
) -> DisclosureDataOut:
    """발행사의 배당 관련 지표를 사업연도별로 조회한다 — 주당순이익(EPS)·주당현금배당금(DPS)·현금배당성향(%)·현금배당수익률(%). 배당 정책·인컴 관점 분석의 근거다. 수익성 전반은 disclosure_financials, 지분 구조는 disclosure_major_shareholder 가 맞다. 수치는 공시 근거이며 미래 배당을 보장하지 않는다."""
    return await disclosure_service.get_dividend(body)


@router.post(
    "/major-shareholder",
    operation_id="disclosure_major_shareholder",
    openapi_extra=few_shot(
        [
            {"질문": "삼성전자 최대주주와 특수관계인 지분 알려줘", "호출": {"corp": "삼성전자"}},
            {"질문": "SK하이닉스 대주주 지분율", "호출": {"corp": "SK하이닉스"}},
        ]
    ),
)
@inject
async def disclosure_major_shareholder(
    body: MajorShareholderIn,
    disclosure_service: DisclosureService = Depends(Provide[Container.disclosure_service]),
) -> DisclosureDataOut:
    """발행사의 최대주주 및 특수관계인 지분 현황을 조회한다 — 성명/법인명·관계·기말 소유주식수·지분율(%). 지배구조·소유 집중도·오너 리스크 분석의 근거다. 재무는 disclosure_financials, 배당은 disclosure_dividend 가 맞다. 지분율은 공시 시점 기준이며 이후 변동될 수 있다."""
    return await disclosure_service.get_major_shareholder(body)
