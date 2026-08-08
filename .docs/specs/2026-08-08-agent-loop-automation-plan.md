# 에이전트 루프 자동화 구현 계획 — 이슈에서 머지까지 손을 떼고 돈다

> **에이전트 워커에게:** 이 계획은 **task 단위로** 구현한다. 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** 리드가 이슈를 세우고 손을 떼면 워커 기동 → PR → 리뷰 → (수정 요청 → 재작업) → 머지까지
사람 없이 돈다. 사람이 끼는 자리는 **고위험 승인과 최종 머지 버튼**뿐이다.

**접근:** Orca automation 3종(워커 기동 · 재작업 기동 · 정리)이 루프의 이음매를 맡고, 정체 감지는
GitHub Actions 가 맡는다 — **Orca 가 죽어도 「멈춰 있다」는 사실은 보여야** 하기 때문이다.

**기술 스택:** `orca-ide automations` · GitHub Actions(cron) · Python 3(stdlib 전용) · `gh` CLI

**설계 정본:** [`2026-08-08-ci-review-architecture-design.md`](2026-08-08-ci-review-architecture-design.md) §5
**선행 계획:** [`2026-08-08-ci-review-architecture-plan.md`](2026-08-08-ci-review-architecture-plan.md)

> **선행 조건**: CI 계획의 Task 7(기록기)이 끝나 있어야 한다. 재작업 기동이 GitHub 의
> `CHANGES_REQUESTED` 리뷰 상태를 신호로 쓰는데, 그 상태를 만드는 것이 기록기다.

## 이 계획이 닫는 공백

공백 점검(설계 문서 §5)에서 드러난 것 중 CI 계획이 손대지 않는 것들이다.

| 공백 | 지금 | 이 계획 |
| --- | --- | --- |
| ① 이슈가 생겨도 워커가 안 뜬다 | 지휘자가 손으로 | Task 2 |
| ③ **「수정 필요」 후 아무도 워커를 안 깨운다** | 없음 — **루프가 안 닫힌다** | Task 3 |
| ④ 워크트리가 쌓인다 | 지휘자가 손으로 | Task 4 |
| ⑤ 리뷰어가 안 뜬 걸 아무도 모른다 | 없음 | Task 5 |

**③이 가장 크다.** 나머지는 「아직 안 만든 것」이지만 ③은 루프가 구조적으로 안 닫히는 자리다.

## 전역 제약

- **automation 은 `risk: low` 로 선언된 이슈만 집는다.** 하드 게이트(`gate declare`/`gate approve`)는
  지휘자의 도구 호출을 가로채는 훅이라 **Orca automation 은 그 훅을 지나가지 않는다.** 고위험을
  automation 이 집으면 게이트가 무력해진다. 고위험은 사람·지휘자가 직접 디스패치한다.
- **fork PR 은 어떤 automation 도 집지 않는다.** 공개 레포다 — 남의 PR 로 리드 노트북에서
  에이전트를 띄우면 원격 코드 실행이 된다. 모든 precheck 에 저장소 대조를 넣는다.
- **한 PR·이슈에 워커 하나.** 잠금은 라벨(`agent: working`)로 하고 **writer 는 automation 하나**다.
- **워크트리 나이로 생사를 판정하지 않는다.** Orca 의 `lastActivityAt` 은 생성 시각에 박히고
  터미널 활동으로 갱신되지 않는다(2026-08-07 실측 — 일하는 리뷰어 5대가 이 때문에 회수됐다).
  정리는 **나이가 아니라 연결된 PR 의 상태**로 판정한다.
- **검사 0건은 통과가 아니다.** precheck·정체 감지는 검사한 대상 수를 세어 출력하고, 기대와
  다르면 실패한다.
- 검증 스크립트는 **stdlib 전용**. 새 `scripts/verify_*.py`·`test_*.py` 는 `repo-scans.yml` 에
  배선해야 `verify_ci_check_coverage.py` 가 통과한다.
- **AI 자기 언급 금지** · **main 직접 커밋 금지** · `git stash`·force push 금지 ·
  포트 3000·3010·8000·5432 불가침 · 개발 DB `fintech` 는 읽기만.

## 파일 구조

| 파일 | 책임 |
| --- | --- |
| `scripts/agent_queue.py` (신규) | GitHub 상태 → 「지금 집을 것」 목록. **순수 판정 + gh 조회** |
| `scripts/test_agent_queue.py` (신규) | 위 순수 판정부의 단위 테스트 |
| `scripts/precheck_worker.sh` (신규) | 워커 기동 automation 의 precheck |
| `scripts/precheck_rework.sh` (신규) | 재작업 기동 automation 의 precheck |
| `scripts/precheck_cleanup.sh` (신규) | 정리 automation 의 precheck |
| `scripts/verify_review_staleness.py` (신규) | 정체 감지 — 리뷰 없이 서 있는 PR |
| `.github/workflows/staleness.yml` (신규) | 위를 cron 으로 돌린다 |
| `.docs/6-도구/에이전트-automation.md` (신규) | 등록된 automation 목록·복구 절차 |

