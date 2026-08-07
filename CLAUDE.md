# CLAUDE.md

## 구성

- **Frontend** (`frontend/`): Next.js 16 + TypeScript + Prisma + Better Auth + DevExtreme + Tailwind
- **Backend**: FastAPI + SQLAlchemy raw SQL + dependency-injector. 선택적이며 **여러 개 가능** — `app/main.py` 가 있는 모든 폴더가 backend (기본 `backend/`, 또는 `api/`/`server/`/도메인별 등). 없으면 frontend-only 구성. docs 의 `backend/` 참조는 실제 경로로 치환.
- **File 모듈** (`backend-service/app/{routers,services,repositories}/file/`): FastAPI + asyncssh (SFTP). 통합 앱 안의 한 모듈이며, 다른 모듈은 `FileService` 를 DI 로 주입받아 호출한다 — `SftpClient`·`FileRepository` 직접 호출 금지 (anti-patterns 룰 14). (doc-search 의 직접 SFTP 이미지 파이프라인만 예외)
- **Platform** (`platform/`): nginx, sftp 인프라
- **DB**: PostgreSQL 단일 `fintech`. 소유를 스키마로 가른다 — `public` 은 통합 앱 alembic(이력), `frontend` 는 Prisma push. 런타임 raw SQL

## 이 repo 서비스

SaaS 멀티테넌트 풀스택 스타터 템플릿 — 시스템관리(워크스페이스/메뉴/사용자/권한/코드/메일로그) + AI 투자 리서치 업무 엔티티(관심종목/포트폴리오).

