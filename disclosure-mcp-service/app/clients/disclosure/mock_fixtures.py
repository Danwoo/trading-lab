"""내장 mock 공시·재무 데이터 — API 키 없이 서비스가 단독 기동·동작하기 위한 in-memory 샘플.

수록 발행사는 모두 공개 상장사(공개 시장 엔티티 — 비밀 아님)이며, 수치는 DART 응답 형태를 본뜬
샘플 근사치다(실시간 정합성 보장 X — 데모/리서치 파이프라인 검증용). USE_REAL_API=true 면 실 DART 로 대체.

**사업연도·접수일은 소스에 박지 않고 조회 시점에 계산한다** — 픽스처가 덮는 사업연도는 스키마 기본값
(`FinancialsIn.year` = 최근 확정 사업연도 = 전년도)과 같은 기준이라, 해가 바뀌어도 인자 없는 호출이 0건이
되지 않는다. 수치 자체는 고정이고 붙는 연도 라벨만 따라 움직인다.

수록 형태 (슬롯 = 최근 확정 사업연도로부터 거슬러 올라간 수, 0 = 최근 확정):
- _FINANCIAL_SPECS: (corp_code, 슬롯, fs_type) -> 계정 금액 (DART fnlttSinglAcntAll 형태로 전개)
- _DIVIDEND_SPECS: (corp_code, 슬롯) -> 배당 지표
- _SHAREHOLDER_SPECS: corp_code -> 최대주주·특수관계인 지분 (최근 확정 사업연도 기준)
- _ANNUAL_REPORT / _OTHER_FILING_SPECS: 접수번호 뒷자리(MMDD+일련) — 접수 연도는 사업연도 +1(정기보고서 제출 연도)
"""

from utils.common.time_utils import now_kst

# corp_code = DART 8자리 고유번호, stock_code = 6자리 종목코드
MOCK_COMPANIES: list[dict] = [
    {
        "corp_code": "00126380",
        "corp_name": "삼성전자",
        "corp_name_eng": "Samsung Electronics",
        "stock_code": "005930",
        "ceo_nm": "한종희",
        "corp_cls": "Y",  # Y=유가증권(KOSPI)
        "induty_code": "반도체·전자",
        "est_dt": "19690113",
    },
    {
        "corp_code": "00164779",
        "corp_name": "SK하이닉스",
        "corp_name_eng": "SK hynix",
        "stock_code": "000660",
        "ceo_nm": "곽노정",
        "corp_cls": "Y",
        "induty_code": "반도체",
        "est_dt": "19490715",
    },
    {
        "corp_code": "00164742",
        "corp_name": "현대자동차",
        "corp_name_eng": "Hyundai Motor",
        "stock_code": "005380",
        "ceo_nm": "장재훈",
        "corp_cls": "Y",
        "induty_code": "완성차",
        "est_dt": "19671229",
    },
    {
        "corp_code": "00266961",
        "corp_name": "NAVER",
        "corp_name_eng": "NAVER Corp",
        "stock_code": "035420",
        "ceo_nm": "최수연",
        "corp_cls": "Y",
        "induty_code": "인터넷·플랫폼",
        "est_dt": "19990602",
    },
]

_BY_NAME = {c["corp_name"].lower(): c["corp_code"] for c in MOCK_COMPANIES}
_BY_STOCK = {c["stock_code"]: c["corp_code"] for c in MOCK_COMPANIES}
_BY_CODE = {c["corp_code"]: c for c in MOCK_COMPANIES}


def resolve_corp_code(corp: str) -> str:
    """회사명·종목코드(6)·고유번호(8) 무엇이 와도 corp_code(8) 로 정규화. 미상이면 입력 원문 반환."""
    key = (corp or "").strip()
    if key in _BY_CODE:
        return key
    if key in _BY_STOCK:
        return _BY_STOCK[key]
    return _BY_NAME.get(key.lower(), key)