**automation 은 코드가 아니라 등록된 상태다.** 그래서 「무엇이 등록돼 있는가」를 문서로 남기지
않으면 다음 사람이 알 길이 없다 — Task 6 이 그것을 맡는다.

---

## Task 1: 큐 판정을 순수 함수로 만든다

automation 3종이 공유하는 질문은 하나다 — **「지금 무엇을 집어야 하나」**. 이것을 먼저 순수
함수로 만들고 테스트를 붙인다. precheck 셸 스크립트는 이 함수를 부르기만 한다.

**Files:**
- Create: `scripts/agent_queue.py`
- Create: `scripts/test_agent_queue.py`
- Modify: `.github/workflows/repo-scans.yml` (배선)

**Interfaces:**
- Produces:
  - `pick_issue(issues: list[dict]) -> dict | None`
  - `pick_rework(prs: list[dict]) -> dict | None`
  - `pick_cleanup(worktrees: list[dict], prs: list[dict]) -> list[str]`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`scripts/test_agent_queue.py`:

```python
"""automation 큐 판정 회귀 그물 — stdlib 전용.

경계 넷을 못박는다:
  ① 고위험은 automation 이 집지 않는다 (하드 게이트가 Orca automation 을 못 막는다).
  ② fork PR 은 집지 않는다 (남의 코드로 리드 노트북에서 에이전트를 띄우면 안 된다).
  ③ 이미 워커가 붙은 것은 다시 집지 않는다.
  ④ 정리는 워크트리 나이가 아니라 연결 PR 상태로 판정한다
     (lastActivityAt 이 생성 시각에 고정돼 일하는 워커를 죽인 실사고, 2026-08-07).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_queue as q

SAME = "Danwoo/trading-lab"


def issue(num, labels):
    return {"number": num, "labels": labels}


def pr(num, repo, review, labels, branch, state="OPEN"):
    return {"number": num, "headRepo": repo, "reviewDecision": review,
            "labels": labels, "headRefName": branch, "state": state}


ISSUE_CASES = [
    ("저위험 + 착수 표식 → 집는다",
     [issue(1, ["risk: low", "agent: ready"])], 1),
    ("고위험은 안 집는다",
     [issue(2, ["risk: high", "agent: ready"])], None),
    ("위험 미선언은 안 집는다",
     [issue(3, ["agent: ready"])], None),
    ("착수 표식이 없으면 안 집는다",
     [issue(4, ["risk: low"])], None),
    ("이미 워커가 붙었으면 안 집는다",
     [issue(5, ["risk: low", "agent: ready", "agent: working"])], None),
    ("빈 목록 → None",
     [], None),
]

REWORK_CASES = [
    ("변경 요청 + 같은 레포 → 집는다",
     [pr(10, SAME, "CHANGES_REQUESTED", ["risk: low"], "fix-1")], 10),
    ("fork PR 은 안 집는다",
     [pr(11, "someone/fork", "CHANGES_REQUESTED", ["risk: low"], "fix-2")], None),
    ("승인된 PR 은 안 집는다",
     [pr(12, SAME, "APPROVED", ["risk: low"], "fix-3")], None),
    ("리뷰 없는 PR 은 안 집는다",
     [pr(13, SAME, None, ["risk: low"], "fix-4")], None),
    ("이미 워커가 붙었으면 안 집는다",
     [pr(14, SAME, "CHANGES_REQUESTED", ["risk: low", "agent: working"], "fix-5")], None),
    ("고위험은 안 집는다",
     [pr(15, SAME, "CHANGES_REQUESTED", ["risk: high"], "fix-6")], None),
]

CLEANUP_CASES = [
    ("연결 PR 이 머지됨 → 회수",
     [{"name": "fix-1-claude", "branch": "fix-1"}],
     [pr(20, SAME, "APPROVED", [], "fix-1", state="MERGED")],
     ["fix-1-claude"]),
    ("연결 PR 이 열려 있음 → 보존 (나이와 무관)",
     [{"name": "fix-2-claude", "branch": "fix-2"}],
     [pr(21, SAME, None, [], "fix-2", state="OPEN")],
     []),
    ("연결 PR 을 못 찾음 → 보존 (모르면 안 지운다)",
     [{"name": "orphan-claude", "branch": "nope"}],
     [pr(22, SAME, None, [], "other", state="OPEN")],
     []),
]


def main() -> int:
    failures = 0
    for desc, issues, want in ISSUE_CASES:
        got = q.pick_issue(issues)
        num = got["number"] if got else None
        if num != want:
            print(f"FAIL [issue/{desc}] got {num!r}, want {want!r}"); failures += 1
    for desc, prs, want in REWORK_CASES:
        got = q.pick_rework(prs)
        num = got["number"] if got else None
        if num != want:
            print(f"FAIL [rework/{desc}] got {num!r}, want {want!r}"); failures += 1
    for desc, wts, prs, want in CLEANUP_CASES:
        got = q.pick_cleanup(wts, prs)
        if got != want:
            print(f"FAIL [cleanup/{desc}] got {got!r}, want {want!r}"); failures += 1

    total = len(ISSUE_CASES) + len(REWORK_CASES) + len(CLEANUP_CASES)
    print(f"agent_queue 케이스 {total}건 검사 · 실패 {failures}건")
    if total == 0:
        print("FAIL 검사 대상 0건")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 실패를 확인한다**

Run: `python3 scripts/test_agent_queue.py`
Expected: `ModuleNotFoundError: No module named 'agent_queue'`

- [ ] **Step 3: 최소 구현을 쓴다**

`scripts/agent_queue.py`:

```python
"""automation 이 「지금 무엇을 집을까」를 정한다 — 순수 판정, stdlib 전용.

automation 은 하드 게이트(gate declare/approve)를 지나가지 않는다. 그래서 위험 판정을
여기서 다시 한다 — `risk: low` 로 선언된 것만 집는다.
"""

