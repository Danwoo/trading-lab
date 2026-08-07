# template-mcp-service — 신규 금융 MCP 서버를 찍어내는 출발점 템플릿

투자 리서치 플랫폼의 모든 도메인 MCP 서버(market-data · disclosure · news · doc-search · portfolio)는 이 템플릿을 복사해서 만든다. 외부 의존이 0인 `example_echo` tool 하나만 있어 **키 없이 복사 직후 바로 기동·검증**되고, 각 파일 상단의 `[가이드 N/8]` 주석이 그 파일에서 할 일을 안내한다.

## 핵심 (보여주는 패턴·기술)

- **FastMCP `from_fastapi` — REST 1벌 = MCP tool 1벌**: 평범한 FastAPI 라우트(`@inject` 라우터 → service → DI)를 그대로 작성하면 `FastMCP.from_fastapi` 가 각 라우트를 MCP tool 로 노출한다. tool 실행은 ASGI 로 **같은 앱의 REST 라우트를 재호출**하므로, REST 실호출 1회가 tool 로직을 전부 커버한다 (FastAPI = MCP 동등성).
- **operation_id = tool 이름 (lockstep glue)**: 라우터의 `operation_id="example_echo"` 가 곧 MCP tool 이름. 소비 쪽(멀티에이전트 sub-agent 의 `mcp_tools`)이 이 문자열로 바인딩하므로 **byte-identical** 이어야 하고, 바꾸면 양쪽을 같이 고친다.
- **docstring·스키마가 도구 선택의 SoT**: 라우터 docstring(용도·반환 필드·형제 tool 구분·0건 해석) + `Field(description=)`(인자 설명) + `few_shot([...])`(호출 예시) 가 tool 메타로 노출돼 에이전트의 도구 선택을 돕는다. `INSTRUCTIONS` 에는 서버-전역 정책만 둔다.
- **서비스 토큰 인증**: MCP 경로는 `JWTVerifier`(HS256 대칭키), REST 경로는 `verify_access_token`. `JWT_SECRET` 은 frontend·backend·소비 에이전트와 동일값(불일치 = 401).
- **복사 친화 스캐폴드**: config(유일한 settings 경계) → schema → service → router → container(DI) → main 순서의 8단계 체크리스트. 외부 API·DB 가 필요하면 `market-data-mcp-service`(client·repository 주입)를 본뜬다.

## 기술 스택

- Python 3.12 · FastAPI · **FastMCP** (`from_fastapi`, Streamable HTTP `/mcp`)
- dependency-injector (DI 컨테이너) · Pydantic v2 (스키마·settings)
- PyJWT (HS256 서비스 토큰) · uv (의존성·lock)

## 아키텍처·동작

```
소비 에이전트 (multi-agent / single-agent)
        │  MultiServerMCPClient (+ 서비스 JWT)
        ▼
   FastMCP  /mcp  (Streamable HTTP, JWTVerifier)
        │  from_fastapi: tool 실행 → ASGI 재호출
        ▼
  FastAPI 라우트  /example/echo  (verify_access_token)
        └─ @inject router → ExampleService → EchoOut
```

이 템플릿이 노출하는 tool (operation_id):

| operation_id | 설명 |
|---|---|
| `example_echo` | 입력 텍스트를 그대로 반환 (외부 의존 0 — 복사 후 실제 조회/검색 tool 로 교체) |

> 이 템플릿을 복사해 만드는 금융 MCP 서버의 실제 operation_id 예시: market-data 의 `market_quote`/`market_ohlc`, disclosure 의 `disclosure_financials`/`disclosure_list`, news 의 `news_search`/`news_sentiment` 등. 각 서버는 **키 없이 mock 데이터로 즉시 동작**하고, `USE_REAL_API` 토글로 실 벤더 API(DART/시세 벤더 등)에 연결한다.

## 실행

```bash
cd template-mcp-service/app && APP_ENV=development uv run uvicorn main:app --reload --port 8009   # --workers=1 전제

# 서비스 JWT 발급 (JWT_SECRET 은 .env.* 와 동일값)
TOKEN=$(uv run python -c "import jwt,time; print(jwt.encode({'sub':'verify','exp':int(time.time())+300}, 'CHANGE_ME', algorithm='HS256'))")

# REST 실호출 1회 = tool 로직 검증
curl -s -X POST localhost:8009/example/echo \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"안녕하세요"}'
```

`.env` 키: `JWT_SECRET`(frontend·backend·소비자와 byte-identical 필수), `SERVICE_NAME`. 외부 API 가 필요하면 `*_BASE_URL`·`*_API_KEY` 를 `core/config.py` 와 `.env.{development,staging,production}` 3종에 추가한다.

## 구조

```
app/
├── main.py                    # 7/8 from_fastapi + JWTVerifier + INSTRUCTIONS (포트 8009)
├── core/
│   ├── config.py              # 2/8 settings 경계 (SERVICE_NAME·JWT_SECRET·외부 키)
│   └── container.py           # 6/8 DI 등록 (config → service → wiring)
├── schemas/example/           # 3/8 EchoIn/EchoOut — Field(description)=인자 설명
├── services/example/          # 4/8 ExampleService — 도메인 로직 (router 는 위임만)
├── routers/example/           # 5/8 operation_id=tool 이름, docstring=설명, few_shot=예시
└── utils/common/few_shot.py   # tool _meta 로 few-shot 예시 부착 (attach_tool_meta 훅)
```

신규 서비스 생성·통합(process-compose 등록, 소비 에이전트 `mcp_tools` 연결)·검증 절차는 [`.docs/2-개발가이드/fastmcp-서버개발.md`](../.docs/2-개발가이드/fastmcp-서버개발.md) 참고.
