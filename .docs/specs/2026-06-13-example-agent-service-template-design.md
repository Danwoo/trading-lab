# example-agent-service — single-agent 개발 교본 (설계)

> 상태: 승인됨 (brainstorming) · 작성 2026-06-13

## 목적

신규 **에이전트 서비스**를 만들 때 복사 시작점이 되는 단독 실행 교본.
`example-mcp-service`(MCP 서버 교본)와 **짝**을 이룬다 — example-mcp 가 노출하는 위키 tool 을
example-agent 가 소비한다. 둘을 함께 복사하면 "MCP 서버 + 그걸 쓰는 에이전트" 수직 슬라이스 완성.

대상 패턴은 **single-agent**: LangGraph `create_agent`(프리빌트 ReAct) 가 MCP tool 을 호출하며
SSE 로 스트리밍 답변. multi-agent(Plan-Execute)는 이 위에 그래프 2층 + 타입드 state 를 얹은
형태이므로, 본 교본은 그 **최하위 부품(③층)**을 가르치고 multi-agent-service 를 졸업 경로로 가리킨다.

### LangGraph 3층과 본 교본의 위치 (근거)

multi-agent-service 는 LangGraph 를 3층으로 쓴다:

1. 최상위 — 커스텀 `StateGraph(PlanExecuteState)` (clarify→plan→execute→answer|map→reduce)
2. 중간 — 도메인별 `res_pipeline`(Route–Execute–Synthesize) 그래프
3. 최하위 — sub-agent = `create_agent(llm, tools, system_prompt=...)`

**example-agent-service = ③층 1개.** multi-agent = ③을 sub-agent 로 쓰고 ②·①과 `PlanExecuteState`
TypedDict 를 더한 것. 따라서 교본의 "졸업 안내"가 코드 사실과 정확히 일치한다.

## 범위 (이번 spec)

- ✅ 단독 실행 `example-agent-service` (single-agent, 위키 tool 소비, SSE 채팅, 가이드 주석)
- ⛔ 별도 spec 으로 분리: multi-agent 교본(도메인 추가) · `.docs/guides/multi-agent-development.md`
  (본 교본 README·주석이 이들을 졸업 경로로 가리키기만 한다)

## 결정 사항 (확정)

| 항목 | 결정 |
|---|---|
| 형태 | 단독 실행 서비스 폴더 (example-mcp-service 와 동급) |
| 에이전트 패턴 | LangGraph `create_agent` 프리빌트 ReAct (devactivity-service 와 동일) |
| 소비 tool | example-mcp-service 의 `wiki_search_pages`·`wiki_get_page_summary` |
| 응답 계약 | 단순 네이티브 SSE (`step`·`token`·`error` + `[DONE]`) |
| 상태/멀티턴 | DB 없음, 단일턴 (state 최소 — 교본 단순성) |
| 포트 | 8010 |
| process-compose | 미등록 (단독 기동 전용, example-mcp 와 동일 정책) |

## 아키텍처 · 레이아웃

```
example-agent-service/app/
  main.py                        # FastAPI + lifespan(에이전트 1회 초기화) + (MCP 미서버, REST only)
  core/                          # config·container·security·exception_handler·logger·middlewares·auth_context (공통본)
  clients/
    mcp/mcp_client.py            # MultiServerMCPClient 빌더 (config.MCP_SERVERS)
    mcp/mcp_auth.py              # ServiceJwtAuth (create_access_token 매 요청 재발급 httpx auth)
    llm/llm_client.py            # ChatOpenAI(vLLM) 빌더
  agents/chat_agent.py           # ★ create_agent(llm, tools, system_prompt=SYSTEM) — 단일 ReAct
  services/chat/chat_service.py  # initialize(MCP tool 1회 수집) + stream_chat(question) → 이벤트 yield
  routers/chat/chat_router.py    # POST /chat (SSE), dependencies=[Depends(verify_access_token)]
  schemas/chat/chat_schema.py    # ChatIn{question}
  utils/                         # (필요 시 순수함수)
  .env.{development,staging,production}
README.md                        # 복사·검증 체크리스트 + multi-agent 졸업 안내
```

