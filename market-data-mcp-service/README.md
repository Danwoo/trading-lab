# market-data-mcp-service — 시세·캔들·지수·환율·종목검색 MCP 서버

> 단일 FastAPI 앱이 REST 라우터를 그대로 서빙하면서, FastMCP `from_fastapi` 로 같은 라우트를 `/mcp` MCP tool 로 노출하는 도메인 MCP 서버 (포트 `:8004`). 시장데이터 5개 tool(시세·캔들·지수·환율·종목검색)을 LLM 투자 리서치 에이전트가 호출한다. DB·LLM 없음 — **기본은 인메모리 MOCK 픽스처라 API 키 없이 즉시 동작**하고, `USE_REAL_API=true` 일 때만 실 벤더를 감싼다.

## 핵심 (이 서비스가 보여주는 것)

- **단일 앱, 두 표면**: 하나의 FastAPI 앱이 REST(`/market/*`) 와 MCP(`/mcp`, Streamable HTTP) 를 동시에 서빙한다. `from_fastapi` 가 라우트를 tool 로 변환하고, tool 실행은 ASGI 로 다시 같은 앱의 라우트를 호출 → 검증·DI·예외처리 **한 벌**을 두 표면이 공유.
- **라우트가 tool 스펙의 SoT**: `operation_id` → tool 이름, docstring → tool 설명, Pydantic `In`/`Out` → 입출력 스키마. multi-agent-service 의 sub-agent 가 이 `operation_id`(`market_quote`·`market_ohlc`·`market_index`·`market_fx`·`market_search`) 로 tool 을 바인딩(lockstep) — 코드 한 곳이 계약을 정의.
- **에이전트 친화 도구 설계**: 각 tool docstring 에 "언제 이 도구를 쓰고 형제 도구와 어떻게 구분하는가"(한 점 가격=quote vs 기간 추세=ohlc, 종목=quote vs 시장=index, 코드 모르면 먼저 search)를 명시. `openapi_extra=few_shot([...])` 로 선언한 few-shot 예시는 `mcp_component_fn` 훅을 통해 tool `_meta` 로 노출 — 서버가 예시를 소유, 소비자(에이전트)는 수집만.
- **MOCK-우선 + 토글**: API 키 없이 바로 기동되도록 시세/캔들/지수/환율/종목검색이 **인메모리 픽스처**(공개 샘플 티커 — 삼성전자·SK하이닉스·NAVER·AAPL·MSFT·NVDA, KOSPI/KOSDAQ/SPX/IXIC, USD/KRW 등)로 응답한다. `USE_REAL_API=true` + `MARKET_API_KEY` 설정 시에만 실 벤더 REST 를 호출(선택·문서화). ⚠️ MOCK 수치는 데모용 고정 스냅샷이며 실거래·실투자용이 아니다.
- **결정론적 0건 폴백 (`staged_search`)**: 종목검색에서 시장 필터(KR/US)로 0건이면 ALL 로 완화해 자동 재검색. LLM 프롬프트의 "조건 줄여 재시도" 지시를 **코드로 보장** → 에이전트가 같은 도구를 반복 호출하지 않고 1회로 완화까지 끝낸다.
- **응답 정규화**: 벤더(또는 mock) 의 `{items, total}` 을 repository 가 `{data, total_count}` 단일 모델로 흡수. 벤더 레벨 오류는 빈 결과로 위장하지 않고 `BadRequestError` 로 즉시 노출.
- **레이어 분리 + DI**: Router(인증·@inject) → Service(도메인 로직·폴백) → Repository(외부 store 접근·파싱) → Client(transport·mock). 시세 벤더를 "외부 데이터 store" 로 보고 repository 로 감싸는 일관된 패턴.
- **컴플라이언스**: 모든 수치는 응답 `asof`(기준시각) 스냅샷이며 정보 제공 목적 — 서버 instructions 가 "투자 조언 아님" 정책을 명시.

