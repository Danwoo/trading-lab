# CI·리뷰 구조 재설계 — 판단은 Orca, 기록은 GitHub (설계)

> 상태: 승인됨 (brainstorming) · 작성 2026-08-08

## 결론

**CI 파이프라인에서 「에이전트가 판단하는 일」을 전부 걷어낸다.** CI 는 결정론적 검사만 돌리고,
리뷰는 GitHub 이 원래 갖고 있는 **PR 리뷰**(Approve / Request changes)로 기록한다. 라벨이 하던
상태 저장 역할은 GitHub 의 리뷰 상태와 required checks 로 옮기고, 라벨에는 **위험도 하나만** 남긴다.

워크플로 **11개 → 7개** (CI 계획 완료 시점) → **5개** (automation 계획이 리뷰어 기동을
가져간 뒤). `cross-review.yml` 은 리뷰어 기동 209줄이 Orca 쪽으로 옮겨져야 비므로 CI 계획만으로는
지울 수 없다 — 그 의존을 초안이 빠뜨려 「5개」가 도달 불가 목표였다.
**워크플로 YAML 총량 → 약 1,000줄** (진단 시점 3,705줄, #26 머지 후 3,797줄) — 단, 사라진 bash 는 `scripts/` 로
옮겨간 것이지 없어진 것이 아니다. 얻는 것은 줄 수가 아니라 **로컬 실행·단위 테스트 가능성**이다.
사라지는 것은 흉내 내던 것들이다 —
`merge-router`(GitHub 이 안 막으니 우리가 흉내), `review-gate`(라벨 위생), 헤드리스 이중 경로,
폴백 체인, 워크트리 생명주기 bash.

## 문제 — 실측

### 부피가 어디 있나

```
워크플로 11개 · 총 3,705줄 · 인라인 bash 1,248줄   ← 진단 시점(2026-08-08 오전). #26 머지 후 3,797줄
  cross-review.yml   2,020줄 (실코드 1,113 · bash 930)
  merge-router.yml     291줄
  frontend-ci.yml      258줄
  ci.yml               342줄
  board-status.yml     170줄 · review-gate.yml 151줄
  repo-scans.yml       159줄 · plan-* 3파일 227줄 · orphaned-branch-scan 87줄

검증 그물 (ci·frontend-ci·repo-scans):   759줄
하네스 기계 (나머지 8개):               2,946줄  ← 79%
```

`cross-review.yml` 의 `review` 잡 618 실코드줄 내역:

| 블록 | 실코드 | 성격 |
| --- | --- | --- |
| 입력 번들 준비 | 230 | 신뢰 경계 (base 에서 루브릭 읽기) |
| `run_orca` | 130 | Orca 워커 기동·폴링 |
| `try_candidate` + 체인 루프 | 81 | 폴백 체인 |
| 한도 감지·분류 6함수 | 57 | 자동화 완결성 |
| 터미널 준비·접수 | 43 | #11 이 여기 |
| 워크트리 생명주기 | 36 | Orca 재구현 |
| 헤드리스 실행 | 30 | 이중 경로 |
| **판정 수집** | **11** | 실제로 리뷰 판정을 읽는 부분 |

**「저자 아닌 컨텍스트가 판정을 남긴다」를 만드는 부분은 11줄이고 나머지는 자동화의 완결성이다.**

### 네 가지 증상, 뿌리는 둘

리드가 겪은 것: ① 라벨이 서로 덮어쓰기·되돌려짐 ② 머지가 언제 되는지 예측 불가
③ 체크가 빨간데 원인 모름 ④ 에이전트끼리 같은 PR·브랜치에서 부딪힘.

| 뿌리 | 실측 |
| --- | --- |
| **(A) 라벨이 상태인데 writer 가 5개** | `cross-review`·`merge-router`·`review-gate`·`plan-label`·`plan-label-issue` 가 같은 라벨 집합을 쓴다. 조정 장치는 없다 |
| **(B) 로직이 YAML 안 bash** | 1,248줄. 로컬 실행 불가, 단위 테스트 없음, 실패하면 러너 로그가 유일한 창 |

### GitHub 이 이미 막고 있다 — 초안이 이것을 반대로 적었다

> **정정 (2026-08-08).** 이 설계의 초안은 「브랜치 보호가 없어 18개 체크가 전부 자문용이다」로
> 썼고, 근거로 아래 404 를 실었다. **그 판정이 틀렸다.**
>
> ```
> $ gh api repos/Danwoo/trading-lab/branches/main/protection
> {"message":"Branch not protected", "status":"404"}     ← 초안이 근거로 쓴 것
> ```
>
> 이 엔드포인트는 **classic 브랜치 보호만** 본다. 이 레포는 **ruleset** 으로 보호돼 있고,
> ruleset 은 여기 나오지 않는다. 404 는 「보호 없음」이 아니라 「classic 보호 없음」이었다.
> **404 하나로 부재를 단정한 것이 오류의 형태다** — 같은 사실을 다른 도구로 한 번 더 재지 않았다.

실제 상태 (2026-08-08 실측):

```
$ gh api repos/Danwoo/trading-lab/branches/main --jq .protected
true

$ gh api repos/Danwoo/trading-lab/rulesets
20552422  main protection  target=branch  enforcement=active

$ gh api repos/Danwoo/trading-lab/rules/branches/main --jq '[.[].type]|unique'
["deletion","non_fast_forward","pull_request","required_status_checks"]
```

| 규칙 | 값 |
| --- | --- |
| `required_status_checks` | **`test: repo-scan` · `test: repo-scan-app` · `test: ci-coverage`** |
| `pull_request` → `required_approving_review_count` | **0** |
| `pull_request` → `require_last_push_approval` | false |
| `pull_request` → `dismiss_stale_reviews_on_push` | false |

**따라서 이 설계에서 바뀌는 것과 안 바뀌는 것이 갈린다.**

- **바뀜**: 「required checks 를 새로 건다」가 아니라 **「이미 있는 ruleset 에 게이트 잡을 추가한다」**
  이다. classic 보호를 `PUT` 으로 새로 만들면 ruleset 과 두 겹이 된다 — 하지 않는다.
- **바뀜**: 테스트 3종은 이미 머지를 막는다. 「아무것도 안 막는다」를 전제한 서술은 전부 무효다.
- **안 바뀜**: `required_approving_review_count = 0` 이므로 **승인은 요구되지 않는다.**
  설계 결정 「Require approvals 를 켜지 않는다」는 **현행 상태와 이미 일치**한다.
- **안 바뀜**: 그래서 `reviewDecision` 은 계속 비어 있다 (아래).

### 우리가 흉내 낸 것 중 GitHub 에 이미 있는 것 넷

| 우리 | GitHub |
| --- | --- |
| `review: passed` 라벨 + 판정 마커 | **Approve / Request changes** |
| `review: needed` 라벨(만들려던 것) | **draft → Ready for review** |
| `merge-router.yml` 291줄 | `gh pr merge --auto` |
| `human: merge` 대기열 | **Approve 유무** (단, 이 설계는 Require approvals 를 켜지 않고 자동 머지 arm 신호로만 쓴다 — §4) |

실측: 열린 PR 전부 `reviewDecision` 이 비어 있다. **이유는 「리뷰 기능을 안 썼다」가 아니다** —
ruleset 의 `required_approving_review_count` 가 **0** 이라 GitHub 이 그 필드를 아예 계산하지
않는다. 승인을 요구하는 규칙이 없으면 리뷰가 존재해도 `reviewDecision` 은 빈 채로 남는다.
**이 구별이 중요하다**: 재작업 automation 이 `reviewDecision` 을 신호로 쓰면 이 설계 아래에서
영원히 「할 일 없음」이 되고, 그 사실이 조용한 초록으로 덮인다 (automation 계획의 불변식).
draft PR 도 10건 중 0건이다. 그런데 `cross-review.yml` 은 이미 `!draft` 가드를 갖고 있다 (`grep -n 'draft' …`) —
**설계는 draft 를 전제했는데 아무도 쓰지 않았다.**

## 결정

### 1. 경계 — 결정론적인 것만 CI 안

CI 파이프라인은 「코드가 맞으면 반드시 초록」이 성립하는 것만 돌린다(2026-08-06 결정 유지).
**에이전트가 코드를 읽고 판단하는 행위는 빌드 단계가 아니라 사람 리뷰어가 하던 일의 자동화**이므로
CI 밖(Orca)에 둔다.

- **CI 안**: `ci.yml` · `frontend-ci.yml` · `repo-scans.yml` + 기록기 1개
- **CI 밖**: Orca 의 워커와 리뷰어. 리드가 Projects 패널에서 눈으로 본다

### 2. 리뷰 = GitHub 네이티브 PR 리뷰

리뷰어는 판정을 PR **리뷰**로 남긴다 — `Approve` 또는 `Request changes`. 본문이 리뷰 내용이다.

- 좋으면 → 승인 → (저위험이면) 자동 머지
- 피드백이면 → `Request changes` → **자동 머지가 안 걸린다** → 저자가 고쳐 push → 재리뷰

**「Require approvals」는 켜지 않는다** (아래 결정 로그). 설계 시점에는 「그래서 `Request changes`
는 사람 머지를 막지 않는다 — 자동 경로만 멈춘다」로 적었는데, **실측은 다르다** (2026-08-10 정정,
#23 Task 10): ruleset 에 `pull_request` 규칙이 있으면 `required_approving_review_count` 가 0 이어도
살아 있는 `CHANGES_REQUESTED` 리뷰가 머지를 막는다 (PR #68 실측 — 체크 전부 초록 +
mergeStateStatus=BLOCKED). 리뷰 판정이 이빨을 가진 것 자체는 의도에 부합해 수용하고, 리뷰 경로가
죽었을 때의 출구(교착 해제)를 §4 에 둔다.

**승인이 낡았는지는 기록기가 본다.** 승인을 required 로 걸지 않으므로 GitHub 의
「dismiss stale approvals」에 기댈 수 없다. 대신 리뷰 API 가 리뷰마다 `commit_id` 를 주므로,
자동 머지를 arm 하기 전에 **`review.commit_id == pr.headRefOid`** 를 대조한다. 지금 `sha=` 마커와
`check-review-dispatch` 가 손으로 지키던 규칙이 **결정론적 한 줄 비교**가 된다.

**승인 신원**: GitHub 은 자기 PR 자기 승인을 금지한다. Orca 리뷰어는 로컬 `gh` 를 쓰므로 리드
계정으로 나가 자기 PR 이면 거부된다. 따라서 **리뷰어는 판정 코멘트를 남기고, 기록기 워크플로가
`github-actions[bot]` 명의로 `gh pr review` 를 대행**한다. 봇 승인은 required approval 로 센다.

> 기록기는 파이프라인이 아니다 — 코멘트를 읽어 리뷰로 옮겨 적는 것뿐이라 결정론적이다.

### 2-1. 봇 PR — 자동 머지 대상이다

2026-08-08 리드 결정. dependabot PR 은 연결 이슈가 없어 `risk` 를 선언할 자리가 없다. 종전 규칙
(미선언 = 고위험 = 사람 대기열)을 그대로 두면 **봇 PR 은 영원히 사람 손을 탄다** — 2026-08-07
하루에 9건이 열렸다. 따라서 **저자가 봇이면 위험 선언 없이도 자동 머지 조건을 만족**한 것으로 본다.

**리뷰는 여전히 필요하다.** 봇 PR 도 `Approve` 가 있어야 자동 머지된다 — 위험 선언만 면제되는
것이지 리뷰가 면제되는 것이 아니다.

**단, major 버전 상승은 사람 경로로 뺀다** (2026-08-08 리드 결정). patch·minor 는 자동으로
흐르고 major 만 리드가 본다.

근거는 2026-08-07 실측이다. 리뷰어가 판정 첫 줄에 올린 사실이 둘 있었다 —
`cryptography 48→50` 이 x86_64 macOS·32비트 Windows 휠을 삭제했고(템플릿을 복사해 쓰는 사람의
환경 요구가 올라감), `pyjwt 2.12→2.13` 이 빈 HMAC 시크릿을 거부하기 시작했다(dev 에서 `.env`
없이 띄우던 경로가 막힘). 둘 다 `merge_ok` 였지만 **리드가 읽고 넘어갈 값어치가 있는 사실**이었고,
자동 머지였다면 아무도 읽지 않았을 것이다.

> **이 정책은 그것을 만들게 한 사례 둘 중 하나를 못 잡는다 — 알고 고른 것이다 (2026-08-09 리드 결정).**
>
> 초안은 위 두 사례를 「전부 major」로 적었는데 **사실이 아니었다.**
> `cryptography 48.0.1 → 50.0.0` 은 major 지만 `pyjwt 2.12.1 → 2.13.0` 은 **minor** 다
> (major 자리 `2` 가 안 바뀐다). 정책을 만들게 한 근거의 절반이 정책 밖에 있다는 뜻이다.
>
> 그 사실을 대고 다시 물었고, 리드는 **㉠ 그대로**를 골랐다 — **"사람 부담을 최소화하고 중요한
> 의사결정에 대해서만 하면 된다."** 기각한 대안: ㉡ minor 도 사람(자동 비율이 크게 줄어 부담이
> 늚), ㉢ 리뷰 판정 내용으로 가름(가장 정확하나 마커에 신호를 실어야 해 구현이 늚).
>
> **감수하는 것**: pyjwt 건 같은 **minor 의 동작 변경은 자동으로 흐른다.** 그런 사실은 리뷰
> 코멘트에 남지만 아무도 안 읽을 수 있다. 이 비용이 실제로 물렸을 때 — minor 자동 머지가
> 무언가를 깨뜨렸을 때 — ㉢ 을 다시 상정한다.

비용: 2026-08-07 에 열린 dependabot PR 9건 중 major 는 `cryptography` **2건**
(web-mcp · template-mcp), 나머지 7건은 minor·patch 다.

판별은 **PR 제목 파싱**으로 한다. Dependabot 제목 형식이 일정하다(실측):

```
build(deps): bump cryptography from 49.0.0 to 50.0.0 in /single-agent-service
build(deps): bump pyjwt from 2.12.1 to 2.13.0 in /template-mcp-service
```

`from A to B` 의 major 자리를 비교한다. `dependabot/fetch-metadata` 액션을 쓰지 않는 이유는
기록기가 `issue_comment` 이벤트로 돌아 그 액션이 기대하는 `pull_request` 컨텍스트가 없기
때문이다. 제목 형식이 바뀌면 판별이 `None` 이 되고 **그때는 자동 머지를 arm 하지 않는다**
(fail-closed).

### 3. 상태 — 라벨은 위험도만

라벨이 하던 상태 저장을 GitHub 이 가져간다. 남는 라벨은 **`risk: low|high` 하나**이고, 그
writer 는 이미 하나다(`gate declare`). `review: passed`·`review: unable`·`review: needs-work`·
`human: merge` 는 **없앤다** — GitHub 리뷰 상태가 그 일을 한다.

### 4. 머지 — 두 문장으로 줄인다

1. **required checks(테스트)가 초록이면 사람은 언제든 머지할 수 있다** — GitHub 이 판정한다
2. 거기에 **승인 + `risk: low`** 가 더해지면 `gh pr merge --auto` 로 자동 머지된다

리뷰 인프라가 죽으면 **자동 머지가 안 될 뿐** 사람 머지는 열려 있다. AI 판정이 작업 정지 장치가
되지 않는다(2026-08-06 결정의 취지 유지).

**「Require approvals」는 켜지 않는다** (2026-08-08 리드 결정). 켜면 승인 없이는 사람도 머지할 수
없어 1번이 깨지고, AI 리뷰가 죽었을 때 그대로 작업 정지 장치가 된다. 승인은 **자동 머지를 arm
하는 신호**일 뿐이고, 사람의 머지 권한은 테스트 초록에만 걸린다.

**교착 출구 — 리뷰 경로가 죽으면 dismiss 가 유일한 출구다** (2026-08-10, #23 Task 10). 승인
하한이 0 이어도 ruleset 의 `pull_request` 규칙은 살아 있는 `CHANGES_REQUESTED` 리뷰를 존중해
머지를 막는다 (§2 정정 참조). 새 판정은 재리뷰(push → cross-review → 기록기)가 내므로, **리뷰
경로가 죽으면(kimi·codex 한도 + claude 폴백 실패 등) 낡은 `CHANGES_REQUESTED` 를 걷어낼 자동
경로가 없다** — 영영 못 미는 교착이 된다. 그때는 사람이 리뷰를 해제한다:

```bash
gh api repos/<owner>/<repo>/pulls/<N>/reviews          # 리뷰 ID 확인
gh api -X PUT repos/<owner>/<repo>/pulls/<N>/reviews/<리뷰ID>/dismissals \
  -f message="<사유>" -f event=DISMISS
```

같은 안내가 빨간 체크 `review: verdict (비게이트)` 의 로그(`scripts/review_verdict.py` 출력)에도
실린다 — 막힌 사람이 처음 여는 자리가 거기다.

**판정은 체크로도 보인다** (#23 Task 10). `review: verdict (비게이트)` 가 판정을 체크 색으로
확정한다 — `merge_ok` 만 초록, `needs_changes`·`unable`·판정 미산출은 빨강 (fail-closed).
required 가 아니고 `test: ` 접두도 아니라서 1번(사람 머지)·자동 머지 어느 쪽도 막지 않는다 —
「초록인데 못 민다」(PR #68 실측)를 체크 목록에서 읽히게 하는 알림이다.

**required checks 에 무엇을 넣나**: 테스트 9종을 개별로 걸지 말고 「전부 초록인가」를 대표하는
**게이트 잡 하나**만 required 로 건다. pending 창이 하나로 줄어 Orca 머지 버튼이 닫혀 있는
시간이 짧아진다.

**자동 머지 arm 조건** (전부 참일 때만):

1. required 게이트 잡 초록
2. `Approve` 리뷰가 있고, 그 `commit_id` 가 현재 head 와 같다
3. `risk: low` — 또는 **저자가 봇이면서 major 상승이 아니다** (§2-1)

**그리고 arm 을 푸는 자리가 반드시 있어야 한다 — 초안이 이것을 빠뜨렸다.**

arm 조건만 정하고 disarm 을 안 만들면 이렇게 뚫린다: 승인 → `commit_id == head` 대조 통과 →
arm. **이때 게이트 잡이 아직 도는 중.** 저자가 sha B 를 push. auto-merge 는 살아 있고, B 에서
게이트가 초록이 되는 순간 **B 가 머지된다 — B 를 본 사람이 아무도 없다.**

가상이 아니다. automation 계획의 재작업 워커가 **설계상 같은 브랜치에 push** 한다. 루프가
닫히는 순간 이 push 가 상시화된다.

지금은 `merge-router.yml` 이 `synchronize`·`edited`·`unlabeled` 에서 `--disable-auto` 로 푼다.
세 갈래를 새 설계에서 각각 누가 받는지 보면 **push 만 비어 있다**:

| 갈래 | 새 설계에서 |
| --- | --- |
| base 변경 | GitHub 이 네이티브로 해제한다 |
| 판정 회수(`unlabeled`) | 라벨이 없어지므로 정당하게 소멸 |
| **push(`synchronize`)** | **없음 — 만들어야 한다** |

받는 곳이 없는 이유가 셋 겹친다. ① 기록기는 `issue_comment` 트리거라 push 에 안 뜬다.
② GitHub 은 **쓰기 권한 없는** 사람의 push 에만 auto-merge 를 해제한다 — 우리 워커는 권한자다.
③ 네이티브 stale-approval 회수도 못 쓴다: `required_approving_review_count = 0` 이라
`require_last_push_approval` 을 켜도 무효이고, 승인을 required 로 안 켜는 것이 결정이다.

**따라서 `pull_request: [synchronize]` 를 듣는 disarm 경로를 기록기에 함께 둔다.**
`commit_id == head` 대조는 **arm 시점 1회** 판정이라 그것만으로는 부족하다 — 지금 규칙은
push 마다 재평가되는 disarm 이 함께 지탱하고 있었다. 한쪽만 옮기면 그물이 실패하는 게 아니라
**조용히 통과**한다.

**경로 필터 처리**: 워크플로 레벨 `on.paths` 를 **잡 레벨 `if:`** 로 바꾼다. 워크플로째 건너뛴
체크는 영영 pending 이라 머지를 막지만, 조건으로 건너뛴 잡은 `skipped` 를 보고하고 GitHub 은
`success`·`skipped`·`neutral` 을 통과로 센다.

### 5. 루프를 닫는 두 축

리뷰만 고쳐서는 「AI 가 주도적으로 진행」이 성립하지 않는다. 공백 점검 결과 자동으로 도는 구간은
`작업 → 테스트 → 판정 → 머지`뿐이고 그 앞뒤가 비어 있다.

**축 ① — Orca automation 3종**

| automation | 트리거 | 하는 일 |
| --- | --- | --- |
| 워커 기동 | 착수 표식이 붙은 이슈 (**표식을 무엇으로 할지 미정 — 구현 1단계에서 정한다**. 후보: 마일스톤 소속 + 담당자 미지정, 또는 전용 라벨) | 워크트리 생성 → 오더 전달 |
| **재작업 기동** | `pull_request_review` = `changes_requested` | 그 PR 의 워커를 깨운다 |
| 정리 | 머지된 PR | 워크트리 회수 |

**재작업 기동이 가장 중요하다.** 지금은 리뷰가 「수정 필요」를 내는 순간 흐름이 멈춘다 — 워커는
알림을 안 받고 폴링도 안 한다. 실제 개발자는 알림을 받고 돌아오는데 우리 워커에겐 수신자가 없다.

**축 ② — 정체 감지**

리뷰를 CI 밖으로 옮기면 **「아직 안 한 것」과 「죽어서 못 한 것」이 화면에서 같아진다.** 이 레포의
교훈(「실패가 조용히 성공처럼 보이는 자리를 의심한다」)에 정면으로 걸리므로, PR 이 일정 시간
리뷰 없이 서 있으면 드러내는 주기 검사를 둔다. **검사한 PR 수를 항상 출력**해 「대상 없음」과
「아무것도 안 봤음」이 구분되게 한다.

### 6. 걷어내는 것

> **이 표는 「무엇을 왜 걷어내는가」이지 진행 상태가 아니다.** 어디까지 걷어냈는지는
> **이슈 #23 의 진행 표**가 정본이다 — 문서에 완료 표시를 달면 다음 것이 착륙할 때마다 낡는다.

| 대상 | 근거 |
| --- | --- |
| `merge-router.yml` (291줄) | 존재 이유가 「GitHub 이 안 막으니 흉내」였다 |
| `review-gate.yml` (151줄) | 라벨 위생 — 라벨이 상태가 아니게 되면 대상이 없다 |
| 헤드리스 이중 경로 (30 실코드) | **게시된 판정 코멘트 21건 전부 `orca`**(2026-08-09 전수 재집계). 판정 코멘트가 안 달린 실행은 이 방법으로 안 보이므로 「미사용」이 아니라 「관측 범위 내 미사용」이다 |
| ~~폴백 체인·한도 감지~~ | **철회 (2026-08-08 리드 정정)** — kimi·codex 한도 시 claude 가 이어받는 것이 의도된 설계다. 실제 판정자는 하나이므로 「한 리뷰를 여러 모델이 이어받아 계속 손대는 것」과 다르다 |
| 워크트리 생명주기 bash (36) + **시작 스윕** (`grep -n '고아 리뷰 워크트리 시작 청소' .github/workflows/cross-review.yml`) | **아래 「스윕 사건」 참조** — CI 가 에이전트 살림을 관장하면 안 된다. 정리는 automation 계획 Task 4 가 연결 PR 상태로 맡는다 |
| `plan-*` 3파일 | 1파일로 통합 (로직 유지) |
| `board-status.yml` (170줄) | **삭제 확정** (2026-08-08 리드 결정). fail-open 이라 초록이 「했다」를 보장하지 못했다 |

### 7. bash 를 `scripts/` 로

워크플로는 스크립트를 부르기만 한다. 밖의 표준 권고와 일치한다("Keep shared scripts in
`scripts/` to avoid huge inline bash"). 얻는 것은 **로컬 실행과 단위 테스트**다 — 「체크가 빨간데
원인 모름」이 여기서 풀린다.

`route` 잡의 저자 판별·교차 모델 배정(205줄)은 **순수 판정 코드**라 그대로 옮기면 CI 밖에서도
동일하게 돈다. 교차 모델 리뷰는 유지한다 — 밖에서도 유효성이 보고된 방향이다.

## 근거 — 이번 설계를 만든 실측 셋

### #11 — 준비·접수 판정 신호가 죽어 있다

`wait_agent_ready` 는 프라이머를 보낸 뒤 `term_cursor`(= `latestCursor`)가
자라기를 기다린다. **Claude Code TUI 는 화면을 제자리에서 다시 그려 이 값이 움직이지 않는다.**

살아 있는 유휴 리뷰어에 같은 절차를 손으로 돌린 결과:

```
base(프라이머 전) = 1
t+5s = 1   t+10s = 1   t+15s = 1   t+20s = 1   t+25s = 1   t+30s = 1
```

대조군 — 20분 넘게 일하며 58k 토큰을 쓰고 PR 을 연 워커 터미널도 `latestCursor = 1`.
따라서 `now > base` 는 claude 경로에서 **영원히 참이 되지 않는다.** 타임아웃을 늘려도 무효다.
kimi 경로가 통과하는 것은 결과로만 안다(워크트리가 스윕돼 커서 미측정).

### 스윕 사건 — CI 가 일하는 에이전트를 죽였다

리뷰어 넷에 지시를 넣고 6분 뒤, dependabot PR 두 건이 5초 간격으로 들어와 `cross-review` 가 돌았고
그 시작 스윕이 **일하는 중인 리뷰어 다섯을 회수**했다.

```
회수: review-15-claude (마지막 활동 52360s 전)
회수: review-16-claude (마지막 활동 52262s 전)
회수: review-17-claude (마지막 활동 52263s 전)
회수: review-18-claude (마지막 활동 52169s 전)
회수: review-7-claude  (마지막 활동 52360s 전)
고아 스윕: review-* 후보 5건 검사 · 회수 5건 · 보존 0건 · 실패 0건
```

「52,360초 전」 = 14.5시간. 6분 전에 지시를 받았는데도 그렇게 읽혔다. 원인은 Orca 의
`lastActivityAt` 이 **생성 시각에 박히고 터미널 활동으로 갱신되지 않는 것**이다:

```
docs-align-move-claude   lastActivity=60,262s 전  created=60,262s 전  같은값=True
review-dep-6-10-claude   lastActivity=56,560s 전  created=56,560s 전  같은값=True
```

즉 스윕의 안전 조항(「살아 있는 남의 리뷰를 죽이지 않는다」)은 **읽는 값이 안 움직여 무력**하다.
`보존 0건`이 그것을 보여준다. 부수 발견: 스윕 필터가 `^review-[0-9]+-` 라 `review-dep-…` 는
후보에 안 잡힌다 — **이름 규칙이 문서에 없는 방식으로 생사를 가르고 있다.**

**이것이 「CI 가 에이전트 살림을 관장하면 안 된다」의 실물 근거다.**

### 진단 가능했던 이유

위 스윕을 명령 하나로 짚을 수 있었던 것은 이 레포가 「검사한 대상 수를 세어 출력에 남겨라」를
지켰기 때문이다(`후보 5건 검사 · 회수 5건 · 보존 0건`). 새로 짜는 것들도 같은 규율을 따른다.

## 남는 위험 — 설계로 못 닫고 재봐야 하는 것

| 위험 | 성격 | 되돌리기 |
| --- | --- | --- |
| 브랜치 보호를 걸면 required check 가 도는 동안 `mergeStateStatus=BLOCKED` → **Orca 머지 버튼이 닫힌다** | 올바른 동작이나 체감은 「또 막혔다」. Orca 가 `UNKNOWN` 창에서 어떻게 구는지는 문서에 없다 | **설정 토글 — 1초** |
| 봇 승인이 required approval 로 세는 것 | 문서·다수 사례 근거 있음. 이 레포에서 실측 안 함 | 필요 시 required approvals 를 끔 |
| automation 이 죽으면 아무도 모름 | 축 ②(정체 감지)가 잡도록 설계했으나 그 자체가 죽으면? | 주기 검사 결과를 사람이 보는 곳에 낸다 |
| fork PR 은 리뷰어를 안 띄운다 | 공개 레포 — 남의 PR 로 리드 노트북에서 에이전트를 띄우면 원격 코드 실행이 된다. 지금 CI 가드를 **디스패처가 그대로 들고 가야** 한다 | 정책으로 유지 |
| 봇 PR(dependabot)은 이슈가 없어 `risk` 미선언 → 자동 머지 대상이 아니다 | 오늘 하루 9건이 열렸다 | 봇 PR 위험 정책을 따로 정한다 — **미결** |

## 이행 순서

각 단계 끝에서 기동·머지가 깨지지 않아야 한다.

1. **`scripts/` 이전** — `cross-review.yml` 의 bash 를 실행 가능한 스크립트로. 동작 동일, 로컬 실행 확보
2. **#11 수정** — 준비·접수 판정을 프롬프트 박스 상태로. **claude·kimi 두 경로에서 각각 재현 검증**
3. **헤드리스·폴백 삭제** — 소비자(`publish` 안내문·`review-gate` 라벨) 함께 정리
4. **경로 필터 전환** — `on.paths` → 잡 레벨 `if:`. 문서 PR 로 `skipped` 가 통과로 세는지 확인
5. **브랜치 보호(required = 게이트 잡 하나, approvals 없음) + auto-merge** — 여기서
   **Orca 머지 버튼을 30분 써 본다.** 체감이 나쁘면 보호를 끈다(토글 1초)
6. **리뷰를 네이티브 PR 리뷰로** — 기록기 워크플로 + 라벨 정리
7. **automation 3종 + 정체 감지** — 루프를 닫는다
8. **`merge-router`·`review-gate`·`board-status` 삭제** · `plan-*` 통합

## 완료 판정

- 리드가 이슈 하나를 세우고 **손을 떼면** 워커 기동 → PR → 리뷰 → (승인 또는 수정 요청 → 재작업) →
  머지까지 돈다. 사람이 끼는 자리는 **고위험 승인과 최종 머지 버튼뿐**이다
- 체크가 빨갛게 나면 **로컬에서 같은 스크립트를 돌려 재현**할 수 있다
- 라벨이 덮어써져도 머지 판정이 흔들리지 않는다
- 리뷰어가 못 뜬 것이 **화면에 드러난다** — 조용히 넘어가지 않는다
- 워크플로 4~5개 · CI 총 줄 수 약 1,000줄

## 결정 로그 (2026-08-08 리드 판단)

| 항목 | 결정 |
| --- | --- |
| `board-status.yml` | **삭제** — fail-open 이라 초록이 「했다」를 보장하지 못했다 |
| 봇 PR 위험 정책 | **자동 머지 대상, 단 major 는 사람 경로** — 위험 선언만 면제, 리뷰는 그대로 필요 (§2-1) |
| 「Require approvals」 | **켜지 않는다 (㉠)** — 승인은 자동 머지 arm 신호일 뿐, 사람 머지는 테스트 초록에만 걸린다 |

## 남은 미결

1. **워커 기동 automation 의 착수 표식** — automation 계획 Task 2 에서 `agent: ready` 라벨로
   확정했다. 다른 표식이 낫다고 보시면 그때 바꾼다

## 관련

- 이슈 #11 — cross-review 접수 판정 결함 (이 설계의 2단계가 닫는다)
- 이슈 #14 — Dependabot 알림이 매니페스트 10개 중 4개만 본다
- 결정 로그 2026-08-06 「CI 체크 = 결정론적인 것만」 — 이 설계가 그 취지를 유지한다