- `backend-service` (:8000) — **통합 앱**. 비즈니스 API 를 모듈(도메인 폴더)로 담는다: watchlist CRUD · 포트폴리오·보유종목 마스터-디테일 · 시세/체결 틱 ingestion 메시지 큐 producer/consumer + NAV 시계열 대시보드 · 리서치 문서 · **file**(업로드/다운로드 + SFTP + 파일 메타) · **scheduler/chat/report**(주간 활동요약 메일 스케줄러 + 포트폴리오 활동 조회 챗). 라우터·매니저 등록은 `app/modules.py` 한 곳. 백그라운드 매니저 3종이 앱 안에서 돌아 `--workers=1`. 신규 엔티티 스캐폴드 템플릿
- `portfolio-mcp-service` (:8002) — 계좌/포트폴리오 데이터 전용 MCP 서버 (FastMCP `from_fastapi` 가 REST 라우터를 `/mcp` MCP tool 로 노출 — 같은 앱이 REST 도 그대로 서빙, DB·LLM 없음). 포트폴리오 데이터 접근 단일 소유 — 타 서비스는 직접 호출 금지, **MCP tool 로만** 접근 (에이전트=`MultiServerMCPClient`, 단발 조회·목록 위젯=`PortfolioMcpClient`). 서비스 간 호출은 `create_access_token` 서비스 토큰
- `multi-agent-service` (:8003) — MCP **소비자** (순수 FastAPI, MCP 서버 아님). 투자 리서치 도메인 Plan-Execute 멀티 에이전트 (4 도메인 · 총 12 sub-agent StateGraph — 종목·시세/재무·공시/리스크·밸류/시장·뉴스·매크로) 가 아래 6개 MCP 서버 tool 을 `MultiServerMCPClient`+`ServiceJwtAuth` 로 오케스트레이션. sub-agent ↔ tool 은 `agents/domains/*` 의 `mcp_tools` 가 각 라우터 **operation_id 와 이름 결합** (lockstep). 엔드포인트: `POST /agent` (네이티브 SSE, `enabled_mcps` 로 MCP 게이팅) · `POST /agent/example-ai` (ai-chatbot 프론트 호환 newline-JSON SSE, `switch1-5`→enabled_mcps, 토큰 스트리밍). switch off = 그 MCP tool 미바인딩(요청별 `_build_graph`). 검색 근거 유무는 tool_calls trace 에서 결정론적 `grounding` 정직 라벨. **멀티턴은 공통 DB `ai_chat_history` 를 `(email, gid)` 로 조회**해 주입하고 매 턴 종료 시 insert 도 한다 (테이블 정의 소유는 frontend Prisma, checkpointer 없음 — `MULTI_AGENT_SQL_DB_*`). `--workers=1`
- `market-data-mcp-service` (:8004) / `disclosure-mcp-service` (:8005) / `news-mcp-service` (:8006) / `web-mcp-service` (:8007) / `doc-search-mcp-service` (:8008) — portfolio-mcp-service 와 동일 패턴의 도메인별 MCP 서버 (시세·지수·환율 market-data 5 tool · DART/EDGAR 공시·재무 6 tool · 금융 뉴스·감성 5 tool · Tavily 웹검색 1 tool · 사내 투자 리서치 지식 Milvus 하이브리드 검색 28 tool[14 분야 × topic/image]). 모든 MCP 는 기본 MOCK 금융 데이터 반환(API 키 없이 즉시 기동), 실데이터는 env 토글(`USE_REAL_API`). DB·LLM 없음 (doc-search 만 Milvus/Redis store)
- `template-mcp-service` (:8009, 템플릿) — 신규 MCP 서비스 개발 **템플릿** (도메인 중립 echo tool 1개 — 입력을 그대로 반환, 외부 의존 0이라 복사 후 바로 기동·동작). 개발 가이드가 주석(`[가이드 N/10]`)으로 내장. 새 MCP 서비스는 이 폴더를 복사해 echo 를 실제 tool 로 교체(README 체크리스트). process-compose 미등록 (단독 기동 전용). 절차 문서: [`.docs/2-개발가이드/fastmcp-서버개발.md`](.docs/2-개발가이드/fastmcp-서버개발.md)
- `single-agent-service` (:8010, 교본) — 신규 **에이전트 서비스** 개발 교본 (single-agent). LangGraph `create_agent`(프리빌트 ReAct)가 web-mcp 의 Tavily 웹검색 tool 을 소비하며 단순 네이티브 SSE(`step`/`token`/`[DONE]`)로 스트리밍. MCP 소비 에이전트 교본 (tool 적은 단일서버는 ReAct 가 적합 — bind_tools 가 도구 선택을 구조적으로 보장, multi-agent 의 writer 파이프라인은 tool 많은 다중서버용). DB·멀티턴 없음, process-compose 미등록 (단독 기동 전용). multi-agent(Plan-Execute)로의 졸업 경로는 README·주석이 안내. 도메인 추가 교본: `multi-agent-service/app/agents/domains/example.py`(dormant) + 절차 문서 [`.docs/guides/multi-agent-development.md`](.docs/guides/multi-agent-development.md)
- `frontend` (:3010) — Next.js UI (로컬 포트 SoT 는 `process-compose.yaml` 의 frontend `PORT` — 3000 은 다른 프로젝트와 겹친다)

서비스별 상세 (레이어/훅/컴포넌트/유틸 + anti-pattern 체크리스트):

- Frontend: [`frontend/CLAUDE.md`](frontend/CLAUDE.md) (모든 서비스 동일)
- Backend: 각 backend 폴더 (`app/main.py` 가 있는 모든 폴더) 의 `CLAUDE.md`. 마커(`<!-- 여기부터 끝까지는 … -->`) 아래 **공통부는 전 서비스 byte-identical** — 정본은 [`backend-service/CLAUDE.md`](backend-service/CLAUDE.md), CI 잡 `test: repo-contracts` ([`scripts/verify_backend_claude_md.py`](scripts/verify_backend_claude_md.py)) 가 대조한다. 규율을 바꾸면 전 서비스에 같은 내용을 반영해야 하고, 서비스 고유 맥락은 마커 위 `> **이 서비스**:` 블록에만 둔다

작업 중 코드 패턴 / 위반 회피 상세는 [`.claude/docs/`](.claude/docs/):

