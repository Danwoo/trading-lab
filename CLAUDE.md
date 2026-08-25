# CLAUDE.md

## 구성

- **Frontend** (`frontend/`): Next.js 16 + TypeScript + Prisma + Better Auth + DevExtreme + Tailwind
- **Backend**: FastAPI + SQLAlchemy raw SQL + dependency-injector. 선택적이며 **여러 개 가능** — `app/main.py` 가 있는 모든 폴더가 backend (기본 `backend/`, 또는 `api/`/`server/`/도메인별 등). 없으면 frontend-only 구성. docs 의 `backend/` 참조는 실제 경로로 치환.
- **File 모듈** (`backend-service/app/{routers,services,repositories}/file/`): FastAPI + asyncssh (SFTP). 통합 앱 안의 한 모듈이며, 다른 모듈은 `FileService` 를 DI 로 주입받아 호출한다 — `SftpClient`·`FileRepository` 직접 호출 금지 (anti-patterns 룰 14). (doc-search 의 직접 SFTP 이미지 파이프라인만 예외)
- **Platform** (`platform/`): nginx, sftp 인프라
- **DB**: PostgreSQL 단일 `fintech`. 소유를 스키마로 가른다 — `public` 은 통합 앱 alembic(이력), `frontend` 는 Prisma push. 런타임 raw SQL

## 이 repo 서비스

**로그인해서 쓰는 개인 투자 지휘소** (결정 로그 2026-07-28). 나란한 두 기둥이 시간축으로 갈린다 —
**실험대**(트레이딩 봇을 만들고 검증하고 굴린다. 장중, 결정론적, LLM 0회) / **리서치**(질문 → 근거 붙은 답. 저녁 배치, LLM).
멀티테넌시는 제거하지 않고 **개인 워크스페이스**로 재해석한다(전략별 격리·읽기전용 게스트 초대·봇 신원·레이아웃 저장).
시스템관리(워크스페이스/메뉴/사용자/권한/코드)는 제품 메뉴에서 빼 관리자 경로(`/admin`)에 둔다.

> 스타터 템플릿 성격(신규 엔티티 스캐폴드·MCP 서비스 템플릿)은 **유지**하되, 그게 제품 정체성은 아니다.

