# Backend CLAUDE.md

> **이 서비스**: `news-mcp-service` (:8006) — 금융 뉴스 도메인 MCP 서버. `FastMCP.from_fastapi` 가 `/news/*` REST 라우터를 `/mcp` MCP tool 로 노출 (DB·LLM 없음, 순수 검색 프록시). 5개 tool 의 `operation_id` 는 multi-agent-service `agents/domains/market.py` 와 **lockstep**: `news_search` · `news_company` · `news_detail` · `news_sentiment` · `news_disclosure`. **기본은 인메모리 목업 픽스처(`clients/news/news_fixtures.py`)라 API 키 없이 즉시 기동**하고, `USE_REAL_API=true` + `NEWS_API_BASE_URL`/`NEWS_API_KEY` 로 뉴스 벤더 실데이터 경로(`NewsClient._get`)로 전환한다. 페르소나는 투자 리서치 애널리스트 — 수치(주가 영향·실적·배당)는 기사·공시 근거 범위로만 인용, 센티먼트는 톤 지표일 뿐 투자 판단의 단일 근거가 아니다. 레이어는 아래 공통 템플릿과 동일하되 store 는 SQL 이 아니라 뉴스 검색 소스(목업/벤더)이므로 Repository 가 그 응답을 정규화한다. ⓘ 정보 제공 목적이며 투자 조언이 아닙니다.

<!-- 여기부터 끝까지는 전 backend 서비스 공통부 — byte-identical 유지 (검사: scripts/verify_backend_claude_md.py). 서비스 고유 맥락은 이 줄 위 `> **이 서비스**:` 블록에 둔다. -->

## 환경

- Python 3.12 (≤3.13), 의존성 `uv` 관리 (`pyproject.toml`)
- 환경 파일: `.env.development` / `.env.staging` / `.env.production`

## 레이어 구조

```
Router (@inject + Depends) → Service → Repository → SQLAlchemy text() + raw SQL
```

- **Router**: `dependencies=[Depends(verify_access_token)]` 인증, `@inject` + `Depends(Provide[Container.xxx_service])` DI 주입. DevExtreme `skip`, `take`, `filter`(JSON), `sort`(JSON) 수신. 라우트는 **kebab-case REST 리소스** (`APIRouter(prefix="/chat-session")`, CRUD 는 단수 명사+HTTP 동사 / 프로세스·RPC 는 `/domain/sub`+동사 허용) — 이 `prefix` 가 frontend proxy route (`app/api/external/{service}/{prefix}/` 의 `{SERVICE}_SERVICE_URL + "/{prefix}"`) 의 **SoT** (byte-identical, 변경 시 frontend lockstep). 상세 [`design-patterns-backend.md`](../.claude/docs/design-patterns-backend.md) "라우트 (REST) 컨벤션"
- **Service**: 도메인 로직 + 트랜잭션 + 도메인 예외 (`NotFoundError`/`ConflictError`) raise
- **Repository**: thin SQL wrapper. `build_filter_params(args)` → SQL WHERE, `parse_sort()` → ORDER BY. 페이지네이션은 `ROW_NUMBER()` + `skip`/`take`. ORM 쿼리 사용 안 함, raw SQL only. **비-SQL 데이터 store(Milvus 벡터DB, MLflow tracking 등)도 repository 로 감쌈** — 데이터소스 연결을 주입(`sql_client`/`milvus_client`/`mlflow_client`)받아 그 store CRUD 담당 (예: doc-search `repositories/vector_search/vector_search_milvus_repository.py`[`VectorSearchMilvusRepository`], mlops `repositories/mlflow/*`). 즉 Repository = 자기 store 접근 계층. **repository 접근은 Service 계층에서만** (util/manager 가 repository 직접 접근 금지 — 필요하면 service 로 승격). compute/외부API(vLLM·upstage·doc-search)는 store 가 아니므로 client (`clients/`) 로 둠
- **DB**: `BACKEND_SQL_DB_*` 1개 — 비즈니스·파일 메타를 한 엔진이 쓴다. 파일 접근은 `FileService` DI 주입으로만 하고 `SftpClient`·`FileRepository` 직접 호출은 금지 (모듈 경계).