def latest_closed_bsns_year() -> int:
    """가장 최근에 정기보고서로 확정된 사업연도 — 통상 전년도 (스키마 기본값과 같은 기준)."""
    return now_kst().year - 1


def _slot(year: int) -> int:
    """사업연도 → 픽스처 슬롯 (0 = 최근 확정 사업연도, 1 = 그 전년도). 수록 밖이면 조회가 빈 결과."""
    return latest_closed_bsns_year() - year


# 발행사·슬롯별 사업보고서(정기공시) 접수번호 뒷자리(MMDD+일련 6자리) — 재무/배당/최대주주 행의 인용 근거.
# 재무·배당·지분 수치는 모두 해당 연도 정기보고서(사업보고서)에서 나오므로 그 공시를 출처로 단다.
_ANNUAL_REPORT: dict[tuple[str, int], str] = {
    ("00126380", 0): "0314000123",
    ("00126380", 1): "0314000100",
    ("00164779", 0): "0313000201",
    ("00164742", 0): "0318000150",
    ("00266961", 0): "0320000310",
}


def _report_ref(corp_code: str, year: int) -> tuple[str, str]:
    """해당 발행사·사업연도의 사업보고서 접수번호·보고서명 (인용 근거). 미수록이면 합성 접수번호."""
    tail = _ANNUAL_REPORT.get((corp_code, _slot(year)), "0401000000")
    return f"{year + 1}{tail}", f"사업보고서 ({year}.12)"


def _fin_row(account_nm: str, thstrm: int, frmtrm: int, sj_div: str, rcept_no: str, report_nm: str) -> dict:
    """DART fnlttSinglAcntAll 한 행 — 당기/전기 금액(원)과 재무제표 구분(BS·IS·CF), 출처 공시(rcept_no)."""
    return {
        "account_nm": account_nm,
        "sj_div": sj_div,  # BS=재무상태표, IS=손익계산서, CF=현금흐름표
        "thstrm_amount": str(thstrm),
        "frmtrm_amount": str(frmtrm),
        "currency": "KRW",
        "rcept_no": rcept_no,
        "report_nm": report_nm,
    }


def _statements(
    corp_code: str,
    year: int,
    *,
    revenue: int,
    op_profit: int,
    net_income: int,
    assets: int,
    liabilities: int,
    equity: int,
    op_cashflow: int,
    prev_revenue: int,
    prev_op_profit: int,
    prev_net_income: int,
) -> list[dict]:
    rcept_no, report_nm = _report_ref(corp_code, year)
    return [
        _fin_row("매출액", revenue, prev_revenue, "IS", rcept_no, report_nm),
        _fin_row("영업이익", op_profit, prev_op_profit, "IS", rcept_no, report_nm),
        _fin_row("당기순이익", net_income, prev_net_income, "IS", rcept_no, report_nm),
        _fin_row("자산총계", assets, assets, "BS", rcept_no, report_nm),
        _fin_row("부채총계", liabilities, liabilities, "BS", rcept_no, report_nm),
        _fin_row("자본총계", equity, equity, "BS", rcept_no, report_nm),
        _fin_row("영업활동현금흐름", op_cashflow, op_cashflow, "CF", rcept_no, report_nm),
    ]