import json
import os
import sys

SAME_REPO = "Danwoo/trading-lab"
READY = "agent: ready"
WORKING = "agent: working"
RISK_LOW = "risk: low"


def _labels(item):
    return set(item.get("labels") or [])


def pick_issue(issues):
    """착수할 이슈 하나. 없으면 None."""
    for it in issues:
        lb = _labels(it)
        if RISK_LOW in lb and READY in lb and WORKING not in lb:
            return it
    return None


def pick_rework(prs):
    """재작업이 필요한 PR 하나. 없으면 None."""
    for p in prs:
        if p.get("headRepo") != SAME_REPO:
            continue
        if p.get("reviewDecision") != "CHANGES_REQUESTED":
            continue
        lb = _labels(p)
        if RISK_LOW in lb and WORKING not in lb:
            return p
    return None


def pick_cleanup(worktrees, prs):
    """회수할 워크트리 이름 목록.

    나이를 보지 않는다 — Orca 의 lastActivityAt 은 생성 시각에 고정돼
    일하는 워커를 죽인 전례가 있다. 연결 PR 이 **머지·닫힘인 것만** 회수한다.
    """
    done = {p["headRefName"] for p in prs if p.get("state") in ("MERGED", "CLOSED")}
    live = {p["headRefName"] for p in prs if p.get("state") == "OPEN"}
    out = []
    for w in worktrees:
        br = w.get("branch")
        if br in done and br not in live:
            out.append(w["name"])
    return out


def main():
    """stdin 의 JSON 을 읽어 판정 하나를 낸다. 인자: issue|rework|cleanup"""
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    data = json.load(sys.stdin)
    if mode == "issue":
        picked = pick_issue(data)
        n = len(data)
    elif mode == "rework":
        picked = pick_rework(data)
        n = len(data)
    elif mode == "cleanup":
        picked = pick_cleanup(data["worktrees"], data["prs"])
        n = len(data["worktrees"])
    else:
        print(f"알 수 없는 모드: {mode!r}", file=sys.stderr)
        return 2
    print(f"{mode}: 후보 {n}건 검사", file=sys.stderr)
    json.dump(picked, sys.stdout)
    print()
    return 0 if picked else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

> `main()` 의 종료코드가 **precheck 의 신호**다 — 집을 것이 있으면 0, 없으면 1.

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python3 scripts/test_agent_queue.py`
Expected: `agent_queue 케이스 15건 검사 · 실패 0건` · 종료코드 0

- [ ] **Step 5: CI 에 배선한다**

`.github/workflows/repo-scans.yml` 의 `repo-scan` 잡에 추가:

```yaml
      - name: automation 큐 판정 회귀 그물
        run: python3 scripts/test_agent_queue.py
```

- [ ] **Step 6: 배선 대조**

Run: `python3 scripts/verify_ci_check_coverage.py`
Expected: 종료코드 0

- [ ] **Step 7: 커밋**

```bash
git add scripts/agent_queue.py scripts/test_agent_queue.py .github/workflows/repo-scans.yml
git commit -m "feat(automation): 큐 판정을 순수 함수로 만든다

automation 3종이 공유하는 질문은 '지금 무엇을 집나' 하나다. 순수 함수로
꺼내 경계 넷을 케이스로 못박는다 — 고위험 제외, fork 제외, 중복 방지,
정리는 나이가 아니라 연결 PR 상태로."
```

---

## Task 2: precheck 의 의미를 확인하고 워커 기동 automation 을 세운다

`orca-ide automations create` 에 `--precheck <command>` 가 있다. **에이전트를 띄우기 전에 값싼
명령으로 「할 일이 있나」를 보는 자리**라 이 설계에 맞는다 — 매 틱마다 워크트리를 만들지 않아도 된다.

**다만 그 의미(종료코드 0 이면 진행인지)를 문서에서 확인하지 못했다. Step 1 에서 실측한다.**

**Files:**
- Create: `scripts/precheck_worker.sh`
- Create: (Orca 등록물 — 파일 아님)

- [ ] **Step 1: precheck 의미를 실측한다**

**확인 없이 다음으로 가지 않는다.**

```bash
# 항상 실패하는 precheck 로 disabled automation 을 만든다
orca-ide automations create --name precheck-probe --trigger hourly \
  --prompt "이 프롬프트는 실행되면 안 된다" --provider claude \
  --repo id:619d5257-8682-4630-9b94-2ada6af355cb \
  --precheck "false" --disabled --environment wsl-native --json