## DI 등록 (`core/container.py`)

`Container(DeclarativeContainer)` 에 위→아래로 등록 — **`config` 가 유일한 settings 경계**, 그 아래 client/db → repository → service, 마지막에 `WiringConfiguration` 으로 `@inject` 대상(router·manager) 모듈을 건다.

```python
class Container(containers.DeclarativeContainer):
    config = providers.Object(settings)                                        # settings 경계 (유일)
    backend_sql_client = providers.Singleton(get_backend_sql_client, config)   # DB (외부타입 → get_* 팩토리)
    sftp_client = providers.Singleton(SftpClient, config)                      # client (우리 클래스 → 직접 Singleton)
    {entity}_repository = providers.Factory({Entity}Repository, sql_client=backend_sql_client)
    {entity}_service = providers.Factory({Entity}Service, {entity}_repository={entity}_repository)
    wiring_config = containers.WiringConfiguration(modules=[
        "routers.{entity}.{entity}_router",   # @inject 대상 (router·manager 모듈 경로)
    ])
```
`main.py` 는 `app.container = Container()` 로 인스턴스화하면 wiring 이 적용(별도 `container.wire()` 호출 없음)되고 `app.include_router(...)` 로 라우터를 붙인다. 이후 router·manager 가 `@inject` + `Depends(Provide[Container.{entity}_service])` 로 주입받는다. client/db provider 작성 규칙(우리 클래스=직접 `Singleton`, 외부타입=`get_*` 팩토리, `config` 무annotation)은 아래 "클라이언트" 절.

## 핵심 유틸 (`utils/`)

> **두 갈래** — `utils/common/` = 전 서비스 공통 교차 헬퍼(아래 목록). `utils/<도메인>/` = 그 서비스 고유의 **순수함수**(IO 없는 계산/변환)를 service 에서 분리한 모듈 (예: `utils/redaction/redactor.py`·`utils/chat/chat_utils.py`). namespace 패키지라 `__init__.py` 는 두지 않는다.

- `devextreme_utils.py` → `build_filter_params()`, `parse_sort()`: DevExtreme 필터/정렬 → SQL 변환
- `database_utils.py` → `create_sql_engine_from_settings()`: SQLAlchemy Engine 생성
- `retry_utils.py` → `is_http_retryable()`, `retry(fn)`: tenacity 기반 sync 재시도 헬퍼 (HTTP 502·503·504 + TransportError/Timeout 자동 분류). 외부 HTTP·SFTP·SMTP 등 재시도가 필요한 호출에서 사용

## 클라이언트 (`clients/`)

외부 시스템 클라이언트는 `app/clients/<domain>/` 패키지에 두고, **`core/container.py` 가 유일한 settings 경계** — `config = providers.Object(settings)` 를 두고 모든 client/db provider 를 `providers.Singleton(<클래스 또는 팩토리>, config)` 로 등록(**client 모듈은 `settings` 미import**, container 만 import) → 서비스 생성자에 **DI 주입**. **우리 소유 클래스는 factory 없이** `__init__(self, config)` 가 `config.X` 를 읽고 `providers.Singleton(Class, config)` (fail-soft 는 `__bool__`, connect/disconnect 는 `__init__` 순수 유지 + main lifespan/manager 가 호출). **외부 타입**(SQLAlchemy `Engine`·pymilvus·mlflow 등 우리 클래스가 아닌 것)만 `get_xxx(config)` 팩토리 유지(인자 조립·연결·fail-soft None+재시도 캐시는 여기) → `providers.Singleton(get_xxx, config)`, `core/database.py` 의 `get_*_sql_client(config)` 와 동일. `config` 는 무annotation. 컨테이너 우회 직접 인스턴스화 금지 (anti-pattern 11).

