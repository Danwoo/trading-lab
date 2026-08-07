# plan_execute.py 분해 리팩터

`multi-agent-service/app/graphs/plan_execute.py` (1,324줄, 단일 파일) →
`multi-agent-service/app/graphs/plan_execute/` 패키지 **13개 파일 (최대 418줄)**.

**계약 보존**: `from graphs.plan_execute import COMPLIANCE_DISCLAIMER, build_plan_execute_graph`
(agent_service.py:20) 은 그대로 동작한다. 패키지 `__init__.py` 가 재노출.

> **2라운드 진행 완료 (issue #8)** — 아래 §1~§4 는 **1라운드** 기록이다. 1라운드는
> 순수 이동만 했고 `build_plan_execute_graph()` 794줄 거대 함수는 `builder.py` 안에 그대로 남겼다.
> 2라운드는 그 함수를 **실제로 분해**했다 — 노드 클로저를 top-level 로 끌어내며 파라미터화(=의도적
> 재작성)했고, **topology 축을 계약**으로 삼아 그래프 구조 동일성을 기계 검증했다. **§5 참조**.

---

## 1. 왜 이 경계인가 (요지)

이 파일의 통증은 두 가지였다. (a) `build_plan_execute_graph()` 하나가 790줄로 그래프 전부를
품고, (b) 새 도메인 추가 시 이 거대 파일의 `_DOMAIN_LABELS`·`_build_subagent_domain_map()` 를
손대야 했다.

경계는 **"함께 바뀌는 것끼리, 그리고 재사용 축끼리"** 로 잘랐다. 그래프 노드 클로저들은
LLM·타임아웃·agents 를 공유 캡처하므로 하나의 빌더 안에 두는 것이 자연스럽다 — 이들은
`builder.py` 로 통째 옮겼다(클로저를 top-level 로 끌어내 파라미터화하는 것은 "재작성"이라
동작 보존 계약을 위협하므로 하지 않았다). 그 대신 빌더가 **호출**하던 순수 헬퍼들 —
스키마(`schemas`), tool-trace 콜백(`tool_trace`), 프롬프트 컨텍스트 포매팅(`context`),
컴플라이언스(`compliance`), 도메인 분류·Map-Reduce 그룹핑(`domains_map`), 위상 정렬(`topology`),
에이전트 호출(`invocation`) — 을 관심사별 모듈로 분리했다. 결과적으로 **새 도메인 추가는 이제
39줄짜리 `domains_map.py` 만** 건드린다(1,324줄 파일이 아니라). 각 모듈은 IO 없는(또는 얕은)
단위라 개별 테스트·재사용이 쉽다.

---

## 2. 구 → 신 매핑표 (전체)

| 구 심볼 (`plan_execute.py`) | 신 위치 |
|---|---|
| `VALID_AGENTS`, `StageTask`, `ExecutionPlan`, `ReplanDecision`, `ClarifyDecision`, `PlanExecuteState` | `plan_execute/schemas.py` |
| `_tool_output_text`, `_ToolTraceCallback` | `plan_execute/tool_trace.py` |
| `_extract_query`, `_build_history_ctx`, `_format_prior_stage_results`, `_format_all_results_for_answer` | `plan_execute/context.py` |
| `COMPLIANCE_DISCLAIMER`, `_ensure_disclaimer` | `plan_execute/compliance.py` |
| `_DOMAIN_LABELS`, `_build_subagent_domain_map`, `_SUBAGENT_DOMAIN_MAP`, `_classify_domain`, `_group_results_by_domain`, `_count_active_domains`, `_format_domain_results` | `plan_execute/domains_map.py` |
| `_normalize_stages` | `plan_execute/topology.py` |
| `_invoke_agent_safe` | `plan_execute/invocation.py` |
| `build_plan_execute_graph` (+ 내부 노드 클로저 전부) | `plan_execute/builder.py` |
| 모듈 최상단 flow docstring + 공개 API 재노출 | `plan_execute/__init__.py` |

모든 심볼은 `graphs.plan_execute.<name>` 경로로 **여전히 접근 가능**(하위호환 재노출). 공개 API
(`__all__`): `COMPLIANCE_DISCLAIMER`, `build_plan_execute_graph`, `VALID_AGENTS`, `StageTask`,
`ExecutionPlan`, `ReplanDecision`, `ClarifyDecision`, `PlanExecuteState`.

파일 크기: `builder.py` 851 · `schemas.py` 111 · `tool_trace.py` 106 · `domains_map.py` 81 ·
`invocation.py` 76 · `__init__.py` 74 · `context.py` 68 · `topology.py` 45 · `compliance.py` 19.

---

## 3. 동작 보존 증명

LLM(ROUTER/GENERATOR)·MCP 키가 없어 그래프를 **실행**할 수 없다. 그래서 실행 대신 **정적 3축**으로
전(前, `origin/main` == 리팩터 직전 HEAD, 두 트리 diff 없음 확인)과 후(後)를 비교했다.

하네스: `multi-agent-service/app/graphs/_refactor_proof.py` — `graphs.plan_execute` 네임스페이스만
통해 접근하므로 **동일 스크립트가 전/후 모두에서 무수정 실행**된다.

1. **getsource (재작성 없음 증명)** — 이동한 20개 심볼(스키마 5 · 콜백 2 · 순수함수 12 ·
   `build_plan_execute_graph` 자체)의 `inspect.getsource()` 텍스트를 덤프. 빌더 790줄 포함 전부
   **byte-identical** = 로직을 다시 쓰지 않고 옮기기만 했음을 증명.
2. **behavior (순수함수 출력)** — `_normalize_stages`(독립/체인/순환/pydantic 입력), `_classify_domain`,
   `_ensure_disclaimer`, `_tool_output_text`(content-block/str/None), `_extract_query`,
   `_build_history_ctx`, `_format_*`, `_group_results_by_domain`, `_count_active_domains` 를
   결정론적 입력으로 호출해 출력 비교.
3. **topology (그래프 구조)** — 빌더는 LLM 을 호출하지 않고 클로저 생성 + StateGraph 배선만
   하므로 **mock LLM/agent 로 빌드 가능**. 컴파일된 그래프의 노드·엣지·조건분기 매핑을 덤프.
   `enable_clarify × enable_guardrail` 4조합 + `agent_descriptions=None` 까지 커버.

### 실행 결과

```
$ cd multi-agent-service/app
# 리팩터 전 (HEAD == origin/main):
$ uv run python -m graphs._refactor_proof > before.json
# 리팩터 후:
$ uv run python -m graphs._refactor_proof > after.json

$ md5sum before.json after.json
eb8199c7dd8e6a9427b13e3d9466a575  before.json
eb8199c7dd8e6a9427b13e3d9466a575  after.json      # ← 동일 해시
$ diff before.json after.json && echo IDENTICAL
IDENTICAL                                          # (67,589 bytes, 완전 일치)
```

증명된 그래프 topology (예: `clarify=T, guardrail=T` — 전/후 동일):

```
nodes: __start__ __end__ 보안검사 보충질문확인 계획수립 도메인실행 재계획 도메인별답변 답변작성 답변통합
edges:
  __start__->보안검사            보안검사->보충질문확인 [cond]   보안검사->__end__ [cond]
  보충질문확인->계획수립 [cond]  보충질문확인->__end__ [cond]    계획수립->도메인실행
  도메인실행->재계획             재계획->도메인실행 [cond]       재계획->답변작성 [cond]
  재계획->도메인별답변 [cond]    답변작성->__end__               도메인별답변->답변통합
  답변통합->__end__
```

behavior 발췌 (전/후 동일): `_normalize_stages` chain `[['a'],['b','c']]` / cycle 안전망
`[['a','b']]`; `_count_active_domains` = 4; `_classify_domain("market_news")` = `"market"`,
`_classify_domain("holdings_sub")` = `"instrument"`(SUBAGENT_SPECS 우선).

**재현**: `uv run python -m graphs._refactor_proof` (cwd=`multi-agent-service/app`).

---

## 4. 발견했지만 고치지 않은 냄새 (기록만)

순수 리팩터 원칙에 따라 **손대지 않았다**. 모두 리팩터 이전부터 존재.

1. **정적 스키마 vs 동적 스키마 이중화** — `schemas.py` 의 `StageTask`/`ExecutionPlan`/
   `ReplanDecision`(Literal 고정)은 타입힌트·정적 참조 전용이고, 런타임 라우팅은 `builder.py` 가
   `agents.keys()` 로 다시 만드는 `_StageTask`/`_ExecutionPlan`/`_ReplanDecision` 를 쓴다. 특히
   `ReplanDecision` 은 런타임에서 **사실상 미사용**(동적 `_ReplanDecision` 로 완전 대체). 의도된
   설계지만 두 정의가 표류할 위험이 있다.
2. **`_plan_node` 반환 타입 불일치(무해)** — `plan: ExecutionPlan` 로 애노테이트하지만 실제로는
   동적 `_ExecutionPlan` 인스턴스가 담긴다(실패 폴백만 진짜 `ExecutionPlan(stages=[])`). `.stages`
   덕타이핑으로 동작. 정적 타입 검사기에는 잡히지 않는 이름 불일치.
3. **`_extract_query` 의 `.content.strip()`** — 메시지 content 가 str 이라고 가정. 멀티모달
   content(list) 가 들어오면 `AttributeError`. 현재 경로에선 항상 str 이라 발현 안 함.

(냄새 1·2 는 `agent_service.py` 밖 그래프 내부 계약이라, 향후 정리 시 §3 하네스로 회귀 검증 가능.)

---

## 5. 2라운드 — `build_plan_execute_graph()` 794줄 실제 분해 (issue #8)

### 왜 1라운드에서 못 했나

1라운드 프롬프트가 "분해"와 "로직 재작성 금지"를 동시에 요구했다. 그래프 노드는 클로저로
`planner_llm`/`generator_llm`/`agents`/타임아웃을 캡처하므로, 노드를 top-level 로 빼려면
**캡처 변수의 파라미터화 = 재작성**이 불가피하다. 그래서 1라운드는 순수 헬퍼만 형제 모듈로 옮기고,
빌더는 통째로 남겼다(§1). 남은 794줄이 이번 대상.

### 안전망 — topology 축이 계약

`getsource`(byte-identical)·`behavior`(순수함수 출력) 축은 **재작성으로 깨지는 게 정상**이다.
대신 `scripts/verify_plan_execute_refactor.py` 의 **topology 축**이 계약이다: mock LLM/agent 로
그래프를 조립해 컴파일된 **노드·엣지·조건분기**를 덤프한다(`enable_clarify × enable_guardrail`
4조합 + `agent_descriptions=None`, 총 5 케이스). 클로저를 파라미터화해도 **그래프 구조가 동일하면
안전**함을 기계적으로 증명한다.

**결과**: 리팩터 전 baseline 대비 topology **완전 일치(MATCH)**. `constants`·`behavior` 축도
일치(순수 헬퍼 미변경). `sources` 축은 `build_plan_execute_graph` **1개 심볼만** 변경 —
곧 블라스트 반경이 정확히 목표 함수에 국한됐음을 뜻한다.

```
$ uv run python scripts/verify_plan_execute_refactor.py   # cwd=multi-agent-service
topology : MATCH        # ← 계약
constants: MATCH
behavior : MATCH
sources changed: ['build_plan_execute_graph']   # 의도된 재작성 1건
```

### 어떻게 잘랐나

클로저가 캡처하던 로컬(LLM·타임아웃·플래그·프롬프트)을 **`_GraphDeps` frozen dataclass** 한 곳에
모으고, 노드/라우터를 `(deps, state, config)` 시그니처의 **top-level async 함수**로 끌어냈다.
빌더는 `functools.partial(node_fn, deps)` 로 바인딩해 등록만 한다 — LangGraph 는 partial 의
signature 를 정확히 스트립하므로 노드 계약(`(state, config)`)이 유지된다. 라우터 trace 표시명은
partial 에 `__name__` 을 얹어 보존(`_named()` 헬퍼).

| 신 모듈 | 담당 | 줄 |
|---|---|---|
| `deps.py` | `_GraphDeps`(해결된 의존성) + 동적 라우팅 스키마 팩토리 | 95 |
| `nodes.py` | 코어 노드 — guardrail·clarify·plan·run_stage·replan·answer | 416 |
| `map_reduce.py` | Map(도메인별 sub-answer)·Reduce(통합) 노드 + 헬퍼 | 290 |
| `routing.py` | 조건 분기 라우터 4종 | 42 |
| `builder.py` | **순수 조립부** — deps 생성 + StateGraph 배선 (851→176줄) | 176 |

`builder.py` 는 이제 **배선 다이어그램**처럼 읽힌다(노드 추가 → partial 등록 → 엣지). 노드 로직·
Map-Reduce·라우팅을 각각 독립 모듈에서 수정·리뷰할 수 있다.

### 새 도메인 추가 절차 — 실제로 짧아졌나 (정직한 기록)

- **새 sub-agent 도메인 추가**: 여전히 **`domains_map.py` 1파일**만 손댄다(`_DOMAIN_LABELS` 라벨
  1줄 + `_build_subagent_domain_map()` import 목록). 이건 1라운드에서 이미 달성 — 2라운드가 더
  줄이지는 **않았다**. LLM 라우팅 스키마는 `agents.keys()` 로 자동 생성이라 수작업 0.
- **2라운드의 실질 이득은 "도메인"이 아니라 "그래프 형태" 변경**이다. 새 노드·새 분기·Map-Reduce
  정책 변경은 794줄 함수를 스크롤하는 대신 `nodes.py`/`routing.py`/`map_reduce.py` 의 해당 함수만
  고친다. 한 노드의 의존성이 무엇인지도 `_GraphDeps` 필드로 명시된다(암묵 클로저 캡처 → 명시 계약).
- 요컨대: **"도메인 추가"는 이미 1파일(불변), "노드/그래프 로직 수정·이해"가 이번에 국소화**됐다.

### 남은 냄새 (§4 에서 이어짐)

§4 의 냄새 1·2(정적 vs 동적 스키마 이중화, `_plan_node` 반환 타입 불일치)는 2라운드에서도
**동작 보존을 위해 그대로 뒀다**. 동적 스키마 팩토리는 `deps.py` 로 이동(`_build_dynamic_schemas`)해
빌더에서 분리했으나, 정적 `schemas.py` 정의와의 이중화 자체는 유지. 향후 통합 시 topology 축으로
회귀 검증 가능.
