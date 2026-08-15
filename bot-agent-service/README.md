# bot-agent-service (:8011)

**봇 만들기 대화.** 사용자의 말을 봇 설정으로 옮긴다 — [`#150`](https://github.com/Danwoo/trading-lab/issues/150) B2.

**로컬 배포 모드 전용**이다. 호스팅에서는 이 서비스를 **띄우지 않는다** (결정 2026-07-28 — 셸 권한이 테넌트 격리를 무력화한다).

## 기동

```bash
cd bot-agent-service/app && APP_ENV=development uv run uvicorn main:app --reload --port 8011
```

`ANTHROPIC_API_KEY` 는 **프로세스 환경변수**로 온다. SDK 는 `.env` 를 자동으로 읽지 않으므로 `.env.development` 에 넣고 기동 스크립트가 주입하거나, 셸에서 export 한다.

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
| 제거 | `Bash` · `Write` · `Edit` · `NotebookEdit` · `WebSearch` · `WebFetch` · `Task` (bare name 이라 도구 정의가 요청에서 빠진다) |
| 권한 모드 | `dontAsk` — 미승인은 프롬프트가 아니라 **거부** |
| 설정 소스 | 없음 — `~/.claude`·레포 `.claude/` 를 안 읽는다 |
| 작업 디렉터리 | `strategies/` |
| 턴 상한 | `AGENT_MAX_TURNS` (기본 12) |

전략 **파일 생성**(봇-전략-모델 §6)은 백테스트에 물려 있어 다음 베팅이다. 그때 `Write`·`Edit` 를 자동승인으로 옮기고, 전략 디렉터리 밖 쓰기를 절대경로 deny 규칙(`Edit(//경로/**)` — 슬래시 **둘**)로 막는다.

## 검증

```bash
uv run python tests/test_agent_boundary.py     # 도구 경계 21건
uv run ruff check app/
```

**대화 한 턴의 실제 왕복은 키가 있어야 검증된다** — 그 전까지 이 서비스가 증명하는 것은 「키가 없을 때 이유와 함께 멈춘다」까지다.