# 단위: 백만원 근사 (DART 는 원 단위 문자열이나, 샘플은 백만원 정수로 가독성 우선)
_FINANCIAL_SPECS: dict[tuple[str, int, str], dict[str, int]] = {
    ("00126380", 0, "CFS"): {
        "revenue": 300_870_000,
        "op_profit": 32_730_000,
        "net_income": 34_450_000,
        "assets": 514_530_000,
        "liabilities": 112_340_000,
        "equity": 402_190_000,
        "op_cashflow": 65_080_000,
        "prev_revenue": 258_940_000,
        "prev_op_profit": 6_570_000,
        "prev_net_income": 15_490_000,
    },
    ("00126380", 1, "CFS"): {
        "revenue": 258_940_000,
        "op_profit": 6_570_000,
        "net_income": 15_490_000,
        "assets": 455_900_000,
        "liabilities": 92_230_000,
        "equity": 363_670_000,
        "op_cashflow": 44_120_000,
        "prev_revenue": 302_230_000,
        "prev_op_profit": 43_380_000,
        "prev_net_income": 55_650_000,
    },
    ("00164779", 0, "CFS"): {
        "revenue": 66_190_000,
        "op_profit": 23_470_000,
        "net_income": 19_800_000,
        "assets": 110_700_000,
        "liabilities": 44_200_000,
        "equity": 66_500_000,
        "op_cashflow": 28_300_000,
        "prev_revenue": 32_770_000,
        "prev_op_profit": -7_730_000,
        "prev_net_income": -9_140_000,
    },
    ("00164742", 0, "CFS"): {
        "revenue": 175_230_000,
        "op_profit": 14_240_000,
        "net_income": 13_120_000,
        "assets": 295_400_000,
        "liabilities": 180_700_000,
        "equity": 114_700_000,
        "op_cashflow": 11_900_000,
        "prev_revenue": 162_660_000,
        "prev_op_profit": 15_130_000,
        "prev_net_income": 12_270_000,
    },
    ("00266961", 0, "CFS"): {
        "revenue": 10_730_000,
        "op_profit": 1_980_000,
        "net_income": 1_130_000,
        "assets": 39_400_000,
        "liabilities": 16_200_000,
        "equity": 23_200_000,
        "op_cashflow": 2_640_000,
        "prev_revenue": 9_670_000,
        "prev_op_profit": 1_490_000,
        "prev_net_income": 985_000,
    },
}


def mock_financials(corp_code: str, year: int, fs_type: str) -> list[dict]:
    """(발행사, 사업연도, 연결/별도) 계정 행 목록. 미수록 조합은 빈 목록 — 수록은 연결(CFS)뿐이다."""
    spec = _FINANCIAL_SPECS.get((corp_code, _slot(year), fs_type))
    return _statements(corp_code, year, **spec) if spec else []


def _filing(rcept_no: str, corp_code: str, report_nm: str, pblntf_ty: str) -> dict:
    c = _BY_CODE.get(corp_code, {})
    return {
        "rcept_no": rcept_no,
        "corp_code": corp_code,
        "corp_name": c.get("corp_name", ""),
        "stock_code": c.get("stock_code", ""),
        "report_nm": report_nm,
        "rcept_dt": rcept_no[:8],  # 접수번호 14자리 = YYYYMMDD + 6자리 일련
        "pblntf_ty": pblntf_ty,  # A=정기, B=주요사항, C=발행, D=지분
        "flr_nm": c.get("corp_name", ""),
    }


# 정기공시(A) 외 공시 샘플 — (접수번호 뒷자리 MMDD+일련, corp_code, 보고서명, 공시유형).
# 접수 연도는 정기보고서와 같은 해(= 최근 확정 사업연도 +1)로 계산한다.
_OTHER_FILING_SPECS: list[tuple[str, str, str, str]] = [
    ("0131000045", "00126380", "현금·현물배당 결정", "B"),
    ("0214000077", "00126380", "주요사항보고서(자기주식취득결정)", "B"),
    ("0105000012", "00126380", "최대주주등소유주식변동신고서", "D"),
    ("0207000088", "00164779", "단일판매·공급계약체결", "B"),
    ("0122000033", "00164742", "주식배당 결정", "B"),
    ("0228000099", "00266961", "전환사채권발행결정", "C"),
]


