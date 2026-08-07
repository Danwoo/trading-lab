"""Financials 도메인 정의 — financials_sub, filings_sub, dividend_sub.

mcp_tools 이름은 각 MCP 서비스 라우터의 operation_id (FastMCP tool 이름의 SoT)와 일치해야 한다.
미존재 이름은 경고 후 제외되고, MCP 서버 확장 시 자동 바인딩된다.
"""

from __future__ import annotations

from agents.specs import DomainSpec, SubAgentSpec, build_subagent_prompt

SUBAGENT_SPECS: dict[str, SubAgentSpec] = {
    "financials_sub": SubAgentSpec(
        domain="financials",
        description="기업 재무제표·실적·재무비율(매출·영업이익·ROE 등) 분석 전문가",
        mcp_tools=[
            "disclosure_financials",
            "disclosure_company",
            "doc_search_topic_earnings",
            "doc_search_topic_workspace",
        ],
        prompt=build_subagent_prompt(
            role="기업 재무·실적 분석 전문가",
            procedure_lines=[
                "1. 사용자가 올린 사내·개인 리서치 문서(리포트·IR·메모)가 있으면 일반 지식보다 먼저 확인하고, "
                "   질문과 관련되면 그 내용을 근거로 인용한다. 없거나 관련이 낮으면 지어내지 말고 근거가 없음을 밝힌다.",
                "2. 대상 기업 개황(업종·결산월·상장 정보)을 조회한다 (1회).",
                "3. 재무제표·실적(매출·영업이익·순이익·자산·부채)을 공시 데이터에서 조회한다 (1회).",
                "4. 실적 해설·컨센서스 맥락이 필요하면 사내 실적 자료를 1회 조회 (선택).",
                "5. 공시 수치가 일부만 있어도 출처(공시·보고기간) 병기 후 비율·추세를 해석 — "
                "   완전한 재무 데이터 부재만으로 즉시 거절하지 마세요.",
            ],
            output_format_lines=[
                "- 기업 개황: 회사명 | 업종 | 결산월",
                "- 핵심 실적: 매출액 | 영업이익 | 순이익 (보고기간·단위·통화 명기)",
                "- 재무비율: 영업이익률·ROE·부채비율 등 (산출 근거 수치 병기)",
                "- 출처(공시 보고서 / 사내 실적 자료 / 사용자 업로드 리서치 문서)",
            ],
            extra_caution=(
                "매출·이익·비율 수치는 공시 데이터에 명시된 값만 인용하고 보고기간을 함께 표기. "
                "공시에 없는 재무 수치를 LLM 지식으로 생성하는 것은 절대 금지 — "
                "비율은 인용한 원수치에서 산출하고 산출식을 밝히세요."
            ),
        ),
    ),
    "filings_sub": SubAgentSpec(
        domain="financials",
        description="공시 목록·공시 상세(사업보고서·주요사항보고 등) 조회 및 요약 전문가",
        mcp_tools=[
            "disclosure_list",
            "disclosure_detail",
            "doc_search_topic_filing",
        ],
        prompt=build_subagent_prompt(
            role="기업 공시 조사·요약 전문가",
            procedure_lines=[
                "1. 대상 기업의 최근 공시 목록을 기간·유형으로 조회한다 (1회).",
                "   찾을 것: 공시 제목, 접수일자, 보고서 유형, 접수번호.",
                "2. 가장 관련성 높은 공시는 접수번호로 상세 내용을 보강한다 (1회).",
                "3. 공시 해석·용어 보완이 필요하면 사내 공시 자료를 1회 조회 (선택).",
                "4. 공시 본문이 길어도 질문 핵심에 맞는 항목만 요약 — "
                "   일부 항목 부재만으로 전체 답변을 거절하지 마세요.",
            ],
            output_format_lines=[
                "- 주요 공시: 공시 제목 | 제출인 | 접수일 | 보고서 유형",
                "- 핵심 내용 요약 (1~3줄, 공시 본문 근거)",
                "- 투자 판단 관련 시사점",
                "- 출처(공시 접수번호 / 사내 공시 자료)",
            ],
            extra_caution=(
                "공시 제목·접수번호·일자·금액은 조회된 공시에 명시된 것만 인용. "
                "조회되지 않은 공시 항목을 지어내지 말고, 0건이면 조회 조건을 밝히고 '찾지 못했습니다'를 명시하세요."
            ),
        ),
    ),
    "dividend_sub": SubAgentSpec(
        domain="financials",
        description="배당(배당금·배당수익률·배당성향)과 최대주주·주요주주 지분 구조 분석 전문가",
        mcp_tools=[
            "disclosure_dividend",
            "disclosure_major_shareholder",
        ],
        prompt=build_subagent_prompt(
            role="배당·주주구조 분석 전문가",
            procedure_lines=[
                "1. 대상 기업의 배당 내역(주당배당금·배당수익률·배당성향)을 조회한다 (1회).",
                "2. 지분 구조가 필요하면 최대주주·주요주주 현황을 조회한다 (1회).",
                "3. 배당·지분 데이터가 일부만 있어도 배당 정책·지배구조 관점의 일반 해석을 제공 — "
                "   일부 수치 부재만으로 전체 답변을 거절하지 마세요.",
            ],
            output_format_lines=[
                "- 배당: 주당배당금 | 배당수익률(%) | 배당성향(%) (기준일·통화 명기)",
                "- 주주구조: 최대주주 | 지분율(%) | 특수관계인 포함 여부",
                "- 배당 지속성·지배구조 관점 코멘트",
                "- 출처(공시 배당·주주 데이터)",
            ],
            extra_caution=(
                "배당금·배당수익률·지분율은 공시 데이터에 명시된 값만 인용하고 기준일을 표기. "
                "공시에 없는 배당·지분 수치를 LLM 지식으로 생성하지 마세요."
            ),
        ),
    ),
}

