# main 을 무엇으로부터, 무엇으로 지키나 — private 전환의 교환 (#420)

> 이 문서는 **판단의 근거**를 남긴다. 방어층 목록은 시간이 지나면 코드가 정본이 되지만,
> 「왜 이 정도로 지키기로 했나」는 코드에 안 적힌다. 그것을 안 적으면 다음 사람이 이 상태를
> **구멍으로 읽는다.**

## 1. 무엇이 바뀌나

리드 목표는 **private 으로 전환해 계속 개발한다**(2026-08-29)이고, 같은 날 **GitHub Pro 결제는
하지 않는다**가 정해졌다. 이 계정은 Free 이고, GitHub 은 private 레포의 ruleset 요청에 이렇게
답한다:

```
$ gh api repos/Danwoo/ai-dev-harness/rulesets
{"message":"Upgrade to GitHub Pro or make this repository public to enable this feature.","status":"403"}
```

즉 전환하는 순간 `main protection` 이 강제하던 넷이 사라진다 — 그리고 **ruleset 만 사라지는 것이
아니다**(§2.5):

| 규칙 | 내용 | 전환 뒤 |
|---|---|---|
| `pull_request` | PR 필수 · 승인 1건 | **사라짐** |
| `required_status_checks` | `test: backend`·`test: frontend`·`test: repo` | **사라짐** |
| `non_fast_forward` | main force push 금지 | **사라짐** |
| `deletion` | main 삭제 금지 | **사라짐** |

## 2. 위협 모델 — 적대자가 아니라 실수다

이 레포는 **1인 레포**다. push 권한을 가진 것은 리드 한 사람이고, 에이전트는 **리드와 같은
GitHub 계정**으로 민다. 그래서:

- **인증 경계가 없다.** 서버 규칙은 「권한 없는 사람」을 막는 장치인데, 여기엔 권한 없는 사람이
  없다. ruleset 이 실제로 막고 있던 것은 침입이 아니라 **리드(와 그 대리인)의 실수**다.
- **실수의 모양은 정해져 있다.** ㉠ 브랜치를 안 파고 main 에 커밋 ㉡ `git push HEAD:main`
  ㉢ 리뷰 전에 머지 ㉣ 게이트가 빨간 채로 머지 ㉤ 여러 ref 를 한 번에
  (`git push origin feature main`).
- **되돌리기가 싸다.** 잘못 착륙한 커밋은 revert 하면 된다. 데이터 유실도, 외부 공개도 아니다.

적대자가 없고 되돌리기가 싼 상황에서는 **「막는 것」보다 「반드시 발각되는 것」이 값이 같거나
낫다.** 막는 층은 우회 경로가 하나만 있어도 무너지지만, 발각은 우회한 사실 자체를 남긴다.

## 2.5 사라지는 것은 셋이다 — 하나만 보고 넘기지 않는다

private 전환으로 없어지는 GitHub 기능은 `main protection` ruleset 하나가 아니다. 셋 다
**public 에서만 무료**이고, 결제하지 않기로 했으므로(리드 결정 2026-08-29) 전부 자리를 옮긴다.

| 사라지는 것 | 근거 | 대체 |
|---|---|---|
| `main protection` ruleset | Free 의 ruleset 은 public 저장소에서만 선다 | 아래 §3 (예방 + 발각) |
| **CodeQL 코드 스캐닝 경보** | *"If you want to use code scanning on private repositories, you need a GitHub Code Security license."* | 업로드를 빼고 **분석은 그대로** — `upload: never` 로 받은 SARIF 를 `scripts/judge_codeql_sarif.py` 가 읽어 잡을 빨갛게 만든다 |
| **secret scanning · push protection** | public 에서만 *"runs automatically for free"* | PR 은 종전 gitleaks(작업 트리), main 착륙마다 **히스토리 전량**, push 직전에 훅 한 겹 |

**끄지 않는다.** 세 자리 모두 「기능을 빼서 빨간불을 없애는」 길이 있었고 전부 택하지 않았다 —
빨간불을 없애는 것과 위험을 없애는 것은 다르고, 전자는 §4.3 이 적은 「발각이 행동으로 이어지지
않는」 상태를 스스로 만든다.

