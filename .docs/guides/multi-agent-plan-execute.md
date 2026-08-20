# plan_execute 그래프 패키지 — 모듈 경계와 계약

> multi-agent-service 의 최상위 그래프(`app/graphs/plan_execute/`)를 **어디를 열어 고치나**와, 고칠 때 깨면 안 되는 계약 두 가지. multi-agent-service 한정 — 도메인·sub-agent 를 끼우는 절차는 [멀티에이전트 개발 가이드](multi-agent-development.md)가 따로 다룬다.

---

## 1. 모듈 경계 — 무엇을 고치려면 어디를 여나

경계는 **재사용 축**으로 잘려 있다. 노드 로직·조립·순수 헬퍼가 각각 다른 파일이라, 그래프 형태를 바꾸는 사람과 도메인을 늘리는 사람이 같은 파일에서 만나지 않는다.

| 모듈 | 담당 |
|---|---|
| `__init__.py` | 공개 API 재노출 + 플로우 개관 |
| `builder.py` | **순수 조립부** — `_GraphDeps` 생성 + `StateGraph` 배선 |
| `deps.py` | `_GraphDeps`(해결된 의존성) + 동적 라우팅 스키마 팩토리 |
| `nodes.py` | 코어 노드 — guardrail·clarify·plan·run_stage·replan·answer |
| `map_reduce.py` | Map(도메인별 sub-answer)·Reduce(통합) 노드 + 헬퍼 |
| `routing.py` | 조건 분기 라우터 4종 |
| `schemas.py` | Pydantic 모델 + `PlanExecuteState` |
| `context.py` | 쿼리·히스토리·이전 stage 결과 프롬프트 포매팅 |
| `domains_map.py` | 도메인 라벨·분류 + Map-Reduce 그룹핑 (**새 도메인 추가 지점**) |
| `topology.py` | `depends_on_agents` 위상 정렬 |
| `invocation.py` | 에이전트 안전 호출(타임아웃·재시도) |
| `tool_trace.py` | `_ToolTraceCallback` + tool 출력 텍스트 추출 |
| `compliance.py` | `COMPLIANCE_DISCLAIMER` + 결정론적 고지 백스톱 |

무게는 `nodes.py`·`map_reduce.py` 에 몰려 있고 `builder.py` 는 배선만 남긴다. 열 곳을 고르는 기준:

- **새 도메인·sub-agent** → 이 패키지에서는 `domains_map.py` 한 파일뿐이다(라벨 1줄 + import 1줄). 나머지 4접점은 패키지 밖 — [개발 가이드 §3](multi-agent-development.md) 참조. LLM 라우팅 스키마는 `agents.keys()` 로 자동 생성이라 수작업이 없다.
- **새 노드·새 분기·Map-Reduce 정책** → `nodes.py` / `routing.py` / `map_reduce.py` 의 해당 함수. `builder.py` 는 배선 다이어그램처럼 읽히도록 로직을 두지 않는다.
- **노드가 무엇에 의존하나** → `deps.py` 의 `_GraphDeps` 필드가 명시 계약이다. 클로저 캡처로 몰래 늘리지 않는다.

---

## 2. 계약 ① — `graphs.plan_execute` 네임스페이스

패키지 밖 소비자는 서브모듈을 직접 import 하지 않는다. `services/agent/agent_service.py` 가 쓰는 형태가 정본이다:

```python
from graphs.plan_execute import COMPLIANCE_DISCLAIMER, build_plan_execute_graph
```

`__init__.py` 는 공개 API(`__all__`) 외에 내부 헬퍼도 같은 경로로 재노출한다 — 검증 하네스가 서브모듈 구조와 무관하게 심볼에 닿기 위해서다. 모듈을 쪼개거나 합칠 때 **재노출 목록을 함께 갱신**해야 이 경로가 끊기지 않는다.

---

## 3. 계약 ② — topology 축

노드 함수는 `(deps, state, config)` 시그니처의 **top-level 함수**이고, `builder.py` 가 `functools.partial(node_fn, deps)` 로 바인딩해 등록한다. LangGraph 는 partial 의 signature 를 정확히 스트립하므로 노드 계약 `(state, config)` 이 유지된다. 라우터는 trace 표시명이 partial 에서 사라지므로 `_named()` 헬퍼가 `__name__` 을 얹어 보존한다.

노드 로직을 옮기거나 의존성을 바꿔도 **컴파일된 그래프의 노드·엣지·조건분기가 같으면 안전**하다 — 그것을 기계로 잡는 것이 `scripts/verify_plan_execute_refactor.py` 의 topology 축이다. LLM·MCP 키 없이 mock LLM/agent 로 그래프를 조립해 구조를 덤프한다(`enable_clarify × enable_guardrail` 4조합 + `agent_descriptions=None`, 5 케이스).

```bash
# cwd = multi-agent-service
uv run python scripts/verify_plan_execute_refactor.py                    # 현재 트리 덤프(JSON)
uv run python scripts/verify_plan_execute_refactor.py --against origin/main   # 축별 MATCH/MISMATCH
```

`--against` 는 ref 를 임시 워크트리로 꺼내 같은 하네스를 돌리고 topology·constants·behavior 세 축을 대조한다. `sources` 축(심볼 소스 텍스트)은 재작성하면 달라지는 것이 정상이라 **의도한 심볼만 바뀌었는지**를 읽는 데 쓴다.

> 그래프 구조를 **의도적으로** 바꾸는 변경이면 topology MISMATCH 가 정답이다. 이 축은 "바뀌면 안 된다"가 아니라 "바뀐 줄 모르고 지나가면 안 된다"를 잡는다.

정적/동적 스키마의 문안 표류는 별도 그물이 맡는다 — `scripts/verify_schema_parity.py` 가 `deps._build_dynamic_schemas` 의 3종이 `schemas.py` 정적 모델의 서브클래스이고 필드 문안이 같은지 대조한다.

---

관련 문서: [멀티에이전트 개발 가이드](multi-agent-development.md) · [멀티에이전트 판단 Flow & 시연](multi-agent-trace-walkthrough.md) · [multi-agent-service README](../../multi-agent-service/README.md)
