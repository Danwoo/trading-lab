# 로컬 Postgres (개발) — process-compose

> `process-compose up` 한 줄로 로컬 Postgres 를 띄우고 스키마를 적재한다. 외부 DB 서버 없이
> 로컬에서 스택을 자립 기동하기 위한 것(#166 슬라이스 0). 관계형 + 벡터(#160 pgvector)를
> **단일 Postgres 인스턴스**(`pgvector/pgvector:pg16`)로 통합한다.

## 전제

- **docker 데몬이 떠 있어야 한다.** `postgres` 프로세스가 `docker run` 으로 컨테이너를 띄운다
  (WSL2 는 `.docs/5-인프라셋팅/wsl2-docker개발환경.md` 참조).
- 각 python SQL 서비스에 **psycopg(v3) 의존성**이 있어야 한다 — backend·devactivity·file·
  multi-agent 네 서비스 모두 `pyproject.toml` 에 `psycopg[binary]`(v3) 를 갖는다.

## DB 구성 — 하나의 DB, 두 스키마

**DB 는 `fintech` 하나다.** 나누는 것은 DB 가 아니라 **스키마**이고, 스키마는 곧 소유 경계다:

| 스키마 | 소유 | 사는 테이블 | 적재 도구 |
|---|---|---|---|
| `public` | 통합 앱 (`backend-service`) | `tn_board`·`tn_portfolio`·`tn_file`·`tn_scheduler` … 11개 + `alembic_version` | alembic (`upgrade head`) |
| `public` | doc-search (자가 DDL) | `workspace_doc_chunk` | 서비스 런타임 `ensure_table` (`CREATE TABLE IF NOT EXISTS` — 색인 직전 멱등 생성, alembic·prisma 관리 밖) |
| `frontend` | Next.js frontend (Prisma) | `tn_user`·`ba_session`·`tc_code` … 14개 | `prisma db push` |

**왜 갈랐나** — `prisma db push` 는 연결된 스키마 **전체**를 자기 모델과 동기화한다. 즉 자기 모델에
없는 테이블은 "지워야 할 것"으로 본다. 넷이 `public` 을 함께 쓰던 동안 push 는 파이썬 테이블 12개를
삭제 대상으로 잡았다. Prisma 에게 자기 스키마를 주면 남의 테이블이 애초에 보이지 않는다.
직접 확인하려면(적용 없이 SQL 만 출력):

```bash
cd frontend
DATABASE_URL="postgresql://fintech:fintech@localhost:5432/fintech?schema=public" \
  npx prisma migrate diff --from-config-datasource --to-schema prisma/schema.prisma --script
#  → DROP TABLE "alembic_version"; DROP TABLE "tn_board"; … 파이썬 12개
#  같은 명령을 ?schema=frontend 로 하면 "This is an empty migration."
```

- 파이썬 세 서비스는 계속 `public` 을 **공유**한다. alembic 은 push 처럼 스키마 전체를 지우지 않고,
  서비스별 `version_table` 과 `include_object` 필터로 공존한다(아래 「공유 DB 에서 alembic 을 쓰는 규칙」).
- **Supabase 로 가도 그대로 통한다** — Supabase 는 프로젝트당 DB 1개 + 스키마 N개다. DB 를 여러 개
  만드는 설계였다면 옮길 때 깨지지만, 이 구조는 스키마만 그대로 옮기면 된다.
- 스키마를 가리키는 곳은 셋이다. 옮기려면 셋을 함께 바꾼다:
  - `frontend/.env.example`·`.env.development` 의 `DATABASE_URL` 끝 `?schema=frontend` (**SoT**)
  - `frontend/lib/prisma/client.ts` — 런타임 어댑터(`PrismaPg`)에 넘길 스키마를 이 URL 에서 읽는다.
    `?schema=` 는 Prisma CLI 만 읽고 `pg` 드라이버는 무시하므로, 넘기지 않으면 앱이 `public` 을 보다
    `The table public.tn_user does not exist` 로 죽는다.
  - `frontend/prisma/table-generator.cjs` 의 `TARGET_SCHEMA` — 생성물 `init/tables.sql` 머리에
    `CREATE SCHEMA IF NOT EXISTS` + `SET search_path` 를 박는다(psql 직접 적용용). `init/seed.sql` 도
    같은 이유로 `SET search_path TO frontend` 로 시작한다.
- 파이썬 서비스가 frontend 소유 테이블을 읽을 때는 **쿼리에서 스키마를 수식**한다 — multi-agent 의
  멀티턴 히스토리 조회가 `FROM frontend.ai_chat_history` 인 이유다(커넥션 `search_path` 는 기본값).

## 무엇이 도는가

`process-compose.yaml` 에 두 프로세스가 추가됐다:

- **`postgres`** — `pgvector/pgvector:pg16` 컨테이너(`fintech-pg`), 포트 5432, user/pass/db 모두
  `fintech`. 데이터는 named volume `fintech-pg-data` 에 영속(재기동해도 유지). `pg_isready`
  readiness probe 가 healthy 를 판정한다.
- **`db-migrate`** — postgres 가 healthy 해지면 1회 실행. backend·devactivity·file 세 서비스가
  `public` 에, frontend 가 `frontend` 스키마에 각자 소유 테이블을 만든다(스키마는 `prisma db push`
  가 없으면 스스로 만든다 — 별도 생성 단계가 없다). `backend`·`frontend` 프로세스는
  이 프로세스의 `process_completed_successfully` 를 `depends_on` 으로 기다린다.
  **순서는 frontend(prisma) 가 먼저, backend(alembic) 가 나중이다** (#333) — alembic 의 일부
  리비전(0005·0006)이 `frontend` 스키마 테이블을 백필·제약하는데, 거꾸로 돌면 그 시점엔
  테이블이 아직 없어 조용히 건너뛰고 head 로 기록돼(다음 실행에도 다시 안 돎) 새 설치에서
  영영 적용되지 않는다. 대상 테이블이 없으면 그 리비전은 이제 조용히 넘어가지 않고
  예외로 죽는다(fail-closed) — 순서가 다시 깨지면 `db-migrate` 자체가 실패로 드러난다.
  - **frontend** — Prisma push 방식: `npm run dev:prisma:push` 가 `frontend` 스키마에 자기 소유
    테이블을 만든다. 초기 데이터는 여기 포함되지 않는다(아래 「실행」 절의 seed 참조).
  - **backend** — 마이그레이션 이력 방식: `cd backend-service/alembic && APP_ENV=development
    uv run python -m alembic upgrade head` (베이스라인 `0001_baseline` 이 전 테이블을 만든다).
    모델을 바꾸면 `uv run python -m alembic revision --autogenerate -m "<요약>"` 으로 리비전을 추가한다.
    (흡수 전 devactivity·file 이 쓰던 이력 없는 push(`db_push.py`)는 폐기됐다 — 파이썬 앱이
    하나뿐이라 두 메커니즘이 공존할 자리가 없고, `--force-reset` 이 남의 테이블을 지운
    사고 경로(#179)도 함께 닫힌다.)

## `.env.development` — 부트스트랩 (최초 1회)

`.env.*` 는 gitignore 대상이라 레포에는 `.env.example` 만 있다. **파일이 없으면 서비스는 기동
시점의 config 검증에서 즉시 죽는다** — `JWT_SECRET`·`*_SQL_DB_*` 가 필수 필드라 pydantic-settings
(python) / `frontend/env.ts` 가 `Field required` 로 예외를 던진다. 클론 직후 `process-compose up`
을 하면 거의 모든 프로세스가 이 이유로 죽는다. 그래서 최초 1회 부트스트랩이 필요하다:

```bash
python3 scripts/bootstrap_local_env.py     # stdlib 전용 — uv 없이 동작
```

각 서비스의 `.env.example` 을 같은 디렉터리의 `.env.development` 로 복사하면서 자동 생성 가능한
값을 채운다 — `JWT_SECRET`(전 서비스 **동일값**), frontend `BETTER_AUTH_SECRET`·`EMAIL_SECRET`,
`*_SQL_DB_USER`/`*_SQL_DB_PASSWORD`(로컬 Postgres 의 `fintech`/`fintech`). 채움 대상은 `CHANGE_ME`
**와 빈 값**(`KEY=`) 둘 다다. **이미 있는 파일은 건드리지 않고 건너뛴다**(`--force` 를 줄 때만
`.env.development.bak` 로 백업 후 재생성 — `.bak` 이 이미 있으면 덮어쓰지 않고
`.env.development.bak.<타임스탬프>` 로 남겨 최초 원본을 지킨다).

외부 서비스 키(LLM·DART·Tavily·SMTP·SFTP …)는 자동 생성이 불가능해 `CHANGE_ME`(또는 빈 값)로 남고,
스크립트가 끝에 "직접 채워야 하는 키"를 파일별로 출력한다. 값이 없어도 필수 키 '존재' 검증은 통과해
서비스는 뜬다 — MCP 서비스는 `USE_REAL_API=false` 기본값이라 키 없이 MOCK 데이터로 동작한다.

## `.env.development` 의 DB 블록 (각 python 서비스 `app/` 아래)

부트스트랩이 만들어 주는 내용이다(직접 만들 때 참고). 라이브 엔진 팩토리
`utils/common/database_utils.py::create_sql_engine_from_settings` 는 `*_DRIVER` 값을 그대로 스킴으로
써 `postgresql+psycopg://user:pass@host:port/db` 로 조립한다:

```dotenv
# backend-service/app/.env.development (devactivity·file 은 접두사만 다름)
BACKEND_SQL_DB_DRIVER=postgresql+psycopg
BACKEND_SQL_DB_ODBC_DRIVER=
BACKEND_SQL_DB_HOST=localhost
BACKEND_SQL_DB_PORT=5432
BACKEND_SQL_DB_NAME=fintech
BACKEND_SQL_DB_USER=fintech
BACKEND_SQL_DB_PASSWORD=fintech
```

- 접두사: backend=`BACKEND_`, devactivity=`DEVACTIVITY_`, file=`FILE_`, multi-agent=`MULTI_AGENT_`.
- `*_ODBC_DRIVER` 는 psycopg 경로에서 미사용(빈 값).
- `JWT_SECRET` 은 frontend 를 포함한 **전 서비스가 같은 값**이어야 한다 — 한 곳만 달라도 서비스 간
  토큰 검증이 401 이 된다. 부트스트랩이 한 값을 만들어 전 파일에 넣고, 이미 만들어진 파일이 있으면
  그 값을 재사용한다(부분 부트스트랩에서 값이 갈리지 않게).

## `.env.development` (frontend)

frontend 는 Prisma(driver adapter `@prisma/adapter-pg`)로 자기 소유 테이블에 직접 붙는다. DB 줄은
`.env.example` 이 이미 로컬 Postgres 를 가리키므로 부트스트랩 결과를 그대로 쓰면 된다:

```dotenv
DATABASE_URL="postgresql://fintech:fintech@localhost:5432/fintech?schema=frontend"
```

끝의 `?schema=frontend` 가 Prisma 소유 스키마를 정하는 SoT 다(위 「DB 구성」). 이 값을 `public` 으로
되돌리면 `prisma db push` 가 파이썬 서비스 테이블을 지운다.

## 실행

```bash
# docker 데몬이 떠 있는지 확인 후
python3 scripts/bootstrap_local_env.py     # 1) .env.development 생성 (최초 1회)
cd frontend && npm install                 # 2) Prisma 클라이언트 포함 (최초 1회)
process-compose up                         # 3) postgres → healthy → db-migrate → 서비스 기동
```

1·2 는 최초 1회면 되고 이후에는 `process-compose up` 만 하면 된다. 1 을 건너뛰면 `.env.development`
가 없어 서비스가 config 검증에서 즉시 죽고, 2 를 건너뛰면 `db-migrate` 의 `npm run dev:prisma:push`
가 실패해 이 프로세스에 의존하는 backend·devactivity·file·frontend 가 기동하지 않는다.

`frontend` 프로세스는 :3010 을 쓴다 — 3000 은 Node 기본 포트라 다른 프로젝트와 겹치기 때문이다(#308).
이 포트의 SoT 는 `process-compose.yaml` 의 frontend `PORT` 이고, 전 backend 서비스의
`CORS_ALLOW_ORIGINS` 기본값과 `frontend/.env.example` 의 `BETTER_AUTH_URL` 이 같은 포트를 쓴다
(`python3 scripts/verify_dev_port_hygiene.py` 가 이 lockstep 과 「남의 포트를 죽이는 명령이 없는지」를
검사한다). 포트를 옮기려면 그 셋을 함께 옮기고, 이미 만들어 둔 `.env.development` 의 `BETTER_AUTH_URL`
도 같이 맞춘다(`.env.*` 는 gitignore 대상이라 각자 로컬에서 바꾼다).

프로세스별로 포트가 점유돼 있으면 그 프로세스는 바인딩 실패로 죽는다 — 점유자를 죽이지 않는다.
이전 인스턴스가 포트를 물고 있으면 `ss -ltnp` 로 그 PID 가 자기 것인지 확인한 뒤 직접 정리한다.

### 마이그레이션 전에 — 체크아웃을 먼저 최신으로 (#387)

**`alembic upgrade head` 의 `head` 는 「그 체크아웃의 `versions/` 안에서 가장 끝」이지 「레포의
최신」이 아니다.** 낡은 트리에서 돌리면 오류 없이 덜 적용되고 종료 코드는 0 이며, `alembic
current` 도 그 트리 기준으로는 "현재 head" 라고 정직하게 답한다. 코드만 최신이고 DB 만 뒤처지면
한참 뒤 런타임에서 `column does not exist` 로 터진다.

그래서 **마이그레이션의 정본은 `origin/main`** 이다. 개발 DB 를 갱신할 때는 최신 main 을 받은 뒤
돌린다:

```bash
git fetch origin main && git merge origin/main
process-compose up          # db-migrate 가 아래 검사를 먼저 돌린다
```

`db-migrate` 는 적용 전에 `python3 scripts/verify_alembic_head_freshness.py --fetch` 로 이 트리가
`origin/main` 의 head 리비전을 가졌는지 확인하고, 없으면 **거기서 멈춘다**(조용한 부분 적용 대신
시끄러운 실패). 새 리비전을 얹은 기능 브랜치는 정본을 포함하므로 그대로 통과한다. 손으로 돌릴
때도 같은 검사를 먼저 칠 수 있다.

스키마가 만들어진 뒤 초기 데이터(메뉴·권한·코드·데모 계정 admin/operator)를 **최초 1회 수동 적용**
한다 — `seed.sql` 이 전체 `DELETE` 로 시작하므로 재실행하면 그 사이 만든 계정도 지워진다:

```bash
docker exec -i fintech-pg psql -U fintech -d fintech < frontend/prisma/init/seed.sql
```

(대상은 `frontend` 스키마다 — `seed.sql` 첫 줄의 `SET search_path TO frontend` 가 정한다.
psql 기본 `search_path` 는 `public` 이라 이 줄이 없으면 테이블을 찾지 못한다.)

backend 데모 데이터(게시판·관심종목·포트폴리오·보유종목·메시지 큐 샘플)도 최초 1회 적용한다 —
대상이 `public` 이라 search_path 수식 없이 그대로 들어간다:

```bash
docker exec -i fintech-pg psql -U fintech -d fintech < backend-service/alembic/init/init.sql
```

종료 시 `postgres` 프로세스가 SIGTERM 을 받으면 `docker run --rm` 이 컨테이너를 정리한다.
데이터를 완전히 비우려면 볼륨까지 삭제: `docker volume rm fintech-pg-data`.

### 업로드 경로 전제 — SFTP (리서치 문서 업로드 E2E)

파일 업로드는 통합 앱의 file 모듈이 SFTP 로 실물을 저장하므로 SFTP 서버가 전제다:

```bash
docker compose -f platform/sftp/compose.yaml up -d     # atmoz-sftp, :2022, 계정 admin/admin
```

`backend-service/app/.env.development` 의 `SFTP_USERNAME`/`SFTP_PASSWORD` 를 `admin`/`admin` 으로 채운다 —
부트스트랩은 외부 자격증명이라 채우지 않는다. `SFTP_HOST`(localhost)·`SFTP_PORT`(2022)·
`SFTP_BASE_PATH`(/upload)는 `.env.example` 기본값이 compose 와 맞다.

### doc-search 워크스페이스 벡터 DB — 같은 `fintech` DB

doc-search 의 워크스페이스 문서 색인(pgvector)도 이 로컬 Postgres 의 `fintech` DB 를 쓴다 — 별도
`docsearch` DB 를 만들지 않는다(CONTEXT.md 결정 로그 2026-07-27). 부트스트랩은 `.env.example` 의
`docsearch` 플레이스홀더를 그대로 두므로, doc-search `.env.development` 의 `DOC_VECTOR_DB_*` 를
직접 채운다:

```dotenv
# doc-search-mcp-service/app/.env.development
DOC_VECTOR_DB_HOST=localhost
DOC_VECTOR_DB_PORT=5432
DOC_VECTOR_DB_NAME=fintech
DOC_VECTOR_DB_USER=fintech
DOC_VECTOR_DB_PASSWORD=fintech
```

`workspace_doc_chunk` 는 doc-search 가 색인 직전 `ensure_table`(IF NOT EXISTS)로 `public` 에 스스로
만든다(위 소유 표). `USE_REAL_API=false`(기본)인 동안 인제스트는 파싱·청킹 리포트까지만 가고 실제
색인(pg 쓰기)은 일어나지 않는다 — 실색인은 임베딩 서버 연결 + `USE_REAL_API=true` 에서만 일어난다.

## 이전 진행 상태 (#166)

S0 가 인프라와 스키마 적재 경로를 놓고, S1~S4 가 서비스별 이전을 마쳤다:

- **psycopg 의존성** — backend·devactivity·file·multi-agent 네 서비스 모두
  `psycopg[binary]`(v3) 를 갖는다(설계 §3 권고).
- **방언·식별자** — 리포지토리 raw SQL 은 PostgreSQL 방언을 쓰고, 테이블 식별자는 소문자다
  (`__tablename__="tn_portfolio"` / Prisma `@@map("tn_portfolio")`, 설계 §2.3).
- **frontend Prisma** — S4 에서 `provider="postgresql"` 로 이전됐다. `db-migrate` 가
  `npm run dev:prisma:push` 로 14 테이블을 만든다(초기 데이터는 위 seed 절 참조).

검증 경계: 각 슬라이스가 **서비스를 따로 띄워** 실 Postgres 에서 엔드포인트 응답까지 확인했다
(file 조회·404, devactivity 스케줄러 CRUD·멤버, backend watchlist/portfolio/nav/research-document
와 그리드 filter, frontend better-auth 로그인·Prisma 조회/쓰기, multi-agent 이력 조회).
`process-compose up` 통합 기동은 부트스트랩 도입 시점(2026-07-27)에 처음 돌려봤고, 여기까지 확인됐다:

- **env 부재로 죽던 것은 해소** — 부트스트랩 후 python 서비스 12종 전부가 config 검증을 통과했고,
  `process-compose up` 에서 MCP·multi-agent 7종(8002~8008)이 기동해 `/openapi.json` 200 을 응답했다.
- **`db-migrate` 가 순서대로 전부 통과한다** — 깨끗한 컨테이너(`pgvector/pgvector:pg16`)에서
  `alembic upgrade head` → `prisma db push` 가 성공하고,
  (2026-07-27 실측 시점에는 devactivity·file `db_push` 를 낀 4단계였다 — 흡수로 2단계가 됐다.)
  같은 DB 에 한 번 더 돌려도 no-op(`변경사항이 없습니다` / `already in sync`)으로 통과한다.
  결과는 `public` 12개(파이썬 11 + `alembic_version`) · `frontend` 14개로 갈린다.
- **소유 경계가 지켜진다** — `prisma db push` 를 두 번 돌린 뒤에도 `public` 의 파이썬 테이블 12개와
  backend 이력(`alembic current` → `0001_baseline (head)`)이 그대로다. 스키마를 가르기 전에는 같은
  push 가 이 12개를 삭제 대상으로 잡았다.
- **기동 확인** — `process-compose up` 으로 backend(8000)·devactivity(8001)·file(8100)·
  multi-agent(8003)가 `/openapi.json` 200. frontend 는 `next dev` 로 띄워 better-auth 로그인이
  200 을 응답했고(세션 행이 `frontend.ba_session` 에 생성됨), 이는 런타임 Prisma 가 `frontend`
  스키마를 보고 있다는 증거다.
- 최초 기동에서 막히면 위 「전제」부터 확인한다(docker 데몬, 부트스트랩, frontend `npm install`).
- **스키마 분리 이전에 만든 로컬 DB** 라면 frontend 소유 테이블이 `public` 에 남아 고아가 된다
  (Prisma 는 이제 `frontend` 만 본다). 로컬 데이터를 버려도 되면 볼륨을 지우고 처음부터 적재한다:
  `docker volume rm fintech-pg-data`.

## 공유 DB 에서 alembic 을 쓰는 규칙

`public` 스키마의 파이썬 소유자는 통합 앱(`backend-service`) 하나이고, 마이그레이션 이력
(`alembic upgrade head`)이 유일한 적재 경로다. 버전 테이블 이름은 `alembic/alembic.ini` 의
`version_table`(`alembic_version`)이 SoT 이고 `env.py`(`context.configure`)가 그 값을 읽는다.

- **이 DB 를 쓰는 파이썬 서비스를 새로 추가하면 반드시 자기 `version_table` 을 지정한다** —
  지정하지 않으면 통합 앱의 이력을 건드린다. (지금은 `workspace_doc_chunk` 를 자가 DDL 로
  만드는 doc-search 가 유일한 예외 소유자다.)
- `env.py` 의 `include_object` 는 **자기 모델에 없는 DB 테이블을 autogenerate 에서 제외**한다.
  frontend 스키마·pgvector 확장 테이블이 "모델에서 사라진 것"으로 잡혀 `drop_table` 이 생성되는
  것을 막는다. 대가는 있다 — **모델에서 테이블을 지워도 DB 테이블은 남는다.** 정리가 필요하면
  직접 지운다. (Prisma 는 이 필터에 해당하는 장치가 없어 스키마 자체를 갈랐다 — 위 「DB 구성」.)
- 흡수 전에는 devactivity·file 이 이력 없는 push(`db_push.py`)로 같은 스키마에 적재해 버전
  테이블을 셋으로 갈라야 했다. 그 경로는 폐기됐다 — file 의 `--force-reset` 이 backend 7 테이블을
  전부 지운 실측(#179)이 있었고, 파이썬 앱이 하나가 된 지금 두 메커니즘이 공존할 이유가 없다.
- 이미 `alembic_version` 이 지워진 로컬 DB(테이블은 있는데 이력이 없는 상태)라면 `upgrade head` 가
  베이스라인을 다시 돌리다 `DuplicateTable` 로 죽는다. 스키마가 baseline 과 같다면 이력만 복구하면 된다:
  `cd backend-service/alembic && APP_ENV=development uv run python -m alembic stamp head`.
  (데이터를 버려도 되면 볼륨 삭제 후 처음부터: `docker volume rm fintech-pg-data`.)
