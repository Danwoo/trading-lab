# CI·리뷰 구조 재설계 구현 계획

> **에이전트 워커에게:** task 단위로 구현한다. 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** CI 파이프라인에서 「에이전트가 판단하는 일」을 걷어내고, 리뷰를 GitHub 네이티브 PR
리뷰로 옮긴다.

**설계 정본:** [`2026-08-08-ci-review-architecture-design.md`](2026-08-08-ci-review-architecture-design.md)
**후속 계획:** [`2026-08-08-agent-loop-automation-plan.md`](2026-08-08-agent-loop-automation-plan.md)

---

## 이 계획이 코드를 미리 쓰지 않는 이유

**초안은 각 task 에 완성형 코드를 넣었다가 두 라운드에 걸쳐 차단급 6건을 맞았다.**

| 라운드 | 차단급 |
| --- | --- |
| 1 | 리뷰어 배정 로직 3자리 오역 · `frontend-ci` 경로 필터 5개 누락 |
| 2 | 마커 코멘트 **저자 필터 누락**(공개 레포 위조 경로) · sha 접두사 매치 · 스윕 삭제 단계 없음 · 완료 수치 모순 |

전부 **계획 저자가 `cross-review.yml` 2,020줄을 줄 단위로 읽지 않은 채 그 대체 코드를 쓴 결과**다.
잘못 옮긴 자리마다 테스트를 같이 써서 **틀린 동작이 초록으로 굳었다** — 자기 일관성만 확인한 것이다.

**그래서 이 계획은 코드를 주지 않는다.** 대신 task 마다 셋을 준다:

1. **읽어야 할 자리** — 현행 코드의 정확한 위치. 여기부터 읽지 않고 시작하지 마라
2. **지켜야 할 불변식** — 깨지면 안 되는 것과 그 근거 위치
3. **검증** — 무엇을 어떻게 증명하는가. 자기가 만든 케이스를 도는 것은 검증이 아니다

**현행 코드가 정본이다.** 이 문서와 어긋나면 코드가 이긴다 — 어긋난 자리를 PR 본문에 적어라.

> **이 문서는 진행 상태를 추적하지 않는다.** 어느 task 가 끝났는지는 **이슈 #23 의 진행 표**가
> 정본이다. 이 문서에 완료 배너를 달아 봤자 다음 task 가 착륙하는 순간 다시 낡는다 — 실제로
> Task 1·2·3 이 각각 머지될 때마다 같은 지적이 세 번 반복됐다. **문서가 리뷰받는 동안 구현이
> 계속 착륙하므로 문서는 영영 못 따라잡는다.** 그래서 추적을 옮긴다.
>
> **task 를 받으면 먼저 이슈 #23 의 진행 표를 보고 그 task 가 이미 끝났는지 확인하라.**
>
> **위치는 줄 번호로 주지 않는다.** 초안이 `cross-review.yml:1148` 처럼 적었다가 #26 이 그 파일에
> 84줄을 더하면서 인용이 전부 밀렸다 — 저자 필터는 2곳에서 **3곳**이 됐는데 문서는 2곳만 알았다.
> 이 계획은 **찾는 명령**으로 준다. 명령은 파일이 바뀌어도 맞는 곳을 가리킨다.
>
> **단, 찾는 명령도 조용히 실패한다.** `grep` 은 0건일 때 아무 말 없이 끝난다 — 줄 번호는
> 틀린 곳을 가리키고 grep 은 아무 곳도 안 가리키는데, 후자가 더 조용하다. 실제로 PR #25 가
> 머지되면서 `grep 'decide() {' cross-review.yml` 이 0건이 됐다(코드가 `scripts/` 로 나갔다).
> **그러니 찾는 명령이 0건이면 「없어졌다」로 읽고 멈춰서 지휘자에게 알려라.** 스스로 판단해
> 새로 만들지 마라 — 이미 머지된 것을 다시 만들 수 있다.

---

## 전역 제약

모든 task 의 요구사항에 암묵적으로 포함된다.

- **검증 스크립트는 stdlib 전용.** 서드파티 import 금지.
- **새 `scripts/verify_*.py`·`scripts/test_*.py` 는 워크플로에 배선해야 한다.** 배선 없이 두면
  `scripts/verify_ci_check_coverage.py` 가 CI 를 빨갛게 만든다. 배선처는 `.github/workflows/repo-scans.yml`.
- **검사 0건은 통과가 아니다.** 새 검사는 검사한 대상 수를 세어 출력하고, 0이거나 기대치와
  다르면 실패한다.
- **동작을 바꾸지 않는 추출에는 차등 테스트를 붙인다.** 원본(bash)과 대체본(파이썬)을 **같은
  입력 집합으로 돌려 출력이 같음을 증명**한다. 「동작 동일」은 주장이 아니라 실측이어야 한다.
