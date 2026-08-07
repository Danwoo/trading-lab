# ── [가이드 6/9] agents/chat_agent.py — ★ create_agent 프리빌트 ReAct 빌더 (이 교본의 핵심) ──
# 무엇: create_agent(model, tools, system_prompt) = LLM 이 tool 을 골라 호출하고 결과를 보고 다시
#   추론하는 ReAct 루프 그래프. SYSTEM 프롬프트가 에이전트의 행동 지침(무엇을 근거로, 언제 tool 을).
# 복사 후: SYSTEM 을 새 도메인 지침으로. tools 는 service 가 MCP 에서 모아 넘긴다(여기선 받기만).
# 함정: system_prompt 가 곧 에이전트 지침 — "검색 결과에만 근거, 없으면 모른다" 같은 정직성 규칙을 여기
#   박는다(환각 방지) · tool 이름은 MCP operation_id 라 SYSTEM 에 적는 이름도 그것과 일치해야 모델이 부른다.
#
# ── multi-agent 졸업 (LangGraph 3층) ──
# 이 create_agent 가 multi-agent-service 에선 ③최하위 sub-agent 다. 다도메인·계획·맵리듀스가 필요해지면
# 그 위에 ②res_pipeline(Route-Execute-Synthesize) + ①StateGraph(PlanExecuteState) 를 얹는다.
# 즉 single-agent → multi-agent 는 "이 부품을 그대로 두고 위에 두 층을 더하는" 경로다. README "졸업" 절 참고.

from langchain.agents import create_agent
from langchain_core.tools import BaseTool

SYSTEM = (
    "당신은 웹 검색 tool 로 사실을 확인해 답하는 투자 리서치 애널리스트입니다. "
    "web_search 로 시장·거시지표·종목 관련 최신 뉴스·동향을 검색해 근거를 확인하세요. "
    "검색 결과에만 근거하고, 수치는 출처가 확인될 때만 인용하며, 없으면 모른다고 솔직히 답하세요. "
    "답변 끝에 'ⓘ 정보 제공 목적이며 투자 조언이 아닙니다'를 덧붙이세요."
)


def build_chat_agent(llm, tools: list[BaseTool], examples: str = ""):
    """단일 ReAct 에이전트 그래프 생성. tools 는 MCP 에서 수집한 목록(0개면 LLM 지식만으로 답).

    examples = tool 들의 few-shot 호출 예시 블록(collect_tool_examples) — 있으면 SYSTEM 에 덧붙여
    LLM 의 인자 구성을 돕는다. 예시는 서버 tool 이 _meta 로 소유, 여기선 받아 끼우기만.
    """
    system = f"{SYSTEM}\n\n{examples}" if examples else SYSTEM
    return create_agent(model=llm, tools=tools, system_prompt=system)
