<!--
  M2 워커 오더 2/3 — 워크스페이스 전환 (다대다 + 전 계층 리네임 + #231).
  이 파일은 오더의 **보관본**이다. 실제 배정 시에는 대상 이슈 코멘트로 옮겨 게시하고
  `human: plan` 승인을 받는다. 이슈 번호는 배정 시 제목 줄에 채운다.
-->

# 오더: 회사를 워크스페이스로 — 다대다 관계와 전 계층 리네임 (FR-023 · FR-050 · #231)

**목표**: 사용자↔워크스페이스를 다대다로 바꾸고, "회사"라는 이름을 화면·코드·DB 전 계층에서 "워크스페이스"로 통일한다. 같은 작업에서 시스템관리자의 테넌트 부재로 인한 401(#231)을 해소한다.

**입력**: [PRD](prd.md) FR-023 · FR-024 · FR-025 · FR-050 · NFR-005 · Clarifications 세션 2026-07-28 · 설계 문서 [M2 전환설계](../4-아키텍처/m2-전환설계.md) **M2-AD-7 ~ M2-AD-10** — 수행자는 이 둘을 먼저 읽는다.

**전제**: 오더 1(모듈 통합)이 완료된 상태에서 착수한다. 두 작업 모두 통합 앱 전역을 건드려 병렬 시 충돌이 확실하다.

## 수용 기준 (AC)

1. 한 사용자가 여러 워크스페이스에 속할 수 있는 관계가 DB 에 존재하고, 기존 사용자 전원이 워크스페이스 1개에 배정된 상태로 이행된다 (FR-023)
2. 추적 파일 기준으로 `company`·`Company`·`COMPANY`·`회사` 잔존이 **의도된 예외 목록 밖에서 0** 이다 (FR-050)
3. 시스템관리자 계정으로 스케줄러 화면이 동작한다 — 운영자와 같은 경로로 200 을 받는다 (#231)
4. 워크스페이스 격리가 유지된다 — 기존 테넌트 격리 검증 스크립트가 이름만 바뀐 채 전부 통과한다 (NFR-005)
5. 세션·JWT 계약 변경이 단계적으로 이뤄져, 어느 중간 커밋에서도 전 서비스가 동시에 401 이 되지 않는다 (M2-AD-7)

## 전역 제약

- `JWT payload = {sub: user.id, email, role: authorId, company_id}. frontend auth.ts 의 definePayload/getSubject 가 발급, backend 가 동일 키로 읽어 core/auth_context.py ContextVar 에 박음. JWT_SECRET 은 frontend·backend 동일값 필수.` [Source: CLAUDE.md#인증]
- `권한 3종: admin(시스템관리자·글로벌) / operator(운영자·자기 회사) / user(일반).` [Source: CLAUDE.md#인증]
- `Prisma 테이블 접두사: TN_(일반), TC_(코드), BA_(인증) / 공통 감사 컬럼: reg_dt, reg_id, mod_dt, mod_id` [Source: CLAUDE.md#네이밍 규칙]
- `테이블명=소문자 snake_case (혼합케이스 기각 — Postgres 폴딩 불일치 실증)` [Source: CONTEXT.md#결정 로그 2026-07-25]
- `DB: PostgreSQL, 공통 DB (Frontend Prisma 관리) + Backend 전용. 스키마 push 방식, 마이그레이션 없음, 런타임 raw SQL` [Source: CLAUDE.md#구성]
- `사용자별·워크스페이스별 데이터는 서로 접근되지 않아야 한다` [Source: .docs/specs/prd.md#NFR-005]
- `브라우저로 열어보지 않은 화면은 "된다"고 말하지 않는다` [Source: CONTEXT.md#교훈]
- `변경 이유·이력 설명 주석 금지` [Source: CLAUDE.md#주석 규칙]

## 태스크

### Phase 1: 데이터 모델과 이행 (AC: 1, 4)

#### T1 (AC: 1) Prisma 소유 테이블 리네임과 멤버십 모델 신설

**범위**: `Company` 계열 모델을 `Workspace` 계열로 리네임하고 `WorkspaceMember` 를 신설한다. Prisma 생성물도 함께 갱신한다.

**Files**
- Modify: `frontend/prisma/schema.prisma:16-58` (`User.company_id` → `workspace_id`, `Company` → `Workspace`, `@@map("tn_company")` → `@@map("tn_workspace")`, `company_code`/`company_nm` → `workspace_code`/`workspace_nm`)
- Modify: `frontend/prisma/schema.prisma:60-88` (`CompanyMenu`→`WorkspaceMenu`(`tn_workspace_menu`), `CompanyDomain`→`WorkspaceDomain`(`tn_workspace_domain`))
- Modify: `frontend/prisma/schema.prisma:90-107` (`BaSession.companyId` → `workspaceId`)
- Modify: `frontend/prisma/schema.prisma` (신규 model `WorkspaceMember` — `@@map("tn_workspace_member")`)
- Modify: `frontend/prisma/init/tables.sql` · `frontend/prisma/init/seed.sql` (생성물 — `table-generator.cjs` 재실행 결과)

**Interfaces**
- Produces: `tn_workspace_member(workspace_id Int, user_id VarChar(36), role VarChar(20), is_default Boolean, reg_dt, reg_id, mod_dt, mod_id)` — PK `(workspace_id, user_id)`, `user_id` 는 `tn_user.id` 참조 FK, `user_id` 단독 인덱스, `role` 은 `owner`·`member`·`viewer`
- Produces: `tn_workspace.id` 는 기존 `tn_company.id` 값을 그대로 승계한다 (리네임이므로 참조 무결성이 유지된다)

**선행조건**: 오더 1 완료

**증명 의무**
- `npm run dev:prisma:push` 실행 후 `frontend` 스키마의 테이블 목록을 조회해 `tn_workspace`·`tn_workspace_member`·`tn_workspace_menu`·`tn_workspace_domain` 이 존재하고 `tn_company*` 가 없음을 보인다
- `tn_workspace_member` 의 인덱스 목록을 조회해 `user_id` 인덱스가 존재함을 보인다 (Postgres 는 FK 컬럼을 자동 인덱스하지 않는다)

**위험**
- **Prisma push 는 컬럼·테이블 리네임을 DROP + CREATE 로 처리한다.** 기존 로컬 데이터는 사라진다. 결정 로그의 "데이터=재시드"(2026-07-25)에 따라 이번에는 재시드로 진행하되, **이 사실을 PR 본문에 명시**한다. 사용자 데이터가 생긴 뒤 같은 방식을 반복하면 사고가 된다.
- `seed.sql` 은 전체 DELETE 로 시작한다 — 재시드 시 개발 중 만든 계정도 지워진다. 사용자가 직접 적용하도록 명령만 안내하고 워커가 실행하지 않는다.
- `user_id` 를 `tn_user.id`(uuid)로 잡는 것은 기존 `AuthorMember.user_id`(email)와 다른 선택이다. 이 비일관은 의도된 것이며, `AuthorMember` 는 이번 범위에서 바꾸지 않는다. [Source: .docs/4-아키텍처/m2-전환설계.md#7.2]

#### T2 (AC: 1) 파이썬 소유 테이블 컬럼 리네임

**범위**: 통합 앱이 소유한 `public` 스키마 테이블의 `company_id` 컬럼을 `workspace_id` 로 바꾼다.

**Files**
- Modify: `backend-service/app/models/schema.py` (`Watchlist`·`Portfolio`·`Holding` 의 **PK 구성 컬럼**, `Nav`·`ResearchDocument`, 오더 1 이 이식한 `Scheduler`·`SchedulerMember`)
- Modify: `backend-service/app/models/schema.py:81` (`Index("idx_research_document_company", ...)` 이름도 함께)
- Modify: `backend-service/app/models/schema.py:142` (`Index("idx_nav_company", ...)`)
- Create: `backend-service/alembic/versions/0004_rename_company_to_workspace.py`
- Modify: `doc-search-mcp-service/app/repositories/workspace/workspace_chunk_repository.py` (자가 DDL 의 `company_id` 컬럼 정의 — 이 서비스는 자기 테이블을 직접 만든다)

**Interfaces**
- Produces: 리비전 `0004_rename_company_to_workspace` — `op.alter_column(..., new_column_name="workspace_id")` 와 `op.execute("ALTER INDEX ... RENAME TO ...")` 로만 구성. **데이터 복사 없음**

**선행조건**: T1 (같은 DB 에 두 소유자가 있으므로 순서를 고정한다)

**증명 의무**
- 리비전 적용 전후로 각 테이블의 행 수가 같음을 보인다 (rename 은 데이터를 옮기지 않는다)
- `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head` 왕복이 성공함을 보인다
- 적용 후 각 테이블의 컬럼 목록을 조회해 `company_id` 가 없고 `workspace_id` 가 있음을 보인다

**위험**
- `tn_watchlist`·`tn_portfolio`·`tn_holding` 은 `company_id` 가 **PK 구성 컬럼**이다. PostgreSQL 의 `RENAME COLUMN` 은 인덱스·제약을 따라 갱신하지만, 리비전이 컬럼을 지웠다 다시 만드는 형태로 생성되면 PK 가 깨지고 데이터가 사라진다. autogenerate 결과를 그대로 쓰지 말고 `alter_column` 인지 확인한다.
- doc-search 는 `workspace_doc_chunk` 를 자가 DDL 로 만든다 — alembic 리비전에 넣으면 소유가 뒤섞인다. 그쪽은 그 서비스 코드에서 바꾼다.

#### T3 (AC: 1, 3) 멤버십 백필과 시스템관리자 워크스페이스 배정

**범위**: 기존 사용자 전원에게 멤버십 행을 만들고, 워크스페이스가 없는 계정(시스템관리자 등)에는 개인 워크스페이스를 만들어 배정한다 (M2-AD-9).

**Files**
- Create: `backend-service/alembic/versions/0005_backfill_workspace_member.py`

**Interfaces**
- Consumes: `tn_workspace_member` (T1) · `tn_user.workspace_id` (T1 리네임 결과)
- Produces: 이행 후 불변식 — **모든 활성 사용자가 `is_default=true` 인 멤버십을 정확히 1개 갖는다**

**선행조건**: T1, T2

**증명 의무**
- 이행 후 `is_default=true` 멤버십이 0개이거나 2개 이상인 사용자를 세는 조회를 실행해 **0행**임을 보인다
- 시스템관리자 계정이 개인 워크스페이스 1개를 갖게 됐음을 조회로 보인다
- 이행 스크립트를 두 번 실행해도 멤버십이 중복 생성되지 않음(멱등)을 보인다

**위험**
- `tn_user` 는 `frontend` 스키마, `tn_workspace_member` 도 `frontend` 스키마다. 통합 앱의 alembic 은 `public` 을 소유한다 — **스키마를 넘는 이행**이므로 SQL 에 스키마를 수식해야 한다. 수식하지 않으면 `relation not found` 로 죽거나, 더 나쁘게는 다른 스키마의 동명 테이블을 건드린다.
- 승인 대기·거부 상태 사용자에게도 워크스페이스를 만들지는 **정하지 않았다**(설계 문서 Q5). 이 태스크는 `appr_at='Y'` 이고 `use_at='Y'` 인 계정만 대상으로 하고, 나머지는 손대지 않는다. 가입 흐름 변경은 별도 결정이다.

**Checkpoint**: DB 계층이 워크스페이스 모델로 이행됐고, 모든 활성 사용자가 정확히 하나의 기본 워크스페이스를 갖는다.

---

### Phase 2: 인증 경로 (AC: 3, 5)

#### T4 (AC: 5) 발급측 — 세션과 JWT claim

**범위**: Better Auth 의 사용자 필드·세션 필드·JWT payload 를 워크스페이스 이름으로 바꾸고, 이행 시점에 전 세션을 무효화한다.

**Files**
- Modify: `frontend/lib/auth/auth.ts:100-106` (user `additionalFields.company_id` → `workspace_id`)
- Modify: `frontend/lib/auth/auth.ts:123-165` (`databaseHooks.session.create.before` — `company` 관계 조회, `InactiveCompany` 메시지, `companyId` 주입)
- Modify: `frontend/lib/auth/auth.ts:171-184` (session `additionalFields.companyId` → `workspaceId`)
- Modify: `frontend/lib/auth/auth.ts:202-226` (jwt `definePayload`·`sign` — payload 키 `company_id` → `workspace_id`)
- Modify: `frontend/lib/auth/authUtils.ts:11-15` (`invalidateUserSessions` 주석과 이름)

**Interfaces**
- Produces: JWT payload = `{sub, email, role, workspace_id}` — 검증측(T5)이 이 키를 읽는다
- Produces: 세션의 워크스페이스 필드 의미가 **"현재 선택된 워크스페이스"** 로 바뀐다 (M2-AD-8). 로그인 시 `is_default=true` 멤버십에서 결정한다

**선행조건**: T3

**증명 의무**
- 로그인 후 발급된 JWT 를 디코드해 `workspace_id` 가 실려 있음을 보인다 (시크릿·토큰 원문은 기록하지 않는다)
- 멤버십이 2개인 테스트 계정을 만들어, 로그인 세션의 워크스페이스가 `is_default=true` 쪽으로 결정되는 것을 보인다
- 로그인 차단 분기 4종(승인 대기·가입 거부·계정 비활성·워크스페이스 비활성)이 그대로 동작함을 각각 1회 확인한다

**위험**
- **T5 보다 먼저 머지되면 검증측이 `workspace_id` 를 모른다.** 그래서 T5 의 폴백을 **먼저** 넣는 순서를 지킨다 (아래 「의존·실행 순서」).
- `InactiveCompany` 는 화면에 노출되는 메시지 키다. 프론트 메시지 매핑을 함께 바꾸지 않으면 사용자에게 빈 메시지가 뜬다.

#### T5 (AC: 5) 검증측 — 10개 서비스 lockstep + 폴백

**범위**: 토큰 검증과 신원 컨텍스트를 워크스페이스 이름으로 바꾸되, **한동안 두 claim 이름을 모두 읽는다** (M2-AD-7). 이 두 파일은 byte-identical lockstep 대상이라 **한 커밋에서 전 서비스를 동시에** 바꾼다.

**Files**
- Modify: `backend-service/app/core/auth_context.py` (`_company_id` → `_workspace_id`, `get_company_id` → `get_workspace_id`, `require_company_id` → `require_workspace_id`)
- Modify: `backend-service/app/core/security.py:44-50, 53-60` (payload 에서 `workspace_id` 를 먼저 읽고 없으면 `company_id` 를 읽는다)
- Modify: 위 두 파일의 동일본 — `portfolio-mcp-service` · `market-data-mcp-service` · `disclosure-mcp-service` · `news-mcp-service` · `web-mcp-service` · `doc-search-mcp-service` · `template-mcp-service` · `multi-agent-service` · `single-agent-service` 의 `app/core/{auth_context,security}.py`
- Modify: `scripts/verify_auth_lockstep.py` (`EXPECTED_SERVICES` 목록 — 오더 1 에서 제거된 서비스가 반영돼 있어야 한다)

**Interfaces**
- Produces: `core/auth_context.get_workspace_id() -> int | None` · `require_workspace_id() -> int` (미설정 시 `UnauthorizedError`)
- Produces: `set_auth_context(*, user_id, role, workspace_id, email=None, is_service=False)` — 호출부(T6·T7)가 이 시그니처를 쓴다

**선행조건**: T3

**증명 의무**
- `python scripts/verify_auth_lockstep.py` 가 통과함을 보인다 (byte-identical 검증)
- `workspace_id` 만 실린 토큰과 `company_id` 만 실린 토큰 **양쪽**으로 보호된 엔드포인트를 호출해 둘 다 200 을 받음을 보인다
- 두 claim 이 모두 없는 토큰으로 호출해 401 을 받음을 보인다 (fail-closed 유지)

**위험**: 10개 파일 쌍을 손으로 맞추면 한 글자 차이로 lockstep 이 깨진다. 한 파일을 고친 뒤 나머지에 **복사**하고, 검증 스크립트로 확인한 뒤 커밋한다.

#### T6 (AC: 3, 4) 권한 게이트와 on-behalf 토큰 · #231 해소

**범위**: 워크스페이스 스코핑을 요구하는 게이트를 이름과 의미 모두 갱신하고, 시스템관리자 비대칭을 없앤다. **스코핑 우회 분기를 만들지 않는다** (M2-AD-9).

**Files**
- Modify: `backend-service/app/core/authorization.py:1-38` (`_ensure_tenant_user` 의 `get_company_id` 호출, 주석의 "회사")
- Modify: `backend-service/app/core/mcp_token.py` (on-behalf payload 키)
- Modify: `multi-agent-service/app/core/mcp_token.py` (같은 변경)
- Modify: `doc-search-mcp-service/app/core/service_guard.py`
- Modify: `frontend/lib/auth/withAuth.ts:18-33, 56-70, 89-100` (`scopeEmailParam` 옵션 주석, `companyId` 파생, `assertSameCompanyOrSysAdmin` 호출)
- Modify: `frontend/lib/auth/authUtils.ts:17-34` (`assertSameCompanyOrSysAdmin` → `assertSameWorkspaceOrSysAdmin` — 멤버십 기반 판정으로)
- Modify: `frontend/hooks/shared/useSessionContext.ts` (`companyId` → `workspaceId`)

**Interfaces**
- Consumes: `require_workspace_id()` (T5)
- Produces: `assertSameWorkspaceOrSysAdmin(session, email) -> string | null` — 대상 사용자가 요청자의 **현재 워크스페이스에 속하는지**를 멤버십으로 판정한다 (기존은 `user.company_id` 단일 비교였다)

**선행조건**: T4, T5

**증명 의무**
- **시스템관리자 계정으로 스케줄러 화면을 브라우저에서 열어** 목록 조회·생성·삭제가 동작함을 보인다 (#231 재현 경로의 역방향 확인)
- 운영자 계정으로 같은 화면이 여전히 동작함을 보인다 (회귀 없음)
- 워크스페이스가 다른 두 계정으로 서로의 데이터가 보이지 않음을 확인한다
- `portfolio-mcp-service/scripts/verify_tenant_isolation.py` · `multi-agent-service/scripts/verify_onbehalf_token.py` · (오더 1 이 이식한) `verify_scheduler_gating.py` 를 실행해 전부 통과함을 보인다

**위험**
- `assertSameCompanyOrSysAdmin` 은 `company_id` 단일 비교이고 `null` 이면 fail-closed 였다. 멤버십 기반으로 바꾸면 **"여러 워크스페이스에 겹쳐 속한 두 사용자"** 라는 새 경우가 생긴다. 판정 기준을 "요청자의 **현재 선택된** 워크스페이스에 대상이 속하는가"로 고정하고, 그 기준을 함수 docstring 에 남긴다.
- 시스템관리자 우회(`isSysAdmin` 이면 통과)는 기존 동작이다. 이번 작업에서 **없애지 않는다** — 없애면 관리 화면이 막힌다. #231 의 해소는 "admin 에게도 워크스페이스를 준다"이지 "우회를 넓힌다"가 아니다.

**Checkpoint**: 인증·세션·게이트가 워크스페이스 이름으로 동작하고, 시스템관리자와 운영자의 비대칭이 사라졌다.

---

### Phase 3: 스코핑과 화면 (AC: 2, 4)

#### T7 [P] (AC: 2, 4) 백엔드 스코핑 리네임

**범위**: 서비스·리포지토리의 테넌트 스코핑 인자와 SQL 바인드 이름을 바꾼다.

**Files**
- Modify: `backend-service/app/services/{watchlist,portfolio,nav,research_document,scheduler}/*.py`
- Modify: `backend-service/app/repositories/{watchlist,portfolio,nav,research_document,scheduler}/*.py`
- Modify: `backend-service/app/schemas/research_document/research_document_schema.py`
- Modify: `backend-service/app/clients/doc_search/doc_search_client.py`
- Modify: `backend-service/app/managers/nav/nav_producer_manager.py`
- Modify: `portfolio-mcp-service/app/services/portfolio/portfolio_service.py` · `app/repositories/portfolio/portfolio_repository.py` · `app/clients/portfolio/portfolio_client.py`
- Modify: `doc-search-mcp-service/app/routers/workspace/workspace_router.py` · `app/services/workspace/workspace_service.py` · `app/repositories/workspace/workspace_chunk_repository.py`

**Interfaces**
- Consumes: `require_workspace_id()` (T5)
- Produces: 리포지토리 SQL 의 바인드 파라미터 이름이 `:workspace_id` 로 통일된다

**선행조건**: T5

**증명 의무**
- anti-patterns Detection 명령 전체를 실행해 hit 수를 표로 제시한다 — 특히 룰 6(페이지네이션)·룰 8(인증 누락)이 리네임 과정에서 깨지지 않았음을 보인다
- 통합 앱의 대표 엔드포인트(watchlist 목록·portfolio 마스터-디테일·nav 이력·research-document 목록)를 각각 호출해 200 과 격리된 결과를 보인다

**위험**: SQL 문자열 안의 컬럼명과 바인드 이름을 함께 바꾸다 한쪽만 놓치면 `column does not exist` 가 아니라 **바인드 미매칭**으로 죽는다 — 에러 메시지가 원인을 가리키지 않는다. 리포지토리 파일마다 컬럼명·바인드명 쌍을 대조한 뒤 커밋한다.

#### T8 [P] (AC: 2) 프론트 화면·서비스·API 경로 리네임

**범위**: 화면 컴포넌트·서비스·스키마·API 라우트 경로를 워크스페이스로 바꾼다. **폴더 이동은 순수 이동 커밋으로 분리**해 git 이 rename 으로 추적하게 한다.

**Files**
- Modify(이동): `frontend/components/features/Common/System/Company/` → `.../Workspace/` (`CompanyDetailForm.tsx`·`CompanyDetailView.tsx`·`CompanyDomainGrid.tsx`·`CompanyMenuGrid.tsx`·`CompanyUserGrid.tsx` 5개)
- Modify(이동): `frontend/services/common/companyService.ts` → `workspaceService.ts` · `frontend/schemas/common/company.ts` → `workspace.ts`
- Modify(이동): `frontend/app/api/common/system/company/**` → `.../workspace/**` (`[company_id]` 세그먼트 포함 — `options/`·`[company_id]/`·`[company_id]/menu/`·`[company_id]/menu/[menu_id]/`·`[company_id]/user/`·`[company_id]/domain/`·`[company_id]/domain/[domain]/`)
- Modify: `frontend/app/api/common/{signup,mypage}/route.ts` · `frontend/app/api/common/system/{adminuser,author,email-log,menu}/**`
- Modify: `frontend/components/features/Common/System/AdminUser/AdminUserDetailForm.tsx` · `frontend/schemas/common/adminUser.ts`
- Modify: 위 화면을 여는 페이지 라우트와 메뉴 데이터(`frontend/prisma/init/seed.sql` 의 메뉴 행)

**Interfaces**
- Consumes: 세션의 `workspaceId` (T4) · `assertSameWorkspaceOrSysAdmin` (T6)
- Produces: 관리 화면의 API 경로가 `/api/common/system/workspace/...` 로 바뀐다

**선행조건**: T6

**증명 의무**
- **브라우저로** 워크스페이스 관리·사용자 관리·메뉴 관리 화면을 열어 목록·상세·저장이 동작함을 확인한 기록 (curl 로는 CSP 자기 차단 같은 문제를 못 잡는다 — CONTEXT 교훈)
- 메뉴 데이터의 URL 이 바뀐 경로를 가리키는지 확인한다 — 시드를 안 바꾸면 사이드바 링크가 404 가 된다

**위험**: API 라우트 폴더를 옮기면 URL 이 바뀐다. 이 API 는 내부 관리 화면 전용이지만, **메뉴 테이블에 URL 이 데이터로 저장돼 있다**. 코드만 옮기고 데이터를 두면 화면에서 링크가 깨진다.

**Checkpoint**: 화면과 API 가 워크스페이스 이름으로 동작하고, 기존 관리 기능이 전부 유지된다.

---

### Phase 4: 마무리 (Polish)

#### T9 (AC: 2) 검증 스크립트·CI·문서 동기화

**범위**: 회귀 그물과 살아있는 문서를 같은 작업에서 갱신한다.

**Files**
- Modify: `portfolio-mcp-service/scripts/verify_tenant_isolation.py` · `verify_portfolio_calc.py`
- Modify: `multi-agent-service/scripts/verify_onbehalf_token.py`
- Modify: `backend-service/scripts/verify_scheduler_gating.py` (오더 1 이 이식한 위치)
- Modify: `doc-search-mcp-service/tests/test_workspace_ingest_status.py` · `tests/test_require_service_token.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `.docs/4-아키텍처/saas-멀티테넌트.md` (제목·용어·3레이어 설명·부록 용어)
- Modify: `.docs/4-아키텍처/인증토큰전략.md` · `.docs/2-개발가이드/fastapi-백엔드개발.md` · `.claude/docs/design-patterns-backend.md` · `.docs/3-기법/동시성-가이드.md` · `.docs/3-기법/동시성-출처인덱스.md`
- Modify: 각 서비스 `CLAUDE.md` (10개) · `CLAUDE.md`(루트) · `backend-service/README.md` · `frontend/README.md`
- Modify: `.docs/specs/prd.md` (FR-023·FR-050 완료 반영) · `.docs/4-아키텍처/m2-전환설계.md` (완료 단계 표시)

**선행조건**: T7, T8

**증명 의무**
- `git grep -inE "company|회사"` 결과 전체를 제시하고, 남은 항목이 **의도된 예외**(과거 이슈 인용·외부 API 필드명·이력 서술)뿐임을 항목별로 분류해 보인다. 분류되지 않은 잔존이 있으면 미완이다
- 갱신한 검증 스크립트를 전부 실행해 통과함을 보인다

**위험**: 문서에서 "회사"를 기계 치환하면 **다른 뜻의 회사**(예: 상장 회사·기업 공시)까지 바뀐다. 투자 도메인 문서에서는 "회사"가 종목의 발행사를 뜻하는 경우가 있다 — 파일별로 눈으로 확인한다.

#### T10 (AC: 5) JWT claim 폴백 제거

**범위**: T5 가 넣은 `company_id` 폴백을 제거한다 (M2-AD-7 의 예약 항목).

**Files**
- Modify: 10개 서비스의 `app/core/security.py` (폴백 분기 제거 — byte-identical 유지)

**선행조건**: T9

**증명 의무**
- `python scripts/verify_auth_lockstep.py` 통과
- 로그아웃 → 로그인 후 전 화면이 동작함을 브라우저에서 확인
- `git grep -n "company_id" -- '*/app/core/security.py'` 가 0 hit

**위험**: 폴백 제거 시점에 살아 있는 오래된 세션이 있으면 그 사용자만 401 이 된다. 제거 커밋과 함께 세션 무효화를 1회 수행하고, 그 사실을 PR 본문에 적는다.

## Dev Notes — 수행자가 알아야 할 맥락

- **리네임 표면의 크기**: `company_id|companyId|company_no|companyNo` 는 684곳/114파일, `[Cc]ompany|COMPANY|회사` 는 1,393곳/168파일이다(추적 파일 기준). 한 번에 기계 치환하면 리뷰가 불가능하다 — Phase 별로 커밋을 나눈다. [Source: .docs/4-아키텍처/m2-전환설계.md#6.1]
- **3레이어 방어를 유지한다**: 클라 페이지 가드 / API 권한 게이트 / 쿼리 격리. 리네임 과정에서 어느 한 층이라도 빠지면 격리가 뚫린다. [Source: .docs/4-아키텍처/saas-멀티테넌트.md#9]
- **`companyId` 가 null 인 비정상 케이스는 매칭 0건(fail-closed)** 이 기존 규약이다. 워크스페이스로 바꿔도 이 성질을 유지한다. [Source: .docs/4-아키텍처/saas-멀티테넌트.md#레이어 3]
- **#231 의 재현 경로**: 프록시 가드를 `requireOperatorOrAdmin` 으로 정렬한 뒤 operator 는 통과하고 admin 은 백엔드에서 401 을 받는다. 원인은 admin 에게 테넌트가 없다는 것이다. [Source: 이슈 #231]
- **on-behalf 토큰의 존재 이유**: 하류 MCP 가 테넌트 격리를 강제할 수 있도록 요청자 테넌트를 payload 에 싣는다. 순수 서비스 토큰(`sub`·`typ` 만)과 구분된다. [Source: devactivity-service/app/core/mcp_token.py:1-9]
- **오더 1 과의 접점**: `scripts/verify_auth_lockstep.py` 의 `EXPECTED_SERVICES` 는 오더 1 의 서비스 삭제가 반영돼 있어야 한다. 반영되지 않았다면 T5 에서 함께 고친다.

## 의존·실행 순서

- Phase 1(T1→T2→T3)은 직렬이다. 같은 DB 를 두 소유자(Prisma·alembic)가 나눠 갖고 있어 순서가 결과를 바꾼다.
- **T5 를 T4 보다 먼저 머지한다.** 검증측이 두 이름을 모두 읽는 상태를 만든 뒤에 발급측을 바꿔야 어느 중간 커밋에서도 401 이 나지 않는다 (AC-5).
- T6 ← T4·T5
- **T7 ∥ T8 병렬 가능** — 백엔드와 프론트는 파일이 겹치지 않는다. 둘 다 T6 이후.
- T9 ← T7·T8 · T10 ← T9