- [`design-patterns-backend.md`](.claude/docs/design-patterns-backend.md) / [`design-patterns-frontend.md`](.claude/docs/design-patterns-frontend.md) — 신규 CRUD 스캐폴드 코드 패턴 (1:1 / 1:N)
- [`anti-patterns-backend.md`](.claude/docs/anti-patterns-backend.md) / [`anti-patterns-frontend.md`](.claude/docs/anti-patterns-frontend.md) — 룰별 예시/룰/Detection grep/예외 — review 에이전트 SoT
- [`.claude/agents/`](.claude/agents/) — `review-backend`/`review-frontend` (슬래시 `/review-*` 전용) · `scaffold-backend`/`scaffold-frontend` (자연어 호출: "X 만들어줘"). review=슬래시 전용 / scaffold=자연어 전용 (의도적 분리)

---

## 데이터 흐름 패턴 (새 기능 추가 시 택1)

**Backend 프록시** — 신규 비즈니스 엔티티 default.

```
Client → services/ → app/api/external/ → withAuth → proxyApiRequest() → Backend(FastAPI) → raw SQL → PostgreSQL
```

**Prisma 직접** — 기존 시스템관리(메뉴, 권한, 코드, 사용자, 이메일로그) + 회원가입 + 마이페이지에 한정. 신규 엔티티는 사용 안 함.

```
Client → services/ → app/api/common/ → withAuth → Prisma → PostgreSQL
```

---

## 네이밍 규칙

|           | Backend (Python) | Frontend (TypeScript)                             |
| --------- | ---------------- | ------------------------------------------------- |
| 파일      | `snake_case.py`  | 컴포넌트 `PascalCase.tsx`, 훅/유틸 `camelCase.ts` |
| 클래스    | `PascalCase`     | `PascalCase`                                      |
| 함수/변수 | `snake_case`     | `camelCase`                                       |

- Prisma 테이블 접두사: `TN_`(일반), `TC_`(코드), `BA_`(인증)
- 공통 감사 컬럼: `reg_dt`, `reg_id`, `mod_dt`, `mod_id`
- 라우트 경로: backend `APIRouter(prefix=...)` 는 **kebab-case REST 리소스** (`/chat-session`; 프로세스·RPC 는 `/domain/sub`+동사 허용), frontend proxy (`app/api/external/{service}/{prefix}/` → `{SERVICE}_SERVICE_URL + "/{prefix}"`) 가 prefix 를 **byte-identical** 복제 — backend 가 SoT, 경로 변경 시 frontend lockstep. 상세 [`design-patterns-backend.md`](.claude/docs/design-patterns-backend.md) "라우트 (REST) 컨벤션"
- lint/format 은 `pre-commit` 이 일괄 처리 (개별 ruff/eslint 명령 불필요)

---

## 인증 — Better Auth (NextAuth 아님), 멀티테넌트

Frontend `lib/auth/`: `auth.ts` (서버), `auth-client.ts` (`signIn/signOut/signUp/useSession`), `withAuth.ts` (API Route 보호 — 세션 검증 후 `session.accessToken` 전달). 미들웨어 `frontend/proxy.ts` 의 경로별 규칙. Backend `core/security.py` 의 `verify_access_token` (JWT HS256).

- 권한 3종: `admin`(시스템관리자·글로벌) / `operator`(운영자·자기 워크스페이스) / `user`(일반). `frontend/constants/protected.ts` 의 `SYS_ADMIN_AUTHOR_ID`/`GENERAL_ADMIN_AUTHOR_ID`/`DEFAULT_USER_AUTHOR_ID`.
- JWT payload = `{sub: user.id, email, role: authorId, workspace_id}`. frontend `auth.ts` 의 `definePayload`/`getSubject` 가 발급, backend 가 동일 키로 읽어 `core/auth_context.py` ContextVar 에 박음. **`JWT_SECRET` 은 frontend·backend 동일값 필수**.

---

## 명령어