- `clients/file/sftp_client.py` → `SftpClient`: asyncssh SFTP (file 모듈 — 파일 저장소 접근). 다른 모듈은 이걸 직접 부르지 않고 `FileService` 를 주입받는다. 서비스별 추가 클라(doc-search `clients/milvus/milvus_client.py`[pymilvus 연결]·`clients/embedding/`·`clients/reranker/`, news `clients/news/news_client.py`[뉴스 벤더 HTTP 프록시], market-data `clients/market/market_client.py`[시세 벤더 HTTP 프록시] 등)는 해당 서비스에만 존재. ※ Milvus 연결 client(`get_milvus_client`)는 데이터접근 repository(`VectorSearchMilvusRepository`)에 주입 — SQL engine→repo 와 동일 구조

## 신원·인증 (`core/auth_context.py`)

멀티테넌트 신원은 ContextVar 로 흐른다. async `verify_access_token` (`core/security.py`) 이 JWT(HS256) 검증 후 `set_auth_context(user_id=payload["sub"], email, role, workspace_id)` 로 박고, Service/Repository 는 인자 없이 getter 로 읽는다.

- `get_email()` → 요청자 email. **감사 `reg_id`/`mod_id` 는 항상 이것** (router 에서 `args["reg_id"] = get_email()`)
- `get_user_id()` → User.id (uuid v7). 비즈니스 소유/식별 `user_id` 컬럼
- `get_workspace_id()` → 워크스페이스 ID (int). 테넌트 격리 `WHERE workspace_id = ...`
- `get_role()` → `admin`/`operator`/`user`
- 요청 밖(백그라운드/기동) 호출 시 전부 `None` → 권한 계층 **fail-closed**. 서비스 간 토큰(`create_access_token`)은 `{sub: SERVICE_NAME}` 만 (role/workspace 없음) — 내부 전용 endpoint 는 토큰 유효성만 검사하고 role/workspace 게이트 금지
- sync offload 는 `run_in_threadpool` (ContextVar 복사 → 같은 신원 유지). `asyncio.to_thread`·`loop.run_in_executor(None, ...)` 금지 사유는 신원이 아니라 AnyIO 풀 분리 (둘 다 별도 풀 → 스레드 예산 이원화; run_in_executor(None)은 ContextVar 도 미복사). CPU 바운드 GIL 탈출용 `run_in_executor(ProcessPoolExecutor)` 만 예외 (anti-pattern 13)

## 예외 처리

`core/exception_handler.py` 가 도메인/표준/외부 lib 예외 → HTTP status 일괄 매핑. Service/Repository 는 `fastapi.HTTPException` 직접 raise 금지 (HTTP-free 유지). 도메인 예외와 builtin 표준 예외의 `str(exc)` 는 클라이언트 `detail` 로 노출되므로 **민감 정보 메시지 금지**.

**builtin 예외 메시지 정책** — 한글 휴리스틱 (`str(exc) if re.search(r"[가-힣]", str(exc)) else None`): 한글 포함 시 그대로 노출 (명시 `raise ValueError("이메일 형식이...")`), 영문/자동발생은 `default_message` 한글로 마스킹 (`int("abc")` → "잘못된 요청입니다.").

| 예외 | HTTP | 메시지 출처 | 비고 |
|---|---|---|---|
| `HTTPError` 서브클래스 17종 (`NotFoundError`/`ConflictError`/`BadRequestError`/`ForbiddenError`/`UnauthorizedError`/...) | 각 클래스 `status_code` | `raise X("msg")` 인자 또는 `default_message` | `core/exceptions.py` |
| `ValueError` / `PermissionError` / `ConnectionError` / `RuntimeError` | 400 / 403 / 503 / 500 | 한글 휴리스틱 | Python builtin (명시 raise) |
| `FileNotFoundError` / `TimeoutError` | 404 / 408 | 한글 휴리스틱 | Python builtin (자동발생 빈도 높음 — 파일 IO / asyncio 타임아웃) |
| `IntegrityError` | 409 / 400 | 한글 매핑 (`SQLSTATE_MAP` — psycopg SQLSTATE 기반, 미매칭 시 409 기본 메시지로 폴백) | SQLAlchemy 자동 |
| `OperationalError` | 503 | "데이터베이스에 일시적으로 연결할 수 없습니다." | SQLAlchemy 자동 (연결 끊김) |
| `HTTPException` | `exc.status_code` | `exc.detail` | Router 의 client-disconnect / 구조화 detail 용 |
| 그 외 모든 `Exception` | 500 | "서버 내부 오류가 발생했습니다." (default, 원본 메시지 마스킹) | catch-all — `KeyError`/`TypeError` 등 코드 버그 |