- **커밋 신원**: `git config --worktree --get user.email` → `claude-<티어>-agent@noreply.local`.
  첫 커밋 뒤 `git log -1 --format='%an <%ae>'` 로 실렸는지 확인한다.
- **main 직접 커밋·머지 금지.** 브랜치 → PR 까지가 워커의 몫이다.
- **`git stash` 금지 · force push 금지 · history 재작성 금지.** 부정 통제는
  `git diff > /tmp/x.patch` → `git apply -R` → 확인 → `git apply`.
- **포트 3000·3010·8000·5432 불가침. 개발 DB `fintech` 는 읽기만.** `pkill`·`fuser -k` 금지.
- **AI 자기 언급 금지.**
- **주석 규칙**: 변경 이유·이력 설명 주석 금지. 코드만으로 드러나지 않는 제약·의도만 한 줄로.

## 전역 불변식 — 어느 task 도 깨면 안 되는 것

리뷰 경로를 손대는 모든 task 에 적용된다.

| 불변식 | 근거 위치 | 깨지면 |
| --- | --- | --- |
| **판정 마커는 저자 필터를 통과한 코멘트에서만 읽는다** (`OWNER`·`MEMBER`·`COLLABORATOR`) | `grep -n author_association .github/workflows/cross-review.yml` (**3곳**) · 위협모델 주석은 `grep -n '저자 필터' …` | 공개 레포에서 **누구든** 마커를 코멘트해 봇 승인·자동 머지를 일으킨다. head sha 는 공개 정보다 |
| **마커 sha 는 head 와 40자 동등 비교** | — (초안 결함) | 접두사 매치면 앞 7자만 같은 다른 커밋의 판정이 통과한다 |
| **리뷰 루브릭은 PR 의 base 커밋에서 읽는다** | `.github/review-prompt.md` 머리 주석 | PR 이 자기 리뷰 기준을 변조한다 |
| **리뷰어는 PR 코드를 체크아웃하지 않는다** (`--base-branch origin/main`) | `grep -n 'base-branch origin/main' .github/workflows/cross-review.yml` | 남의 코드가 self-hosted 러너에서 실행될 표면이 생긴다 |
| **fork PR 은 리뷰어를 띄우지 않는다** | `grep -n 'head.repo.full_name' .github/workflows/cross-review.yml` | 같음 |
| **저자 ≠ 리뷰어** | `scripts/review_route.py` 의 `decide()` (Task 1 이 여기로 옮겼다) | 자기리뷰 |
| **판정 코멘트는 배정값이 아니라 실제 판정자를 적는다** | 루브릭: 「`reviewer` 는 route 가 정한 **배정값**이라 폴백이 일어나면 실제 판정자와 다르다」 | 누가 판정했는지가 기록과 어긋난다 |
| **리뷰어는 고치지 않는다.** 판정과 근거만 낸다 | `.github/review-prompt.md` | 심판이 선수가 된다. 발견 → **저자가** 고침 → 리뷰어가 재판정 순서만 쓴다 |

---

## Task 1: 리뷰어 배정을 순수 판정 스크립트로 추출

**바뀌는 자리**: `scripts/review_route.py` · `scripts/test_review_route.py` 신설,
`cross-review.yml` 의 `route` 잡이 그것을 호출.
outputs 목록만 보고 옮기지 마라 — 초안이 그렇게 해서 3자리를 틀렸다.

**만드는 것**: `scripts/review_route.py`(순수 판정) · `scripts/test_review_route.py` ·
`repo-scans.yml` 배선 · `cross-review.yml` 의 `route` 잡이 스크립트를 호출.

**불변식** (전역 불변식 외에):

- 반환은 `decide(emails, head_ref, issue_risks, codex_on) -> dict`. **`risk` 는 인자가 아니라
  반환값**이다 — 현행이 `ISSUE_RISKS` 로 함수 안에서 계산한다.
- 아래 넷은 초안이 틀렸던 자리다. 현행 코드로 각각 확인하고 그대로 옮겨라:
  - 고위험 codex 는 **claude 저자**일 때다
  - 벤더 혼재 시 후보 소진으로 **`reviewer=none`** 이 될 수 있다
  - 커밋 신원이 없어도 **브랜치명 `fix-N-<model>`** 로 저자를 판별한다
  - 위험 미선언·이슈 없음은 **high** (fail-closed)
  - **`identity_note` 의 모든 갈래를 옮겨라.** 판정 코멘트에 `주의: …` 로 실리는 사람 대상
    신호다. 초안 구현이 두 갈래(브랜치명↔커밋신원 불일치 · 목록 밖 에이전트형 이메일 관측)를
    빠뜨렸고, **차등 테스트의 대조 키에도 이 키가 없어 4,752조합을 돌리고도 못 잡았다**

**검증**

