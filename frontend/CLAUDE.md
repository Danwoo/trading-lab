# Frontend CLAUDE.md

## 환경

- 환경 파일: `.env.development` / `.env.staging` / `.env.production` — **`env-cmd` 로 명시 로딩** (Next.js 기본 동작 아님). 모든 npm script 가 환경 명시 (예: `npm run dev` = `env-cmd -f .env.development next dev`)
- **의존성 핀**: `better-auth` `1.6.11` / `kysely`(+`@better-auth/kysely-adapter`) `0.28.17` **정확 고정** (캐럿 `^` 금지 — 1.6.12 가 kysely 0.29 를 끌어와 `DEFAULT_MIGRATION_TABLE` 제거 → adapter 깨짐). `uuid`(v7, `auth.ts` 의 `generateId`) 직접 의존성 필수. `prisma.config.ts` 는 env 검증 우회 위해 `process.env.DATABASE_URL ?? ""` 직접 사용.

## Container 구조 (모든 CRUD 페이지의 기본)

`SplitPane`(`components/shared/Layout/SplitPane.tsx`, O1)으로 좌측(목록) + 우측(상세) 분할. (O8-1 이전에는 devextreme-react 의 `Splitter` 였다 — 레포 전체 이주 완료.)
```tsx
<SplitPane orientation="horizontal" initialSizes={[60, 40]}>
  {[
    <MasterPanel key="master" title buttons>
      <MasterGrid dataSource columns onSelectionChanged />
    </MasterPanel>,
    <DetailPanel key="detail" data ViewComponent FormComponent apiService onComplete />,
  ]}
</SplitPane>
```

**변형** (상세: [`design-patterns-frontend.md`](../.claude/docs/design-patterns-frontend.md) 의 "패턴 변형", anti-patterns 룰 5 예외):
- **2-depth 스코프**: `SplitPane` 위 `ConditionBar` / `{Scope}ControlBar` 로 부모 스코프 선택 후 자식 CRUD (예: Document = Project 선택 → 문서 목록)
- **비-CRUD**: 대화형/워크스페이스 (채팅) 는 `SplitPane` + 도메인 패널 — `MasterPanel`/`DetailPanel` 없음
- **추출 상세 섹션**: View/Form 이 공유하는 섹션 컴포넌트는 `editable` prop 으로 모드 전환 (View=false / Form 기본 true)

## 재사용 훅/컴포넌트 (새로 만들지 말 것)

**훅 (`hooks/shared/`)**
- `useMasterGridData({ fetchGrid, fetchData })` → `{ dataSource, selectedData, handleSelect, handleCreate, handleRefresh }` 반환
- `useMasterGridActions({ onCreate, onRefresh, onExcelDownload })` → 툴바 버튼
- `useDetailGridData` → 2-depth 디테일 그리드
- `useFormState` → 폼 입력 상태
- `useExcelExport`(레거시 그리드 화면), `useFileList`, `useFileGroups`
- `useServerTable({ fetchGrid, pageSize?, clientSide?, dependencies? })` → `ServerTableState<T>`(신규 그리드 커널, `DataTable` 짝). `clientSide: true` 로 클라이언트 페이징/정렬/필터
- `useTableExport({ columns, fetchAll, fileName? })` → `DataTable` 전용 엑셀 다운로드(`DataGrid`/`useExcelExport` 와 별개)

**컴포넌트 (`components/shared/`)**
- `DataGrid/` → MasterGrid, DetailGrid, DualSelectGrid (레거시 CRUD 화면용 얇은 어댑터 — 안이 `DataTable` 커널이다. 컬럼은 `LegacyGridColumn`, 변환은 `DataGrid/legacyColumns.tsx`)
- `DataTable/` → DataTable, DataTablePager, DataTableFilterRow (그리드 커널: @tanstack/react-table + react-virtual — `useServerTable` 짝, 새 화면은 이쪽에 `GridColumn` 으로)
- `DataPanel/` → MasterPanel, DetailPanel, DetailGridPanel
- `ui/` → TextBox, DateBox, SelectBox, CheckBox 등 (자체 구현 — 네이티브 입력 + radix-ui, `ui/primitives/`)
- `Layout/FormModal`, `Feedback/MessagePopup`, `Layout/SplitPane`(신규 분할 화면 래퍼)

**스토어 (`stores/shared/`)**
- `codeStore` → `getCode("그룹코드")`로 공통코드 목록 반환. 가장 자주 사용됨
- `navStore`, `messageStore`, `uploadProgressStore`

**스토어 (`stores/terminal/`)** — 터미널 전용 도메인 스토어 폴더(`stores/shared/` 와 별개)
- `contextStore` → 터미널 문맥(종목·주기·기간·선택봇). 쓰기는 `stores/terminal/contextActions.ts` 를
  통해서만 — 스토어·액션 모듈 밖에서 `contextStore` 를 직접 import 하지 않는다(패널은 읽기 전용
  훅 `hooks/terminal/useTerminalContext.ts` 만 쓴다)
