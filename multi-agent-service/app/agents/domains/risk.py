"""Risk 도메인 정의 — risk_sub, valuation_sub, credit_sub.

mcp_tools 이름은 각 MCP 서비스 라우터의 operation_id (FastMCP tool 이름의 SoT)와 일치해야 한다.
미존재 이름은 경고 후 제외되고, MCP 서버 확장 시 자동 바인딩된다.
"""

from __future__ import annotations

from agents.specs import DomainSpec, SubAgentSpec, build_subagent_prompt

SUBAGENT_SPECS: dict[str, SubAgentSpec] = {
    "risk_sub": SubAgentSpec(
        domain="risk",
        description="가격 변동성·재무 건전성 기반 투자 리스크(베타·MDD·재무 레버리지) 분석 전문가",
        mcp_tools=[
            "disclosure_financials",
            "market_ohlc",
            "doc_search_topic_risk",
        ],
        prompt=build_subagent_prompt(
            role="투자 리스크 분석 전문가",
            procedure_lines=[
                "1. 대상 종목의 일별 OHLC를 조회해 변동성·낙폭 흐름의 근거를 확보한다 (1회).",
                "   찾을 것: 기간 변동성, 최대낙폭(MDD) 추정, 가격 추세.",
                "2. 재무 레버리지·이익 변동이 필요하면 공시 재무제표를 조회한다 (1회).",
                "3. 리스크 지표 정의·해석이 필요하면 사내 리스크 자료를 1회 조회 (선택).",
                "4. 일부 데이터만 있어도 변동성·재무 리스크 관점의 해석을 제공 — "
                "   수치 일부 부재만으로 전체 답변을 거절하지 마세요.",
            ],
            output_format_lines=[
                "- 가격 리스크: 기간 변동성·최대낙폭(MDD) 추정 (산출 기간 명기)",
                "- 재무 리스크: 부채비율·이자보상배율 등 (공시 원수치 병기)",
                "- 종합 리스크 코멘트 (한계·전제 포함)",
                "- 출처(시세 OHLC / 공시 재무 / 사내 리스크 자료)",
            ],
            extra_caution=(
                "변동성·MDD는 '조회 OHLC 기준 추정'임을 명시하고 산출 기간을 표기. "
                "공시·시세에 없는 리스크 수치를 LLM 지식으로 생성하지 말고, 원수치에서 산출하세요."
            ),
        ),
    ),
    "valuation_sub": SubAgentSpec(
        domain="risk",
        description="밸류에이션(PER·PBR·EV/EBITDA)과 지수 대비 상대가치 분석 전문가",
        mcp_tools=[
            "disclosure_financials",
            "market_index",
            "doc_search_topic_valuation",
        ],
        prompt=build_subagent_prompt(
            role="밸류에이션·상대가치 분석 전문가",
            procedure_lines=[
                "1. 공시 재무제표에서 이익·자본·EBITDA 등 밸류 산출 기준 수치를 조회한다 (1회).",
                "2. 시장 지수·섹터 대비 상대 비교가 필요하면 지수 데이터를 조회한다 (1회).",
                "3. 밸류에이션 방법론·멀티플 해석이 필요하면 사내 밸류 자료를 1회 조회 (선택).",
                "4. 일부 수치만 있어도 멀티플 산출·상대가치 관점을 제공 — "
                "   완전한 데이터 부재만으로 전체 답변을 거절하지 마세요.",
            ],
            output_format_lines=[
                "- 밸류 멀티플: PER·PBR·EV/EBITDA (산출 근거 수치·기준일 병기)",
                "- 상대 비교: 시장 지수·섹터 평균 대비 위치",
                "- 밸류에이션 코멘트 (고평가/저평가 판단의 전제 명시)",
                "- 출처(공시 재무 / 지수 데이터 / 사내 밸류 자료)",
            ],
            extra_caution=(
                "PER·PBR 등 멀티플은 인용한 원수치(이익·자본·주가)에서 산출하고 산출식을 밝히세요. "
                "도구에 없는 멀티플·목표주가를 LLM 지식으로 단정 생성하는 것은 금지."
            ),
        ),
    ),
    "credit_sub": SubAgentSpec(
        domain="risk",
        description="채권·신용 리스크(부채구조·이자보상·신용등급 맥락)와 컴플라이언스 점검 전문가",
        mcp_tools=[
            "disclosure_financials",
            "doc_search_topic_fixed_income",
            "doc_search_topic_compliance",
        ],
        prompt=build_subagent_prompt(
            role="신용·채권 리스크 및 컴플라이언스 분석 전문가",
            procedure_lines=[
                "1. 공시 재무제표에서 부채구조·이자비용·현금흐름 관련 수치를 조회한다 (1회).",
                "2. 채권·신용 관점의 해석 기준이 필요하면 사내 채권(fixed income) 자료를 1회 조회 (선택).",
                "3. 공시·규제 준수 관점 점검이 필요하면 사내 컴플라이언스 자료를 1회 조회 (선택).",
                "4. 데이터가 일부만 있어도 신용 건전성·준수 관점의 일반 해석을 제공 — "
                "   수치 부재만으로 전체 답변을 거절하지 마세요.",
            ],
            output_format_lines=[
                "- 부채·신용: 총차입금 | 이자보상배율 | 단기/장기 비중 (공시 원수치 병기)",
                "- 상환·유동성 코멘트 (현금흐름 근거)",
                "- 컴플라이언스 점검 포인트 (해당 시)",
                "- 출처(공시 재무 / 사내 채권·컴플라이언스 자료)",
            ],
            extra_caution=(
                "차입금·이자보상·신용 관련 수치는 공시에 명시된 값만 인용. "
                "신용등급·채무불이행 단정 등 도구에 없는 평가를 LLM 지식으로 생성하지 마세요."
            ),
        ),
    ),
}

DOMAIN_SPEC = DomainSpec(
    sub_agents=["risk_sub", "valuation_sub", "credit_sub"],
    description="가격 변동성·밸류에이션·신용/채권 리스크·컴플라이언스 분석. 재무·시세 데이터를 받아 변동성·멀티플·신용 건전성을 구체 수치로 평가 가능.",
    prompt=(
        "당신은 리스크·밸류(Risk) 도메인 관리자입니다.\n\n"
        "━━ 하위 에이전트 ━━\n"
        "- risk_sub: 가격·재무 리스크. 변동성·최대낙폭(MDD)·부채비율·이자보상 등 리스크 지표 제공.\n"
        "- valuation_sub: 밸류에이션. PER·PBR·EV/EBITDA와 지수·섹터 대비 상대가치 제공.\n"
        "- credit_sub: 신용·채권·컴플라이언스. 부채구조·이자보상·상환 여력과 준수 점검 포인트 제공.\n\n"
        "작업 지시문의 의미상 가장 적합한 에이전트 1개를 우선 호출하세요.\n\n"
        "복합 작업이면:\n"
        "  1. 핵심 1개 먼저 호출 → 결과 확인 후 보완 필요 시 2번째 호출.\n"
        "  2. 최대 2회 호출 후 즉시 답변. 추가 호출 금지.\n\n"
        "수집 결과(변동성·멀티플·신용 지표 등)를 통합해 리스크·밸류 종합 평가를 제공하세요."
    ),
)


def register() -> dict:
    return {
        "sub_agents": SUBAGENT_SPECS,
        "domain_key": "risk_domain",
        "domain_spec": DOMAIN_SPEC,
    }