- multi-agent-service 와 달리 MCP **서버가 아니라 소비자** — `from_fastapi` 없음, 순수 FastAPI REST + SSE.
- DI 는 표준 컨테이너 (config→client(mcp/llm)→service→wiring). agent 는 service 가 보유.

## 에이전트 코어

- **mcp_client.py**: `config.MCP_SERVERS`(기본 `[{"name":"wiki","url":"http://localhost:8009"}]`) →
  `langchain_mcp_adapters.MultiServerMCPClient` + `ServiceJwtAuth`. multi-agent 의 MCP 소비 축약본.
- **mcp_auth.py**: `httpx.Auth` 서브클래스 — 매 요청 `create_access_token()`(sub=SERVICE_NAME, exp 분단위)
  로 Authorization 헤더 주입. exp 가 짧아 정적 토큰 금지.
- **chat_agent.py**: `create_agent(model=llm, tools=mcp_tools, system_prompt=SYSTEM)`.
  SYSTEM = "위키 tool 로 사실 확인, 검색 결과에만 근거, 없으면 모른다고 답" 정직 지침.
- **chat_service.py**: lifespan `initialize()` 가 MCP tool 1회 수집 후 agent 빌드(Singleton).
  `stream_chat(question)` 가 `graph.astream({"messages":[Human]}, stream_mode=["updates","messages"])`:
  - `updates` 의 tool 노드 → `step` 이벤트(tool 명·진행)
  - `messages` 의 answer 토큰 → `token` 이벤트
  MCP 미기동 시 tool 0개 fail-soft (LLM 지식 답변).

## 엔드포인트 · SSE 계약

`POST /chat` · body `ChatIn{question: str}` · `dependencies=[Depends(verify_access_token)]`
프레이밍 `data: {json}\n\n` … 종료 `data: [DONE]\n\n`. 이벤트 type:

- `step` — `{"type":"step","tool":"wiki_search_pages","message":"위키 검색 중"}`
- `token` — `{"type":"token","content":"..."}`
- `error` — `{"type":"error","message":"..."}` (StreamingResponse 시작 후 예외는 라우터가 매핑)

(multi-agent 의 media/title/follow_up/grounding 라벨 없음 — 교본 최소. 졸업 시 추가 안내)

## 교본 요소 (핵심 가치)

- 파일별 `[가이드 N/N]` 헤더 (간결화된 example-mcp 톤: 무엇 / 복사 후 바꿀 것 / **함정**).
  함정 예: MCP `operation_id` 의존(서버 tool 이름 바뀌면 못 찾음) · `ServiceJwtAuth` 매요청 재발급 ·
  `create_agent` 의 `system_prompt` 가 에이전트 지침 · MCP 미기동 fail-soft · lifespan 1회 초기화.
- `README.md`: 복사 절차 + "example-mcp(8009) 먼저 기동" + curl 로 `/chat` SSE 검증.
- **multi-agent 졸업 안내** (README 말미 + chat_agent.py 주석): "단일 에이전트로 부족(다도메인·계획·
  맵리듀스)하면 multi-agent-service 의 Plan-Execute 로 — `create_agent` 가 거기선 sub-agent(③층),
  그 위에 res_pipeline(②) + StateGraph(①) + PlanExecuteState 가 얹힌다" + 포인터.

## 검증

- `ruff check` (앱 전체) + import smoke.
- **실런타임 E2E**: example-mcp(8009) + example-agent(8010) 동시 기동 →
  `POST /chat {"question":"판소리가 뭐야?"}` →
  `step`(wiki_search_pages 호출) + `token` 답변 스트림 + 실 위키 grounding 확인.

## 비목표 (YAGNI)

- 멀티턴/DB/checkpointer (단일턴) · media/title/follow_up · 다중 에이전트 · 가드레일 (single-agent 교본 범위 밖, 졸업 경로로만 언급)