### CodeQL — 오히려 강해진다, 다만 베이스라인 위에서

**켜는 시점에 이미 발견이 17건 있었다** (2026-09-14 실측: `py/stack-trace-exposure` 13 ·
`py/clear-text-logging-sensitive-data` 2 · `js/polynomial-redos` 1 · `js/request-forgery` 1,
규칙·파일 기준). 그대로 게이트를 켜면 첫 push 부터 영영 빨갛고, **상시 빨간 잡은 아무도 안
본다** — §4.3 이 적은 바로 그 상태를 만들면서 「탐지를 살렸다」고 말하게 된다.

그래서 그날의 발견을 `.codeql-baseline.json` 에 고정하고 **거기 없는 것만** 막는다. 목록은
줄어들기만 하고(고친 것은 지운다), 한 줄을 더하는 것은 「새 발견을 받아들인다」는 선언이라
리뷰에서 보인다. 못 읽으면 목록이 없는 것으로 보고 **전부 막는다**.

알갱이는 (규칙, 파일) 이다 — 줄 번호는 코드가 움직일 때마다 흔들려 쓰지 않았고, 그 대가로
**같은 파일에서 같은 규칙 위반이 하나 더 늘어도 안 잡힌다.** 이 한계를 안고 켜는 이유는,
「새 파일·새 규칙의 발견을 잡는 것」이 지금 없는 것보다 낫기 때문이다.



업로드하던 시절 이 체크는 **12일 내내 실패 0**이었다. 발견은 Security 탭으로만 갔고 워크플로는
언제나 초록이었다. 이제는 차단 수준(`error`·`warning`) 발견이 하나라도 있으면 잡이 빨개진다.
SARIF 를 못 읽거나 규칙이 0개로 분석된 경우도 실패다 — 분석이 조용히 안 돈 상태를 통과로
읽지 않는다.

### secret scanning — 세 겹으로 나눠 받는다

- **PR**: 작업 트리 스캔(`--no-git`). 종전 그대로.
- **main 착륙**: 히스토리 전량(`--log-opts=--all`). 작업 트리 스캔이 **구조적으로 못 보는 것**이
  여기 있다 — 한 커밋에 들어왔다가 다음 커밋에서 지워진 값은 트리에 없다. main 은 커밋이
  붙기만 하므로 착륙마다 전량을 훑으면 빠지는 구간이 없다 (실측: 479커밋 3초).
