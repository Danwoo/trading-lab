# bot-agent-service (:8011)

**봇 만들기 대화.** 사용자의 말을 봇 설정으로 옮긴다 — [`#150`](https://github.com/Danwoo/trading-lab/issues/150) B2.

**로컬 배포 모드 전용**이다. 호스팅에서는 이 서비스를 **띄우지 않는다** (결정 2026-07-28 — 셸 권한이 테넌트 격리를 무력화한다).

## 기동

```bash
cd bot-agent-service/app && APP_ENV=development uv run uvicorn main:app --reload --port 8011
```

`ANTHROPIC_API_KEY` 는 **프로세스 환경변수**로 온다. SDK 는 `.env` 를 자동으로 읽지 않으므로 `.env.development` 에 넣고 기동 스크립트가 주입하거나, 셸에서 export 한다. `build_options` 가 이 값을 `env` 로 자식 프로세스에 명시해 넘긴다.

### 인증 경계 — 키 설정만으로 다른 경로가 닫히지는 않는다

기계에 Claude Code 로그인(`~/.claude/.credentials.json`)이 있으면 CLI 가 **그 자격증명으로 인증할 수 있다.** SDK 는 `options.env` 를 부모 환경 **위에 병합**할 뿐 격리하지 않아 `HOME` 이 그대로 상속되고, 그래서 그 파일이 계속 보이는 자리에 있다 — 여기까지는 SDK 소스(`subprocess_cli.py` 의 `inherited_env`)로 확인한 사실이다.

**확인하지 않은 것**: 키를 `env` 로 명시해 넘기는 지금 상태에서 CLI 가 (a) 유효한 키를 실제로 쓰는지, (b) 무효한 키일 때 정말 OAuth 로 넘어가는지. 가짜 키로 대화가 왕복한 관측은 **이 배선이 없던 시점**의 것이라 조건이 다르다. 다시 재려면 소유자의 실제 자격증명을 소모해야 해서 하지 않았다.

따라서 `readiness()` 의 `ready` 는 **「키가 설정돼 있다」이지 「그 키로 인증한다」가 아니다.** 이 서비스를 로컬 배포 모드에서만 띄우는 결정이 그 잔여 위험의 실질적 경계다 — 호스팅에서 띄우면 로그인한 누구든 기계 소유자의 자격증명을 소모시킬 수 있다.

## 엔드포인트

| 메서드 | 경로 | 하는 일 |
|---|---|---|
| `GET` | `/bot-agent/readiness` | 대화를 걸 수 있는가. 아니면 **이유**를 함께 준다 |
| `POST` | `/bot-agent` | 대화 한 턴을 SSE 로 (`text`·`tool`·`result`·`unavailable`·`error` + `[DONE]`) |

키가 없으면 조용히 빈 응답을 흘리지 않고 `{"type":"unavailable","reasons":[...]}` 를 한 번 낸다 — 「대화가 안 붙었다」와 「모델이 할 말이 없다」는 다르다.

## 에이전트가 할 수 있는 것

정본은 [`app/agents/bot_agent.py`](app/agents/bot_agent.py) 이고, 같은 내용을 [`tests/test_agent_boundary.py`](tests/test_agent_boundary.py) 가 실행되는 단언으로 한 번 더 잡는다.

| | 지금 |
|---|---|
| 자동승인 | `Read` · `Glob` · `Grep` — 전략 파일을 **읽는** 것까지 |
| 경로 스코프 | PreToolUse 훅([`app/agents/tool_scope.py`](app/agents/tool_scope.py))이 위 셋의 경로 인자를 검사해 **전략 디렉터리 밖이면 거부**한다 |
| 제거 | `Bash` · `Write` · `Edit` · `NotebookEdit` · `WebSearch` · `WebFetch` · `Task` (bare name 이라 도구 정의가 요청에서 빠진다) |
| 권한 모드 | `dontAsk` — 미승인은 프롬프트가 아니라 **거부** |
| 설정 소스 | 없음 — `~/.claude`·레포 `.claude/` 를 안 읽는다 |
| 작업 디렉터리 | `strategies/` — 상대경로의 기준점이자 위 스코프의 뿌리다 |
| 턴 상한 | `AGENT_MAX_TURNS` (기본 12) |

> **`cwd` 는 접근 범위를 좁히지 않는다.** `allowed_tools` 에 bare name 으로 적은 허용은 경로와 무관한 전체 자동승인이라, `cwd` 만 걸어 두면 절대경로나 `..` 로 밖을 읽을 수 있다 (SDK 자신이 *"Filesystem read restrictions: Use Read deny rules"* 라고 적는다). 그래서 훅이 실제 통제 수단이고, 권한 평가 순서(훅 → deny → ask → 권한 모드 → allow → `can_use_tool`)에서 훅이 맨 앞이라 자동승인보다 먼저 판정된다. 자동승인된 도구는 `can_use_tool` 콜백에 아예 오지 않으므로 그 자리로는 못 막는다. — PR #154 독립 리뷰가 잡은 결함.

전략 **파일 생성**(봇-전략-모델 §6)은 백테스트에 물려 있어 다음 베팅이다. 그때 `Write`·`Edit` 를 자동승인으로 옮기고, 전략 디렉터리 밖 쓰기를 절대경로 deny 규칙(`Edit(//경로/**)` — 슬래시 **둘**)로 막는다.

## 검증

```bash
uv run python tests/test_agent_boundary.py     # 도구 경계 23건 (정적 구성)
uv run python tests/test_tool_scope.py         # 경로 스코프 6건 — 탈출 시도 11개를 실제로 판정
uv run python tests/test_http_contract.py      # HTTP 경계 8건 — 빈 메시지 422 · 키 없을 때 사유 · 권한 게이트
uv run ruff check app/
```

**대화 한 턴의 실제 왕복은 키가 있어야 검증된다** — 그 전까지 이 서비스가 증명하는 것은 「키가 없을 때 이유와 함께 멈춘다」까지다.