```bash
# 전체 lint/format (Backend ruff + Frontend ESLint+Prettier 일괄)
pre-commit run --all

# Frontend
npm run dev
npm run dev:prisma:push        # 스키마 → DB
npm test                       # 순수 유틸 단위 테스트 (vitest, 0건이면 실패)

# Backend (cwd=app 필수 — config/import 가 app 디렉토리 기준, APP_ENV=development 필수 — 없으면 .env.production 을 읽음)
cd <backend>/app && APP_ENV=development uv run uvicorn main:app --reload

# dev 멀티서비스 일괄 기동 (각 backend working_dir=<svc>/app + APP_ENV=development 주입, 통합 앱 :8000)
process-compose up        # staging+ 는 docker-compose (compose.staging.yaml + 환경별 prod compose)
```

---

## 주석 규칙

- 변경 이유·이력 설명 주석 금지 ("~를 위해 수정", "기존 X 를 Y 로 변경", "~ 때문에 추가") — 그건 커밋 메시지/PR 설명의 몫
- 내레이션 주석 금지 ("여기서 ~를 처리합니다", "위 함수와 동일")
- 주석은 코드만으로 드러나지 않는 제약·의도가 있을 때만, 깔끔한 한 줄로

---

## 작업 보고 규칙 (커밋·PR·문서)

