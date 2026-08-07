# Multi-Agent 개발 가이드 — 도메인/에이전트 추가

multi-agent-service 에 **도메인을 추가**하는 절차·결합점·함정. single-agent 교본
(`single-agent-service`)에서 멀티 에이전트로 넘어올 때 본다.

## 1. 큰 그림 — LangGraph 3층

multi-agent 는 LangGraph 를 3층으로 쌓는다:

| 층 | 위치 | 역할 |
|---|---|---|
| ① 최상위 | `graphs/plan_execute/builder.py` `StateGraph(PlanExecuteState)` | clarify→plan→execute→answer\|map→reduce 오케스트레이션 (손수 짠 그래프) |
| ② 중간 | `graphs/res_pipeline.py` (도메인별) | Route–Execute–Synthesize. sub-agent 들을 tool 로 보유 |
| ③ 최하위 | `agents/builders.py`·`sub_agents.py` `create_agent(...)` | 프리빌트 ReAct. **= single-agent-service 가 만든 그것** |

**도메인을 추가한다 = ②③층에 도메인 1개(관리자 + sub-agent N개)를 끼우고, ①층 planner 가 고르게
하는 것.** state(`PlanExecuteState` TypedDict)는 노드가 dict 업데이트를 반환해 병합되며, checkpointer 는
쓰지 않는다 — 멀티턴은 공통 DB `ai_chat_history` 를 읽어 초기 messages 로 주입.

## 2. 도메인 1개 = 무엇으로 이뤄지나

`agents/domains/<name>.py` 한 파일에 3가지 (`agents/domains/example.py` 가 복사용 교본):

- `SUBAGENT_SPECS: dict[str, SubAgentSpec]` — sub-agent 들. 각자 `mcp_tools`(MCP tool 이름)·`description`·`prompt`.
- `DOMAIN_SPEC: DomainSpec` — `sub_agents`(이름 목록)·`description`(planner 단서)·`prompt`(도메인 관리자)·`builder`(기본 `res_pipeline`).
- `register() -> dict` — `{"sub_agents", "domain_key": "<name>_domain", "domain_spec"}`.

`SubAgentSpec.prompt` 는 `build_subagent_prompt(role, tool_budget, procedure_lines, output_format_lines,
failure_keyword, extra_caution)` 로 만든다 — 공통 5섹션 + 보안·진실성 footer 자동 삽입.

## 3. 활성화 — 5접점 배선

교본(`example.py`)은 dormant(미배선)다. 새 도메인을 **실제로 켜려면** 5곳:

1. **`agents/domains/<name>.py`** — 위 3종 작성 (example.py 복사).
2. **`agents/registry.py`** — `from agents.domains import <name>` + `_DOMAIN_MODULES` 에 `"<name>": <name>` 등록.
3. **`core/config.py`** — `MULTI_AGENT_DOMAINS` 기본값(또는 env)에 `"<name>"` 키 추가.
4. **`graphs/plan_execute/domains_map.py`** — `_DOMAIN_LABELS` 에 `"<name>_domain": "라벨"` + `_build_subagent_domain_map()`
   의 `from agents.domains.<name> import SUBAGENT_SPECS` 추가 (Map-Reduce 도메인 분류·라벨용).
5. **`utils/agent/events.py`** — `DOMAIN_KO_LABEL` 에 `"<name>_domain": "라벨"` (UI step 이벤트).

플래너 프롬프트·plan 스키마는 DOMAIN_REGISTRY 에서 동적 구성되므로 별도 수정 불필요.

## 4. 결합점 (lockstep)

- **`mcp_tools` ↔ MCP `operation_id`**: sub-agent 의 tool 이름 = 해당 MCP 서버 라우터의 `operation_id` 와
  정확히 일치해야 바인딩된다. 미존재 이름은 기동 시 `[sub_agents] MCP 도구 없음` 경고 후 제외(서버에
  그 tool 이 생기면 자동 바인딩). → MCP 서버는 `fastmcp-development.md` 로 먼저 만든다.
- **`description` ↔ 라우팅**: 2단계 모두 description 주도다. `DOMAIN_SPEC.description` 으로 **planner** 가
  도메인을 고르고, `SubAgentSpec.description`(+ 도메인 prompt 의 sub-agent 안내)으로 **도메인 RES** 가
  sub-agent 를 고른다. 두 곳에 도메인 키워드가 없으면 라우팅이 안 된다.

## 5. 함정 (실증된 것)

- **라우팅은 description 주도** — tool 을 sub-agent 에 붙여도, 도메인·sub-agent description 에 그 주제
  키워드가 없으면 planner/RES 가 그 경로를 안 고른다 (예: "배당" 질의가 description 누락으로
  instrument 로 잘못 가던 사례 → financials description 에 "배당·주요주주" 추가로 해결).