# 손으로 한 번 돌린다
orca-ide automations run <automationId> --environment wsl-native --json
orca-ide automations runs --id <automationId> --environment wsl-native --json
```

Expected: precheck 가 실패했으므로 **에이전트가 안 뜬다**. `runs` 출력에 건너뛴 흔적이 있어야 한다.
`--precheck "true"` 로 바꿔(`automations edit`) 다시 돌리면 뜬다.

**의미가 다르면(예: precheck 실패해도 실행) 이 계획의 precheck 전략을 버리고 프롬프트 안에서
「할 일이 없으면 즉시 종료」로 바꾼다.** 그 경우 매 틱 워크트리가 생겼다 지워지는 비용을
감수하는 것이므로 트리거 간격을 늘린다.

정리:
```bash
orca-ide automations remove <automationId> --environment wsl-native --json
```

- [ ] **Step 2: precheck 스크립트를 쓴다**

`scripts/precheck_worker.sh`:

```bash
#!/usr/bin/env bash
# 워커 기동 automation 의 precheck — 집을 이슈가 있으면 0, 없으면 1.
# 에이전트를 띄우기 전에 도는 값싼 조회다. 여기서 1 이면 워크트리가 안 생긴다.
set -uo pipefail

gh issue list --repo Danwoo/trading-lab --state open --limit 100 \
  --json number,labels \
  --jq '[.[] | {number, labels: [.labels[].name]}]' \
| python3 scripts/agent_queue.py issue
```

- [ ] **Step 3: 손으로 돌려 본다**

Run: `bash scripts/precheck_worker.sh; echo "종료코드=$?"`
Expected: 집을 이슈가 없으면 `issue: 후보 N건 검사` + `null` + `종료코드=1`.
`agent: ready` 와 `risk: low` 가 붙은 이슈를 하나 만들면 `종료코드=0` 과 그 이슈 JSON.

- [ ] **Step 4: `agent: ready` · `agent: working` 라벨을 만든다**

```bash
gh label create "agent: ready"   --description "AI 워커가 집어도 되는 이슈 (사람이 붙인다)" --color BFD4F2
gh label create "agent: working" --description "워커가 붙어 있음 — automation 중복 방지 잠금" --color D4C5F9
```

- [ ] **Step 5: automation 을 등록한다 (처음엔 `--disabled`)**

```bash
orca-ide automations create \
  --name "worker-dispatch" \
  --trigger "*/15 * * * *" \
  --provider claude \
  --repo id:619d5257-8682-4630-9b94-2ada6af355cb \
  --precheck "bash scripts/precheck_worker.sh" \
  --prompt "이 파일을 읽고 완주하라: /home/tjeksdn1/orders/automation-worker.md" \
  --disabled --environment wsl-native --json
```

- [ ] **Step 6: 오더 파일을 쓴다**

`/home/tjeksdn1/orders/automation-worker.md` — 워커가 매 실행마다 읽는다. 반드시 담을 것:

1. **첫 일**: `bash scripts/precheck_worker.sh` 로 집을 이슈를 다시 확인하고 그 번호를 잡는다
   (precheck 이후 사람이 라벨을 뗐을 수 있다). 없으면 **아무것도 하지 않고 종료**한다.
2. **잠금**: `gh issue edit <N> --add-label "agent: working"` 을 **작업 시작 전에** 건다.
3. **신원**: `git config --worktree user.name/user.email` 을 `claude-opus-agent` /
   `claude-opus-agent@noreply.local` 로 걸고, 커밋 전에 `--get user.email` 로 확인한다.
4. **완주 규율**: 중간에 묻지 말고 완주한다. 막히면 그 조각을 남기고 다음으로 간다.
5. **PR**: 본문에 `Closes #<N>` 과 「발견」 절을 둔다. 열고 나면 `agent: working` 을 뗀다.
6. **경계**: main 머지 금지 · `git stash` 금지 · force push 금지 · 포트 3000·3010·8000·5432
   불가침 · 개발 DB `fintech` 읽기만 · AI 자기 언급 금지 · 옛 레포
   `~/projects/fintech-ai-platform` 는 보관용이니 건드리지 않는다.

- [ ] **Step 7: 손으로 한 번 돌려 본다**

`agent: ready` + `risk: low` 가 붙은 **작고 안전한 이슈**를 하나 만들고:

Run: `orca-ide automations run <automationId> --environment wsl-native --json`
Expected: 워크트리가 생기고 워커가 그 이슈를 집어 PR 까지 연다.
`orca-ide worktree list` 와 `gh pr list` 로 확인한다.

- [ ] **Step 8: 활성화한다**

```bash
orca-ide automations edit <automationId> --enabled --environment wsl-native --json
orca-ide automations list --environment wsl-native --json
```