- [ ] `decide()` 를 워크플로에서 추출해 셸에서 실행 가능한 형태로 만든다
- [ ] **차등 테스트**: 원본 bash 와 파이썬을 같은 입력으로 돌려 출력 대조.
      입력에 최소 포함 — 벤더 3종 단독 · 티어 혼재 · 구형식 `claude-agent@` · 벤더 혼재
      (codex on/off 양쪽) · 브랜치명 판별(3벤더) · 신원 없음 · 목록 밖 에이전트형 이메일 ·
      대소문자 오타 · 이슈 라벨 없음/low/high/혼재 · 빈 입력
- [ ] 불일치 0건을 **명령과 출력으로** PR 본문에 싣는다
- [ ] `python3 scripts/test_review_route.py` 통과 (케이스 수를 출력하고 0건이면 실패)
- [ ] `python3 scripts/verify_ci_check_coverage.py` 종료코드 0

> **참고**: 이 task 의 코드는 계획 초안 시점에 작성돼 차등 테스트(입력 22가지, 불일치 0건)를
> 통과했고, 그 내용이 브랜치 `docs-ci-review-design` 의 이전 리비전에 있다. 참고해도 되지만
> **현행 `decide()` 와 다시 대조하고 네 차등 테스트로 증명하라.**

---

## Task 2: 터미널 준비·접수 판정을 교체한다 (구 #11)

**바뀌는 자리**: `scripts/terminal_state.py` · `scripts/test_terminal_state.py` ·
`scripts/fixtures/terminal_screens.json` 신설, `cross-review.yml` 의 `terminal_ready()` ·
`wait_agent_ready()` · `send_review_prompt()` 가 그 판정부를 부른다.

**문제**: 준비·접수를 `latestCursor` 성장으로 판정하는데, Claude Code TUI 는 화면을 제자리에서
다시 그려 이 값이 **움직이지 않는다**. 유휴 30초·완주한 워커 모두 `1` 이었다. `now > base` 는
claude 경로에서 영원히 참이 되지 않으므로 **타임아웃을 늘려도 무효**다. 재현 7/7.

**불변식**

- 판정 근거를 **화면 내용**으로 바꾼다 — 프롬프트 박스의 잔여 입력 유무, TUI 배너 존재 여부.
  판정부는 **I/O 없는 순수 함수**여야 한다 (터미널 tail 을 받아 bool 을 낸다)
- **kimi 경로를 깨지 마라.** 지금 판정이 claude 에서만 깨졌다 — 고친 판정이 kimi 에서도
  서는지 확인해야 한다
- 접수 판정이 고쳐지면 **재전송 루프는 지운다** — 중복 송신의 근거가 사라진다

**검증**

- [ ] 실제로 읽은 화면을 케이스로 박은 단위 테스트 (유휴 배너 · 미전송 입력이 남은 프롬프트 ·
      작업 중 화면 · TUI 아닌 맨 셸)
- [ ] **실환경 재현** — 워크트리를 띄워 새 판정이 준비·접수를 맞게 내는지 본다.
      종전 함수는 같은 조건에서 60초 뒤 실패했다
- [ ] **claude·kimi 두 경로에서 각각** 확인한다. kimi 는 `--agent` 가 받지 않으므로
      `orca-ide terminal create --worktree <셀렉터> --command kimi` 로 띄운다
- [ ] 확인이 끝나면 워크트리를 지운다
- [ ] 돌린 명령과 출력을 PR 본문에 그대로 싣는다

---

## Task 3: 죽은 경로를 지운다 — 헤드리스 · **스윕**

**읽어야 할 자리**: `cross-review.yml` 의 `build_prompt`·`run_headless_once`·`synth_verdict` ·
**시작 스윕** — `grep -n '고아 리뷰 워크트리 시작 청소' .github/workflows/cross-review.yml`. **한도 감지 6함수와 `try_candidate` 체인 루프는 남긴다.**

**왜 스윕도 지우나**: 2026-08-08 에 그 스윕이 **일하는 중인 리뷰어 다섯을 회수**했다. 안전 조항이
읽는 `lastActivityAt` 이 생성 시각에 고정돼 갱신되지 않아 무력했다(`보존 0건`). 이 재설계의
핵심 근거이므로 **원인 코드를 남기면 안 된다.** 정리는 automation 계획 Task 4 가 연결 PR 상태로
판정해 맡는다.

**불변식**

- **폴백 체인은 지우지 않는다** (2026-08-08 리드 정정). kimi·codex 가 한도로 막히면 claude 가
  이어받는 것이 의도된 설계다 — 실제 판정자는 여전히 하나이므로 「한 리뷰를 여러 모델이 이어받아
  계속 손대는 것」과 다르다. 한도 프로브도 유지한다 (그것이 폴백을 **확증된 한도에만** 걸리게 한다)