- 커밋 메시지·PR 본문·문서에 `$ 명령` 과 그 출력을 함께 적을 때는, **그 명령을 그대로 실행해서 나온 출력만** 적는다.
- 여러 단계를 거쳐 얻은 결과를 단일 명령의 출력인 것처럼 표기하지 않는다.
- 가공·요약한 결과는 명령 출력 블록(```)이 아니라 산문으로 적는다.
- 이유: 재현 불가능한 "검증 결과"는 검증이 아니다. 읽는 사람이 그 명령을 쳤을 때 같은 결과가 나와야 한다. 그렇지 않으면 리뷰어가 주장을 그냥 믿는 습관을 갖게 된다.

---

## 코드 읽기 규칙 (에이전트)

- 사람의 로컬 체크아웃(이 저장소의 작업 트리)에 있는 파일을 main 의 현재 상태라고 가정하지 않는다 — 작업 트리는 자동으로 갱신되지 않아 origin 보다 뒤처져 있을 수 있다.
- main 기준 판단·대조가 필요하면 `git fetch` 후 `git show origin/main:<경로>` 로 읽거나, origin/main 을 base 로 만든 전용 워크트리에서 읽는다. (`git fetch` 는 원격 참조만 갱신하므로 안전하다)
- 사람의 작업 트리를 `pull`·`checkout` 등으로 임의 갱신하지 않는다 — 작업 중 상태는 사람의 것이다.
- 이유: 낡은 체크아웃(origin 대비 11 커밋 뒤)의 ci.yml 을 읽고 틀린 결론을 낼 뻔한 실사례가 있다. 에이전트가 읽는 코드의 기준 리비전은 항상 명시적이어야 한다.

---

## 브랜치 정리 규칙 (스택 PR — #330)

- **PR 이 머지되면 그 head 브랜치는 즉시 삭제한다.** 스택 PR(브랜치 위에 브랜치를 쌓아 작업)에서
  머지된 브랜치를 살려 두면, 그 뒤 그 브랜치에 커밋이 더 착륙해도 다시 올라갈 자리가 없어
  **조용히 고립**된다 — squash 머지라 `git log main..branch` 로는 못 가린다(실측: #261 이 이렇게
  사라졌었다). 착륙할 자리를 없애는 것이 가장 싸고 확실한 예방이다.
- 구현은 레포 설정 **"Automatically delete head branches"**(Settings → General → Pull Requests)
  다 — PR 머지 시 GitHub 가 그 head 브랜치만 지운다(스택의 부모 브랜치가 나중에 머지될 때도 같은
  규칙이 다시 적용돼 체인이 순차적으로 정리된다). **이 레포에서는 켜져 있다** — 이사 때 다시
  적용했다(`gh api repos/Danwoo/trading-lab --jq .delete_branch_on_merge` → `true`).
- 사후 그물(이미 벌어진 고립을 잡는 것)은 `scripts/detect_orphaned_merged_branches.py` +
  `.github/workflows/orphaned-branch-scan.yml`(주기 스캔) 이 맡는다. **오탐이 있어 자동 차단은
  하지 않는다** — 후보만 뽑아 워크플로 요약 + 이슈 코멘트로 사람에게 낸다.

---

## 병렬 작업 격리 규칙 (에이전트 — #351)

- **워커는 `git worktree` 가 아니라 별도 `git clone` 에서 일한다.** 워크트리는 워킹트리만 나누고
  `.git` 의 상당 부분을 **공유**한다 — 그래서 저장소 단위 상태가 워커끼리 섞인다:
  - **`refs/stash`** — 한 워커의 `git stash pop` 이 다른 워커의 WIP 를 소비했다(양쪽 끝에서
    각각 관측, 2회). 팝은 조용히 성공하고 팝된 게 남의 것인지 알려주지 않는다.
  - **`.git/shallow`** — 한 워커의 fetch 가 다른 워커의 병합을 `refusing to merge unrelated
    histories` 로 깨뜨렸다.
- **`git stash` 를 쓰지 않는다.** 부정 통제(변경을 잠깐 빼고 확인)는 파일로 남는 방식으로 한다:
  `git diff > /tmp/x.patch` → `git apply -R /tmp/x.patch` → 확인 → `git apply /tmp/x.patch`.
  스태시와 달리 팝으로 사라지지 않고, 무엇이 빠졌는지 파일로 확인된다.
- **`--force`·history 재작성·`git stash`·워크트리 공유 `.git` 조작을 남의 작업 중에 하지 않는다.**
  `fetch --unshallow`·`gc`·`prune` 은 공유 `.git` 을 건드리므로 별도 클론에서만 안전하다.
- 참고 — **pre-commit 훅은 `git stash` 를 쓰지 않는다.** unstaged 변경을 뺄 때
  `~/.cache/pre-commit/patch<타임스탬프>-<pid>` 로 패치 파일을 쓰고 `git checkout -- .` +
  `git apply` 로 되돌린다(`pre_commit/staged_files_only.py`, 4.6.0 확인). 로그 문구가
  "Stashing unstaged files to …" 라 스태시로 오인하기 쉬우나 `refs/stash` 는 건드리지 않는다.
  즉 커밋 자체가 공유 스택을 오염시키지는 않는다 — 그래도 **클론 격리가 기본**인 이유는 위
  두 공유 상태(`refs/stash` 직접 사용·`.git/shallow`)가 그대로 남기 때문이다.
- **로컬 클론은 싸다** — 같은 파일시스템이면 오브젝트를 하드링크하므로 실디스크 증가가 거의 없다.
  단, 클론의 `origin` 은 로컬 경로를 가리키니 **GitHub URL 로 바꾼 뒤** push 한다.

---

## 현재 베팅

<!-- 매 세션 재주입층 — 베팅 교체 시 갱신 -->

M2 터미널 골조: 리드가 직접 기동→로그인→터미널 진입→종목 선택→패널 전체 전환→배치 변경 후 새로고침 유지→적재 실행→차트가 실데이터로 그려지는 것까지 확인하면 완료.
no-go: 실주문·호스팅 SaaS 운영·봇 실행 엔진·백테스트·AI 콘솔·스크리너·에이전트 답변 품질. 범위와 진행 상태의 원본은 [마일스톤 2](https://github.com/Danwoo/trading-lab/milestone/2) 다.

---

## 이슈 번호 표기

<!-- 2026-08-07 완전 이사 — 옛 번호가 문서·주석에 그대로 남아 있다 -->

문서·주석의 `#N` 은 **기본적으로 옛 비공개 레포(`Danwoo/fintech-ai-platform`) 번호**이며 이 레포에서 열리지 않는다. **자릿수로는 못 가른다** — `#8`·`#85`·`#360` 이 전부 옛 번호다. 이사 때 살아 있던 3건만 새 번호를 받았고(`#1` RAG 후속 하드닝 · `#2` M2 시세 적재 · `#3` 탈퇴자 PII), 닫힌 229건은 보관용 레포에 남아 그 밖의 대조표는 없다. 앞으로 이 레포 이슈를 인용할 때는 번호만 적지 말고 링크를 걸어 옛 번호와 섞이지 않게 한다.