- [ ] **Step 9: 커밋**

```bash
git add scripts/precheck_worker.sh
git commit -m "feat(automation): 워커 기동 precheck

에이전트를 띄우기 전에 집을 이슈가 있는지 값싼 조회로 본다. 없으면
워크트리가 아예 안 생긴다."
```

---

## Task 3: 재작업 기동 automation — 루프를 닫는다

**이 계획에서 가장 중요한 task 다.** 지금은 리뷰가 「수정 필요」를 내는 순간 흐름이 멈춘다.

**Files:**
- Create: `scripts/precheck_rework.sh`

- [ ] **Step 1: precheck 스크립트를 쓴다**

`scripts/precheck_rework.sh`:

```bash
#!/usr/bin/env bash
# 재작업 기동 automation 의 precheck — 변경 요청된 PR 이 있으면 0, 없으면 1.
# fork PR 은 headRepo 대조로 제외한다 (남의 코드로 로컬 에이전트를 띄우지 않는다).
set -uo pipefail

gh pr list --repo Danwoo/trading-lab --state open --limit 100 \
  --json number,reviewDecision,labels,headRefName,headRepositoryOwner,headRepository \
  --jq '[.[] | {number, reviewDecision, headRefName,
                headRepo: (.headRepositoryOwner.login + "/" + .headRepository.name),
                labels: [.labels[].name]}]' \
| python3 scripts/agent_queue.py rework
```

- [ ] **Step 2: fork 판별이 실제로 되는지 확인한다**

`gh pr list` 가 `headRepositoryOwner`·`headRepository` 를 주는지 먼저 본다.

Run: `gh pr list --repo Danwoo/trading-lab --state all --limit 3 --json number,headRepositoryOwner,headRepository`
Expected: 각 PR 에 `headRepositoryOwner.login` 과 `headRepository.name` 이 있다.
**필드 이름이 다르면** `gh pr list --json` 없이 `gh api repos/{owner}/{repo}/pulls` 의
`head.repo.full_name` 을 쓰도록 스크립트를 바꾼다.

- [ ] **Step 3: 손으로 돌려 본다**

Run: `bash scripts/precheck_rework.sh; echo "종료코드=$?"`
Expected: 변경 요청된 PR 이 없으면 `rework: 후보 N건 검사` + `null` + `종료코드=1`

- [ ] **Step 4: automation 을 등록한다**

```bash
orca-ide automations create \
  --name "rework-dispatch" \
  --trigger "*/10 * * * *" \
  --provider claude \
  --repo id:619d5257-8682-4630-9b94-2ada6af355cb \
  --precheck "bash scripts/precheck_rework.sh" \
  --prompt "이 파일을 읽고 완주하라: /home/tjeksdn1/orders/automation-rework.md" \
  --disabled --environment wsl-native --json
```

- [ ] **Step 5: 오더 파일을 쓴다**

`/home/tjeksdn1/orders/automation-rework.md` — 워커 기동 오더와 다른 점만 적는다.

1. **첫 일**: `bash scripts/precheck_rework.sh` 로 대상 PR 번호와 브랜치를 잡는다. 없으면 종료.
2. **기존 브랜치를 이어받는다**: 새 브랜치를 파면 그 PR 에 push 할 자리가 없어진다.
   ```bash
   git fetch origin && git checkout -B <headRefName> origin/<headRefName>
   ```
3. **잠금**: `gh pr edit <N> --add-label "agent: working"`
4. **리뷰를 읽는다**: `gh pr view <N> --json reviews --jq '.reviews[] | select(.state=="CHANGES_REQUESTED") | .body'`
   그리고 인라인 코멘트도 본다: `gh api repos/Danwoo/trading-lab/pulls/<N>/comments`
5. **고친다.** 리뷰가 지적한 것을 고치고 push 한다. **push 하면 승인이 무효화되고 재리뷰가 붙는다.**
6. **반박도 산출물이다.** 리뷰 지적이 틀렸다고 판단하면 고치지 말고 **근거를 코멘트로 남긴다** —
   맹목적 반영은 리뷰를 의식 절차로 만든다.
7. **끝나면** `agent: working` 을 뗀다.
8. 경계는 워커 기동 오더와 동일하다.

- [ ] **Step 6: 루프가 실제로 닫히는지 확인한다 — 이 task 의 완료 조건**

**자기가 만든 케이스가 아니라 실제 왕복으로 확인한다.**

1. 작은 PR 을 하나 연다 (일부러 고칠 거리를 남긴다)
2. 리뷰어를 붙여 `Request changes` 판정을 받는다 (CI 계획 Task 7 의 기록기 경유)
3. `gh pr view <N> --json reviewDecision` 이 `CHANGES_REQUESTED` 인지 확인
4. `orca-ide automations run <rework-id>` 를 돌린다
5. **워커가 그 PR 브랜치를 체크아웃해 고치고 push 하는지** 본다
6. push 후 **승인이 무효화되고 재리뷰가 붙는지** 본다
7. 명령과 출력을 PR 본문에 그대로 싣는다