- `backend-service` (:8000) — **통합 앱**. 비즈니스 API 를 모듈(도메인 폴더)로 담는다 — `app/modules.py` 에 등록된 **15개가 전부**다: `watchlist` · `portfolio`(보유종목 마스터-디테일) · `nav`(시계열 대시보드) · `research_document` · `file`(업로드/다운로드 + SFTP + 파일 메타) · `chat`·`scheduler`(주간 활동요약 메일 스케줄러 + 포트폴리오 활동 조회 챗) · `ingest`(시세/체결 틱 메시지 큐 producer/consumer) · `bar`(적재본 캔들 조회) · `quote`(일괄 시세) · `capability`(소스별 「무엇이 왜 막혔나」) · `data_key`(소스 키 상태 — 읽기 전용, 값은 안 낸다) · **`bot`**(봇 정의 CRUD) · **`backtest`**(격자 실행·칸 조회) · **`instrument`**(종목 마스터 검색 — 「없다」와 「아직 안 받았다」를 가른다). 라우터·매니저 등록은 `app/modules.py` 한 곳. 백그라운드 매니저 3종이 앱 안에서 돌아 `--workers=1`. 신규 엔티티 스캐폴드 템플릿
- `portfolio-mcp-service` (:8002) — 계좌/포트폴리오 데이터 전용 MCP 서버 (FastMCP `from_fastapi` 가 REST 라우터를 `/mcp` MCP tool 로 노출 — 같은 앱이 REST 도 그대로 서빙, DB·LLM 없음). 포트폴리오 데이터 접근 단일 소유 — 타 서비스는 직접 호출 금지, **MCP tool 로만** 접근 (에이전트=`MultiServerMCPClient`, 단발 조회·목록 위젯=`PortfolioMcpClient`). 서비스 간 호출은 `create_access_token` 서비스 토큰
- `multi-agent-service` (:8003) — MCP **소비자** (순수 FastAPI, MCP 서버 아님). 투자 리서치 도메인 Plan-Execute 멀티 에이전트 (4 도메인 · 총 12 sub-agent StateGraph — 종목·시세/재무·공시/리스크·밸류/시장·뉴스·매크로) 가 아래 6개 MCP 서버 tool 을 `MultiServerMCPClient`+`ServiceJwtAuth` 로 오케스트레이션. sub-agent ↔ tool 은 `agents/domains/*` 의 `mcp_tools` 가 각 라우터 **operation_id 와 이름 결합** (lockstep). 엔드포인트: `POST /agent` (네이티브 SSE, `enabled_mcps` 로 MCP 게이팅) · `POST /agent/example-ai` (ai-chatbot 프론트 호환 newline-JSON SSE, `switch1-5`→enabled_mcps, 토큰 스트리밍). switch off = 그 MCP tool 미바인딩(요청별 `_build_graph`). 검색 근거 유무는 tool_calls trace 에서 결정론적 `grounding` 정직 라벨. **멀티턴은 공통 DB `ai_chat_history` 를 `(email, gid)` 로 조회**해 주입하고 매 턴 종료 시 insert 도 한다 (테이블 정의 소유는 frontend Prisma, checkpointer 없음 — `MULTI_AGENT_SQL_DB_*`). `--workers=1`
- `market-data-mcp-service` (:8004) / `disclosure-mcp-service` (:8005) / `news-mcp-service` (:8006) / `web-mcp-service` (:8007) / `doc-search-mcp-service` (:8008) — portfolio-mcp-service 와 동일 패턴의 도메인별 MCP 서버 (시세·지수·환율 market-data 5 tool · DART/EDGAR 공시·재무 6 tool · 금융 뉴스·감성 5 tool · Tavily 웹검색 1 tool · 사내 투자 리서치 지식 Milvus 하이브리드 검색 28 tool[14 분야 × topic/image]). 모든 MCP 는 기본 MOCK 금융 데이터 반환(API 키 없이 즉시 기동), 실데이터는 env 토글(`USE_REAL_API`). DB·LLM 없음 (doc-search 만 Milvus/Redis store)
- `template-mcp-service` (:8009, 템플릿) — 신규 MCP 서비스 개발 **템플릿** (도메인 중립 echo tool 1개 — 입력을 그대로 반환, 외부 의존 0이라 복사 후 바로 기동·동작). 개발 가이드가 주석(`[가이드 N/10]`)으로 내장. 새 MCP 서비스는 이 폴더를 복사해 echo 를 실제 tool 로 교체(README 체크리스트). process-compose 미등록 (단독 기동 전용). 절차 문서: [`.docs/2-개발가이드/fastmcp-서버개발.md`](.docs/2-개발가이드/fastmcp-서버개발.md)
- `bot-agent-service` (:8011) — **봇 만들기 대화**. Claude Agent SDK(`claude-agent-sdk`)를 임베드해 사용자의 말을 봇 설정으로 옮긴다. **로컬 배포 모드 전용** — 호스팅에서는 안 띄운다(셸 권한이 테넌트 격리를 무력화, 결정 2026-07-28). 이 레포에서 **유일하게 Anthropic 경로**(`ANTHROPIC_API_KEY`)를 쓴다 — 나머지는 OpenAI 호환 `LLM_BASE_URL` (결정 2026-08-15 ㉮). 에이전트가 무엇을 할 수 있는지는 `app/agents/bot_agent.py` 가 정본이고 `tests/test_agent_boundary.py` 가 같은 내용을 단언으로 잡는다. DB 없음, **process-compose 미등록 — 손으로 띄운다**(`bot-agent-service/README.md` 의 기동 명령). 프론트는 이미 부른다(`frontend/app/api/external/bot-agent/**` 프록시 2개 + `components/features/Bot/BotConversation.tsx`), 그래서 `process-compose up` 만 한 상태에서는 봇 대화가 「안 떠 있음」으로 보인다
- `single-agent-service` (:8010, 교본) — 신규 **에이전트 서비스** 개발 교본 (single-agent). LangGraph `create_agent`(프리빌트 ReAct)가 web-mcp 의 Tavily 웹검색 tool 을 소비하며 단순 네이티브 SSE(`step`/`token`/`[DONE]`)로 스트리밍. MCP 소비 에이전트 교본 (tool 적은 단일서버는 ReAct 가 적합 — bind_tools 가 도구 선택을 구조적으로 보장, multi-agent 의 writer 파이프라인은 tool 많은 다중서버용). DB·멀티턴 없음, process-compose 미등록 (단독 기동 전용). multi-agent(Plan-Execute)로의 졸업 경로는 README·주석이 안내. 도메인 추가 교본: `multi-agent-service/app/agents/domains/example.py`(dormant) + 절차 문서 [`.docs/guides/multi-agent-development.md`](.docs/guides/multi-agent-development.md)
- `frontend` (:3010) — Next.js UI (로컬 포트 SoT 는 `process-compose.yaml` 의 frontend `PORT` — 3000 은 다른 프로젝트와 겹친다)