- **clarifier 게이트** — `graphs/system.py` `CLARIFY_SYSTEM` 이 공시·시세·뉴스 등 도구 보유 사실을 알아야 한다.
  모르면 "공시 자료 검색" 류 요청을 "접근 불가"로 거절한다. 새 데이터원을 추가하면 여기 반영.
- **planner 보수성** — `PLAN_SYSTEM_TEMPLATE` 이 "명시적 조회 요청"(시세·공시·재무·뉴스)엔 도메인을 선택하게 안내해야,
  일반지식으로 충분해 보이는 질의도 실제 조회를 탄다.
- **grounding 정직 라벨** — `utils/agent/grounding.py` 는 **MCP 데이터 tool 호출만** 근거로 인정하고
  sub-agent 래퍼 호출은 제외한다. 새 tool prefix 는 `utils/agent/mcp_classify.py` 에 분류 추가.
- **동시성 × LLM** — 동시 다발 멀티도메인 질의는 공유 LLM 엔드포인트를 포화시켜 `MA_AGENT_TIMEOUT_S`
  초과(도메인 timeout)를 부른다. 운용 시 `MA_MAX_CONCURRENT_STREAMS`·타임아웃·LLM 용량 고려.

## 6. 검증

활성화 후 native `/agent` (`enabled_mcps` 로 게이팅) 호출 → `trace` 이벤트의 `grounding`·`tool_calls`
(tool·input·status) 로 **그 도메인이 라우팅되고, 의도한 MCP tool 이 올바른 인자로 호출되며,
grounding 이 sourced 인지** 확인. SSE 스트림 형식은 `routers/agent/agent_router.py` 참조.

## 7. few-shot 예시 주입 (sub-agent별)

MCP tool 이 `_meta.few_shot_examples` 로 노출한 "질문 → 인자" 예시를 sub-agent 프롬프트에 주입해
LLM 의 인자 구성을 돕는다. **예시는 서버 tool 이 소유**(라우터에서 선언 — fastmcp-development.md),
소비자는 수집만 한다.

- `clients/mcp/mcp_client.py` `collect_tool_examples(tools)` — tool 들의 `metadata["_meta"]["few_shot_examples"]`
  를 프롬프트 블록으로. (서버 meta → wire → `tool.metadata["_meta"]` hop 을 이 함수 한 곳에 가둠)
- `create_sub_agents` 가 **각 sub-agent 의 바인딩 tool 만** 넘겨 호출 → 자기 예시만 받는다 (전역 주입 아님).
  생성 로그 `few-shot=있음/없음` 으로 부착 가시화.

```python
examples = collect_tool_examples(tools)  # 이 sub-agent 의 tool 들
parts = [base_prompt, examples, _SECURITY_FOOTER] if examples else [base_prompt, _SECURITY_FOOTER]
agent = create_agent(router_llm, tools, system_prompt="\n\n".join(parts))
```

## 8. 프롬프트 지식 SoT 경계 (도메인 사실 vs 오케스트레이션)

tool 을 쓰는 데 필요한 지식은 **소유 위치를 갈라** 중복·드리프트를 막는다. 입도(granularity)가 핵심:
sub-agent 는 tool 을 **개별 단위로(여러 서버 가로질러)** 묶으므로 지식도 **tool 단위로 tool 에 붙어 있어야** 어떤 묶음에도 따라온다.

| 지식 | SoT (소유) | sub-agent prompt 에 |
|---|---|---|
| tool 선택 규칙 (형제 대조: 보유→owner, korean vs international) | tool **docstring** (서버) | 적지 않는다 |
| 파라미터 예시 (질문→인자) | tool **`_meta.few_shot_examples`** (서버, §7) | 적지 않는다 |
| 도메인 식별자/포맷 규칙 (13자리·한글→영문) | tool docstring / 서버 `INSTRUCTIONS` | 적지 않는다 |
| 역할·tool 예산·호출 순서·ID 체인·출력 형식 | **sub-agent prompt (소비자)** | 여기만 |

즉 **sub-agent prompt = 오케스트레이션 전용** (역할·예산·절차·출력 + mcp_tools 바인딩). tool "사용법·선택 규칙"은
서버(docstring·few_shot)에 두고 prompt 에 복붙하지 않는다 — 서버만 고치면 모든 소비자에 반영된다.

> 단일 agent(서버 tool 을 통째로 쥠)는 서버 `INSTRUCTIONS` 를 통째로 끌어 쓰는 게 맞지만(devactivity 패턴),
> multi-agent 는 tool 부분집합을 쥐므로 서버 단위 `INSTRUCTIONS` 가 입도에 안 맞는다 — docstring+few_shot(tool 단위)을 쓴다.
> 둘 다 "서버가 도메인 지식 소유, 소비자는 조립"이라는 같은 철학의 다른 입도다.
