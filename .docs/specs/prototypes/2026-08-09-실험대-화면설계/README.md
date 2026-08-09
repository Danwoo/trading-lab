# 실험대 화면 설계 시안 (2026-08-08 ~ 08-09)

브라우저로 파일을 직접 열면 됩니다 (의존성 없는 단일 HTML).
설계 결정과 근거는 [`../../2026-08-09-screen-db-decisions.md`](../../2026-08-09-screen-db-decisions.md) 에 있습니다.

> **주의 — 화면 안의 숫자는 전부 가짜입니다.**
> 낙폭 14.2% · 거래 131건 · 수익 몰림 88% · 모의 47일 등은 실측이 아니라 시안용으로 지어낸 값입니다.
> 백테스트 엔진이 아직 없어서 실제 값을 뽑을 수 없었습니다.
> **이 시안으로 판단할 수 있는 것은 「무엇을 어떤 순서로 보여줄 것인가」까지**이고,
> 숫자의 타당성은 실데이터가 생긴 뒤에 다시 봐야 합니다.
> (4차 검증에서 `유효 종목 3.5` 가 수학적으로 불가능한 값임이 드러난 것이 이 한계의 실례입니다.)

## 제품 화면 — 현재 안

| 파일 | 화면 | 상태 |
|---|---|---|
| [`home.html`](home.html) | 홈 — 자율 에이전트가 밤새 한 일을 아침에 보고 | 미검증 항목 있음 |
| [`board-live.html`](board-live.html) | 실험대 — 격자 클릭 → 곡선, 구간 브러시 → 재계산 | 인터랙션 동작 |
| [`bot-make.html`](bot-make.html) | 봇 만들기 — 3열 폼 | |
| [`bot-live.html`](bot-live.html) | 봇 검진 — 기간(단타/중장기)에 따라 화면이 적응 | |
| [`bot-run.html`](bot-run.html) | 모의 운용 일일 화면 | |
| [`bot-agent.html`](bot-agent.html) | 대화형 에이전트 (Claude Code 임베드) — 재생 가능한 시안 | |
| [`trades.html`](trades.html) | 거래 로그 + DB 설계 | 산수 오류 3건 미수정 (§17.7) |
| [`rules.html`](rules.html) | 내 기준 + DB 설계 | 4차 반영 완료 |
| [`golive.html`](golive.html) | 실전 전환 + DB 설계 | 4차 반영 완료 |
| [`screen-audit.html`](screen-audit.html) | 기존 23개 라우트 존치/폐기 판정 | 폐기분 삭제 완료 (`22e8cc9`) |

## 탐색 과정 — 참고용

**흐름·구조**: [`ia.html`](ia.html) (정보구조) · [`flow-bot.html`](flow-bot.html) · [`flow-daily.html`](flow-daily.html) · [`states.html`](states.html) (상태별 화면) · [`shell.html`](shell.html) (레이아웃 골격)

**디자인 언어**: [`palette.html`](palette.html) · [`tokens.html`](tokens.html) · [`typo.html`](typo.html) · [`derived.html`](derived.html) · [`neutral.html`](neutral.html) · [`accent.html`](accent.html) / [`accent-v2.html`](accent-v2.html) / [`what-is-accent.html`](what-is-accent.html) · [`mood-direction.html`](mood-direction.html) / [`mood-hybrid.html`](mood-hybrid.html) · [`final.html`](final.html)

**초기 시안 (대체됨)**: [`bench.html`](bench.html) · [`board.html`](board.html) (→ `board-live.html`) · [`market.html`](market.html) · [`terminal-p2.html`](terminal-p2.html)

## 검증 이력

손실 경험 트레이더 페르소나(2018 반대매매, 원금 4,200만 → 1,100만)로 4회 검증했습니다.
회차별 지적과 조치는 결정 문서 §15~§17 에 있습니다.

| 회차 | 판정 |
|---|---|
| 1차 | 계산 오류 6건 (수수료 10배 과소 · MDD 분모 · 연환산 · 매매 빈도) |
| 2차 | 실전 전환 「못 막았다」 — 금액 상한식이 순환해 해가 없음 |
| 3차 | 「막았다」 — 순환 해소. 단 「기다리면 늘어난다」 경로 잔존 |
| 4차 | 「사흘은요」 — 벽을 사흘 만에 우회. **벽을 걷어내는 결정으로 이어짐** (§17) |
