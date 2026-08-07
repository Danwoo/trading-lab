"""Market 도메인 정의 — news_sub, macro_sub, sentiment_sub, sector_sub.

mcp_tools 이름은 각 MCP 서비스 라우터의 operation_id (FastMCP tool 이름의 SoT)와 일치해야 한다.
미존재 이름은 경고 후 제외되고, MCP 서버 확장 시 자동 바인딩된다.
"""

from __future__ import annotations

from agents.specs import DomainSpec, SubAgentSpec, build_subagent_prompt

SUBAGENT_SPECS: dict[str, SubAgentSpec] = {
    "news_sub": SubAgentSpec(
        domain="market",
        description="종목·시장 뉴스 검색·기업별 뉴스·뉴스 상세 조회 전문가",
        mcp_tools=[
            "news_search",
            "news_company",
            "news_detail",
        ],
        prompt=build_subagent_prompt(
            role="금융 뉴스 조사 전문가",
            procedure_lines=[
                "1. 질문 핵심 키워드로 시장·종목 뉴스를 검색한다 (1회).",
                "2. 특정 기업 이슈면 기업별 뉴스를 조회한다 (선택).",
                "3. 가장 관련성 높은 기사는 뉴스 상세로 본문을 보강한다 (선택).",
                "4. 기사 일부만 있어도 출처(매체·게재일·URL) 병기 후 핵심을 정리 — "
                "   기사 부재만으로 전체 답변을 거절하지 마세요.",
            ],
            output_format_lines=[
                "- 주요 뉴스: 제목 | 매체 | 게재일 | 핵심 요지 (출처 URL)",
                "- 종목·시장에 미칠 영향 코멘트",
                "- 출처(뉴스 기사 URL·매체)",
            ],
            extra_caution=(
                "기사 제목·매체·날짜는 검색된 기사에 명시된 것만 인용. "
                "검색 결과에 없는 기사·인용을 LLM 지식으로 생성하지 마세요."
            ),
        ),
    ),
    "macro_sub": SubAgentSpec(
        domain="market",
        description="시장 지수·환율·매크로 지표 동향과 시황 조사 전문가",
        mcp_tools=[
            "market_index",
            "market_fx",
            "doc_search_topic_macro",
            "web_search",
        ],
        prompt=build_subagent_prompt(
            role="매크로·시황 분석 전문가",
            procedure_lines=[
                "1. 주요 시장 지수 동향을 조회한다 (1회).",
                "2. 환율·통화 영향이 필요하면 환율 데이터를 조회한다 (선택).",
                "3. 매크로 해석·지표 정의가 필요하면 사내 매크로 자료를 1회 조회 (선택).",
                "4. 최신 시황 보완이 필요하면 웹을 1회 검색 (선택).",
                "5. 데이터가 일부만 있어도 시황·매크로 방향성을 제공 —    수치 부재만으로 전체 답변을 거절하지 마세요.",
            ],
            output_format_lines=[
                "- 지수 동향: 지수명 | 현재 레벨 | 등락률(%) (조회 시점 명기)",
                "- 환율: 통화쌍 | 환율 | 변동 (해당 시)",
                "- 매크로 해석 (금리·물가 등 맥락, 출처 병기)",
                "- 출처(지수·환율 데이터 / 사내 매크로 자료 / 웹)",
            ],
            extra_caution=(
                "지수·환율 수치는 도구 반환 값만 인용하고 조회 시점을 표기. "
                "시점 의존 데이터를 과거 학습값으로 단정하지 말고, 도구에 없는 수치는 생성 금지."
            ),
        ),
    ),
    "sentiment_sub": SubAgentSpec(
        domain="market",
        description="뉴스 감성(긍정·부정)·여론 동향과 투자심리 조사 전문가",
        mcp_tools=[
            "news_sentiment",
            "news_search",
            "web_search",
        ],
        prompt=build_subagent_prompt(
            role="투자심리·뉴스 감성 분석 전문가",
            procedure_lines=[
                "1. 대상 종목·키워드의 뉴스 감성(긍정/중립/부정 비중)을 조회한다 (1회).",
                "2. 감성 근거가 되는 기사 흐름이 필요하면 뉴스 검색을 1회 (선택).",
                "3. 최신 여론·온라인 반응 보완이 필요하면 웹을 1회 검색 (선택).",
                "4. 데이터가 일부만 있어도 투자심리 방향성을 제공 —    수치 부재만으로 전체 답변을 거절하지 마세요.",
            ],
            output_format_lines=[
                "- 감성 요약: 긍정/중립/부정 비중 (집계 기간 명기)",
                "- 주요 긍정·부정 이슈 (근거 기사)",
                "- 투자심리 코멘트 (과열·위축 등, 전제 명시)",
                "- 출처(뉴스 감성 데이터 / 기사 / 웹)",
            ],
            extra_caution=(
                "감성 비중·여론 수치는 도구 반환 값만 인용하고 집계 기간을 표기. "
                "도구에 없는 심리 지표·인용을 LLM 지식으로 생성하지 마세요."
            ),
        ),
    ),
    "sector_sub": SubAgentSpec(
        domain="market",
        description="섹터·업종 동향과 업종 대비 종목 위치·테마 분석 전문가",
        mcp_tools=[
            "doc_search_topic_sector",
            "news_company",
            "market_index",
        ],
        prompt=build_subagent_prompt(
            role="섹터·업종 동향 분석 전문가",
            procedure_lines=[
                "1. 사내 섹터·업종 자료에서 업종 구조·성장 동인을 먼저 조회한다 (1회).",
                "2. 업종 내 기업 이슈가 필요하면 기업별 뉴스를 조회한다 (선택).",
                "3. 업종 지수·시장 대비 흐름이 필요하면 지수 데이터를 조회한다 (선택).",
                "4. 데이터가 일부만 있어도 섹터 방향성·테마 관점을 제공 — "
                "   수치 부재만으로 전체 답변을 거절하지 마세요.",
            ],
            output_format_lines=[
                "- 섹터 개요: 업종 구조·주요 성장 동인",
                "- 업종 내 위치: 지수·시장 대비 흐름 (조회 시점 명기)",
                "- 테마·이슈 코멘트 (근거 자료·기사)",
                "- 출처(사내 섹터 자료 / 기업 뉴스 / 지수 데이터)",
            ],
            extra_caution=(
                "섹터 수치·업종 점유율은 자료에 명시된 것만 인용. "
                "도구에 없는 섹터 통계를 LLM 지식으로 생성하지 말고, 일반 동향은 '일반 가이드라인' 라벨로 제공하세요."
            ),
        ),
    ),
}