- [ ] **Step 7: 활성화하고 커밋**

```bash
orca-ide automations edit <automationId> --enabled --environment wsl-native --json
git add scripts/precheck_rework.sh
git commit -m "feat(automation): 변경 요청된 PR 의 워커를 깨운다

지금은 리뷰가 '수정 필요'를 내는 순간 흐름이 멈춘다 — 워커는 알림을 안 받고
폴링도 안 한다. 실제 개발자는 알림을 받고 돌아오는데 우리 워커에겐 수신자가
없었다. 이 automation 이 그 수신자다."
```

---

## Task 4: 정리 automation — 나이가 아니라 PR 상태로 판정한다

2026-08-07 에 시작 스윕이 **일하는 중인 리뷰어 다섯을 회수**했다. 원인은 Orca 의
`lastActivityAt` 이 생성 시각에 박히고 갱신되지 않는 것이다. **같은 실수를 반복하지 않는다.**

**Files:**
- Create: `scripts/precheck_cleanup.sh`

- [ ] **Step 1: precheck 스크립트를 쓴다**

`scripts/precheck_cleanup.sh`:

```bash
#!/usr/bin/env bash
# 정리 automation 의 precheck — 회수할 워크트리가 있으면 0, 없으면 1.
# 나이를 보지 않는다. Orca 의 lastActivityAt 은 생성 시각에 고정돼 일하는 워커를
# 죽인 전례가 있다 (2026-08-07). 연결 PR 이 머지·닫힘인 것만 회수한다.
set -uo pipefail

WT=$(orca-ide worktree list --repo id:619d5257-8682-4630-9b94-2ada6af355cb \
       --environment wsl-native --json 2>/dev/null \
     | python3 -c '
import json,sys
ws=json.load(sys.stdin)["result"]["worktrees"]
print(json.dumps([{"name": w.get("displayName") or "",
                   "branch": (w.get("git",{}).get("branch") or "").replace("refs/heads/","")}
                  for w in ws if not w.get("git",{}).get("isMainWorktree")]))')

PRS=$(gh pr list --repo Danwoo/trading-lab --state all --limit 200 \
        --json number,state,headRefName \
      | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)))')

printf '{"worktrees": %s, "prs": %s}' "$WT" "$PRS" | python3 scripts/agent_queue.py cleanup
```

- [ ] **Step 2: 지금 상태로 손으로 돌려 본다**

Run: `bash scripts/precheck_cleanup.sh; echo "종료코드=$?"`
Expected: `cleanup: 후보 N건 검사` 와 회수 대상 이름 목록.
**살아 있는 워커의 워크트리가 목록에 나오면 판정이 틀린 것이므로 고치고 다시 돈다.**

- [ ] **Step 3: automation 을 등록한다**

정리는 에이전트가 필요 없다 — 명령 몇 개다. 그래도 Orca CLI 를 써야 하므로 automation 으로 둔다.

```bash
orca-ide automations create \
  --name "worktree-cleanup" \
  --trigger hourly \
  --provider claude \
  --repo id:619d5257-8682-4630-9b94-2ada6af355cb \
  --precheck "bash scripts/precheck_cleanup.sh" \
  --prompt "이 파일을 읽고 완주하라: /home/tjeksdn1/orders/automation-cleanup.md" \
  --disabled --environment wsl-native --json
```

- [ ] **Step 4: 오더 파일을 쓴다**

`/home/tjeksdn1/orders/automation-cleanup.md`:

1. `bash scripts/precheck_cleanup.sh` 로 회수 대상 이름 목록을 잡는다. 비면 종료.
2. **지우기 전에 각각을 확인한다** — 터미널에 사람이 입력해 둔 미전송 텍스트가 있으면
   **그 워크트리는 건너뛰고 그 사실을 보고한다.**
   `orca-ide terminal read --terminal <핸들> --environment wsl-native --json` 의 tail 에서
   `❯` 뒤에 텍스트가 남아 있는지 본다 (`scripts/review_terminal.py` 의 `prompt_is_empty`).
3. 미커밋·미push 가 있으면 건너뛴다:
   `git -C <경로> status --porcelain` 과 `git -C <경로> log --oneline origin/main..HEAD`
4. 위 셋을 통과한 것만:
   `orca-ide worktree rm --worktree "id:<repoId>::<경로>" --force --environment wsl-native --json`
5. **검사·회수·보존 건수를 항상 출력한다.** 「대상 없음」과 「아무것도 안 봤음」이 구분돼야 한다.

- [ ] **Step 5: 손으로 돌려 확인하고 활성화한다**

Run: `orca-ide automations run <automationId> --environment wsl-native --json`
그다음 `orca-ide worktree list` 로 **살아 있어야 할 것이 살아 있는지** 확인한다.

```bash
orca-ide automations edit <automationId> --enabled --environment wsl-native --json
```

- [ ] **Step 6: 커밋**