DOMAIN_SPEC = DomainSpec(
    sub_agents=["financials_sub", "filings_sub", "dividend_sub"],
    # 업로드 문서 능력 문구는 graphs/system.py DEFAULT_AGENTS_SECTION 의 financials 행과 lockstep (#204)
    description="재무제표·실적·재무비율·공시·배당·주주구조 분석. 사용자 업로드 리서치 문서·사내 자료 검색·요약(doc-search workspace) 포함. 공시 기반 펀더멘털을 제공해 후속 도메인(리스크·밸류·시장)이 기업 가치 판단에 활용 가능.",
    prompt=(
        "당신은 재무·공시(Financials) 도메인 관리자입니다.\n\n"
        "━━ 하위 에이전트 ━━\n"
        "- financials_sub: 재무제표·실적 조사. 매출·영업이익·순이익·ROE·부채비율 등 재무 수치·비율 제공.\n"
        "- filings_sub: 공시 목록·상세 조회. 사업보고서·주요사항보고 등 공시 제목·접수번호·핵심 요약 제공.\n"
        "- dividend_sub: 배당·주주구조. 주당배당금·배당수익률·배당성향과 최대주주·주요주주 지분 제공.\n\n"
        "작업 지시문의 의미상 가장 적합한 에이전트 1개를 우선 호출하세요.\n\n"
        "복합 작업이면:\n"
        "  1. 우선 1개 호출 → 결과 확인 후 보완 필요 시 2번째 추가.\n"
        "  2. 최대 2회 호출 후 즉시 답변. 추가 호출 금지.\n\n"
        "수집 결과(실적 수치·공시 접수번호·배당 등)를 통합해 재무·공시 종합 분석을 제공하세요."
    ),
)


def register() -> dict:
    return {
        "sub_agents": SUBAGENT_SPECS,
        "domain_key": "financials_domain",
        "domain_spec": DOMAIN_SPEC,
    }
