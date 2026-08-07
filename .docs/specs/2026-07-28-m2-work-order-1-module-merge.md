<!--
  M2 워커 오더 1/3 — 모듈러 모놀리스 전환.
  이 파일은 오더의 **보관본**이다. 실제 배정 시에는 대상 이슈 코멘트로 옮겨 게시하고
  `human: plan` 승인을 받는다 (계획 승인 규약). 이슈 번호는 배정 시 제목 줄에 채운다.
-->

# 오더: 비즈니스 백엔드 3종을 한 앱의 모듈로 통합

**목표**: `backend-service`·`file-service`·`devactivity-service` 를 프로세스 하나로 합치되, 라우트 계약·레이어 규율·테넌트 격리를 그대로 보존한다.

**입력**: [PRD](prd.md) — 범위 밖 절·NFR · 설계 문서 [M2 전환설계](../4-아키텍처/m2-전환설계.md) **M2-AD-1 ~ M2-AD-6, M2-AD-11, M2-AD-12** — 수행자는 이 둘을 먼저 읽는다.

## 수용 기준 (AC)

1. `process-compose up` 으로 통합 앱 하나(:8000)가 뜨고, 기존 backend·devactivity·file 의 모든 엔드포인트가 **같은 경로·같은 응답 형태**로 응답한다
2. 흡수 전후의 `/openapi.json` 경로 + `operation_id` 집합이 **합집합으로 보존**된다 (누락 0 · 예기치 않은 추가 0)
3. 스키마 적재가 단일 진입점(`alembic upgrade head`)으로 끝나고, 깨끗한 DB 와 이미 적재된 DB 양쪽에서 통과한다
4. anti-patterns Detection 명령 13종이 통합 앱 경로에서 **그대로 동작**한다 (0 hit 이 되는 룰이 없다)
5. 프론트엔드 변경은 `.env` 의 서비스 URL 값 조정에 그친다 — 라우트 폴더·프록시 코드 변경 0
6. 인증 lockstep 검증(`scripts/verify_auth_lockstep.py`)이 통과한다 — 서비스 목록이 통합 결과를 반영한다

## 전역 제약

아래는 레포 SoT 에서 **값 그대로** 옮긴 것이다. 모든 태스크에 암묵 포함된다.