```bash
git add scripts/precheck_cleanup.sh
git commit -m "feat(automation): 워크트리 정리를 연결 PR 상태로 판정한다

종전 CI 스윕은 lastActivityAt 으로 나이를 재 회수했다. 그 값이 생성 시각에
고정돼 갱신되지 않아 일하는 리뷰어 다섯을 죽였다 (2026-08-07, 로그 확인).
나이를 아예 보지 않고 연결 PR 이 머지·닫힘인 것만 회수한다."
```

---

## Task 5: 정체 감지 — 멈춘 것이 보이게 한다

리뷰를 CI 밖으로 옮기면 **「아직 안 한 것」과 「죽어서 못 한 것」이 화면에서 같아진다.**
이 레포의 교훈에 정면으로 걸리는 자리다.

**Orca 가 아니라 GitHub Actions 가 맡는다** — Orca 가 죽었을 때도 「멈춰 있다」는 사실은 보여야 한다.

**Files:**
- Create: `scripts/verify_review_staleness.py`
- Create: `.github/workflows/staleness.yml`
- Modify: `.github/workflows/repo-scans.yml` (배선 — 스크립트는 워크플로에서 돌아야 한다)

- [ ] **Step 1: 스크립트를 쓴다**

`scripts/verify_review_staleness.py`:

```python
"""리뷰 없이 오래 서 있는 PR 을 드러낸다 — stdlib 전용.

리뷰가 CI 밖(Orca)으로 나가면 '아직 안 한 것'과 '죽어서 못 한 것'이 화면에서 같아진다.
이 스크립트가 그 둘을 가른다. **검사한 PR 수를 항상 출력**해 통과가 '정체 없음' 인지
'아무것도 안 봤음' 인지 구분되게 한다.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

REPO = "Danwoo/trading-lab"
STALE_HOURS = int(os.environ.get("REVIEW_STALE_HOURS", "6"))


def fetch_prs():
    out = subprocess.run(
        ["gh", "pr", "list", "--repo", REPO, "--state", "open", "--limit", "200",
         "--json", "number,title,createdAt,reviewDecision,isDraft"],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def stale(prs, now):
    out = []
    for p in prs:
        if p.get("isDraft"):
            continue
        if p.get("reviewDecision"):
            continue
        created = datetime.fromisoformat(p["createdAt"].replace("Z", "+00:00"))
        hours = (now - created).total_seconds() / 3600
        if hours >= STALE_HOURS:
            out.append((p["number"], round(hours, 1), p["title"]))
    return out


def main():
    prs = fetch_prs()
    found = stale(prs, datetime.now(timezone.utc))
    print(f"정체 감지: 열린 PR {len(prs)}건 검사 · 기준 {STALE_HOURS}시간 · 정체 {len(found)}건")
    for num, hours, title in found:
        print(f"  #{num} — {hours}시간째 리뷰 없음 — {title[:60]}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 손으로 돌려 본다**

Run: `python3 scripts/verify_review_staleness.py; echo "종료코드=$?"`
Expected: `정체 감지: 열린 PR N건 검사 · 기준 6시간 · 정체 M건`.
지금 열린 PR 중 리뷰 없이 6시간 넘은 것이 있으면 종료코드 1 이 정상이다.

- [ ] **Step 3: 워크플로를 만든다**

`.github/workflows/staleness.yml`:

```yaml
# staleness — 리뷰 없이 서 있는 PR 을 주기적으로 드러낸다.
#
# Orca 가 아니라 여기서 도는 이유: Orca 가 죽었을 때도 '멈춰 있다'는 사실은 보여야 한다.
# 판단이 아니라 결정론적 조회라 CI 안에 있어도 설계의 경계를 어기지 않는다.
name: staleness
on:
  schedule:
    - cron: "0 * * * *"
  workflow_dispatch: {}

permissions:
  pull-requests: read
  contents: read

jobs:
  detect:
    name: "chore: staleness (비게이트)"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: 리뷰 정체 감지
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          set -uo pipefail
          python3 scripts/verify_review_staleness.py | tee "$GITHUB_STEP_SUMMARY"
```

> **fail-open 이 의도적이다.** 정체는 사람이 볼 신호이지 머지를 막을 사유가 아니다.
> 그래서 스크립트의 종료코드를 잡 실패로 올리지 않고 요약에 싣는다.

- [ ] **Step 4: 배선한다**

`verify_ci_check_coverage.py` 는 `scripts/verify_*.py` 가 워크플로에서 실행되는지 본다.
`staleness.yml` 이 그 실행처다 — 위 워크플로를 만들면 배선이 성립한다.

Run: `python3 scripts/verify_ci_check_coverage.py`
Expected: 종료코드 0. **실패하면** `repo-scans.yml` 에도 스텝을 추가한다.

- [ ] **Step 5: 손으로 한 번 태운다**

```bash
gh workflow run staleness.yml
gh run list --workflow staleness.yml --limit 1
```
Expected: 요약에 `정체 감지: 열린 PR N건 검사 …` 가 찍힌다.

- [ ] **Step 6: 커밋**

```bash
git add scripts/verify_review_staleness.py .github/workflows/staleness.yml
git commit -m "feat(ci): 리뷰 없이 서 있는 PR 을 주기적으로 드러낸다

