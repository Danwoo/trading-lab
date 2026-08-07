# multi-agent 도메인 추가 교본 + 개발 가이드 (설계)

> 상태: 승인됨 (brainstorming 후속) · 작성 2026-06-13

## 목적

example-agent-service(single-agent 교본)의 **졸업 경로** 두 조각:
1. multi-agent-service 에 **도메인/sub-agent 를 추가**하는 dormant 교본 파일.
2. `.docs/guides/multi-agent-development.md` — `fastmcp-development.md` 와 대칭되는 절차 문서.

single-agent(③층 `create_agent`)에서 multi-agent(③을 sub-agent 로 쓰는 ②res_pipeline + ①Plan-Execute
StateGraph + PlanExecuteState)로 넘어갈 때, "도메인 1개를 어떻게 추가하나"를 코드 교본 + 절차 문서로 가르친다.

## 범위

- ✅ `agents/domains/example.py` — **dormant 교본 도메인** (`SUBAGENT_SPECS`+`DOMAIN_SPEC`+`register()`, 가이드 주석).
  실재 tool(`web_search`)에 바인딩 — 5접점 배선만 하면 즉시 동작하지만 기본은 미배선(미동작).
- ✅ `.docs/guides/multi-agent-development.md` — 절차·결합점·함정 문서.
- ⛔ 실제 활성화(5접점 배선)는 하지 않는다 — 교본은 dormant, 활성화는 가이드가 설명.

## example.py 설계

financials.py 구조를 그대로 따르되 가이드 주석 내장. 최소 1 sub-agent:

- `SUBAGENT_SPECS = {"example_sub": SubAgentSpec(domain="example", description=..., mcp_tools=["web_search"], prompt=build_subagent_prompt(...))}`
  - `mcp_tools` 는 실재 operation_id(`web_search`) — 미존재 이름은 기동 시 "MCP 도구 없음" 경고 후 제외됨을 주석으로.
- `DOMAIN_SPEC = DomainSpec(sub_agents=["example_sub"], description=..., prompt=..., builder="res_pipeline")`
  - `description` = **planner 가 이 도메인을 고르는 유일 단서** (이번 세션 news(뉴스·매크로) 라우팅 교훈: 도메인·sub-agent description 에 도메인 키워드가 없으면 planner/RES 가 라우팅 안 함).
- `register()` → `{"sub_agents":..., "domain_key":"example_domain", "domain_spec":...}`.
- 가이드 주석: SubAgentSpec(mcp_tools lockstep)·DomainSpec(description=planner 라우팅, prompt=도메인내 sub 선택)·
  build_subagent_prompt(공통 5섹션+보안footer)·builder(res_pipeline vs react)·**dormant 이유와 활성화 5접점 포인터**.

## 가이드 문서 설계 (`multi-agent-development.md`)

`fastmcp-development.md` 와 대칭 구조:
1. 개요 — LangGraph 3층(StateGraph→res_pipeline→create_agent), 어디에 도메인이 끼는가.
2. **도메인 추가 5접점** (registry.py docstring 기반, 정본화):
   ① `agents/domains/<name>.py` (SUBAGENT_SPECS+DOMAIN_SPEC+register)
   ② `registry.py` `_DOMAIN_MODULES` 등록
   ③ `config.MULTI_AGENT_DOMAINS` 키 추가
   ④ `plan_execute/domains_map.py` `_DOMAIN_LABELS` + `_build_subagent_domain_map()` import
   ⑤ `events.py` `DOMAIN_KO_LABEL` 라벨
3. 결합점 — mcp_tools↔MCP operation_id lockstep, description↔planner/RES 라우팅.
4. 함정 (이번 세션 실증) — 라우팅은 description 주도(뉴스·매크로 도메인 사례), clarifier 가 사내 KB 인지해야 함,
   grounding 은 MCP 데이터 tool 만 인정(sub-agent 래퍼 제외), 동시성×LLM 타임아웃.
5. 검증 — 활성화 후 native `/agent` trace 로 도메인·tool·grounding 확인.

## 검증

- `example.py`: ruff + 독립 import (dormant 이라 런타임 미로드 — import 로 구조 유효성만).
- 가이드: 5접점 파일·심볼명이 실제 코드와 일치하는지 grep 대조.

## 비목표

- example_domain 실제 활성화·E2E (dormant 유지) · 새 MCP 서버 (web_search 재사용)