서비스별 상세 (레이어/훅/컴포넌트/유틸 + anti-pattern 체크리스트):

- Frontend: [`frontend/CLAUDE.md`](frontend/CLAUDE.md) (모든 서비스 동일)
- Backend: 각 backend 폴더 (`app/main.py` 가 있는 모든 폴더) 의 `CLAUDE.md`. 마커(`<!-- 여기부터 끝까지는 … -->`) 아래 **공통부는 전 서비스 byte-identical** — 정본은 [`backend-service/CLAUDE.md`](backend-service/CLAUDE.md), CI 잡 `test: backend` ([`scripts/verify_backend_claude_md.py`](scripts/verify_backend_claude_md.py)) 가 대조한다. 규율을 바꾸면 전 서비스에 같은 내용을 반영해야 하고, 서비스 고유 맥락은 마커 위 `> **이 서비스**:` 블록에만 둔다

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

- 권한 3종: `admin`(시스템관리자·글로벌) / `operator`(운영자·자기 워크스페이스, **개인 워크스페이스를 받은 회원가입이 배정한다** — 리드 결정 2026-08-23) / `user`(초대받은 읽기전용 게스트 — `require_role` 이 걸린 쓰기 라우트가 전부 403. **이메일 도메인 매핑으로 남의 공용 워크스페이스에 들어간 가입도 여기다** — 결정 보완 2026-08-24). `frontend/constants/protected.ts` 의 `SYS_ADMIN_AUTHOR_ID`/`GENERAL_ADMIN_AUTHOR_ID`/`GUEST_AUTHOR_ID`, 가입 배정은 `SIGNUP_AUTHOR_ID`.
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

## 목표층 문서 변경 — 통행료를 걷지 않는다

**대상은 셋뿐이다**: `CONTEXT.md` · 루트 `CLAUDE.md` · GitHub 마일스톤 description. 목표·베팅·결정 로그가 사는 자리이고, **결정은 리드가 이미 내린 뒤** 그것을 받아적는 작업이다. 깨질 코드가 없고 리뷰어가 결정한 사람 자신이라, 코드용 절차를 그대로 씌우면 비용만 남는다.

| 항목 | 코드 변경 | **목표층 문서 변경** |
|---|---|---|
| 브랜치 | `fix-<이슈>-<에이전트>` | `goal-<주제>`(사람) · `goal-<주제>-<에이전트>`(에이전트) |
| PR 본문 | 템플릿 전 절 | **3줄** — 무엇을·왜·무엇으로 확인했나 |
| `gate declare` | 한다 | **안 한다** |
| 독립 리뷰 | 기다린다 | **안 기다린다** — 바로 머지 |
| CI | 기다린다 | 기다린다 (문서 전용 PR 은 22초·8종 skipped — 실측) |