리뷰가 CI 밖으로 나가면 '아직 안 한 것'과 '죽어서 못 한 것'이 화면에서
같아진다. 검사한 PR 수를 항상 출력해 통과가 '정체 없음'인지 '아무것도 안
봤음'인지 구분되게 한다."
```

---

## Task 6: 등록물을 문서로 남긴다

**automation 은 코드가 아니라 등록된 상태다.** 레포를 클론해도 따라오지 않는다. 무엇이 왜
등록돼 있는지 문서가 없으면 다음 사람이 알 길이 없다.

**Files:**
- Create: `.docs/6-도구/에이전트-automation.md`
- Modify: `CLAUDE.md` (「현재 베팅」 아래에 포인터 한 줄)

- [ ] **Step 1: 실제 등록 상태를 뽑는다**

Run: `orca-ide automations list --environment wsl-native --json`
이 출력의 id·이름·트리거·precheck 를 문서에 **그대로** 옮긴다. 손으로 지어내지 않는다.

- [ ] **Step 2: 문서를 쓴다**

`.docs/6-도구/에이전트-automation.md` 에 담을 것:

- 등록된 automation 표 (이름 · 트리거 · precheck · 오더 파일 경로 · 무엇을 하나)
- **재등록 절차** — 다른 기계에서 처음 세울 때 그대로 칠 수 있는 명령
- **끄는 법**: `orca-ide automations edit <id> --disabled --environment wsl-native`
- **관측**: `orca-ide automations runs --id <id> --environment wsl-native --json`
- **알려진 한계**:
  - automation 은 하드 게이트를 지나가지 않는다 → `risk: low` 만 집는다
  - Orca 가 죽으면 automation 도 죽는다 → 정체 감지(Task 5)가 그것을 드러낸다
  - 트리거는 cron 뿐이라 이벤트 즉시 반응이 아니다 (최대 트리거 간격만큼 늦다)

- [ ] **Step 3: `CLAUDE.md` 에 포인터를 단다**

`## 현재 베팅` 절 아래에 한 줄:

```markdown
에이전트 automation 등록물·복구 절차: [`.docs/6-도구/에이전트-automation.md`](.docs/6-도구/에이전트-automation.md)
```

- [ ] **Step 4: 커밋**

```bash
git add .docs/6-도구/에이전트-automation.md CLAUDE.md
git commit -m "docs: 에이전트 automation 등록물과 복구 절차

automation 은 코드가 아니라 등록된 상태라 레포를 클론해도 따라오지 않는다.
무엇이 왜 등록돼 있는지와 다른 기계에서 다시 세우는 절차를 남긴다."
```

---

## 자체 검토 결과

**설계 §5 대비 커버리지**

| 설계 항목 | task |
| --- | --- |
| 축 ① 워커 기동 automation | Task 2 |
| 축 ① **재작업 기동 automation** | Task 3 |
| 축 ① 정리 automation | Task 4 |
| 축 ② 정체 감지 | Task 5 |
| 「착수 표식을 무엇으로 할지」(미결 2) | **Task 2 Step 4 에서 `agent: ready` 라벨로 확정** |

**공백 점검 대비**

| 공백 | 닫는 곳 |
| --- | --- |
| ① 이슈가 생겨도 워커가 안 뜬다 | Task 2 |
| ③ 「수정 필요」 후 아무도 안 깨운다 | Task 3 |
| ④ 워크트리가 쌓인다 | Task 4 |
| ⑤ 리뷰어가 안 뜬 걸 모른다 | Task 5 |

**미검증 전제** (이 계획이 스스로 재는 것)

1. **`--precheck` 의 의미** — 종료코드 0 이면 진행인지 문서에서 확인 못 했다. Task 2 Step 1 이
   실측하고, 다르면 전략을 바꾼다
2. **`gh pr list` 의 fork 판별 필드** — Task 3 Step 2 가 확인하고, 없으면 `gh api` 로 바꾼다
3. **재작업 왕복이 실제로 도는가** — Task 3 Step 6 이 실제 PR 로 확인한다

## 이 계획이 못 닫는 것

- **automation 은 하드 게이트를 우회한다.** `gate declare`/`gate approve` 는 지휘자의 도구 호출을
  가로채는 훅이라 Orca 가 내부에서 만드는 워크트리는 지나가지 않는다. 완화책은 「`risk: low` 만
  집는다」이고, 이것은 **automation 이 스스로 지키는 규칙이지 강제되는 것이 아니다.**
  더 단단히 하려면 워커 오더가 아니라 Orca 쪽에 훅이 있어야 하는데 그 자리는 없다.
- **트리거가 cron 뿐이라 즉시 반응이 아니다.** 리뷰가 「수정 필요」를 낸 뒤 최대 10분 늦는다.
  이벤트 트리거가 생기면 그때 바꾼다.
- **고위험 작업은 여전히 사람·지휘자가 디스패치한다.** 그것이 게이트의 목적이므로 의도된 경계다.