---

## Anti-patterns 체크리스트 (작업 중 즉시 회피)

상세 (❌/✅ 예시, grep, 예외) 는 [`.claude/docs/anti-patterns-backend.md`](../.claude/docs/anti-patterns-backend.md). 신규 CRUD 코드 패턴은 [`.claude/docs/design-patterns-backend.md`](../.claude/docs/design-patterns-backend.md).

> 룰 번호/이름은 [`anti-patterns-backend.md`](../.claude/docs/anti-patterns-backend.md) 의 `### N.` 헤더와 텍스트 정확히 일치.

**레이어 분리**
1. **Router 에 비즈니스 로직 / SQL** → Service 위임. Router 는 controller (조합/HTTP 검증/병렬은 OK)
2. **Repository 의 비즈니스 디폴트/검증** → 디폴트는 Pydantic / 검증은 Service. Repository = thin SQL
3. **반환값 안 쓰는 self.select_X 호출** → 결과 명시 체크 + 도메인 예외 raise

**데이터베이스 / 스키마**
4. **ORM Session/Model/query runtime 사용** → Core `text()` + `.mappings()` only (`models/schema.py` 정의는 OK)
5. **공통 감사 컬럼 누락** → INSERT `reg_id`/`reg_dt`, UPDATE `mod_id`/`mod_dt` (background 는 `mod_id='system'`)
6. **페이지네이션 누락** → DevExtreme 그리드는 `ROW_NUMBER()` + `skip`/`take`

**응답 / 인증 / 에러**
7. **Pydantic Response 모델 / list wrapper 누락** → 모든 endpoint `response_model=`, list 는 `{items, total_count}`
8. **인증 누락** → 비즈니스 router 는 `Depends(verify_access_token)`
9. **catch-all try/except Exception (handler 우회)** → 예외 자연 전파, handler 가 매핑
10. **fastapi.HTTPException 직접 raise (Service/Repository)** → 도메인/표준 예외 사용 (Router 만 일부 허용)

**DI / I/O**
11. **DI 우회 (직접 인스턴스화)** → `core/container.py` provider + `Depends(Provide[Container.xxx])`
12. **DB I/O 패턴 (sync 표준)** → 동기 Engine 표준: `def` + `engine.connect()`. HTTP/파일은 async
13. **async 컨텍스트에서 sync blocking → run_in_threadpool 누락** → `fastapi.concurrency.run_in_threadpool` (`asyncio.to_thread`·`loop.run_in_executor(None, ...)` 금지, ProcessPoolExecutor 만 예외). critical path 만 (heavy CPU / N+1 / polling loop)

**모듈 경계**
14. **모듈 경계 침범** → 서비스는 자기 모듈 리포지토리만 주입, 모듈 간은 service → service. `repositories/` 안의 `from services.` 는 언제나 위반. file 접근은 `FileService` 주입으로만 (`SftpClient`·`FileRepository` 직접 호출 금지)
15. **provider 경계 침범 (소스 이름 누출)** → 시세 소스 어댑터(`app/providers/<소스>/`)는 `providers/` 밖에서 import 금지. 소비자는 `get_provider(source, key)` 레지스트리로만 접근하고, 어댑터는 `settings.` 를 읽지 않는다 (키는 생성자 주입)
