from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field
from utils.common.time_utils import now_kst

# 재무제표 구분 — 연결(CFS)·별도(OFS)
FinancialStatementType = Literal["CFS", "OFS"]
# 보고서 종류 — 사업보고서·반기·분기
ReportCode = Literal["11011", "11012", "11013", "11014"]
# 공시 유형 대분류 — 정기·주요사항·발행·지분·기타
DisclosureType = Literal["A", "B", "C", "D", "ALL"]

# DART 재무·배당 API 가 제공하는 최초 사업연도 (시간이 지나도 움직이지 않는 값이라 상수)
MIN_BSNS_YEAR = 2015


def _max_bsns_year() -> int:
    """조회 가능한 사업연도 상한 — 당해 연도 +1.

    +1 은 12월 결산이 아닌 발행사·연말 경계를 위한 여유다. 그 너머 미래 연도는 공시 자체가 없다.
    """
    return now_kst().year + 1


def _latest_closed_bsns_year() -> int:
    """가장 최근에 정기보고서로 확정된 사업연도 — 통상 전년도 (client 의 최대주주 조회와 같은 기준)."""
    return now_kst().year - 1


def _check_bsns_year(value: int) -> int:
    upper = _max_bsns_year()
    if value > upper:
        raise ValueError(f"사업연도는 {upper} 이하여야 합니다 — 그 이후 사업연도는 아직 공시가 없습니다")
    return value


# 상한은 상수가 아니라 '지금'의 함수다 — 검증 시점에 계산해야 해가 바뀌어도 당해 재무가 거부되지 않는다.
# JSON 스키마에 상한을 싣지 않는 것도 의도다: 기동 시점에 박힌 숫자가 LLM 의 세계관("그 해까지만 있나 보다")이 된다.
BsnsYear = Annotated[int, Field(ge=MIN_BSNS_YEAR), AfterValidator(_check_bsns_year)]
_BSNS_YEAR_DESC = f"사업연도 (4자리). {MIN_BSNS_YEAR}년부터 당해 연도까지. 생략하면 최근 확정 사업연도(전년도)"


class CompanySearchIn(BaseModel):
    query: str | None = Field(
        default=None, description="회사명 또는 종목코드(6자리)·고유번호(corp_code)로 발행사를 찾는 검색어"
    )


class FinancialsIn(BaseModel):
    corp: str = Field(
        description="회사명 또는 종목코드(6자리). 정확한 발행사 식별이 어려우면 disclosure_company 로 먼저 조회"
    )
    year: BsnsYear = Field(default_factory=_latest_closed_bsns_year, description=_BSNS_YEAR_DESC)
    report_code: ReportCode = Field(
        default="11011",
        description="보고서 종류. 11011=사업보고서(연간), 11012=반기, 11013=1분기, 11014=3분기",
    )
    fs_type: FinancialStatementType = Field(
        default="CFS", description="재무제표 구분. CFS=연결, OFS=별도. 모호하면 CFS"
    )


class DisclosureListIn(BaseModel):
    corp: str | None = Field(
        default=None, description="회사명 또는 종목코드(6자리). 비우면 전체 발행사 대상 최신 공시 목록"
    )
    disclosure_type: DisclosureType = Field(
        default="ALL",
        description="공시 유형. A=정기공시, B=주요사항보고, C=발행공시, D=지분공시, ALL=전체. 모호하면 ALL",
    )
    start_date: str | None = Field(default=None, description="검색 시작일 (YYYYMMDD). 비우면 최근 90일")
    end_date: str | None = Field(default=None, description="검색 종료일 (YYYYMMDD). 비우면 오늘")
    page_no: int = Field(default=1, ge=1, description="조회 페이지 (1부터). total_count 가 더 크면 올려 추가 조회")
    page_count: int = Field(default=10, ge=1, le=100, description="페이지당 조회 건수 (최대 100)")


class DisclosureDetailIn(BaseModel):
    rcept_no: str = Field(
        description="공시 접수번호 (14자리). disclosure_list 결과의 rcept_no 로 본문 메타·요약을 조회"
    )


class DividendIn(BaseModel):
    corp: str = Field(description="회사명 또는 종목코드(6자리)")
    year: BsnsYear = Field(default_factory=_latest_closed_bsns_year, description=f"배당 기준 {_BSNS_YEAR_DESC}")


class MajorShareholderIn(BaseModel):
    corp: str = Field(description="회사명 또는 종목코드(6자리)")


class DisclosureDataOut(BaseModel):
    data: list[dict] = Field(default_factory=list, description="조회 결과 목록")
    total_count: int = Field(default=0, description="전체 결과 수 (data 건수보다 크면 페이지네이션으로 추가 조회 가능)")
    source: Literal["mock", "real"] = Field(
        default="mock", description="데이터 출처. mock=내장 샘플, real=DART OpenAPI"
    )