- 헤드리스 경로는 **이 레포에서 9/9 미사용**(게시된 판정 코멘트의 「실행 경로」 필드 전수).
  옛 레포 이력은 확인 못 했다 — 지우기 전에 이 레포 기준 수치를 다시 세라
- **스윕을 지우면 워크트리가 쌓인다.** automation 계획 Task 4 가 서기 전까지는 사람이 치운다.
  그 사실을 PR 본문에 적어라

**검증**

- [ ] 삭제 **전에** 소비자를 전수 조사한다 (`chain`·`fallback_tier`·`EXHAUSTED`·`DEGRADED`·
      `exec_path` 등). 조사 목록과 처리 결과를 PR 본문에 담는다
- [ ] 삭제 **후에** 같은 grep 이 0건인지 확인한다
- [ ] `review-gate.yml` 의 `review: fallback-claude` 라벨 회수 목록에서도 뺀다
- [ ] 줄 수 변화를 `wc -l` 로 재어 PR 본문에 적는다

---

## Task 4: 경로 필터를 워크플로 레벨에서 잡 레벨로 옮긴다

**읽어야 할 자리**: `ci.yml` 과 `frontend-ci.yml` 의 `on:` 블록 **전체**.

**왜**: 워크플로째 건너뛴 체크는 **영영 pending** 이라 required 로 걸 수 없다. 잡 레벨 `if:` 로
건너뛴 잡은 `skipped` 를 보고하고 GitHub 은 `success`·`skipped`·`neutral` 을 통과로 센다.

**불변식**

- **현행 트리거 경로를 하나도 잃지 마라.** 초안은 `frontend-ci` 의 5개
  (`scripts/verify_filter_negation.mjs` · `scripts/fixtures/filter_conformance_cases.json` ·
  `backend-service/alembic/**` · `THIRD-PARTY-NOTICES.md` · `scripts/verify_notice_counts.py`)를
  빠뜨렸다. **파일에서 뽑아 대조하라** — 이 문서의 목록을 믿지 마라
- 필터 판정은 잡 하나가 내고 나머지 잡이 그 출력을 `if:` 로 읽는다

**검증**

- [ ] 전환 전후의 경로 목록을 뽑아 **집합이 같음**을 보인다
- [ ] `.md` 만 바꾼 PR 을 열어 `gh pr checks` 가 **`skipping`** 을 내는지 확인한다.
      **pending 이 하나라도 남으면 Task 5·6 을 진행하지 마라** — 그 PR 이 영영 막힌다
- [ ] 필터 안쪽 파일을 바꾼 PR 로 해당 잡이 **실제로 도는지**도 확인한다 (한쪽만 보면
      「전부 skip」이 초록으로 읽힌다)

---

## Task 5: required 게이트 잡을 세운다

**만드는 것**: `repo-scans.yml` 에 상류 잡을 대표하는 잡 하나. 이 워크플로는 경로 필터가 없어
모든 PR 에서 돈다.

**불변식**

- **`needs:` 가 아니라 `check-runs` 조회로 전수 판정한다** (2026-08-09 리드 결정).
  `needs:` 는 같은 워크플로 안만 묶으므로 `ci.yml` 7종·`frontend-ci.yml` 3종을 대표하지 못하고,
  그대로 두면 Task 8 이 `merge-router` 를 지울 때 자동 머지가 그 10종을 안 보게 된다.
  **검증된 구현이 `merge-router.yml` 에 있다** — `test: ` 접두 전수 조회 · 같은 이름은 id 최대만 ·
  `completed` ∧ `success|skipped` · `MIN_TEST_CHECKS` 하한 · 조회 실패는 0건(fail-closed).
  새로 짜지 말고 그것을 읽고 옮겨라
- **게이트 잡은 자기 자신을 제외해야 한다.** 게이트도 `test: ` 접두 체크라, 전수 조회하면
  자기 자신이 `in_progress` 로 잡혀 **영영 초록이 안 된다.** 제외가 실제로 동작하는지 케이스로 못박아라