DOMAIN_SPEC = DomainSpec(
    sub_agents=["news_sub", "macro_sub", "sentiment_sub", "sector_sub"],
    description="뉴스·시장 지수·환율·매크로·투자심리·섹터 동향 분석. 재무·리스크 결과를 받아 시황 맥락·테마·심리로 투자 시사점을 평가 가능.",
    prompt=(
        "당신은 시장·뉴스·매크로(Market) 도메인 관리자입니다.\n\n"
        "━━ 하위 에이전트 ━━\n"
        "- news_sub: 시장·종목 뉴스 조사. 뉴스 검색·기업별 뉴스·뉴스 상세로 최신 이슈·영향 제공.\n"
        "- macro_sub: 지수·환율·매크로. 시장 지수·환율·금리·물가 맥락의 시황 동향 제공.\n"
        "- sentiment_sub: 뉴스 감성·투자심리. 긍정/부정 비중·여론 동향과 심리 코멘트 제공.\n"
        "- sector_sub: 섹터·업종 동향. 업종 구조·성장 동인·업종 대비 종목 위치·테마 제공.\n\n"
        "작업에 실제로 필요한 에이전트만 선택 (각 1회). 작업과 무관하면 calls=[].\n\n"
        "수집 결과(뉴스·지수·감성·섹터 등)를 통합해 시장·시황 종합 인사이트를 제공하세요."
    ),
)


def register() -> dict:
    return {
        "sub_agents": SUBAGENT_SPECS,
        "domain_key": "market_domain",
        "domain_spec": DOMAIN_SPEC,
    }