**면제는 fail-closed 다.** 위 셋 **밖의 파일이 하나라도 섞이면 면제가 통째로 사라지고** 보통 코드 PR 규칙을 따른다. "문서도 같이 고쳤으니 문서 취급"이 아니라 **"문서만 고쳤을 때만"** 이다.

> **왜 PR 을 아예 없애지 않았나** — main 은 ruleset `main protection` 의 `pull_request` 규칙으로 보호돼 있고 `bypass_actors` 가 비어 있다. 그리고 에이전트가 리드와 **같은 GitHub 계정으로 push** 하므로, 리드에게 여는 문은 에이전트에게도 똑같이 열린다. 그래서 서버 규칙은 그대로 두고 그 위에 쌓인 절차만 걷어냈다. 실측상 마찰의 대부분이 거기 있었다 (2026-08-09).
>
> **이 규칙에 검사 스크립트를 붙이지 않는다.** 「표식을 늘리는 것은 방어가 아니다」(교훈) — 규약 하나에 CI 잡을 하나씩 붙이는 습관이 이 레포에서 이미 값을 치렀다. 이건 지키는 사람이 읽는 규약이지 기계가 잡을 것이 아니다.

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

## 쓸어담기 — 조용히 죽은 리뷰·머지를 줍는다 (에이전트)

리뷰·판정 게시·라벨·승인·자동 머지 arm 이 **한 self-hosted 잡**의 스텝이라, 그 잡이 통째로
죽으면(러너 동결·취소·큐 사망) 아무것도 안 남는다. 종전에 그 자리를 받던 두 장치
(GitHub-hosted `review: publish` 폴백 · `runner-freeze-rerun.yml`)는 없앴다 — private 에서
과금의 몸통이 되기 때문이다. **대신 에이전트가 주기적으로 훑는다.**

```bash
python3 scripts/review_sweep.py collect | python3 scripts/review_sweep.py plan
```

- **처분을 내놓을 뿐 실행하지 않는다.** `rerun` 이면 `gh run rerun <run_id> --failed`,
  `relabel`·`rearm` 은 그 PR 에서 손으로(또는 에이전트가) 한다.
- **주기는 10~15분**이면 충분하다 — 리뷰 중앙 실행시간이 약 9분이다.
- **동결 판정은 잡 단위 annotation 으로 한다.** run conclusion 으로 하면 놓친다 —
  옛 워크플로가 그렇게 죽어 있었다(12일간 365번 깨어나 재실행 0건, 진짜 동결 4건 전부 놓침).
- 판정부를 부를 때는 **`git show origin/main:scripts/review_sweep.py`** 로 꺼내 쓴다.
  PR 워크트리의 판본을 쓰면 PR 이 자기 처분을 고칠 수 있다.

---

## PR 은 draft 로 연다 (에이전트·사람 공통)

**PR 을 열 때는 draft 로 열고, 스스로 확인한 뒤 ready 로 바꾼다.** CI 의 `pull_request` 트리거가
`types: [ready_for_review, synchronize, reopened]` 라, **draft 인 동안의 push 는 CI 를 안 깨운다.**
ready 로 바꾸는 순간 전량이 한 번 돌고, 그 뒤 리뷰 지적을 반영하는 push 는 `synchronize` 라
종전대로 돈다.

- 왜: 「일단 올리고 CI 로 고친다」가 잡 17개 × 커밋 수만큼 청구된다. draft 구간에서 로컬
  게이트(`pre-commit run --all` · 관련 `verify_*.py`)로 먼저 거르면 그 반복이 사라진다.
- **초안에서 CI 를 한 번 보고 싶으면** ready 로 바꿨다가 다시 draft 로 내리면 된다 —
  `ready_for_review` 가 그때 한 번 뜬다.
- 독립 리뷰(`cross-review`)도 draft 를 안 본다. 리뷰를 받을 준비가 됐다는 신호가 ready 다.

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