- `layoutStore` → 패널 배치. 워크스페이스별로 `terminal-layout:{workspaceId}` localStorage 키에
  영속. 레이아웃 복원은 `setWorkspace()` 호출 시점에만 일어나므로(스토어 생성 시 자동 read 없음)
  마운트 이펙트에서 불러야 한다 — 렌더 중 호출하면 안 된다
- `realtimeStore` → 동시 1종목 실시간 구독을 소유하는 싱글턴(설계 §3.6). `contextActions` 의
  종목 변경을 구독해 `switchTo` 를 호출하는 유일한 곳 — 패널에서 직접 import 하지 않고
  `hooks/terminal/useRealtimeQuote.ts` 를 통해서만 쓴다(anti-patterns 룰 15)

## 핵심 유틸

- `utils/common/api/client.ts` → `apiCall()`: 모든 클라이언트 API 호출
- `utils/common/api/server.ts` → `proxyApiRequest(url, options, mode)`: API Route에서 Backend 프록시. `mode`: `stream`/`binary`/`passthrough`
- `utils/common/api/responses.ts` → `createSuccessResponse()`, `createErrorResponse()`
- `lib/grid/filters.ts` → `convertFilterToPrismaWhere()`, `convertSortToPrismaOrderBy()`
- `lib/zod/helpers.ts` → `str()`, `int()`, `float()`, `bool()`, `date()`, `StrRange()`, `IntRange()`, `Field()`, `Optional()`, `object()` 등 — Zod schema 작성 시 직접 `z.*` 대신 이 헬퍼 사용

## 에러 처리

Backend → 사용자 토스트 자동 흐름 — 페이지·feature 컴포넌트에서 `try/catch` 추가 불필요:

```
Backend exception_handler → {detail: "한글 메시지", status: 4xx/5xx}
  → API Route createErrorResponse (axios 에러는 패스스루)
  → apiCall axios throw
  → 공용 훅 (useMasterGridData / useDetailGridData / DetailPanel / FileUploader) catch
  → getApiErrorMessage(error) → showToast(msg, "error")
```

- `utils/common/api/responses.ts` → `createErrorResponse(error, operation)`: API Route 의 5 갈래 매핑 (AUTH / Prisma / Axios 패스스루 / `{message}` plain / fallback)
- `utils/common/errors/apierrors.ts` → `getApiErrorMessage(error)`: 우선순위 ① `detail` 문자열 (Backend 도메인 예외) ② `detail` 배열 (Prisma type 한글 번역 → 첫 `msg`) ③ `error`/`message` 필드 ④ STATUS_MESSAGES (400~504 17개) ⑤ "네트워크 연결을 확인해주세요"
- 입력 검증은 Zod 가 사전 차단 → Pydantic 422 도달 거의 없음 (STATUS_MESSAGES 422 는 안전망)

## 테스트 (Vitest)

`npm test` (= `vitest run`) / `npm run test:watch`. 설정은 `vitest.config.ts`.

- **기본 대상은 순수 함수** — 부수효과·import-time 부트스트랩이 없는 유틸. 기본 환경은 `node`(빠름).
  - `utils/common/locale/index.ts` 는 import 만으로 Zod 를 부트스트랩한다 — 이걸 (간접으로라도) 끌어오는 모듈은 순수 유틸이 아니다.