def mock_filings() -> list[dict]:
    """최신 공시 목록 샘플 — 정기공시(사업보고서)는 재무·배당·지분 행의 rcept_no 와 같은 접수번호를 쓴다."""
    year = latest_closed_bsns_year()
    annual = []
    for company in MOCK_COMPANIES:
        rcept_no, report_nm = _report_ref(company["corp_code"], year)
        annual.append(_filing(rcept_no, company["corp_code"], report_nm, "A"))
    others = [
        _filing(f"{year + 1}{tail}", corp_code, report_nm, pblntf_ty)
        for tail, corp_code, report_nm, pblntf_ty in _OTHER_FILING_SPECS
    ]
    return [*annual, *others]


def _dividend(corp_code: str, year: int, eps: int, dps_common: int, payout_ratio: str, yield_pct: str) -> dict:
    rcept_no, report_nm = _report_ref(corp_code, year)
    return {
        "corp_code": corp_code,
        "bsns_year": str(year),
        "주당순이익(원)": str(eps),
        "주당현금배당금(원)": str(dps_common),
        "현금배당성향(%)": payout_ratio,
        "현금배당수익률(%)": yield_pct,
        "rcept_no": rcept_no,
        "report_nm": report_nm,
    }


# (corp_code, 슬롯) -> (주당순이익, 주당현금배당금, 현금배당성향(%), 현금배당수익률(%))
_DIVIDEND_SPECS: dict[tuple[str, int], tuple[int, int, str, str]] = {
    ("00126380", 0): (5048, 1444, "29.8", "2.6"),
    ("00126380", 1): (2131, 1444, "67.8", "1.8"),
    ("00164779", 0): (27190, 1500, "5.5", "0.8"),
    ("00164742", 0): (49160, 12000, "24.4", "5.0"),
    ("00266961", 0): (7460, 1206, "16.2", "0.6"),
}


def mock_dividends(corp_code: str, year: int) -> list[dict]:
    """(발행사, 사업연도) 배당 지표 행. 미수록 조합은 빈 목록."""
    spec = _DIVIDEND_SPECS.get((corp_code, _slot(year)))
    return [_dividend(corp_code, year, *spec)] if spec else []


def _shareholder(corp_code: str, year: int, name: str, relation: str, shares: int, ratio: str) -> dict:
    rcept_no, report_nm = _report_ref(corp_code, year)
    return {
        "corp_code": corp_code,
        "nm": name,
        "relate": relation,  # 본인·특수관계인 관계
        "trmend_posesn_stock_co": str(shares),  # 기말 소유주식수
        "trmend_posesn_stock_qota_rt": ratio,  # 기말 지분율(%)
        "rcept_no": rcept_no,
        "report_nm": report_nm,
    }


# corp_code -> [(성명·법인명, 관계, 기말 소유주식수, 기말 지분율(%)), ...]
_SHAREHOLDER_SPECS: dict[str, list[tuple[str, str, int, str]]] = {
    "00126380": [
        ("이재용", "최대주주 본인", 97_414_196, "1.63"),
        ("삼성생명보험", "특수관계인", 508_157_148, "8.51"),
        ("삼성물산", "특수관계인", 298_818_100, "5.01"),
    ],
    "00164779": [
        ("SK스퀘어", "최대주주 본인", 145_213_812, "19.94"),
        ("국민연금공단", "특수관계인 외", 65_400_000, "8.98"),
    ],
    "00164742": [
        ("현대모비스", "최대주주 본인", 44_606_273, "21.43"),
        ("정의선", "특수관계인", 5_433_198, "2.61"),
    ],
    "00266961": [
        ("국민연금공단", "최대주주 본인", 12_900_000, "8.34"),
        ("이해진", "특수관계인", 5_000_000, "3.23"),
    ],
}


def mock_shareholders(corp_code: str) -> list[dict]:
    """발행사의 최대주주·특수관계인 지분 행 — 인용 근거는 최근 확정 사업연도의 사업보고서."""
    year = latest_closed_bsns_year()
    return [_shareholder(corp_code, year, *spec) for spec in _SHAREHOLDER_SPECS.get(corp_code, [])]