## 기술 스택

FastAPI · FastMCP 3 (`from_fastapi`, Streamable HTTP) · Pydantic v2 · dependency-injector · httpx(AsyncClient) · tenacity(재시도) · PyJWT(HS256) · uv · Python 3.12

## 아키텍처 / 동작

```mermaid
flowchart LR
  Agent[LLM Agent / MCP Client] -->|JWT| MCP["/mcp (Streamable HTTP)"]
  REST[REST Client] -->|JWT| R["/market/* Router"]
  MCP -->|from_fastapi: tool→ASGI 재호출| R
  R --> S[MarketService]
  S -->|staged_search 폴백| Repo[MarketRepository]
  Repo -->|{items,total}→{data,total_count} 정규화| C[MarketClient]
  C -->|USE_REAL_API=false| MOCK[(인메모리 픽스처)]
  C -.->|USE_REAL_API=true + key| Vendor[(시세 벤더 REST)]
```

- **두 인증 경로, 한 시크릿**: MCP 는 `JWTVerifier(public_key=JWT_SECRET, HS256)`, REST 는 `router.dependencies=[Depends(verify_access_token)]`. 둘 다 동일 `JWT_SECRET` 으로 검증 — 서비스 간 호출은 `create_access_token`(sub=SERVICE_NAME) 단발 토큰.
- **lifespan 중첩**: `mcp_app.lifespan` 안에서 서비스가 돌아 StreamableHTTP 세션매니저 task group 을 살리고, 종료 시 `market_client.aclose()` 로 httpx 연결 풀을 정리.
- **라우트 우선순위**: REST(`/market/*`)·`/openapi.json` 이 먼저 등록돼 우선 매칭되고, 나머지는 `app.mount("/", mcp_app)` 로 MCP 에 위임.
- **기동 가시화**: few-shot 부착 tool 개수를 로그로 남겨 "조용한 배선 누락"을 잡는다(0개면 선언/배선 의심).
- **tool 목록**: `market_quote`(단일 종목 시세) · `market_ohlc`(기간별 캔들 OHLCV) · `market_index`(대표 지수) · `market_fx`(통화쌍 환율) · `market_search`(종목명·티커 검색→symbol 확정).

## 실행

```bash
uv sync
cd app && APP_ENV=development uv run uvicorn main:app --reload   # http://0.0.0.0:8004  (MCP: /mcp, REST: /market/*)
```

키 없이 바로 동작한다 (기본 `USE_REAL_API=false` → 인메모리 MOCK). `.env.example` 키 (실제 env 는 `.env.development` / `.env.staging` / `.env.production`):

```
USE_REAL_API=false                                          # 기본 MOCK. true 면 아래 키로 실 벤더 호출
MARKET_API_URL=https://api.example-market-vendor.com/v1     # USE_REAL_API=true 일 때만 사용
MARKET_API_KEY=CHANGE_ME                                    # USE_REAL_API=true 일 때만 필요
JWT_SECRET=CHANGE_ME                                        # frontend·전 서비스 동일값 필수
```

## 구조

```
app/
  main.py                              # FastAPI + from_fastapi → MCP, lifespan, mount
  routers/market/market_router.py      # 5 tool (operation_id=tool명, docstring=설명, few_shot 예시)
  services/market/market_service.py    # 도메인 로직 + staged_search 0건 폴백
  repositories/market/market_repository.py  # 외부/mock 응답 파싱·정규화 ({items,total}→{data,total_count})
  clients/market/market_client.py      # 시세 transport — 기본 MOCK 픽스처, USE_REAL_API 토글로 실 벤더(httpx async, 재시도)
  schemas/market/market_schema.py      # Pydantic In/Out = tool 입출력 스키마
  core/                                # config·container(DI)·security(JWT)·exception_handler·middlewares
  utils/common/                        # few_shot(메타 부착)·staged_search(폴백)·retry_utils
```