- **컴포넌트(DOM) 테스트**: `jsdom` + `@testing-library/react` + `@testing-library/user-event` 도입 완료(#315). DOM 이 필요한 테스트 파일만 최상단에 `// @vitest-environment jsdom` 을 붙인다(파일 단위 opt-in — `vitest.config.ts` 주석에 근거). 붙이지 않으면 `render()` 가 `ReferenceError: document is not defined` 로 즉시 실패하므로, 빠뜨린 채 조용히 통과하지 않는다. `@testing-library/react` cleanup 은 `globals: true` 를 안 쓰므로 각 테스트 파일이 `afterEach(cleanup)` 을 직접 호출한다(예시: `tests/components/features/Terminal/PanelPicker.test.tsx`).
- **위치 규약**: `tests/` 아래에 소스 경로를 그대로 미러링한다 (백엔드 서비스의 `tests/` 와 같은 자리).
  `tests/lib/grid/filters.test.ts` ↔ `lib/grid/filters.ts`
  수집 자체는 `**/*.{test,spec}.*` 기본값이라 다른 곳에 둬도 돌긴 한다 — 안 도는 테스트를 만들지 않으려는 의도적 선택이고, 배치는 위 규약을 따른다.
- **수집된 테스트가 0건이면 실패한다** (`passWithNoTests: false`). `--passWithNoTests` 를 붙이면 이 방어가 사라지므로 붙이지 않는다 — 검사 대상이 0건인데 초록인 상태는 이 레포에서 실제로 사고를 냈다.
- 게이트: CI `test: frontend` (`.github/workflows/ci.yml`, `on.paths` 에 `frontend/**`) + pre-commit `vitest` 훅. pre-commit 훅은 `frontend/node_modules` 가 없으면 SKIP 하므로(eslint·tsc 훅과 같은 동작) **권위 있는 게이트는 CI 쪽**이다.

## 죽은 코드 상한 (knip)

`scripts/check-dead-code.js` 가 knip 을 돌려 축별 건수를 `CEILINGS` 와 **정확히 대조**한다 (넘어도 밑돌아도 빨간불 — 걷어낸 PR 은 상한을 함께 내린다). CI 스텝은 `test: frontend` 의 「죽은 코드 상한」.

- **knip 의 「미사용」을 그대로 지우지 마라.** 이 레포의 소비자 상당수가 TS import 그래프 밖에 있다 — 워크플로가 `node` 로 실행하는 `scripts/*.js`, 파이썬 그물이 경로로 열어 정규식으로 파싱하는 상수(`schemas/terminal/ingest.ts` 의 `DATA_KINDS`·`JOB_KINDS`·`RUN_STATUSES` ↔ `scripts/verify_capability_kind_lockstep.py`), prisma 가 문자열로 지정하는 생성기(`prisma/table-generator.cjs`). 지우면 그 그물이 **조용히 죽는다**.
- 그런 소비자는 `knip.jsonc` 에 **이유 한 줄과 함께** `entry`/`ignore`/`ignoreDependencies` 로 선언한다. 「안 쓰이지만 남긴다」는 판정은 선언하지 않는다 — 목록에 그대로 두고 상한이 잠근다.

---

## Anti-patterns 체크리스트 (작업 중 즉시 회피)

상세 (❌/✅ 예시, grep, 예외) 는 [`.claude/docs/anti-patterns-frontend.md`](../.claude/docs/anti-patterns-frontend.md). 신규 CRUD 코드 패턴은 [`.claude/docs/design-patterns-frontend.md`](../.claude/docs/design-patterns-frontend.md).

> 룰 번호/이름은 [`anti-patterns-frontend.md`](../.claude/docs/anti-patterns-frontend.md) 의 `### N.` 헤더와 텍스트 정확히 일치.

**재사용 / 위치**
1. **재사용 훅/컴포넌트 무시하고 자체 구현** → `hooks/shared/` + `components/shared/` 먼저 (`useMasterGridData`/`useFormState`)
2. **컴포넌트 위치 위반** → `components/features/{Entity}/`(PascalCase) / `shared/` / `providers/` / `layouts/` 4 폴더만
3. **자식 컴포넌트 Props snake_case (camelCase 위반)** → Props 는 camelCase, DB/API payload key 만 snake_case

**UI / Container**
4. **DevExtreme 재도입** → 이 레포에 devextreme 은 없다(#341). 폼은 `components/shared/ui/`, 그리드는 `DataTable/`(새 화면)·`DataGrid/`(레거시)
5. **Container 구조 위반** → `SplitPane` + `MasterPanel` + `DetailPanel`

**데이터 / API**
6. **fetch / axios 직접 사용** → 클라이언트 `apiCall` · API Route `proxyApiRequest`
7. **데이터 흐름 패턴 혼재** → 한 엔티티는 Prisma 직접 / Backend 프록시 중 하나만
8. **API Route 인증 누락** → 모든 route `withAuth` (면제는 `proxy.ts` `PUBLIC_RULES` 등록)
9. **codeStore 무시** → 공통코드는 항상 `useCodeStore().getCode('GROUP_CODE')`

**스키마 / DB**
10. **Zod 직접 호출 (helpers 우회)** → `@/lib/zod/helpers` 사용
11. **Prisma 마이그레이션 명령 사용** → push-only (`npm run dev:prisma:push`), `prisma migrate *` 금지

**컴포넌트 타입**
12. **Server / Client Component 혼동** → `useState`/`useEffect`/`useRef`/`useReducer`/`useMemo`/`useCallback` 사용 시 첫 줄 `'use client'`

**라우트 정합성**
13. **Frontend 라우트 경로가 backend prefix 와 불일치** → proxy `{SERVICE}_SERVICE_URL + "/{prefix}"` 의 prefix 가 backend `APIRouter(prefix=...)` 와 byte-identical. external `app/api/external/{service}/{prefix}/`·`BASE_URL`·admin page 일치 (backend SoT, 변경 시 lockstep)

**터미널 / 패널**
14. **패널이 문맥을 직접 변경** → 패널은 `useTerminalContext` 로 읽기만, 문맥 변경은 `TerminalContainer.tsx`·종목 사이드바·차트 컨트롤·AI 콘솔만
15. **패널이 데이터 세 갈래 훅을 우회** → `*Panel/` 안에서 `apiCall`/`WebSocket` 직접 호출 금지, `useLoadedSeries`/`useRealtimeQuote`/`useOnDemand` 경유
16. **패널 데이터 훅이 provenance 없이 반환** → `hooks/terminal/` 데이터 훅은 `PanelData<T>`(또는 `provenance` 필드 포함)로 반환
17. **샘플 데이터가 실데이터 경로에서 쓰임** → `sample*`/`Sample*` 모듈은 `provenance.kind === "placeholder"` 분기에서만

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
