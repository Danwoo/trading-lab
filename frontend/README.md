# Frontend — Fintech AI Platform

AI 투자 리서치 / 핀테크 플랫폼의 **멀티테넌트 SaaS 웹 UI**. 투자자가 종목·재무·리스크·시장 질문을 던지면
Plan-Execute 멀티에이전트가 금융 MCP 도구를 오케스트레이션한 근거(공시) 기반 리서치를 스트리밍으로 보여주고,
관심종목·포트폴리오·보유종목·NAV 등 업무 CRUD 를 마스터-디테일 화면으로 제공합니다.

> 페르소나: 투자 리서치 애널리스트. 모든 답변에는 "ⓘ 정보 제공 목적이며 투자 조언이 아닙니다" 가 부기됩니다.

## 기술 스택

- **Next.js 16** (App Router) + **React 19** + **TypeScript**
- **Better Auth 1.6.11** (NextAuth 아님) — 멀티테넌트 인증, `kysely`/`@better-auth/kysely-adapter` 정확 고정 핀
- **Prisma 7** (PostgreSQL, push 방식 · 마이그레이션 없음) — 시스템관리·회원가입·마이페이지 직접 접근
- **DevExtreme 24.2** (DataGrid/Form) + **Tailwind 3** + **ECharts** (시세·NAV 차트) + **react-markdown/KaTeX** (리서치 렌더)
- **Zod 4** 입력 검증, **Zustand** 클라이언트 스토어, **env-cmd** 환경 명시 로딩

## 멀티테넌트 인증

`lib/auth/` 가 코어 — `auth.ts`(서버), `auth-client.ts`(`signIn/signUp/useSession`), `withAuth.ts`(API Route 보호).

- 권한 3종: `admin`(시스템관리자·글로벌) / `operator`(운영자·자기 워크스페이스) / `user`(일반 투자자)
- JWT payload `{sub, email, role, workspace_id}` 를 `auth.ts` 가 발급 → 모든 backend·MCP 서비스가 동일 `JWT_SECRET` 으로 검증 (frontend·backend 동일값 필수)
- 미들웨어 `proxy.ts`: Better Auth 세션 쿠키 optimistic check. 미인증 시 API 는 401, 페이지는 `/` 리다이렉트. `PUBLIC_RULES` 에 회원가입·인증 플로우만 면제 등록

## API 프록시 (데이터 흐름 2종)

- **Backend 프록시** (신규 비즈니스 엔티티 default): `services/` → `app/api/external/{service}/{prefix}/` → `withAuth` → `proxyApiRequest()` → backend(FastAPI) raw SQL → PostgreSQL
- **Prisma 직접** (시스템관리·회원가입·마이페이지 한정): `services/` → `app/api/common/` → `withAuth` → Prisma → PostgreSQL
- `proxyApiRequest(url, options, mode)` 의 `mode`: `stream`(멀티에이전트 SSE) / `binary` / `passthrough`
- 라우트 prefix 는 backend `APIRouter(prefix=...)` 와 **byte-identical** (backend 가 SoT). `app/api/external/multi-agent/`(투자 리서치 SSE), `portfolio`·`devactivity` 등이 백엔드/MCP 로 프록시

## 재사용 훅 (`hooks/shared/`, 새로 만들지 말 것)

- `useMasterGridData({ fetchGrid, fetchData })` → `{ dataSource, selectedData, handleSelect, handleCreate, handleRefresh }` (관심종목·포트폴리오 목록)
- `useDetailGridData` / `useDetailGridActions` → 2-depth 디테일 (포트폴리오 → 보유종목)
- `useFormState` (폼 상태), `useExcelExport`, `useTreeGridData`, `useFileList`/`useFileGroups`, `useWebSocketService`(시세·체결 틱)
- 공통: `components/shared/`(DataGrid/DataPanel/ui DevExtreme 래퍼) · `stores/shared/codeStore`(`getCode("그룹코드")`)

## 에러 처리

backend 예외 → 사용자 토스트 자동 흐름 (페이지·feature 에서 `try/catch` 불필요):
`exception_handler {detail, status}` → API Route `createErrorResponse` → `apiCall` throw → 공용 훅 catch → `getApiErrorMessage` → `showToast(msg, "error")`.
입력은 Zod 가 사전 차단(`lib/zod/helpers` 사용, `z.*` 직접 호출 금지).

## 환경 변수 (`env.ts` · `@t3-oss/env-nextjs`)

`.env.development` / `.env.staging` / `.env.production` 를 env-cmd 로 명시 로딩. 주요 server 변수:

- `BACKEND_SERVICE_URL`, `MULTI_AGENT_SERVICE_URL`(:8003), `DEV_ACTIVITY_SERVICE_URL`
- MCP: `MARKET_DATA_MCP_SERVICE_URL`(:8004) · `DISCLOSURE_MCP_SERVICE_URL`(:8005) · `NEWS_MCP_SERVICE_URL`(:8006) · `WEB_MCP_SERVICE_URL`(:8007) · `DOC_SEARCH_MCP_SERVICE_URL`(:8008) · `PORTFOLIO_MCP_SERVICE_URL`(:8002)
- 인증/인프라: `JWT_SECRET`, `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `DATABASE_URL`, `EMAIL_*`
- client(`NEXT_PUBLIC_*`): `APP_NAME="Fintech AI Platform"`, `APP_EDITION`(SAAS/OEM), `FILE_SERVICE_URL`

## 실행

```bash
npm install                 # postinstall 이 prisma generate
npm run dev:prisma:push     # 스키마 → DB (마이그레이션 없음, push-only)
PORT=3010 npm run dev       # env-cmd -f .env.development next dev (로컬 포트 SoT: process-compose.yaml frontend PORT)

npm run build && npm run start   # 프로덕션 (.env.production)
npm run lint                     # eslint --fix
```

> `prisma migrate *` 금지 — 항상 `*:prisma:push`. lint/format 은 루트 `pre-commit` 이 일괄 처리.

## 구조

```
app/
  (auth)/signup/          회원가입 플로우
  (main)/admin/           시스템관리 + 업무 화면 (관심종목/포트폴리오/리서치 챗)
  api/common/             Prisma 직접 (system·signup·mypage)
  api/external/           Backend·MCP 프록시 (multi-agent·portfolio·devactivity 등)
  api/auth/[...all]/      Better Auth 핸들러
components/  features/{Entity}/ · shared/ · providers/ · layouts/ (4 폴더만)
hooks/shared/   재사용 훅          stores/shared/  Zustand 스토어
lib/   auth/ · zod/ · devextreme/   services/  API 호출 래퍼
utils/common/api/   client.ts(apiCall) · server.ts(proxyApiRequest) · responses.ts
schemas/  Zod 스키마               prisma/  schema · 클라이언트
proxy.ts(미들웨어) · env.ts(환경 검증)
```

자세한 컨테이너 패턴·anti-pattern 체크리스트는 [`CLAUDE.md`](./CLAUDE.md) 및 [`.claude/docs/`](../.claude/docs/) 참조.
