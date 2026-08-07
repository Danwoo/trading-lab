# ── [도메인 추가 교본] agents/domains/example.py — 복사용 dormant 참조 ──────────────────
# 이 파일은 "multi-agent 에 새 도메인 추가" 교본이다. 실제로는 미배선(dormant) — registry 의
# _DOMAIN_MODULES·config.MULTI_AGENT_DOMAINS 에 없어 기동 시 로드되지 않는다. 복사해 새 도메인을
# 만들 때 출발점으로 쓰고, 활성화 5접점은 .docs/guides/multi-agent-development.md 참조.
#
# 한 도메인 = sub-agent N개(각자 MCP tool 보유) + 도메인 관리자(RES pipeline). 라우팅은 2단계:
#   ① planner 가 DOMAIN_SPEC.description 으로 이 도메인을 고름 → ② 도메인 RES 가
#   SubAgentSpec.description 으로 sub-agent 를 고름. 두 description 에 도메인 키워드가 없으면
#   라우팅이 안 된다 (descriptions = LLM 라우팅의 유일 단서).
# ──────────────────────────────────────────────────────────────────────────────────────

from agents.specs import DomainSpec, SubAgentSpec, build_subagent_prompt

# ── sub-agent 들 ──
# 함정: mcp_tools 이름 = MCP 서버 라우터의 operation_id 와 정확 일치 (lockstep). 미존재 이름은
#   기동 시 "[sub_agents] MCP 도구 없음" 경고 후 제외 — 서버에 그 tool 이 생기면 자동 바인딩.
#   여기선 항상 실재하는 web_search(web-mcp-service) 하나로 최소 시연.
SUBAGENT_SPECS: dict[str, SubAgentSpec] = {
    "example_sub": SubAgentSpec(
        domain="example",
        # description = 도메인 RES 가 sub-agent 를 고르는 단서. 무엇을 조사하는 전문가인지 명확히.
        description="예시 주제를 웹에서 조사하는 전문가 (교본용)",
        mcp_tools=["web_search"],
        # build_subagent_prompt = 공통 5섹션(역할·도구상한·절차·출력·실패문구) + 보안/진실성 footer 자동 삽입.
        prompt=build_subagent_prompt(
            role="예시 주제 웹 조사 전문가",
            procedure_lines=[
                "1. 주제 핵심 키워드를 웹에서 1~2회 검색한다.",
                "2. 결과의 제목·요약·URL 로 근거를 정리. 검색 결과 밖 사실은 만들지 않는다.",
            ],
            output_format_lines=[
                "- 핵심 요지 2~3가지 (근거 URL 포함)",
                "- 출처(웹 검색 / '일반 가이드라인' 라벨)",
            ],
        ),
    ),
}

# ── 도메인 관리자 ──
# 함정: description = planner 가 이 도메인을 선택하는 유일 단서 (이 도메인이 다루는 주제 키워드를
#   빠짐없이). builder 기본 "res_pipeline"(Route-Execute-Synthesize 병렬). 단일 ReAct 가 필요하면 "react".
DOMAIN_SPEC = DomainSpec(
    sub_agents=["example_sub"],
    description="예시 도메인 — 교본용 웹 조사. (복사 후 이 도메인이 다루는 실제 주제로 교체)",
    prompt=(
        "당신은 예시(Example) 도메인 관리자입니다.\n\n"
        "━━ 하위 에이전트 ━━\n"
        "- example_sub: 예시 주제 웹 조사 (web_search).\n\n"
        "작업에 실제로 필요한 에이전트만 선택 (각 1회). 무관하면 calls=[].\n"
        "수집 결과를 통합해 간결한 인사이트로 제공하세요."
    ),
)


# register() = registry 가 호출하는 진입점. 이 형태를 그대로 유지한다 (domain_key 는 "<도메인>_domain").
def register() -> dict:
    return {
        "sub_agents": SUBAGENT_SPECS,
        "domain_key": "example_domain",
        "domain_spec": DOMAIN_SPEC,
    }