- **push 직전**: `scripts/scan_push_for_secrets.sh` 가 **push 되는 커밋 구간**을 훑는다. 커밋
  훅은 `--no-verify` 나 훅이 없는 클론이면 지나가고, 그렇게 들어온 값은 CI 가 빨개져도
  **이미 히스토리에 박힌다.**
  gitleaks 의 공식 pre-commit 훅(`protect --staged`)을 이 자리에 그대로 걸면 안 된다 — 그것은
  **git 인덱스**를 보는데 push 시점에는 인덱스가 비어 있는 것이 정상이라 **아무것도 안 보고 늘
  통과한다.** 있는 척만 하는 층이 된다(#488 리뷰가 잡은 실제 결함). 범위를 못 받으면 거부한다.

**못 받는 것은 정직하게 적는다**: 서버가 push 를 **거부**하는 층은 사라진다. 위 셋은 전부
이 레포 안에서 도는 층이라 `--no-verify` 로 지나갈 수 있고, 그때는 히스토리 스캔이 뒤에서
잡는다 — 막지는 못하고 반드시 발각된다. 파트너 토큰 유효성 검사(GitHub 이 발급처에 물어보는
것)도 대체가 없다.

### 히스토리 예외는 지문으로만

전량 스캔은 **과거 커밋**을 본다. 가림 기능을 시험하려고 넣은 합성 문자열 3건이 거기 남아 있고
(현재 트리에는 셋 다 `gitleaks:allow` 표시가 붙어 깨끗하다), 과거는 고쳐 쓸 수 없다. 그래서
`.gitleaksignore` 에 **`커밋:파일:규칙:줄` 지문**으로 그 세 자리만 고정했다 — 이름으로 거는
예외와 달리 같은 값이 다른 자리에 다시 들어오면 그대로 걸린다. 그리고 그 목록이 문이 되지
않게 `scripts/verify_gitleaks_ignore.py` 가 각 줄의 파일이 지금도 `gitleaks:allow` 로
스스로를 밝히는지 대조한다.

## 3. 그래서 무엇으로 대체하나

| 사라지는 것 | 대신 서는 것 | 성격 |
|---|---|---|
| main 위 커밋 금지 | pre-commit `no-commit-to-branch` | 예방 (이미 있었다) |
| main 직접 push 금지 | **pre-push `reject-push-to-main`** (#420 P1) | 예방 (새로 지음) |
| force push 금지 | `danger-guard.sh` H4 (에이전트) | 예방 (이미 있었다) |
| PR·승인·게이트 필수 | **`audit: main 착륙`** CI 잡 (#420 P2) | **발각** (새로 지음) |
| 자동 머지 | `cross-review.yml`·`ci.yml` 의 직접 머지 경로 | 그대로 (보호 없어도 돈다) |
| **main 브랜치 삭제 금지** | **없다** — 아래 참고 | — |

`deletion` 규칙에는 대체층이 없다. pre-commit 은 삭제 push(로컬 sha 가 0)를 건너뛰어 훅이 아예
안 돌고, 삭제된 브랜치의 push 이벤트에서는 감사 잡도 유의미하게 돌지 않는다. 수용하는 근거는
위 위협 모델과 같다 — 실수의 모양에 「main 을 지운다」가 없고, 지워져도 로컬 클론·PR 참조·
GitHub 의 되살리기로 복구된다. **없는 것을 없다고 적는 것까지가 이 표의 일이다.**

### 예방층의 한계를 정직하게

- `pre-push` 훅은 **`--no-verify` 로 지나간다.** 그 문을 닫지 않는 이유는, 훅 자체가 고장 났을 때
  사람이 손으로 밀 길이 남아야 하기 때문이다. 대신 우회가 **의식적 행위**가 되므로, 그렇게
  들어온 커밋은 사후 감사가 잡는다.
- 훅은 **한 ref 만 본다.** pre-commit 4.6.0 은 stdin 의 ref 목록에서 조건에 맞는 **첫 줄
  하나**로 `PRE_COMMIT_REMOTE_BRANCH` 를 만들고 끝낸다 — `git push origin feature main` 처럼
  feature 를 앞에 쓰면 훅은 `feature` 만 보고 통과시킨다. 착륙은 감사가 잡으므로 심층 방어는
  선다.
- 훅은 **설치된 클론에만** 있다. `default_install_hook_types: [pre-commit, pre-push]` 가
  `pre-commit install` 한 번으로 둘 다 걸어 주지만, 설치를 안 한 클론에는 아무 층도 없다.
- 그래서 **예방은 「대부분의 실수」를 막고, 발각은 「전부」를 잡는다.** 후자가 fail-closed 여야
  이 교환이 성립한다 — 감사가 조용히 초록이면 남는 것이 아무것도 없다.

### 발각층이 fail-closed 인 방식

`scripts/audit_main_landing.py` 는 착륙 커밋마다 셋을 본다: PR 을 거쳤는가 · 리뷰 통과 마커가
머지된 head 를 가리키는가 · required 게이트 3종이 초록이었는가. 그리고:

- **검사한 커밋이 0건이면 실패한다.** 「볼 것이 없었다」와 「위반이 없었다」는 다르다.
- **조회가 실패하면(`None`) 통과로 읽지 않는다.** API 한도·권한·경로 변경으로 조용히 빈 결과가
  오는 경로가 실제로 있다.
- **리뷰 마커의 `sha=` 가 머지된 head 와 다르면 위반이다.** 리뷰 뒤에 커밋이 얹혔다면 그 리뷰는
  머지된 코드를 본 적이 없다.
- **재실행된 체크는 최신 것으로 읽는다.** 재실행은 이 레포의 정규 운용이고(루트 `CLAUDE.md`
  「쓸어담기」), 같은 이름의 체크런이 여럿 올 때 API 응답 순서에 기대면 안 된다 — 실측:
  한 head 에 12일 차이 나는 두 판정이 **기본 필터에서도** 함께 오고 **새것이 앞에** 있다.
  순서에 기대면 옛 판정이 최종값이 된다. 판정은 `verify_upstream_gate.latest_by_name` 한 곳이다.
- **잘린 목록을 완전한 것으로 쓰지 않는다.** 조회는 페이지를 끝까지 따라가고, 한 페이지라도
  못 읽으면 빈 목록이 아니라 「못 읽었다」로 남긴다. 한 페이지(100건)만 읽으면 앞 100개가
  문서이고 101번째가 코드인 PR 이 「문서 전용」으로 접혀 리뷰 마커를 면제받는다.
- **`source=manual` 마커는 통과시키되 기록에 남긴다.** 신뢰 저자가 붙였으니 리뷰가 없었던 것은
  아니지만, 자동 머지 권한은 얻지 못한다(#285 규약). 「사람이 손으로 붙였다」와 「CI 가
  판정했다」를 같은 줄로 적으면 나중에 구분할 근거가 사라진다 — **이 우회는 막지 못하고
  기록만 한다**는 것이 이 층의 한계다.
- **마커는 아무나 쓰지 못한다.** 마커는 텍스트일 뿐이고 head sha 는 공개 정보라, 저자를 안 가르면
  아무 GitHub 사용자나 코멘트 하나로 「리뷰 통과」를 만들어 낸다. 읽는 것은 멤버 축
  (OWNER·MEMBER·COLLABORATOR) 또는 이 레포의 워크플로 자신이 쓴 코멘트뿐이고, 그 판정은
  `review_record.is_trusted_author` **한 곳**이다 — 같은 마커를 읽는 자리가 둘이 되면 한쪽만
  조여도 다른 쪽이 열려 있다.
- 문서 전용 PR 은 리뷰 마커를 면제한다(루트 `CLAUDE.md` 의 면제 규약). **게이트는 면제하지
  않는다.** 문서에 코드가 한 파일이라도 섞이면 면제가 통째로 사라진다.
- **「문서 전용」이 무엇인지는 감사가 정하지 않는다.** 면제를 실제로 만들어 내는 것은
  `scripts/review_notice.py` 의 판정이고(그것이 App 승인·리뷰 건너뜀을 건다), 감사는 그 판정을
  그대로 부른다. 감사가 자기 정의를 따로 두면 정당하게 착륙한 문서 PR 이 **영구히** 위반으로
  적히고 — 고칠 방법도 없다(그 PR 에는 마커를 달 경로가 애초에 안 돈다) — §4.3 이 적은
  「상시 빨간 감사」 상태가 그대로 만들어진다. `verify_docs_only_lockstep.py` 가 그 재발을 막는다.

## 4. 이 교환이 성립하지 않게 되는 조건

다음 중 하나라도 참이 되면 이 문서의 판단을 다시 해야 한다.

1. **레포에 두 번째 사람이 생긴다** — 그 순간 위협 모델의 전제(적대자 없음)가 깨진다.
2. **되돌리기가 비싸지는 것이 main 에 실린다** — 배포 트리거, 마이그레이션 자동 실행 등.
3. **감사 잡이 오래 빨간 채로 방치된다** — 발각이 행동으로 이어지지 않으면 발각이 아니다.
4. **결제 결정이 바뀐다** — ruleset 이 돌아오면 이 대체층은 중복이 되고, 그때는 예방으로 되돌린다.

## 5. 전환·되돌리기

전환은 **리드가 실행한다.** 아래 순서를 그대로 따르면 되고, 각 줄의 명령은 그대로 쳐서 같은
결과가 나와야 한다.

### 전환 전 — 대체층이 다 서 있는가

```bash
# ① 예방·발각 (P1·P2·P3) 이 main 에 있는가
git show origin/main:scripts/reject_push_to_main.py >/dev/null && echo "P1 있음"
git show origin/main:scripts/audit_main_landing.py  >/dev/null && echo "P2 있음"

# ② 탐지 대체 (CodeQL·secret scanning) 가 main 에 있는가
git show origin/main:scripts/judge_codeql_sarif.py  >/dev/null && echo "CodeQL 대체 있음"
git show origin/main:scripts/install_gitleaks.sh    >/dev/null && echo "히스토리 스캔 있음"

# ③ 이 클론의 훅이 실제로 걸려 있는가 (설치한 클론에만 산다)
ls "$(git rev-parse --git-path hooks)"/pre-commit "$(git rev-parse --git-path hooks)"/pre-push
```

셋 다 나와야 넘어간다. 하나라도 없으면 **그 층 없이 전환하는 것**이다.

### 전환 — 네 걸음

```bash
# 1. CI 를 self-hosted 로 옮긴다. private 이 되면 GitHub-hosted 분이 과금되기 때문이다.
#    **전환보다 먼저** 해서, 러너가 실제로 잡을 받는지 public 상태에서 확인한다.
gh variable set CI_RUNNER --body ci
#    확인: 아무 PR 이나 깨워 잡이 self-hosted 에서 도는지 본다
gh run list --limit 3 --json databaseId,status

# 2. 전환
gh repo edit Danwoo/trading-lab --visibility private --accept-visibility-change-consequences

# 3. 즉시 확인 — 무엇이 사라졌나
gh api repos/Danwoo/trading-lab --jq '{visibility, security: .security_and_analysis}'
gh api repos/Danwoo/trading-lab/rulesets            # 403 이면 ruleset 이 사라진 것 (예상대로)
gh api repos/Danwoo/trading-lab/code-scanning/alerts # 403 이면 코드 스캐닝이 사라진 것 (예상대로)

# 4. 대체층이 실제로 도는지 — main 에 한 번 착륙시켜 본다 (문서 한 줄이면 된다)
#    `audit: main 착륙` · `CodeQL` · 히스토리 스캔 셋이 초록인지 확인
gh run list --workflow ci.yml --limit 3
gh run list --workflow codeql.yml --limit 2
```

**3번에서 403 이 안 나오면 그게 이상한 것이다** — 사라졌어야 할 것이 남아 있다는 뜻이고,
그때는 요금제·설정을 다시 본다.

### 되돌리기

```bash
gh repo edit Danwoo/trading-lab --visibility public --accept-visibility-change-consequences
gh variable delete CI_RUNNER          # CI 를 다시 호스티드로 (public 은 무료)
gh api repos/Danwoo/trading-lab/rulesets --jq '.[].name'   # `main protection` 이 돌아왔나
```

**ruleset 이 삭제가 아니라 비활성이라 즉시 복원된다는 것은 가정이다** — 전환 직후 3번에서
403 을 확인했다면, 되돌린 뒤 이 명령이 `main protection` 을 다시 내는지까지 봐야 그 가정이
확인된다. 안 나오면 ruleset 을 손으로 다시 만들어야 하므로, **전환 전에 현재 ruleset 정의를
받아 둔다**:

```bash
gh api repos/Danwoo/trading-lab/rulesets --jq '.[0].id' \
  | xargs -I{} gh api repos/Danwoo/trading-lab/rulesets/{} > /tmp/main-protection.json
```

### 전환 뒤에도 남는 구멍

| 없어지는 것 | 대체 | 남는 구멍 |
|---|---|---|
| PR·승인 필수 | pre-push 훅(예방) + 착륙 감사(발각) | `--no-verify` 로 지나갈 수 있다 — 막지 못하고 발각만 한다 |
| 코드 스캐닝 경보 | SARIF 를 CI 가 읽어 판정 | Security 탭의 이력·추세는 없다 |
| secret scanning | 작업 트리·히스토리·push 직전 세 겹 | 서버가 push 를 **거부**하는 층이 없다. 파트너 토큰 유효성 검사도 대체가 없다 |
| main 삭제 금지 | **없다** | §3 참고 |