M2 터미널 골조: 리드가 직접 기동→로그인→**실험대(홈)가 열림**(봇 0개 첫 진입에서 빈 자리가 무엇이 올 자리인지 말한다)→46px 레일에서 패널을 열면 보드를 안 덮고 372px 로 옆에 붙음→레일의 「시세」에서 종목 선택→전 패널이 그 종목으로 전환→적재 실행→차트가 적재된 캔들로 그려지고 값이 소스와 일치→소스 없는 패널은 이유와 함께 빔→**대화로 봇 하나를 만들어 저장하고 그 조건이 폼에 그대로 보임**→`/admin` 은 MDI 탭으로 열림, 까지 확인하면 완료.
no-go: 실주문·호스팅 SaaS 운영·**봇 검증(백테스트 엔진·격자 실행)**·봇 실행 엔진(장중 신호 판정)·AI 콘솔·스크리너·에이전트 답변 품질. 범위와 진행 상태의 원본은 [마일스톤 2](https://github.com/Danwoo/trading-lab/milestone/2) 다.

**다음 베팅은 백테스트 엔진이다 (리드 결정 2026-08-18).** 목표는 「보드에 결과가 찬다」 — 자산·승률·손익비·MDD, 날짜별 손익, 드로다운 곡선, 캔들 위 매수·매도 마커. **M2 는 그대로 끝낸다** — 백테스트는 시세 적재(#2)에 물려 있는데 키가 아직 없어, 지금 넣으면 mock 위에 성과 화면을 짓게 된다. 그래서 **M2 완료 시점의 보드는 여전히 빈 채로 남는다.** 근거는 결정 로그 2026-08-18.

**봇 만들기가 M2 안에 있다 (리드 결정 2026-08-15).** 대화(Claude Code 임베드)가 폼을 채우고 봇이 저장되는 데까지다 — 정본은 [`.docs/specs/2026-08-08-experiment-bench-spec.md`](.docs/specs/2026-08-08-experiment-bench-spec.md) §8.6. **검증은 그다음이다**: 백테스트 엔진이 없으면 격자·곡선은 빈 채로 남고 그 빈 상태까지가 M2 다(§20.5·§21.4). 경계가 여기인 이유 — 시세 파이프라인 문서가 *"백테스트는 로컬 DB 에서 읽는다 … 그래서 적재가 먼저다"* 라고 못박아 **검증은 적재(#2)에 물려 있는데 봇을 만드는 것은 거기 안 물린다.**

**셸 개편과 디자인 시스템 적용이 M2 안에 있다.** 화면 작업은 2026-08-09 결정([`.docs/specs/2026-08-09-screen-db-decisions.md`](.docs/specs/2026-08-09-screen-db-decisions.md) §20~§25)과 [`.docs/4-아키텍처/디자인-시스템.md`](.docs/4-아키텍처/디자인-시스템.md)를 정본으로 삼는다 — 색·타이포·선·상태는 그 토큰만 쓰고, 새 화면을 기존 화면에서 복사해 만들지 않는다. 보드의 격자·곡선은 백테스트·봇 엔진 산출물이라 **빈 상태까지**가 M2 다(§20.5·§21.4).

---

## 이슈 번호 표기

<!-- 2026-08-07 완전 이사 — 옛 번호가 문서·주석에 그대로 남아 있다 -->

문서·주석의 `#N` 은 **기본적으로 옛 비공개 레포(`Danwoo/fintech-ai-platform`) 번호**이며 이 레포에서 열리지 않는다. **자릿수로는 못 가른다** — `#8`·`#85`·`#360` 이 전부 옛 번호다. 이사 때 살아 있던 3건만 새 번호를 받았고(`#1` RAG 후속 하드닝 · `#2` M2 시세 적재 · `#3` 탈퇴자 PII), 닫힌 229건은 보관용 레포에 남아 그 밖의 대조표는 없다. 앞으로 이 레포 이슈를 인용할 때는 번호만 적지 말고 링크를 걸어 옛 번호와 섞이지 않게 한다.