- `Backend (cwd=app 필수 — config/import 가 app 디렉토리 기준, APP_ENV=development 필수 — 없으면 .env.production 을 읽음)` [Source: CLAUDE.md#명령어]
- `라우트 경로: backend APIRouter(prefix=...) 는 kebab-case REST 리소스 (/chat-session; 프로세스·RPC 는 /domain/sub+동사 허용), frontend proxy (app/api/external/{service}/{prefix}/ → {SERVICE}_SERVICE_URL + "/{prefix}") 가 prefix 를 byte-identical 복제 — backend 가 SoT, 경로 변경 시 frontend lockstep` [Source: CLAUDE.md#네이밍 규칙]
- `lint/format 은 pre-commit 이 일괄 처리 (개별 ruff/eslint 명령 불필요)` [Source: CLAUDE.md#네이밍 규칙]
- `변경 이유·이력 설명 주석 금지 ("~를 위해 수정", "기존 X 를 Y 로 변경", "~ 때문에 추가") — 그건 커밋 메시지/PR 설명의 몫` [Source: CLAUDE.md#주석 규칙]
- `커밋 메시지·PR 본문·문서에 $ 명령 과 그 출력을 함께 적을 때는, 그 명령을 그대로 실행해서 나온 출력만 적는다.` [Source: CLAUDE.md#작업 보고 규칙]
- `사람의 로컬 체크아웃(이 저장소의 작업 트리)에 있는 파일을 main 의 현재 상태라고 가정하지 않는다` [Source: CLAUDE.md#코드 읽기 규칙]
- `백그라운드 매니저가 앱 안에서 실행 → 매니저 있는 서비스는 단일 프로세스(--workers=1)로 운영 (멀티워커 시 매니저 중복)` [Source: backend-service/app/main.py:19]
- 실행 중인 포트(3000·3010·5432·8000~8010)의 프로세스와 `fintech-pg`·`sgt-demo-*` 컨테이너를 건드리지 않는다

## 태스크

### Phase 1: 기반 (Foundational)

통합 앱이 들어설 자리를 만든다. **이 Phase 는 기능 변경이 0 이어야 한다** — 흡수의 회귀 원인을 골격에서 분리한다.

#### T1 (AC: 2, 4) 모듈 레지스트리와 prefix 충돌 fail-fast

**범위**: `backend-service` 를 통합 앱의 골격으로 만든다. 라우터·매니저 등록을 목록 하나로 모으고, 등록 시 prefix 중복을 검사한다.

**Files**
- Create: `backend-service/app/modules.py`
- Modify: `backend-service/app/main.py:11-14,46-49` (개별 import·`include_router` 나열 → 레지스트리 순회)
- Modify: `backend-service/app/core/container.py:55-66` (`router_modules`·`manager_modules` 를 `modules.py` 에서 읽도록)

**Interfaces**
- Produces: `modules.ROUTERS: list[APIRouter]` — 등록 순서가 곧 OpenAPI 문서 순서
- Produces: `modules.MANAGERS: list[object]` — 각 원소는 `start()`·`stop()` 코루틴을 갖는다 (기존 `message_consumer_manager`·`nav_producer_manager` 와 동일 형태)
- Produces: `modules.WIRING_MODULES: list[str]` — `Container.wiring_config` 가 그대로 쓴다
- Produces: `modules.register_routers(app: FastAPI) -> None` — 등록 전 `router.prefix` 중복을 검사해 중복 시 `RuntimeError` 로 기동 중단

**선행조건**: 없음 (첫 태스크)

**증명 의무**
- 변경 전후 `/openapi.json` 의 경로 집합이 완전히 동일함을 보인다 — 두 시점의 출력을 파일로 받아 `diff` 결과가 빈 것을 제시한다
- 일부러 같은 prefix 를 가진 라우터를 임시로 추가해 기동이 `RuntimeError` 로 거부되는 것을 1회 보이고, 그 임시 변경을 되돌린 커밋을 남긴다

**위험**: `include_router` 순서가 바뀌면 OpenAPI 문서의 태그 순서가 달라진다 — 경로 집합은 같아도 문서 diff 가 커진다. 기존 순서(portfolio → watchlist → nav → research_document)를 그대로 유지한다.

#### T2 [P] (AC: 1) DB 좌표 폴백 별칭과 DSN 불일치 기동 거부

**범위**: `BACKEND_SQL_DB_*` 를 정본으로 두고 `FILE_SQL_DB_*`·`DEVACTIVITY_SQL_DB_*` 를 폴백으로 받는다. 세 좌표가 서로 다른 DSN 으로 해석되면 기동을 거부한다 (M2-AD-4).

**Files**
- Modify: `backend-service/app/core/config.py:17-25` (SQL 좌표 필드에 폴백 별칭 추가)
- Modify: `backend-service/app/core/config.py:44-49` (`model_validator` 옆에 DSN 일치 검증 추가)

**Interfaces**
- Consumes: `utils/common/database_utils.get_sql_db_url(...)` — 기존 시그니처 그대로
- Produces: `Settings` 가 노출하는 SQL 좌표 이름은 변경 없음 (`BACKEND_SQL_DB_*`) — 소비자(`core/database.py`·`alembic/env.py`·`alembic/db_push.py`)는 손대지 않는다

**선행조건**: 없음 (T1 과 파일이 겹치지 않아 병렬 가능)

**증명 의무**
- `.env.development` 에 `FILE_SQL_DB_HOST` 만 다른 값으로 넣고 기동해 거부되는 것을 보이고, 원래 값으로 되돌려 기동되는 것을 보인다 (두 실행의 출력 그대로)
- 별칭이 전혀 없는 현재 `.env.development` 로도 기동됨을 보인다

**위험**: 세 서비스의 `.env.development` 가 실제로 같은 DB 를 가리키는지 확인하지 않은 채 검증을 넣으면 기동이 막힌다. 검증을 켜기 전에 세 파일의 좌표를 읽어 비교한 결과를 먼저 보고한다.

**Checkpoint**: 통합 앱 골격이 서고, 기능·경로·응답이 T1 이전과 완전히 같다.

---

### Phase 2: file-service 흡수 (AC: 1, 2, 3, 5)

#### T3 (AC: 1, 2) file 모듈 이식

**범위**: `file-service/app/` 의 라우터·서비스·리포지토리·스키마·클라이언트와 **검증 스크립트**를 통합 앱으로 옮긴다. **라우트 prefix 를 바꾸지 않는다** (M2-AD-3).

**Files**
- Create: `backend-service/app/routers/file/file_router.py` (출처 `file-service/app/routers/file/file_router.py`)
- Create: `backend-service/app/services/file/file_service.py` (출처 `file-service/app/services/file/file_service.py`)
- Create: `backend-service/app/repositories/file/file_repository.py` · `backend-service/app/repositories/file/sftp_file_repository.py`
- Create: `backend-service/app/clients/file/sftp_client.py` (출처 `file-service/app/clients/file/sftp_client.py`)
- Create: `backend-service/app/utils/common/file_utils.py`
- Create: `backend-service/scripts/verify_extension_normalization.py` · `backend-service/scripts/verify_upload_file_count_limit.py` (출처 `file-service/scripts/`)
- Modify: `backend-service/app/schemas/file/file_schema.py` (기존 파일 — `file-service` 쪽 스키마와 병합, 이름 충돌 시 file-service 정의가 정본)
- Modify: `backend-service/app/core/container.py` (file 리포지토리·서비스·SFTP 클라이언트 provider 등록)
- Modify: `backend-service/app/core/config.py` (SFTP 좌표 필드 추가 — `file-service/app/core/config.py` 에서 그대로)
- Modify: `backend-service/app/modules.py` (file 라우터 등록)
- Modify: `backend-service/app/models/schema.py` (file 모델 클래스 추가 — `file-service/app/models/schema.py` 에서 그대로)

**Interfaces**
- Consumes: `modules.ROUTERS`·`modules.WIRING_MODULES` (T1)
- Produces: `FileService` — DI 로 주입 가능한 서비스. 다른 모듈은 이것만 호출하고 `SftpClient`·`FileRepository` 는 직접 호출하지 않는다 (M2-AD-2)

**선행조건**: T1, T2

**증명 의무**
- 흡수 전 `file-service` 의 `/openapi.json` 경로 집합과 흡수 후 통합 앱의 `/openapi.json` 을 각각 파일로 받아, file 경로가 전부 포함되고 경로 문자열이 동일함을 `diff` 로 보인다
- 파일 업로드 1건 → 목록 조회 → 다운로드 → 삭제를 통합 앱 단독으로 수행한 실행 기록을 남긴다
- 이동한 검증 스크립트 2종을 통합 앱 대상으로 실행해 통과함을 보인다
- anti-patterns 룰 8(인증 누락) Detection 을 통합 앱 경로로 실행해 file 라우터가 인증 dependency 를 유지함을 보인다

**위험**: `schemas/file/file_schema.py` 가 양쪽에 이미 존재한다 — backend 쪽은 `FileServiceClient` 응답용, file-service 쪽은 라우터 입출력용이다. 병합하지 않고 덮으면 `research_document` 흐름이 조용히 깨진다. 두 파일의 클래스 이름을 먼저 대조한 결과를 보고한 뒤 병합한다.

#### T4 (AC: 1) 파일 접근 경로를 in-process 로 전환

**범위**: `FileServiceClient`(HTTP proxy) 호출부를 `FileService` 직접 주입으로 바꾸고, HTTP 클라이언트를 제거한다.

**Files**
- Modify: `backend-service/app/services/research_document/research_document_service.py` (`file_service_client` → `file_service`)
- Modify: `backend-service/app/core/container.py` (`file_service_client` provider 제거, `research_document_service` 의 의존 교체)
- Delete: `backend-service/app/clients/file/file_service_client.py`
- Modify: `backend-service/app/core/config.py` (`FILE_SERVICE_URL` 제거)

**Interfaces**
- Consumes: `FileService` (T3 이 등록한 provider)
- Produces: 없음 (내부 배선 변경)

**선행조건**: T3

**증명 의무**
- 리서치 문서 업로드 → 인덱싱 상태 조회 흐름을 통합 앱 단독으로 1회 수행한 기록
- `git grep -n "FileServiceClient" -- backend-service` 가 0 hit

**위험**: `FileServiceClient` 는 HTTP 경계라 예외를 HTTP 오류로 변환했을 수 있다. in-process 로 바꾸면 도메인 예외가 그대로 올라와 상태 코드가 달라질 수 있다. 교체 전 두 경로의 예외 처리를 대조해 응답 상태 코드가 유지되는지 확인한 결과를 보고한다.

#### T5 (AC: 3) file 스키마를 통합 마이그레이션에 편입

**범위**: file 모델을 통합 `Base` 에 넣고, 기존 DB 에서도 통과하는 멱등 리비전을 만든다 (M2-AD-6).

**Files**
- Create: `backend-service/alembic/versions/0002_absorb_file.py`
- Delete: `file-service/alembic/` 전체 (`alembic.ini`·`env.py`·`db_push.py`·`versions/`)
- Modify: `process-compose.yaml:33-44` (`db-migrate` 에서 file `db_push.py` 단계 제거)

**Interfaces**
- Consumes: `models/schema.py` 의 통합 `Base` (T3)
- Produces: 리비전 `0002_absorb_file` — `down_revision = "0001_baseline"`

**선행조건**: T3

**증명 의무**
- 깨끗한 DB(볼륨 삭제 후)에서 `alembic upgrade head` 가 성공하고 file 테이블이 생성됨을 보인다
- 이미 file 테이블이 있는 DB 에서 같은 명령이 성공(멱등)함을 보인다
- 같은 DB 에 두 번 연속 실행해 두 번째가 no-op 임을 보인다

**위험**: `include_object` 필터가 "내 모델에 없는 reflected 테이블"을 제외하므로, 모델을 옮기기 전에 autogenerate 를 돌리면 아무것도 안 나온다. 반대로 옮긴 뒤에는 `create_table` 이 나온다 — 이 순서를 지키지 않으면 빈 리비전을 만들고 넘어가게 된다.

**Checkpoint**: file-service 프로세스 없이 파일 업로드·다운로드·리서치 문서 흐름이 동작하고, 스키마 적재가 3단계로 줄었다.

---

### Phase 3: devactivity-service 흡수 (AC: 1, 2, 3, 5)

#### T6 (AC: 1, 2) devactivity 모듈 이식

**범위**: 스케줄러·챗·리포트 모듈과 APScheduler 매니저, **검증 스크립트**를 통합 앱으로 옮긴다. **라우트 prefix 를 바꾸지 않는다**.

**Files**
- Create: `backend-service/app/routers/scheduler/scheduler_router.py` · `backend-service/app/routers/chat/chat_router.py`
- Create: `backend-service/app/services/scheduler/scheduler_service.py` · `backend-service/app/services/chat/portfolio_chat_service.py` · `backend-service/app/services/report/activity_report_service.py`
- Create: `backend-service/app/repositories/scheduler/scheduler_repository.py`
- Create: `backend-service/app/schemas/scheduler/scheduler_schema.py` · `backend-service/app/schemas/chat/chat_schema.py` · `backend-service/app/schemas/report/report_schema.py`
- Create: `backend-service/app/managers/scheduler_manager.py`
- Create: `backend-service/app/clients/mcp/` (`mcp_client.py`·`mcp_agent.py`·`mcp_auth.py`·`mcp_prompt.py`) · `backend-service/app/clients/llm/llm_client.py` · `backend-service/app/clients/mail/mail_client.py`
- Create: `backend-service/app/core/mcp_token.py` (on-behalf 서비스 토큰 — devactivity 에서 그대로)
- Create: `backend-service/app/utils/chat/chat_utils.py` · `backend-service/app/utils/report/report_utils.py`
- Create: `backend-service/scripts/verify_scheduler_gating.py` · `backend-service/scripts/verify_activity_report.py` (출처 `devactivity-service/scripts/`)
- Modify: `backend-service/app/core/container.py` · `backend-service/app/modules.py` · `backend-service/app/core/config.py` · `backend-service/app/models/schema.py`
- Modify: `backend-service/pyproject.toml` (langchain-mcp-adapters·apscheduler 등 devactivity 의존성 편입)

**Interfaces**
- Consumes: `modules.MANAGERS` (T1) — `scheduler_manager` 가 `start()`/`stop()` 규약을 따른다
- Produces: `core/mcp_token.create_onbehalf_service_token() -> str` — 요청 컨텍스트의 테넌트를 실은 서비스 JWT. 하류 MCP 호출부가 이것을 쓴다

**선행조건**: T5 (file 흡수가 끝난 골격 위에서)

**증명 의무**
- 흡수 전 `devactivity-service` 의 `/openapi.json` 경로 집합이 통합 앱에 전부 포함됨을 `diff` 로 보인다
- 스케줄러 CRUD + 멤버 등록/삭제를 통합 앱 단독으로 수행한 기록
- 이동한 `verify_scheduler_gating.py`·`verify_activity_report.py` 를 통합 앱 대상으로 실행해 통과함을 보인다
- 부팅 시 활성 스케줄이 APScheduler 잡으로 자가 적재되는 로그를 보인다

**위험**
- devactivity 는 `--workers=1` 로 운영된다. 통합 앱도 이미 매니저가 있어 같은 제약이지만, 매니저가 셋으로 늘면 기동 실패 시 원인이 겹친다. 매니저 등록을 한 번에 하지 말고 스케줄러 하나만 먼저 붙여 기동을 확인한 뒤 나머지를 붙인다.
- LangGraph·langchain 의존성이 통합 앱에 들어와 기동 시간이 늘어난다. 흡수 전후의 기동 소요를 측정해 보고한다.

#### T7 (AC: 3) devactivity 스키마 편입과 db_push 폐기

**범위**: `tn_scheduler`·`tn_scheduler_member` 를 통합 `Base` 에 넣고 멱등 리비전을 만든다. `db_push.py` 경로를 완전히 없앤다.

**Files**
- Create: `backend-service/alembic/versions/0003_absorb_devactivity.py`
- Delete: `devactivity-service/alembic/` 전체
- Modify: `process-compose.yaml:33-44` (`db-migrate` 를 `alembic upgrade head` + `prisma db push` 2단계로)

**Interfaces**
- Produces: 리비전 `0003_absorb_devactivity` — `down_revision = "0002_absorb_file"`

**선행조건**: T6

**증명 의무**
- 깨끗한 DB 와 기존 DB 양쪽에서 `db-migrate` 통과
- `db-migrate` 를 두 번 연속 실행해 두 번째가 no-op
- `git grep -rn "db_push"` 결과에 삭제 대상이 남지 않음 (문서 참조는 갱신 대상으로 별도 보고)

**위험**: `db_push.py` 는 `--force-reset` 경로를 갖고 있어 일부 개발 절차 문서가 이를 참조한다. 삭제만 하고 문서를 두면 다음 사람이 없는 명령을 친다. T9 에서 문서를 갱신할 때까지 이 사실을 PR 본문에 명시한다.

**Checkpoint**: 통합 앱 하나가 backend·file·devactivity 의 모든 기능을 서빙하고, 스키마 적재가 2단계다.

---

### Phase 4: 마무리 (Polish)

#### T8 (AC: 1, 5, 6) 프로세스·환경 정리와 lockstep 목록 갱신

**범위**: `process-compose.yaml` 에서 흡수된 두 프로세스를 제거하고, 프론트 env 를 통합 앱 주소로 맞추고, 인증 lockstep 검증의 서비스 목록을 통합 결과로 갱신한다.

**Files**
- Modify: `process-compose.yaml:59-83` (`devactivity`·`file` 프로세스 블록 제거)
- Modify: `frontend/.env.example:23-28` (`DEV_ACTIVITY_SERVICE_URL`·`NEXT_PUBLIC_FILE_SERVICE_URL` 를 `http://localhost:8000` 으로)
- Modify: `scripts/verify_auth_lockstep.py:35-` (`EXPECTED_SERVICES` 에서 `file-service`·`devactivity-service` 제거)
- Delete: `file-service/` · `devactivity-service/` 디렉터리 전체 (이식 완료 후)

**Interfaces**
- Consumes: 없음
- Produces: 없음

**선행조건**: T7

**증명 의무**
- `python scripts/verify_auth_lockstep.py` 가 통과함을 보인다. 목록을 갱신하지 않으면 "`app/core/security.py` 미발견"으로 실패한다 — 이 실패를 먼저 재현한 뒤 갱신해 통과시키고, 두 출력을 함께 제시한다
- `process-compose up` 후 프로세스 목록을 보여 통합 앱 1개만 뜬 것을 제시한다
- 브라우저로 스케줄러 화면·파일 업로드 화면·리서치 문서 화면에 실제로 들어가 동작을 확인한 기록을 남긴다 (`curl` 만으로는 화면 차단을 못 잡는다 — CONTEXT 교훈)

**위험**
- `frontend/env.ts:33` 의 `DEV_ACTIVITY_SERVICE_URL` 은 `z.string().default("")` 이다. 값을 지우면 빈 문자열로 통과해 런타임에 잘못된 URL 로 호출한다 — 지우지 말고 값을 바꾼다.
- `verify_auth_lockstep.py` 는 `*-service/app/core/security.py` glob 으로 대상을 찾고 `EXPECTED_SERVICES` 를 **삭제 감지용 하한**으로 쓴다. 폴더를 지우면서 목록을 두면 정상 변경이 실패로 보고된다.

#### T9 (AC: 4) 규율 문서 동기화

**범위**: 폴더 구조가 하나로 합쳐진 사실을 룰 SoT 와 서비스 문서에 반영하고, 모듈 경계 룰을 추가한다.

**Files**
- Modify: `CLAUDE.md`(루트) — 「이 repo 서비스」 목록에서 file·devactivity 항목 통합, 데이터 흐름 패턴의 서비스 이름
- Modify: `.claude/docs/anti-patterns-backend.md` — 룰 5 예외에 "대용량 시계열 테이블" 추가, 룰 14 「모듈 경계 침범」 신설
- Modify: `.claude/agents/review-backend.md` — 출력 표에 룰 14 추가 (헤더 일치 규칙)
- Modify: `backend-service/CLAUDE.md` — 체크리스트에 룰 14 추가
- Modify: `.docs/5-인프라셋팅/로컬-postgres.md:237-267` — 「공유 DB 에서 alembic 을 쓰는 규칙」을 단일 앱 기준으로 갱신
- Modify: `.docs/4-아키텍처/경량msa.md` — 서비스 토폴로지 갱신
- Modify: `.docs/4-아키텍처/m2-전환설계.md` — 완료된 단계 표시

**Interfaces**
- Consumes: 없음
- Produces: 없음

**선행조건**: T8

**증명 의무**
- anti-patterns 의 Detection 명령 14종을 **전부 실행**해 각각의 hit 수를 표로 제시한다. 0 hit 인 룰이 있으면 그 이유(진짜 위반 없음 vs 경로가 안 맞음)를 구분해 적는다
- `git grep -n "file-service\|devactivity-service" -- '*.md'` 결과에 남은 참조가 의도된 것(이력 서술)뿐임을 보인다

**위험**: 헤더 일치 규칙상 룰 번호·텍스트는 3곳(anti-patterns·review-backend·backend CLAUDE.md)이 정확히 같아야 한다. 한 곳만 고치면 review 에이전트가 조용히 어긋난다.

#### T10 (AC: 1) DB 좌표 폴백 별칭 제거

**범위**: T2 가 넣은 폴백 별칭을 제거하고 `BACKEND_SQL_DB_*` 하나만 남긴다 (M2-AD-4 의 예약 항목).

**Files**
- Modify: `backend-service/app/core/config.py` (별칭 필드·DSN 일치 검증 제거)
- Modify: `backend-service/app/.env.example` (남은 `FILE_SQL_DB_*`·`DEVACTIVITY_SQL_DB_*` 줄 제거)

**선행조건**: T8

**증명 의무**: 별칭 제거 후 `process-compose up` 이 뜨고, `git grep -n "FILE_SQL_DB_\|DEVACTIVITY_SQL_DB_"` 가 0 hit

**위험**: 로컬 `.env.development` 는 git 에 없을 수 있다. 사용자 로컬 파일을 임의로 고치지 말고, 제거해야 할 줄 목록을 PR 본문에 적어 사용자가 직접 반영하게 한다.

## Dev Notes — 수행자가 알아야 할 맥락

- **폴더 모양을 바꾸지 않는 이유**: anti-patterns 의 Detection 명령이 `{backend}/app/routers/**`·`services/**`·`repositories/**` 경로에 묶여 있다. 수직 슬라이스로 바꾸면 13개 룰이 조용히 0 hit 이 된다. [Source: .docs/4-아키텍처/m2-전환설계.md#M2-AD-1]
- **라우트 prefix 를 흡수 단계에서 바꾸지 않는 이유**: 프론트 프록시가 prefix 를 byte-identical 복제한다. 경로를 바꾸면 프론트 라우트 폴더까지 같은 커밋에 들어와 회귀 원인이 두 배가 된다. [Source: .docs/4-아키텍처/m2-전환설계.md#M2-AD-3]
- **버전 테이블이 셋인 이유와 정리 대상**: `db_push.py` 는 실행 끝에 자기 버전 테이블을 DROP 하므로 평상시 DB 에는 `alembic_version` 하나만 있다 — 정리할 잔재가 없다. [Source: .docs/5-인프라셋팅/로컬-postgres.md#공유 DB 에서 alembic 을 쓰는 규칙]
- **`--force-reset` 의 과거 사고**: file 의 `--force-reset` 이 backend 7 테이블을 전부 지운 실측이 있다(#179). 통합 후 이 도구를 없애는 것이 이 사고 경로를 닫는다. [Source: backend-service/alembic/db_push.py:261-269]
- **cron 의 신원 주입 자리**: 스케줄러의 요청 밖 실행은 스케줄 행에 적힌 테넌트를 컨텍스트에 실어 하류 MCP on-behalf 토큰이 스코핑되게 한다. 이식할 때 이 한 줄을 빠뜨리면 하류가 fail-closed 로 막힌다. [Source: devactivity-service/app/services/scheduler/scheduler_service.py:113-115]
- **인증 lockstep 의 범위**: `scripts/verify_auth_lockstep.py` 는 `*-service/app/core/security.py` 를 가진 모든 서비스에 대해 `security.py`·`auth_context.py` 가 `backend-service` 와 byte-identical 인지 본다. 흡수는 이 파일들을 건드리지 않으므로 검증은 서비스 목록만 갱신하면 통과한다. [Source: scripts/verify_auth_lockstep.py:9-10,32-35]
- **검증 스크립트도 함께 옮긴다**: 서비스 폴더를 지우면서 `scripts/` 를 같이 지우면 회귀 그물이 사라진다. file 2종·devactivity 2종이 대상이다.

## 의존·실행 순서

- Phase 1(T1·T2)은 뒤 전부를 막는다. T1 과 T2 는 파일이 겹치지 않아 **병렬 가능**.
- T3 ← T1·T2 · T4 ← T3 · T5 ← T3
- T6 ← T5 (file 흡수가 끝난 골격 위에서) · T7 ← T6
- T8 ← T7 · T9 ← T8 · T10 ← T8 (T9 와 T10 은 **병렬 가능**)