- **게이트는 상류가 끝날 때까지 기다린다.** `repo-scans.yml` 과 `ci.yml`·`frontend-ci.yml` 은
  **같은 `pull_request` 이벤트로 동시에** 시작하므로, 게이트가 개시 직후 한 번만 조회하면
  상류가 `in_progress` 로 잡혀 **빨강**이 된다. required 로 걸린 잡이 코드 PR 마다 빨가면
  **사람 머지까지 막히는 작업 정지 장치**가 된다 — 설계 §4 가 금지한 것이다.
  완료까지 다시 조회하고, **대기 상한을 못박고, 상한을 넘기면 미완을 실패로 접어라**(fail-closed).
  잡의 `timeout-minutes` 도 그 상한보다 크게 둔다.
  실측(2026-08-09 PR #49): 상류 마지막 `test: frontend` 가 `01:46:02`, 게이트가 `01:46:16` —
  **14초 뒤에 초록**. 같은 SHA 의 `test: ` 체크런 시각을 `check-runs` 로 뽑으면 이 간격이 보인다
- **판정부는 순수 함수로 `scripts/` 에 둔다** — check-runs JSON 을 받아 판정을 내는 함수면
  로컬에서 돈다
- 통과 조건은 **`success` 또는 `skipped`** 인 것뿐이다
- **0건이면 실패**한다 — 「검사할 게 없어서 초록」이 되지 않게

**검증**

- [ ] **0건 입력에서 실패하는지** 확인한다. 명령과 출력을 PR 본문에
- [ ] **자기 자신이 포함된 입력에서 제외 후 판정이 나오는지** 확인한다
- [ ] 상류 하나를 일부러 실패시킨 상태에서 게이트가 **빨간지** 확인한다
- [ ] 상류가 `skipped` 일 때 게이트가 **초록인지**도 확인한다 — 한쪽만 보면 반쪽이다
- [ ] 같은 이름의 체크런이 재실행으로 여러 개일 때 **최신 것만 보는지** 확인한다
- [ ] **상류가 아직 안 끝난 입력에서 「통과」로 접히지 않는지** 확인한다 — 위 다섯은 전부
      상류가 이미 완료된 상태를 전제한다. 이 케이스가 빠지면 가장 흔한 실제 상황이 안 덮인다
- [ ] **상한을 넘겼을 때 실패하는지** 확인한다 (fail-closed)

---

## Task 6: **이미 있는 ruleset** 에 게이트 잡을 추가하고 Orca 체감을 잰다

**코드 변경이 아니라 설정 변경 + 실측이다.**

> **초안 정정.** 이 task 는 원래 「브랜치 보호를 새로 건다」였다. **이 레포에는 이미 활성 ruleset
> 이 있다** — 초안이 `gh api …/branches/main/protection` 의 404 만 보고 「보호 없음」으로 단정했다.
> 그 엔드포인트는 **classic 보호만** 보고 ruleset 은 안 보여준다.

**읽어야 할 자리** (손대기 전에 현재 상태를 직접 확인한다):

```bash
gh api repos/Danwoo/trading-lab/branches/main --jq .protected
gh api repos/Danwoo/trading-lab/rulesets
gh api repos/Danwoo/trading-lab/rules/branches/main --jq '[.[].type]|unique'
gh api repos/Danwoo/trading-lab/rulesets/<id>
```

2026-08-08 실측: ruleset `20552422` (`main protection`, active) 이 `deletion` ·
`non_fast_forward` · `pull_request`(승인 필요 수 **0**) · `required_status_checks`
(**`test: repo-scan` · `test: repo-scan-app` · `test: ci-coverage`**) 를 건다.

**불변식**

- **classic 브랜치 보호를 새로 만들지 마라.** `gh api -X PUT …/branches/main/protection` 은
  ruleset 과 **겹치는 별개 보호**를 만든다. 기존 ruleset 을 **수정**한다
- **승인 필요 수는 0 을 유지한다.** 올리면 AI 리뷰가 죽었을 때 사람도 머지 못 해 작업 정지
  장치가 된다 (2026-08-06 결정 취지 · 2026-08-08 리드 결정). **현행이 이미 0 이므로 건드리지
  않는 것이 곧 결정 이행이다**
- required 목록에 넣는 것은 **Task 4 에서 `skipping` 이 확인된 것만**이다
- **`ci.yml`·`frontend-ci.yml` 의 `test: ` 잡 대표는 선택이 아니다 — Task 8 의 선행 조건이다.**
  **2026-08-09 리드 결정으로 ㉡(게이트 잡이 `check-runs` 로 전수 대표)를 택했고 Task 5 가 그것을
  구현한다.** 따라서 이 task 에서 required 에 더할 것은 **게이트 잡 하나**다. 아래는 그 결정의 근거다. 지금 `merge-router.yml` 이 자동 머지 전에 **`test: ` 접두 체크런
  전부**(13개)를 확인하는데, ruleset 의 required 는 `repo-scans.yml` 의 3종뿐이다. Task 5 의
  게이트 잡은 같은 워크플로 안만 `needs` 로 묶으므로 나머지 10종을 대표하지 못한다.
  **이 상태로 Task 8 이 `merge-router.yml` 을 지우면 자동 머지가 backend·frontend 테스트 결과를
  안 보고 머지한다.** 사람 머지 경로는 원래 3종만 걸려 변화가 없지만 자동 경로가 약해진다.
  대안은 둘이다 — ㉠ 그 10종을 required 에 넣는다 ㉡ 게이트 잡이 `check-runs` 조회로 대표한다
  (`merge-router` 가 지금 하는 방식). **어느 쪽이든 Task 8 전에 서 있어야 한다**
- **`allow_auto_merge` 를 켠다.** 2026-08-09 실측으로 **꺼져 있다**(`gh api repos/Danwoo/trading-lab
  --jq .allow_auto_merge` → `false`). 머지된 PR 40건 중 `autoMergeRequest` 가 있던 것은 **0건** —
  이 레포에서 네이티브 auto-merge 는 한 번도 선 적이 없다. 지금 흐름이 도는 것은
  `merge-router.yml` 의 **거부되면 직접 머지하는 폴백** 덕분인데 **Task 8 이 그 파일을 지운다.**
  이 설정을 다루는 task 는 여기뿐이므로, 안 켜면 계획의 완료 조건 「저위험·봇 PR 은 자동 머지가
  arm 된다」가 **이 계획만으로 도달 불가**다. 설정 변경이므로 사람이 켠다:
  Settings → General → Pull Requests → *Allow auto-merge*
- **required 항목은 GitHub Actions 앱에 고정한다** (`integration_id: 15368`, 2026-08-09 리드 결정).
  현행 3종 중 `test: repo-scan`·`test: repo-scan-app` 만 고정돼 있고 **`test: ci-coverage` 는
  없다.** 고정이 없으면 같은 이름을 보고하는 다른 앱도 그 required 를 만족시킨다. 지금 그런 앱은
  설치돼 있지 않아 실제 구멍은 아니지만, 이번에 **`ci-coverage` 와 새 게이트 잡 둘 다 고정해**
  맞춘다. 앱 id 는 `gh api apps/github-actions --jq .id` 로 확인한다
- 기존 required 3종을 **빼지 마라.** 게이트 잡을 **더하는** 것이지 대체하는 것이 아니다.
  뺄지 말지는 게이트 잡이 그 셋을 실제로 대표하는지 확인한 뒤 별도로 판단한다

**검증**

- [ ] 변경 **전** ruleset 전문을 파일로 떠 둔다 (되돌릴 근거)
- [ ] 변경 **후** `rules/branches/main` 을 다시 조회해 의도한 것만 바뀌었는지 대조한다
- [ ] **Orca 에서 30분 써 본다** — 테스트가 도는 동안 버튼이 닫히나, 끝나면 열리나,
      `mergeStateStatus=UNKNOWN` 창에서 어떻게 구나. 설계 문서의 미검증 위험이 이 자리다
- [ ] 체감이 나쁘면 되돌린다. 결과를 `CONTEXT.md` 결정 로그에 한 줄 남긴다 (추가 전용)

---

## Task 7: 판정을 GitHub 리뷰로 기록하는 기록기

**읽어야 할 자리**: `cross-review.yml` 의 `publish` 잡, 그리고 **저자 필터가 걸린 자리 전부** —
`grep -n author_association .github/workflows/cross-review.yml`. **곳 수를 세어라.** 초안이 2곳으로
알고 있었는데 #26 이 한 곳을 더 만들어 3곳이 됐다. 「몇 곳인지」를 문서에서 읽지 말고 직접 세라.
`parse_marker`·`poll_verdict` 도 같은 방식으로 찾는다.

**만드는 것**: `scripts/review_record.py`(순수 판정) · 테스트 · `.github/workflows/review-record.yml` ·
`repo-scans.yml` 배선.

**하는 일**: 리뷰어가 남긴 판정 코멘트를 읽어 `github-actions[bot]` 명의로 `gh pr review` 를
대행한다. GitHub 이 자기 PR 자기 승인을 금지하므로 로컬 `gh`(리드 계정)로는 승인이 안 된다.

**불변식** — 전역 불변식의 앞 둘이 **이 task 의 것**이다. 특히:

- **저자 필터를 반드시 옮겨라.** 마커 코멘트는 `OWNER`·`MEMBER`·`COLLABORATOR` 것만 읽는다.
  초안이 이걸 빠뜨려 **공개 레포에서 누구든 위조 마커로 봇 승인·자동 머지를 일으킬 수 있었다.**
  승인을 required 로 안 거는 이 설계에서 **유일한 위조 방어**다
- **sha 는 40자 동등 비교.** 접두사 매치 금지
- 자동 머지 arm 조건은 전부 참일 때만: ① required 게이트 초록 ② 승인 리뷰가 있고 그
  `commit_id` 가 현재 head 와 같다 ③ **리뷰어 벤더 ≠ 저자 벤더, 또는 같은 벤더여도 작성
  티어를 안다** ④ `risk: low` **또는** 저자가 봇이면서 **major 상승이 아니다**
- **자기리뷰 차단을 arm 조건으로 승계하라** (조건 ③). `cross-review.yml` 이 「동일-벤더 폴백 +
  작성 티어 미상 → 라벨 미부착」으로 자동 경로를 막던 것을, 판정 라벨을 없애면서 코멘트 문구로
  강등했다 — 문구는 아무 자동 경로도 읽지 않으므로 그 차단은 승계되지 않으면 사라진다.
  저자 신원은 커밋 author 이메일·브랜치명으로 읽고(형식 SoT 는 `scripts/review_route.py`),
  **못 읽으면 arm 하지 않는다** (fail-closed)
- **`source=manual` 마커는 arm 하지 않는다** — 사람이 타이핑한 한 줄일 수 있다
- 봇 PR 의 상승 종류는 PR 제목에서 읽는다. **읽지 못하면 arm 하지 않는다** (fail-closed)
- **arm 조건 ③ 의 `risk: low` 를 어디서 읽는지 명시하라.** 현행이 이미 못 박아 뒀으니 옮겨라 —
  `git show origin/main:.github/workflows/merge-router.yml` 머리 주석: **SoT 는 이슈의 risk
  라벨이고 판정 시점마다 fresh 조회한다. PR 의 risk 라벨은 가시화 미러일 뿐 판정 입력이 아니다**
  (미러가 낡아 오통과되지 않게). 이슈 연결은 `closingIssuesReferences` 로 읽는데 그것은
  **closing 키워드(Closes/Fixes/Resolves)만** 잡는다 — `Refs #N` 만 쓴 PR 은 그 API 로는
  연결 이슈가 0건이다 (2026-08-09 실측: #49·#47·#24 셋 다).
- **`Refs #N` 도 위험도 출처로 읽는다** (2026-08-09 리드 결정). `closingIssuesReferences` 만
  보면 **위험도를 읽히려고 PR 마다 전용 이슈를 만들게 되고, 그것이 이슈를 문어발로 늘린다.**
  이 레포가 이미 겪은 실패다 — 리드가 「이슈는 보수적으로」를 반복해 요청한 이유가 그것이다.
  이슈 하나에 PR 여럿을 `Refs` 로 매달 수 있어야 이슈가 안 는다. 구현 규칙:
  - `closingIssuesReferences` 로 못 읽으므로 **PR 본문에서 직접 파싱**한다
  - **`Refs #N` 의 N 은 PR 일 수 있다 — 배제하라.** `repos/{repo}/issues/{N}` 은 PR 에도
    응답하고, `merge-router` 는 PR 에 risk 를 **가시화 미러**로 붙인다. 배제하지 않으면
    `Refs #<PR번호>` 만 있는 PR 이 그 미러 라벨로 `low` 에 접혀 arm 된다 — SoT 는 이슈의
    risk 라벨이라는 규칙을 정면으로 어긴다 (2026-08-09 실측: `#13` 이 `risk: low` 미러 보유).
    `.pull_request` 로 판별해 배제하고 **배제한 번호를 로그에 남긴다.** 배제 후 참조가 0건이면
    미선언 = 사람 경로라 fail-closed 방향이 유지된다. 조회 실패도 미선언으로 접는다 —
    빈 라벨 목록으로 흡수하면 실패가 다른 이슈의 `low` 에 묻힌다
  - **여러 이슈를 참조하면 가장 높은 위험을 취한다** (fail-closed)
  - **하나도 못 읽으면 미선언 = 고위험** (현행과 같다)
  - 참조한 이슈에 risk 라벨이 없어도 미선언이다
  - 이 계획의 task PR 은 전부 `Refs #23` 인데 **#23 은 `risk: high`** 라 여전히 사람 경로다 —
    이 결정이 이번 작업의 흐름을 바꾸지는 않는다
- **disarm 경로를 반드시 함께 만든다.** `pull_request: [synchronize]` 를 듣고 `--disable-auto`
  로 arm 을 푼다. arm 조건만 옮기면 「승인 → arm → push → 아무도 안 본 커밋이 머지」가 뚫린다
  (설계 §4 참조). 지금 그 일을 `merge-router.yml` 이 하고 있고 Task 8 이 그 파일을 지운다 —
  **지우기 전에 이 경로가 서 있어야 한다.** Task 8 은 그것을 확인하고 지운다
- **라벨을 붙이는 쪽도 함께 지운다.** 설계 결정 3 은 `review: passed`·`review: unable`·
  `review: needs-work`·`human: merge` 를 **없앤다**고 정했는데, 초안은 **읽는 쪽**(Task 8 의
  `merge-router`·`review-gate`)만 지우고 **붙이는 쪽**을 안 건드렸다. 그러면 아무도 안 읽는
  라벨이 계속 붙는다. 붙이는 자리를 전수로 찾아라:
  `grep -n 'review: passed\|review: unable\|review: needs-work\|human: merge' .github/workflows/*.yml`
  (2026-08-09 실측 **4파일**: `cross-review.yml` · `board-status.yml` · `review-gate.yml` ·
  `merge-router.yml`. 뒤 셋은 Task 8 이 지우므로 자동 해소되고, **`cross-review.yml` 만 손으로
  지워야 한다.** 곳 수를 이 문서에서 읽지 말고 위 명령으로 직접 세라)

**검증**

- [ ] 단위 테스트에 **공격 케이스**를 넣는다 — 위조 마커(비-멤버 코멘트) · 접두 sha ·
      낡은 sha · `source=manual` · major 봇 PR · 제목 파싱 실패
- [ ] **봇 승인이 실제로 서는지 확인한다** — 테스트 PR 에 마커 코멘트를 달고
      `gh pr view <N> --json reviews` 에 `github-actions` / `APPROVED` 가 뜨는지 본다
- [ ] **낡은 sha 로도 해 보고 아무 리뷰도 안 달리는지** 확인한다
- [ ] 명령과 출력을 PR 본문에 그대로 싣는다

---

## Task 8: 흉내 내던 워크플로를 삭제하고 `plan-*` 을 통합한다

**삭제**: `merge-router.yml` · `review-gate.yml` · `board-status.yml` ·
`plan-check.yml` · `plan-label.yml` · `plan-label-issue.yml`
**신설**: `plan.yml` (위 셋의 잡을 이벤트로 갈라 담는다)

**불변식**

- **체크 이름을 바꾸지 마라.** `gh pr checks` 에서 확인한 기존 이름과 byte-identical 로 유지한다
- 삭제 대상이 검증 스크립트를 돌리는지 먼저 확인한다. 돌린다면 고아가 되므로 먼저 옮긴다
- **`cross-review.yml` 은 이 계획에서 지우지 않는다** — 아래 참조
- **`merge-router.yml` 을 지우기 전에 두 가지가 서 있어야 한다.** 지우면 사라지는 것을 받는
  자리가 없으면 조용히 약해진다:
  1. **자동 머지 disarm 경로** (Task 7 불변식) — 없으면 승인 뒤 push 가 무검증으로 머지된다
  2. **`test: ` 전수 초록 판정** — `merge-router` 가 13개 체크런을 다 보는데, required 는 3종뿐이다.
     Task 6 이 나머지를 required 에 넣었거나 게이트 잡이 `check-runs` 조회로 대표해야 한다
  **둘 중 하나라도 없으면 이 task 를 진행하지 마라.** 확인한 결과를 PR 본문에 적어라

**검증**

- [ ] 삭제 전 참조를 전수 조사한다 (문서·스크립트·CI·훅). 조사 목록과 처리 결과를 PR 본문에
- [ ] 삭제 후 `python3 scripts/verify_ci_check_coverage.py` 종료코드 0
- [ ] 워크플로 수와 총 줄 수를 세어 PR 본문에 적는다

---

## 완료 판정 — 이 계획이 닿는 곳과 못 닿는 곳

**이 계획이 끝나면**:

- 순수 판정 3종이 `scripts/` 에서 로컬로 돌고 회귀 그물이 붙는다
- required 게이트가 서고 머지가 예측 가능해진다
- 판정이 GitHub 리뷰로 기록되고, 저위험·봇(major 제외) PR 은 자동 머지가 arm 된다
- 리뷰 인프라가 죽어도 사람 머지는 막히지 않는다
- 워크플로 **11개 → 7개** (`ci` · `frontend-ci` · `repo-scans` · `plan` · `review-record` ·
  `cross-review` · `orphaned-branch-scan`)

**「5개 · 약 1,000줄」에는 이 계획만으로 도달하지 못한다.** `cross-review.yml` 이 남기 때문이다.
그 파일이 하는 일 중 `route`(→ Task 1)와 `publish`(→ Task 7)는 옮겨지지만, **리뷰어 기동
209줄은 automation 계획이 가져가야** 비로소 빈다.

```
cross-review.yml 618줄(review 잡)
  ├ 입력 번들 준비 230줄 — 신뢰 경계. 누군가는 해야 한다
  └ 리뷰어 기동   209줄 — automation 계획 소관
```

**따라서 순서는**: 이 계획 → automation 계획(리뷰어 기동 이관) → `cross-review.yml` 삭제.
마지막 단계는 automation 계획이 끝난 뒤 별도로 판단한다. 이슈 #23 의 완료 조건
「5개 · 약 1,000줄」은 **그 시점의 목표**이지 이 계획의 목표가 아니다.

## 이 계획이 못 닫는 것

- **Orca `UNKNOWN` 창의 머지 버튼 동작** — Task 6 이 재보지만 설계로는 못 닫는다
- **`lastActivityAt` 이 안 움직이는 것** — Orca 가 주는 값이라 못 고친다. Task 3 이 스윕을 지워
  우회하지만, 나이로 생사를 판정하는 코드가 다시 생기면 같은 함정을 밟는다
- **스윕 삭제와 automation 정리 사이의 공백** — 그 사이 워크트리는 사람이 치운다
