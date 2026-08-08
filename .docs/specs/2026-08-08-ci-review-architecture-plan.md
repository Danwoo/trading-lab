# CI·리뷰 구조 재설계 구현 계획

> **에이전트 워커에게:** 이 계획은 **task 단위로** 구현한다. 각 task 는 독립적으로 테스트되고
> 리뷰어의 게이트를 통과할 수 있는 단위다. 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** CI 파이프라인에서 「에이전트가 판단하는 일」을 걷어내고, 리뷰를 GitHub 네이티브 PR
리뷰로 옮긴다. 워크플로 11개·3,705줄 → 5개·약 1,000줄.

**접근:** YAML 안의 bash 를 `scripts/` 의 테스트 가능한 파이썬으로 꺼내고(Task 1~2), 죽은
경로를 지우고(Task 3), required check 가 성립하게 경로 필터를 바꾸고(Task 4), 판정을 GitHub
리뷰로 기록하는 얇은 기록기를 세운 뒤(Task 5~6), 흉내 내던 워크플로를 삭제한다(Task 7~8).
각 task 는 끝난 시점에 CI 가 깨지지 않은 상태를 남긴다.

**기술 스택:** GitHub Actions · Python 3(stdlib 전용) · `gh` CLI · `orca-ide` CLI

**설계 정본:** [`2026-08-08-ci-review-architecture-design.md`](2026-08-08-ci-review-architecture-design.md)

## 전역 제약

이 절은 **모든 task 의 요구사항에 암묵적으로 포함된다.**

- **검증 스크립트는 stdlib 전용**이다. 서드파티 import 금지 (`verify_ci_check_coverage.py` 머리 주석).
- **새 `scripts/verify_*.py` · `scripts/test_*.py` 는 워크플로에 배선해야 한다.** 배선 없이 두면
  `verify_ci_check_coverage.py` 가 CI 를 빨갛게 만든다. 배선처는 `.github/workflows/repo-scans.yml`.
- **검사 0건은 통과가 아니다.** 새로 짜는 검사는 검사한 대상 수를 세어 출력하고, 0이거나 기대치와
  다르면 **실패**한다.
- **커밋 신원**: 워크트리에서 작업하면 `git config --worktree user.name/user.email` 이
  `claude-<티어>-agent` / `claude-<티어>-agent@noreply.local` 이어야 한다. 커밋 전에
  `git config --worktree --get user.email` 로 확인한다.
- **main 에 직접 커밋·머지 금지.** 브랜치 → PR 까지가 워커의 몫이다. pre-commit 훅
  `no-commit-to-branch` 가 main 커밋을 막는다.
- **`git stash` 금지 · force push 금지 · history 재작성 금지.** 부정 통제는
  `git diff > /tmp/x.patch` → `git apply -R` → 확인 → `git apply` 로 한다.
- **포트 3000·3010·8000·5432 불가침. 개발 DB `fintech` 는 읽기만.** `pkill`·`fuser -k` 금지.
- **AI 자기 언급 금지** — 커밋 메시지·PR 본문에 `🤖 Generated with …`,
  `Co-Authored-By: Claude` 를 쓰지 않는다.
- **주석 규칙**: 변경 이유·이력 설명 주석 금지. 코드만으로 드러나지 않는 제약·의도만 한 줄로.

## 파일 구조

| 파일 | 책임 |
| --- | --- |
| `scripts/review_route.py` (신규) | 커밋 신원 → 리뷰어 배정. **순수 판정** — I/O 없음 |
| `scripts/test_review_route.py` (신규) | 위의 단위 테스트 |
| `scripts/review_terminal.py` (신규) | 터미널 tail 텍스트 → 준비·접수 판정. **순수 판정** |
| `scripts/test_review_terminal.py` (신규) | 위의 단위 테스트 (#11 회귀 그물) |
| `scripts/review_record.py` (신규) | 판정 마커 + PR 상태 → 리뷰 행동·자동 머지 arm 여부. **순수 판정** |
| `scripts/test_review_record.py` (신규) | 위의 단위 테스트 |
| `.github/workflows/cross-review.yml` (수정) | 위 스크립트를 부르기만 한다 |
| `.github/workflows/review-record.yml` (신규) | 기록기 — 마커를 읽어 `gh pr review` 대행 |
| `.github/workflows/repo-scans.yml` (수정) | 새 테스트 배선 + required 게이트 잡 |
| `.github/workflows/ci.yml` · `frontend-ci.yml` (수정) | `on.paths` → 잡 레벨 `if:` |
| `.github/workflows/plan.yml` (신규) | `plan-check`·`plan-label`·`plan-label-issue` 통합 |
| 삭제 | `merge-router.yml` · `review-gate.yml` · `board-status.yml` · `plan-*.yml` 3개 |

**순수 판정 3종이 이 계획의 핵심이다.** 지금 실패의 원인이 「YAML 안 bash 라 로컬에서 못
돌린다」이므로, 판정 로직을 I/O 없는 함수로 꺼내 테스트를 붙이는 것이 곧 처방이다.

---

## Task 1: 리뷰어 배정을 순수 판정 스크립트로 추출

지금 `cross-review.yml:324` 의 `decide()` 가 이 일을 한다. 주석에 이미
`# ---- 순수 판정부 시작 (입력: EMAILS·HEAD_REF·ISSUE_RISKS·CODEX_ON — 로컬 단위 테스트 대상) ----`
라고 적혀 있는데, bash 라 실제로는 단위 테스트가 없다.

**Files:**
- Create: `scripts/review_route.py`
- Create: `scripts/test_review_route.py`
- Modify: `.github/workflows/repo-scans.yml` (배선)
- Modify: `.github/workflows/cross-review.yml:318-628` (`decide()` 를 스크립트 호출로 교체)

**Interfaces:**
- Produces: `decide(emails: list[str], codex_on: bool, risk: str) -> dict` — 반환 키는
  `reviewer`(`"claude"|"kimi"|"codex"|"none"`) · `author_kind`(`"agent"|"human"|"mixed"`) ·
  `author_vendor`(`str|None`) · `author_tier`(`str|None`) · `label_allowed`(`bool`).
- `label_allowed` 의 소비자는 **리뷰어 디스패치**다. `False` 면(사람·봇·티어 미상·벤더 혼재)
  교차 모델 리뷰가 성립했다고 볼 수 없으므로, 디스패처는 리뷰 오더에 **판정 마커 끝에
  `source=manual` 을 붙이라**고 지시한다. Task 7 의 `decide_record` 가 그 필드를 보고
  **자동 머지를 arm 하지 않는다.** 즉 `label_allowed` 는 `decide_record` 의 인자가 아니라
  마커 생성 시점에 반영되는 값이다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`scripts/test_review_route.py`:

```python
"""review_route.decide 회귀 그물 — 저자 판별·리뷰어 배정 (stdlib 전용).

이 판정은 종전 cross-review.yml 의 bash `decide()` 였고 단위 테스트가 없었다.
티어 어휘는 로컬 실측으로 확인된 것만 받는다 (없는 이름은 미상 처리).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_route as rr

CASES = [
    # (설명, emails, codex_on, risk, 기대 reviewer, 기대 author_kind, 기대 label_allowed)
    ("claude-opus 저자 → kimi 리뷰",
     ["claude-opus-agent@noreply.local"], False, "low", "kimi", "agent", True),
    ("kimi 저자 + 저위험 → claude 리뷰",
     ["kimi-agent@noreply.local"], False, "low", "claude", "agent", True),
    ("kimi 저자 + 고위험 + codex 가용 → codex 리뷰",
     ["kimi-agent@noreply.local"], True, "high", "codex", "agent", True),
    ("kimi 저자 + 고위험 + codex 불가 → claude 폴백",
     ["kimi-agent@noreply.local"], False, "high", "claude", "agent", True),
    ("codex 저자 → claude 리뷰",
     ["codex-agent@noreply.local"], False, "low", "claude", "agent", True),
    ("사람 저자 → claude 리뷰, 판정 라벨 금지",
     ["danwoo@example.com"], False, "low", "claude", "human", False),
    ("봇 저자(dependabot) → claude 리뷰, 판정 라벨 금지",
     ["49699333+dependabot[bot]@users.noreply.github.com"], False, "low",
     "claude", "human", False),
    ("벤더 혼재 → 판정 라벨 금지",
     ["claude-opus-agent@noreply.local", "kimi-agent@noreply.local"], False, "low",
     "codex", "mixed", False),
    ("목록에 없는 티어는 미상으로 읽고 라벨 금지",
     ["claude-sonar-agent@noreply.local"], False, "low", "claude", "human", False),
]


def main() -> int:
    failures = 0
    for desc, emails, codex_on, risk, want_rev, want_kind, want_label in CASES:
        got = rr.decide(emails, codex_on, risk)
        for key, want in (("reviewer", want_rev),
                          ("author_kind", want_kind),
                          ("label_allowed", want_label)):
            if got[key] != want:
                print(f"FAIL [{desc}] {key}: got {got[key]!r}, want {want!r}")
                failures += 1
    print(f"review_route 케이스 {len(CASES)}건 검사 · 실패 {failures}건")
    if not CASES:
        print("FAIL 검사 대상 0건")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 실패를 확인한다**

Run: `python3 scripts/test_review_route.py`
Expected: `ModuleNotFoundError: No module named 'review_route'`

- [ ] **Step 3: 최소 구현을 쓴다**

`scripts/review_route.py`:

```python
"""커밋 신원으로 저자를 판별해 반대 모델 리뷰어를 배정한다 — 순수 판정, stdlib 전용.

티어 어휘는 **로컬에서 실재를 확인한 것만** 받는다. 여기 없는 이름은 미상으로 읽어
판정 라벨을 막는다 (동일-모델 자기리뷰 가능성을 배제할 수 없기 때문).
"""

import json
import os
import re
import sys

CLAUDE_TIERS = ("opus", "sonnet", "fable", "haiku")
KIMI_TIERS = ("k3", "k3-256k", "kimi-for-coding", "kimi-for-coding-highspeed")
CODEX_TIERS = ("gpt-5.6-terra",)

_VENDOR_TIERS = {"claude": CLAUDE_TIERS, "kimi": KIMI_TIERS, "codex": CODEX_TIERS}

# `<벤더>[-<티어>]-agent@noreply.local` — 와일드카드 금지, 명시 목록만
_IDENTITY = re.compile(
    r"^(?P<vendor>claude|kimi|codex)(?:-(?P<tier>[a-z0-9.\-]+))?-agent@noreply\.local$"
)

# 저자 벤더 → 리뷰어 벤더. 고위험 kimi 만 codex 를 쓴다 (가용할 때)
_OPPOSITE = {"claude": "kimi", "kimi": "claude", "codex": "claude"}


def decide(emails, codex_on, risk):
    vendors, tiers, unknown_agentish = set(), set(), False
    for raw in emails:
        m = _IDENTITY.match(raw.strip())
        if not m:
            continue
        vendor, tier = m.group("vendor"), m.group("tier")
        if tier is not None and tier not in _VENDOR_TIERS[vendor]:
            unknown_agentish = True
            continue
        vendors.add(vendor)
        if tier:
            tiers.add(tier)

    if unknown_agentish or not vendors:
        # 사람·봇·미상 티어 — 리뷰는 하되 판정 라벨은 붙이지 않는다 (사람 경로)
        return {"reviewer": "claude", "author_kind": "human",
                "author_vendor": None, "author_tier": None, "label_allowed": False}

    if len(vendors) > 1:
        return {"reviewer": "codex", "author_kind": "mixed",
                "author_vendor": None, "author_tier": None, "label_allowed": False}

    vendor = next(iter(vendors))
    reviewer = _OPPOSITE[vendor]
    if vendor == "kimi" and risk == "high" and codex_on:
        reviewer = "codex"
    return {"reviewer": reviewer, "author_kind": "agent", "author_vendor": vendor,
            "author_tier": next(iter(tiers)) if len(tiers) == 1 else None,
            "label_allowed": True}


def main():
    emails = [ln for ln in os.environ.get("EMAILS", "").splitlines() if ln.strip()]
    result = decide(emails, os.environ.get("CODEX_ON", "") == "on",
                    os.environ.get("RISK", "low"))
    json.dump(result, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python3 scripts/test_review_route.py`
Expected: `review_route 케이스 9건 검사 · 실패 0건` · 종료코드 0

- [ ] **Step 5: CI 에 배선한다**

`.github/workflows/repo-scans.yml` 의 `repo-scan` 잡에 스텝을 추가한다. 기존 스텝과 같은 형식이다:

```yaml
      - name: 리뷰어 배정 판정 회귀 그물
        run: python3 scripts/test_review_route.py
```

- [ ] **Step 6: 배선 대조가 통과하는지 확인한다**

Run: `python3 scripts/verify_ci_check_coverage.py`
Expected: 종료코드 0. 새 `scripts/test_review_route.py` 가 배선됐다고 나와야 한다.
배선을 빼먹었으면 여기서 빨갛게 실패한다 — 그것이 이 스크립트의 목적이다.

- [ ] **Step 7: 워크플로가 스크립트를 부르게 바꾼다**

`.github/workflows/cross-review.yml` 의 `route` 잡에서 인라인 `decide()` 를 지우고 다음으로 바꾼다:

```yaml
      - name: 저자 판별·리뷰어 배정
        id: decide
        env:
          EMAILS: ${{ steps.collect.outputs.emails }}
          CODEX_ON: ${{ vars.CROSS_REVIEW_CODEX }}
          RISK: ${{ steps.risk.outputs.risk }}
        run: |
          set -euo pipefail
          OUT=$(python3 scripts/review_route.py)
          echo "$OUT" | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(f"{k}={v}") for k,v in d.items()]' >> "$GITHUB_OUTPUT"
```

- [ ] **Step 8: 커밋**

```bash
git add scripts/review_route.py scripts/test_review_route.py .github/workflows/repo-scans.yml .github/workflows/cross-review.yml
git commit -m "refactor(ci): 리뷰어 배정을 순수 판정 스크립트로 꺼낸다

bash decide() 는 '로컬 단위 테스트 대상'이라고 주석에 적혀 있었으나 YAML
안에 있어 실제로는 테스트가 없었다. stdlib 전용 파이썬으로 옮기고 9개
케이스의 회귀 그물을 붙인다."
```

---

## Task 2: #11 — 터미널 준비·접수 판정을 교체하고 회귀 그물을 건다

`wait_agent_ready`(`cross-review.yml:1093`)가 `latestCursor` 성장을 준비 신호로 쓴다. Claude Code
TUI 는 화면을 제자리에서 다시 그려 이 값이 **영원히 안 움직인다**(설계 문서 「근거」 참조).
판정을 **프롬프트 박스 상태**로 바꾼다.

**Files:**
- Create: `scripts/review_terminal.py`
- Create: `scripts/test_review_terminal.py`
- Modify: `.github/workflows/repo-scans.yml` (배선)
- Modify: `.github/workflows/cross-review.yml:1078-1130`

**Interfaces:**
- Consumes: 없음
- Produces: `prompt_is_empty(tail: list[str]) -> bool` · `tui_is_ready(tail: list[str]) -> bool`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`scripts/test_review_terminal.py`:

```python
"""터미널 준비·접수 판정 회귀 그물 (#11) — stdlib 전용.

종전 판정은 `latestCursor` 성장이었고, Claude Code TUI 가 화면을 제자리에서 다시 그려
그 값이 움직이지 않아 **항상 실패**했다 (2026-08-07 실측: 유휴 30초 · 완주한 워커 모두 1).
아래 tail 은 그때 실제로 읽은 화면이다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_terminal as rt

BANNER_IDLE = [
    " ▐▛███▜▌   Claude Code v2.1.224",
    "▝▜█████▛▘  Opus 5 (1M context) · Claude Max",
    "  ▘▘ ▝▝    ~/orca/workspaces/trading-lab/review-6-claude",
    "─" * 40,
    "❯",
    "─" * 40,
    "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents",
]

PENDING_INPUT = list(BANNER_IDLE)
PENDING_INPUT[4] = "❯ 이 파일을 읽고 완주하라: /home/tjeksdn1/orders/x.md"

WORKING = [
    "● I'll start by reading the order file.",
    "  Read 1 file",
    "✢ Musing… (32s · ↓ 1.1k tokens · thinking)",
    "─" * 40,
    "❯",
    "─" * 40,
    "  ⏵⏵ bypass permissions on (shift+tab to cycle) · ← for agents",
]

SHELL_NOT_TUI = ["$ ls", "orders", "$ "]

CASES = [
    ("유휴 TUI — 프롬프트 비어 있음", rt.prompt_is_empty, BANNER_IDLE, True),
    ("입력이 남아 있음 — 접수 안 됨", rt.prompt_is_empty, PENDING_INPUT, False),
    ("작업 중 — 프롬프트는 비어 있음", rt.prompt_is_empty, WORKING, True),
    ("유휴 TUI — 준비됨", rt.tui_is_ready, BANNER_IDLE, True),
    ("작업 중 — 준비됨", rt.tui_is_ready, WORKING, True),
    ("TUI 아님(맨 셸) — 준비 안 됨", rt.tui_is_ready, SHELL_NOT_TUI, False),
]


def main() -> int:
    failures = 0
    for desc, fn, tail, want in CASES:
        got = fn(tail)
        if got is not want:
            print(f"FAIL [{desc}] got {got!r}, want {want!r}")
            failures += 1
    print(f"review_terminal 케이스 {len(CASES)}건 검사 · 실패 {failures}건")
    if not CASES:
        print("FAIL 검사 대상 0건")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 실패를 확인한다**

Run: `python3 scripts/test_review_terminal.py`
Expected: `ModuleNotFoundError: No module named 'review_terminal'`

- [ ] **Step 3: 최소 구현을 쓴다**

`scripts/review_terminal.py`:

```python
"""에이전트 TUI 의 준비·접수를 화면 내용으로 판정한다 — 순수 판정, stdlib 전용.

`latestCursor` 를 쓰지 않는다. TUI 가 화면을 제자리에서 다시 그리면 그 값이 안 움직여
살아 있는 에이전트를 죽은 것으로 읽는다 (#11).
"""

import re

_PROMPT = re.compile(r"^\s*❯\s*(?P<rest>.*?)\s*$")
# TUI 가 그렸다는 표식 — 배너 또는 하단 상태줄
_TUI_MARKS = ("Claude Code v", "bypass permissions on", "for agents")


def prompt_is_empty(tail):
    """프롬프트 박스에 잔여 입력이 없으면 True. 접수 확인은 이 값으로 한다."""
    for line in reversed(tail):
        m = _PROMPT.match(line)
        if m:
            return m.group("rest") == ""
    return False


def tui_is_ready(tail):
    """TUI 가 화면을 그렸으면 True. 출력 증가가 아니라 내용으로 본다."""
    joined = "\n".join(tail)
    if not any(mark in joined for mark in _TUI_MARKS):
        return False
    return any(_PROMPT.match(line) for line in tail)
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python3 scripts/test_review_terminal.py`
Expected: `review_terminal 케이스 6건 검사 · 실패 0건` · 종료코드 0

- [ ] **Step 5: CI 에 배선한다**

`.github/workflows/repo-scans.yml` 의 `repo-scan` 잡에 추가:

```yaml
      - name: 터미널 준비·접수 판정 회귀 그물 (#11)
        run: python3 scripts/test_review_terminal.py
```

- [ ] **Step 6: 배선 대조**

Run: `python3 scripts/verify_ci_check_coverage.py`
Expected: 종료코드 0

- [ ] **Step 7: 워크플로의 `wait_agent_ready`·`send_review_prompt` 를 교체한다**

`.github/workflows/cross-review.yml` 에서 `term_cursor()`·`wait_agent_ready()`·
`send_review_prompt()` 세 함수를 지우고 다음으로 바꾼다:

```bash
          term_tail() {   # $1=핸들 → tail 을 JSON 배열로
            orca-ide terminal read --terminal "$1" $ORCA_ENV --json 2>/dev/null \
              | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["result"]["terminal"]["tail"]))'
          }
          tui_ready() {   # $1=핸들 → 0=준비됨
            local deadline; deadline=$(( $(date +%s) + READY_TIMEOUT ))
            orca-ide terminal send --terminal "$1" --enter $ORCA_ENV >/dev/null 2>&1
            while [ "$(date +%s)" -lt "$deadline" ]; do
              sleep "$READY_INTERVAL"
              term_tail "$1" | python3 -c '
import json,sys,pathlib
sys.path.insert(0, "scripts")
import review_terminal as rt
sys.exit(0 if rt.tui_is_ready(json.load(sys.stdin)) else 1)' && return 0
            done
            return 1
          }
          send_review_prompt() {   # $1=핸들 $2=프롬프트 → 0=접수 확인
            orca-ide terminal send --terminal "$1" --text "$2" --enter $ORCA_ENV >/dev/null 2>&1
            local deadline; deadline=$(( $(date +%s) + SEND_VERIFY_TIMEOUT ))
            while [ "$(date +%s)" -lt "$deadline" ]; do
              sleep 2
              term_tail "$1" | python3 -c '
import json,sys
sys.path.insert(0, "scripts")
import review_terminal as rt
sys.exit(0 if rt.prompt_is_empty(json.load(sys.stdin)) else 1)' && return 0
            done
            return 1
          }
```

재전송 루프는 지운다 — 접수 판정이 고쳐지면 중복 송신의 근거가 사라진다.

- [ ] **Step 8: 실환경 재현 검증**

**이것이 이 task 의 완료 조건이다.** 자기가 만든 케이스를 돌린 것은 재현 확인이지 검증이 아니다.

1. 워크트리를 하나 만든다:
   `orca-ide worktree create --repo id:619d5257-8682-4630-9b94-2ada6af355cb --name t11-verify --agent claude --no-parent --environment wsl-native --json`
2. 응답의 `agentTerminalHandle` 로 위 `tui_ready` 를 손으로 돌려 **0 을 반환하는지** 확인한다.
   종전 `wait_agent_ready` 는 같은 조건에서 60초 뒤 1 을 반환했다.
3. `send_review_prompt` 로 아무 문장을 보내고 **접수가 확인되는지**, 그리고 **재전송이 일어나지
   않는지** 본다.
4. **kimi 경로도 같이 확인한다** — 지금 판정이 claude 에서만 깨졌으므로 고친 판정이 kimi 를
   깨뜨리지 않는지 봐야 한다. `--agent` 가 kimi 를 받지 않으므로 워크트리를 만든 뒤
   `orca-ide terminal create --worktree <셀렉터> --command kimi` 로 띄운다.
5. 확인이 끝나면 워크트리를 지운다:
   `orca-ide worktree rm --worktree id:<repoId>::<경로> --force --environment wsl-native`
6. **돌린 명령과 그 출력을 PR 본문에 그대로 싣는다.**

- [ ] **Step 9: 커밋**

```bash
git add scripts/review_terminal.py scripts/test_review_terminal.py .github/workflows/repo-scans.yml .github/workflows/cross-review.yml
git commit -m "fix(ci): 터미널 준비·접수를 화면 내용으로 판정한다 (#11)

종전 판정은 latestCursor 성장이었다. Claude Code TUI 는 화면을 제자리에서
다시 그려 그 값이 움직이지 않으므로 살아 있는 에이전트를 죽은 것으로 읽었다
— 재현 7/7. 타임아웃을 늘려도 무효인 종류다.

판정을 프롬프트 박스 상태로 바꾸고, 그때 실제로 읽은 화면을 케이스로 박는다."
```

---

## Task 3: 헤드리스 이중 경로와 폴백 체인을 삭제한다

**Files:**
- Modify: `.github/workflows/cross-review.yml` — `build_prompt`·`run_headless_once`·`synth_verdict`
  (984~1030) · 한도 감지 6함수(867~983) · `try_candidate` 와 체인 루프(1326~1421)
- Modify: `.github/workflows/cross-review.yml` — `publish` 잡의 폴백 안내문(1683~1810 산재)
- Modify: `.github/workflows/review-gate.yml:112` — `review: fallback-claude` 회수 목록에서 제거

**Interfaces:**
- Consumes: Task 1 의 `decide()` 반환값 (`chain`·`fallback_tier` 는 더 이상 만들지 않는다)

- [ ] **Step 1: 삭제 전에 소비자를 전수 조사한다**

Run:
```bash
grep -rn "CHAIN\|chain\|fallback_tier\|FALLBACK\|EXHAUSTED\|DEGRADED\|exec_path\|EXEC_PATH" .github/workflows/ | grep -v "^Binary"
```
Expected: `cross-review.yml` 과 `review-gate.yml` 두 파일에서만 나온다. **다른 파일이 나오면
이 계획이 낡은 것이므로 멈추고 보고한다.**

- [ ] **Step 2: 헤드리스 실행부를 지운다**

`build_prompt()` · `run_headless_once()` · `synth_verdict()` 와 그것을 부르는 자리를 삭제한다.
`decide_mode()` 가 `orca|headless` 를 고르던 것을 없애고 Orca 경로만 남긴다.

- [ ] **Step 3: 한도 감지·폴백 체인을 지운다**

`remaining()` · `is_rate_limited()` · `is_transient()` · `classify()` · `terminal_hints_limit()` ·
`probe_limit()` · `try_candidate()` 와 체인 루프를 삭제한다. 리뷰어 기동은 **1순위 하나만**
시도하고, 실패하면 실패로 끝낸다.

- [ ] **Step 4: `publish` 의 폴백 안내문을 지운다**

`FALLBACK_NOTE`·`CAUSE` 를 만드는 블록과 그것을 쓰는 `printf` 를 지운다. `route` 잡의
`chain`·`fallback_tier` 출력 선언도 지운다.

- [ ] **Step 5: 남은 참조가 없는지 확인한다**

Run:
```bash
grep -rn "fallback\|FALLBACK\|EXHAUSTED\|DEGRADED\|headless\|probe_limit" .github/workflows/ | grep -v "^Binary"
```
Expected: 0건. 하나라도 남으면 그 자리를 마저 지운다.

- [ ] **Step 6: YAML 문법을 확인한다**

Run: `python3 -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]; print('YAML OK')" .github/workflows/*.yml`
Expected: `YAML OK`

> `yaml` 은 stdlib 이 아니다. 없으면 `python3 -c "import json;print()"` 대신
> `gh workflow list` 로 대체하지 말고 `pip install --user pyyaml` 없이
> `git diff --check` 후 GitHub 이 파싱하는 것으로 확인한다 (push 후 Actions 탭).

- [ ] **Step 7: 줄 수를 세어 기록한다**

Run: `wc -l .github/workflows/cross-review.yml`
Expected: 삭제 전 2,020줄 → **1,700줄 안팎**. PR 본문에 실제 숫자를 적는다.

- [ ] **Step 8: 커밋**

```bash
git add .github/workflows/cross-review.yml .github/workflows/review-gate.yml
git commit -m "refactor(ci): 헤드리스 이중 경로와 폴백 체인을 걷어낸다

헤드리스 경로는 이 레포에서 9/9 안 탔다(게시된 판정 코멘트 전수의 '실행 경로'
필드). 두 경로를 유지하느라 한도 감지·재시도·판정 합성이 전부 두 벌이었다.

폴백 체인도 지운다. 리뷰어가 못 뜨면 자동 머지가 안 되는 것으로 정직하게
드러나고, 사람 머지는 막히지 않는다."
```

---

## Task 4: 경로 필터를 잡 레벨 조건으로 바꾼다

워크플로 레벨 `on.paths` 로 건너뛴 체크는 **영영 pending 이라 required 로 걸 수 없다.** 잡 레벨
`if:` 로 건너뛴 잡은 `skipped` 를 보고하고 GitHub 은 그것을 통과로 센다.

**Files:**
- Modify: `.github/workflows/ci.yml` (`on.paths` 제거 → `changes` 잡 + 잡별 `if:`)
- Modify: `.github/workflows/frontend-ci.yml` (동일)

**Interfaces:**
- Produces: `changes` 잡의 출력 `backend`·`frontend`·`mcp`·`workflows` (각 `'true'|'false'`)

- [ ] **Step 1: 지금 경로 필터를 기록한다**

Run: `awk '/^on:/,/^jobs:/' .github/workflows/ci.yml`
이 목록이 그대로 `changes` 잡의 필터가 된다. **하나도 빠뜨리지 않는다** — 빠뜨리면 그 경로
변경에 검사가 안 돈다.

- [ ] **Step 2: `changes` 잡을 추가한다**

`.github/workflows/ci.yml` 의 `on:` 에서 `paths:` 블록을 지우고 `pull_request: {}` 로 바꾼 뒤,
`jobs:` 맨 앞에 넣는다:

```yaml
  changes:
    name: "test: changes"
    runs-on: ubuntu-latest
    outputs:
      backend: ${{ steps.f.outputs.backend }}
      mcp: ${{ steps.f.outputs.mcp }}
      frontend: ${{ steps.f.outputs.frontend }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: f
        with:
          filters: |
            backend:
              - 'backend-service/**'
              - 'multi-agent-service/**'
              - '*/app/core/security.py'
              - '*/app/core/auth_context.py'
              - '*/app/core/config.py'
              - 'scripts/verify_auth_lockstep.py'
              - '*-service/CLAUDE.md'
              - 'scripts/verify_backend_claude_md.py'
              - 'scripts/run_standalone_tests.py'
              - 'scripts/run_verify_scripts.py'
              - 'scripts/verify_alembic_head_freshness.py'
              - 'frontend/prisma/init/tables.sql'
              - 'frontend/prisma/table-generator.cjs'
              - '.github/workflows/**'
            mcp:
              - '*-mcp-service/**'
              - '.github/workflows/**'
            frontend:
              - 'frontend/**'
              - '.github/workflows/**'
```

- [ ] **Step 3: 각 잡에 조건과 의존을 건다**

기존 잡마다 두 줄을 넣는다. 예:

```yaml
  mcp-services:
    name: "test: mcp-services"
    needs: changes
    if: ${{ needs.changes.outputs.mcp == 'true' }}
    runs-on: ubuntu-latest
```

- [ ] **Step 4: 문서 PR 에서 `skipped` 가 나오는지 확인한다**

`.md` 파일 하나만 바꾼 브랜치를 push 하고 PR 을 연다.
Run: `gh pr checks <번호>`
Expected: `test: backend` 등이 **`skipping`** 으로 나오고 pending 이 아니다.
**pending 이 하나라도 남으면 Task 5 의 브랜치 보호를 걸면 안 된다** — 그 PR 은 영영 막힌다.

- [ ] **Step 5: 커밋**

```bash
git add .github/workflows/ci.yml .github/workflows/frontend-ci.yml
git commit -m "refactor(ci): 경로 필터를 워크플로 레벨에서 잡 레벨로 옮긴다

워크플로째 건너뛴 체크는 영영 pending 이라 required 로 걸 수 없다. 잡 레벨
조건으로 건너뛴 잡은 skipped 를 보고하고 GitHub 은 그것을 통과로 센다."
```

---

## Task 5: required 게이트 잡을 세운다

테스트 9종을 개별로 required 로 걸지 않는다. 「전부 초록인가」를 대표하는 잡 하나만 건다 —
pending 창이 하나로 줄어 Orca 머지 버튼이 닫혀 있는 시간이 짧아진다.

**Files:**
- Modify: `.github/workflows/repo-scans.yml` (경로 필터가 없어 모든 PR 에서 돈다)

**Interfaces:**
- Produces: 체크 이름 `test: gate` — Task 6 의 브랜치 보호가 이 이름을 required 로 건다

- [ ] **Step 1: 게이트 잡을 추가한다**

`.github/workflows/repo-scans.yml` 에 넣는다:

```yaml
  gate:
    name: "test: gate"
    if: ${{ always() }}
    needs: [ci-coverage, repo-scan, repo-scan-app]
    runs-on: ubuntu-latest
    steps:
      - name: 상류 잡 전수 판정 (skipped·success 만 통과)
        env:
          RESULTS: ${{ toJSON(needs) }}
        run: |
          set -euo pipefail
          python3 - <<'PY'
          import json, os, sys
          needs = json.loads(os.environ["RESULTS"])
          if not needs:
              print("FAIL 검사 대상 0건 — needs 가 비었다")
              sys.exit(1)
          bad = {k: v["result"] for k, v in needs.items()
                 if v["result"] not in ("success", "skipped")}
          print(f"게이트: 상류 {len(needs)}건 검사 · 실패 {len(bad)}건")
          for k, v in bad.items():
              print(f"  {k}: {v}")
          sys.exit(1 if bad else 0)
          PY
```

> `needs` 에는 `ci.yml`·`frontend-ci.yml` 의 잡을 넣을 수 없다 — 다른 워크플로다.
> 그쪽은 Task 6 에서 required 목록에 개별로 넣거나, 넣지 않고 자문으로 둔다.
> **어느 쪽인지는 Task 6 Step 2 에서 정한다.**

- [ ] **Step 2: 검사 0건이 실패하는지 확인한다**

`needs` 목록을 일시적으로 비운 사본으로 위 파이썬 블록을 손으로 돌린다:

Run: `RESULTS='{}' python3 -c "$(sed -n '/^import json/,/sys.exit/p' /dev/stdin)" <<< ""`
간단히는 다음으로 확인한다:
```bash
RESULTS='{}' python3 -c '
import json,os,sys
needs=json.loads(os.environ["RESULTS"])
print("FAIL 검사 대상 0건" if not needs else "OK"); sys.exit(1 if not needs else 0)'
```
Expected: `FAIL 검사 대상 0건` · 종료코드 1

- [ ] **Step 3: 커밋**

```bash
git add .github/workflows/repo-scans.yml
git commit -m "feat(ci): 상류 잡을 대표하는 required 게이트 잡을 세운다

테스트를 개별로 required 로 걸면 pending 창이 여러 개가 되어 머지 버튼이
오래 닫힌다. 하나로 대표하고, skipped·success 만 통과시킨다. 상류가 0건이면
실패한다."
```

---

## Task 6: 브랜치 보호를 걸고 Orca 에서 체감을 잰다

**이 task 는 코드 변경이 아니라 설정 변경 + 실측이다.** 되돌리기가 토글 하나이므로 논쟁하지 말고
재본다.

**Files:** 없음 (레포 설정)

- [ ] **Step 1: 현재 상태를 기록한다**

Run: `gh api repos/Danwoo/trading-lab/branches/main/protection`
Expected: `{"message":"Branch not protected", "status":"404"}`

- [ ] **Step 2: required 목록을 정한다**

Task 4 Step 4 에서 `skipping` 이 확인된 워크플로만 required 후보다. 확인 안 된 것은 넣지 않는다.
최소 구성은 `test: gate` 하나다.

- [ ] **Step 3: 보호를 건다 (approvals 없이)**

```bash
gh api -X PUT repos/Danwoo/trading-lab/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  --input - <<'JSON'
{
  "required_status_checks": {"strict": false, "contexts": ["test: gate"]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```

`"required_pull_request_reviews": null` 이 핵심이다 — 승인을 required 로 걸지 않는다
(설계 결정 로그 2026-08-08).

- [ ] **Step 4: 걸렸는지 확인한다**

Run: `gh api repos/Danwoo/trading-lab/branches/main/protection --jq '{checks: .required_status_checks.contexts, reviews: .required_pull_request_reviews}'`
Expected: `{"checks": ["test: gate"], "reviews": null}`

- [ ] **Step 5: Orca 에서 30분 써 본다**

PR 을 하나 열고 Orca 에서 다음을 본다:
1. 테스트가 도는 동안 머지 버튼이 닫히는가 (닫히는 것이 정상)
2. 테스트가 끝나면 열리는가
3. **`mergeStateStatus` 가 `UNKNOWN` 인 창에서 버튼이 어떻게 구는가** — 설계 문서의
   미검증 위험이 이 자리다

체감이 나쁘면 되돌린다: `gh api -X DELETE repos/Danwoo/trading-lab/branches/main/protection`

- [ ] **Step 6: 결과를 결정 로그에 적는다**

`CONTEXT.md` 의 `## 결정 로그` 에 한 줄 추가한다 (추가 전용 — 기존 항목 수정 금지):

```
- 2026-08-08 브랜치 보호=required 체크 `test: gate` 하나, 승인 required 아님 (개별 체크 required 기각 — pending 창이 여러 개가 되어 Orca 머지 버튼이 오래 닫힌다 / 승인 required 기각 — AI 리뷰가 죽으면 사람도 못 머지해 작업 정지 장치가 된다, 2026-08-06 결정 취지)
```

- [ ] **Step 7: 커밋**

```bash
git add CONTEXT.md
git commit -m "docs: 브랜치 보호 결정을 결정 로그에 남긴다"
```

---

## Task 7: 판정을 GitHub 리뷰로 기록하는 기록기

리뷰어는 판정 코멘트를 남기고, 기록기가 `github-actions[bot]` 명의로 `gh pr review` 를 대행한다.
GitHub 은 자기 PR 자기 승인을 금지하므로 로컬 `gh`(리드 계정)로는 승인이 안 된다.

**Files:**
- Create: `scripts/review_record.py`
- Create: `scripts/test_review_record.py`
- Create: `.github/workflows/review-record.yml`
- Modify: `.github/workflows/repo-scans.yml` (배선)

**Interfaces:**
- Consumes: Task 1 의 `label_allowed`
- Produces: `decide_record(marker, head_sha, gate_ok, risk, author_login) -> dict` —
  키는 `action`(`"approve"|"request_changes"|"none"`) · `arm_automerge`(`bool`) · `reason`(`str`)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`scripts/test_review_record.py`:

```python
"""판정 마커 → 리뷰 행동·자동 머지 arm 회귀 그물 — stdlib 전용.

경계 셋을 못박는다:
  ① 마커 sha 가 head 와 다르면 낡은 판정이다 (승인을 켜지 않으므로 GitHub 의
     stale 무효화에 기댈 수 없다 — 우리가 대조한다).
  ② source=manual 마커는 사람이 타이핑한 한 줄일 수 있으므로 자동 머지를 arm 하지 않는다.
  ③ 봇 저자는 위험 선언이 없어도 자동 머지 대상이다 (2026-08-08 리드 결정).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_record as rr

HEAD = "a" * 40
OLD = "b" * 40

CASES = [
    ("merge_ok + 최신 + 저위험 → 승인·arm",
     {"verdict": "merge_ok", "sha": HEAD, "source": None}, HEAD, True, "low",
     "danwoo", "approve", True),
    ("merge_ok + 낡은 sha → 아무것도 안 한다",
     {"verdict": "merge_ok", "sha": OLD, "source": None}, HEAD, True, "low",
     "danwoo", "none", False),
    ("needs_changes → 변경 요청, arm 안 함",
     {"verdict": "needs_changes", "sha": HEAD, "source": None}, HEAD, True, "low",
     "danwoo", "request_changes", False),
    ("unable → 아무것도 안 한다",
     {"verdict": "unable", "sha": HEAD, "source": None}, HEAD, True, "low",
     "danwoo", "none", False),
    ("source=manual → 승인은 하되 arm 안 함",
     {"verdict": "merge_ok", "sha": HEAD, "source": "manual"}, HEAD, True, "low",
     "danwoo", "approve", False),
    ("게이트 빨강 → 승인은 하되 arm 안 함",
     {"verdict": "merge_ok", "sha": HEAD, "source": None}, HEAD, False, "low",
     "danwoo", "approve", False),
    ("고위험 → 승인은 하되 arm 안 함",
     {"verdict": "merge_ok", "sha": HEAD, "source": None}, HEAD, True, "high",
     "danwoo", "approve", False),
    ("위험 미선언 + 사람 저자 → arm 안 함",
     {"verdict": "merge_ok", "sha": HEAD, "source": None}, HEAD, True, None,
     "danwoo", "approve", False),
    ("위험 미선언 + 봇 저자 → arm 한다",
     {"verdict": "merge_ok", "sha": HEAD, "source": None}, HEAD, True, None,
     "dependabot[bot]", "approve", True),
]


def main() -> int:
    failures = 0
    for desc, marker, head, gate_ok, risk, author, want_action, want_arm in CASES:
        got = rr.decide_record(marker, head, gate_ok, risk, author)
        if got["action"] != want_action or got["arm_automerge"] is not want_arm:
            print(f"FAIL [{desc}] got action={got['action']!r} "
                  f"arm={got['arm_automerge']!r}, want {want_action!r}/{want_arm!r}")
            failures += 1
    print(f"review_record 케이스 {len(CASES)}건 검사 · 실패 {failures}건")
    if not CASES:
        print("FAIL 검사 대상 0건")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 실패를 확인한다**

Run: `python3 scripts/test_review_record.py`
Expected: `ModuleNotFoundError: No module named 'review_record'`

- [ ] **Step 3: 최소 구현을 쓴다**

`scripts/review_record.py`:

```python
"""판정 마커와 PR 상태로 리뷰 행동과 자동 머지 arm 여부를 정한다 — 순수 판정, stdlib 전용.

승인을 required 로 걸지 않으므로 GitHub 의 stale approval 무효화를 못 쓴다.
마커의 sha 를 head 와 직접 대조하는 것이 그 대체다.
"""

import re

MARKER = re.compile(
    r"<!--\s*cross-review v1"
    r"(?=[^>]*\bverdict=(?P<verdict>[a-z_]+))"
    r"(?=[^>]*\bsha=(?P<sha>[0-9a-f]{7,40}))"
    r"(?:(?=[^>]*\bsource=(?P<source>[a-z]+)))?"
    r"[^>]*-->"
)

BOT_SUFFIX = "[bot]"


def parse_marker(body):
    """코멘트 본문에서 마지막 마커를 읽는다. 없으면 None."""
    last = None
    for m in MARKER.finditer(body):
        last = {"verdict": m.group("verdict"), "sha": m.group("sha"),
                "source": m.group("source")}
    return last


def decide_record(marker, head_sha, gate_ok, risk, author_login):
    if marker is None:
        return {"action": "none", "arm_automerge": False, "reason": "마커 없음"}
    if not head_sha.startswith(marker["sha"]):
        return {"action": "none", "arm_automerge": False,
                "reason": f"낡은 판정 (마커 {marker['sha']} ≠ head {head_sha[:12]})"}

    verdict = marker["verdict"]
    if verdict == "needs_changes":
        return {"action": "request_changes", "arm_automerge": False,
                "reason": "수정 필요"}
    if verdict != "merge_ok":
        return {"action": "none", "arm_automerge": False,
                "reason": f"판정 {verdict} — 기록하지 않는다"}

    reasons = []
    if marker["source"] == "manual":
        reasons.append("수동 마커")
    if not gate_ok:
        reasons.append("게이트 미통과")
    if not (risk == "low" or author_login.endswith(BOT_SUFFIX)):
        reasons.append("저위험 아님" if risk else "위험 미선언")

    return {"action": "approve", "arm_automerge": not reasons,
            "reason": "자동 머지 arm" if not reasons else " · ".join(reasons)}
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python3 scripts/test_review_record.py`
Expected: `review_record 케이스 9건 검사 · 실패 0건` · 종료코드 0

- [ ] **Step 5: 기록기 워크플로를 만든다**

`.github/workflows/review-record.yml`:

```yaml
# review-record — 판정 마커를 GitHub 리뷰로 옮겨 적는다.
#
# 파이프라인이 아니라 기록기다. 판단은 Orca 의 리뷰어가 하고 여기서는 읽어서
# 옮기기만 한다. 승인이 github-actions[bot] 명의여야 하는 이유는 GitHub 이
# 자기 PR 자기 승인을 금지하기 때문이다 (Orca 리뷰어는 리드 계정으로 나간다).
name: review-record
on:
  issue_comment:
    types: [created]

permissions:
  pull-requests: write
  contents: read
  checks: read

concurrency:
  group: review-record-${{ github.event.issue.number }}
  cancel-in-progress: false

jobs:
  record:
    name: "chore: review-record (비게이트)"
    if: ${{ github.event.issue.pull_request && contains(github.event.comment.body, 'cross-review v1') }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: 마커 판독 → 리뷰 기록 · 자동 머지 arm
        env:
          GH_TOKEN: ${{ github.token }}
          PR: ${{ github.event.issue.number }}
          BODY: ${{ github.event.comment.body }}
        run: |
          set -euo pipefail
          HEAD_SHA=$(gh pr view "$PR" --json headRefOid --jq .headRefOid)
          AUTHOR=$(gh pr view "$PR" --json author --jq .author.login)
          RISK=$(gh pr view "$PR" --json labels --jq '[.labels[].name] | map(select(startswith("risk: "))) | first // ""' | sed 's/^risk: //')
          GATE=$(gh pr checks "$PR" --json name,state --jq '[.[] | select(.name=="test: gate")] | first | .state // ""')
          DECISION=$(python3 - <<'PY'
          import json, os, sys
          sys.path.insert(0, "scripts")
          import review_record as rr
          marker = rr.parse_marker(os.environ["BODY"])
          print(json.dumps(rr.decide_record(
              marker, os.environ["HEAD_SHA"],
              os.environ.get("GATE") == "SUCCESS",
              os.environ.get("RISK") or None,
              os.environ["AUTHOR"])))
          PY
          )
          ACTION=$(printf '%s' "$DECISION" | python3 -c 'import json,sys;print(json.load(sys.stdin)["action"])')
          ARM=$(printf '%s' "$DECISION" | python3 -c 'import json,sys;print(json.load(sys.stdin)["arm_automerge"])')
          REASON=$(printf '%s' "$DECISION" | python3 -c 'import json,sys;print(json.load(sys.stdin)["reason"])')
          echo "판독: action=${ACTION} arm=${ARM} 사유=${REASON}"
          case "$ACTION" in
            approve)         gh pr review "$PR" --approve --body "독립 리뷰 판정을 기록한다 — ${REASON}" ;;
            request_changes) gh pr review "$PR" --request-changes --body "독립 리뷰 판정을 기록한다 — ${REASON}" ;;
            none)            echo "기록할 것 없음 (${REASON})" ;;
          esac
          if [ "$ARM" = "True" ]; then
            gh pr merge "$PR" --squash --auto
            echo "자동 머지 arm 됨"
          fi
```

- [ ] **Step 6: CI 에 배선한다**

`.github/workflows/repo-scans.yml` 의 `repo-scan` 잡에 추가:

```yaml
      - name: 리뷰 기록 판정 회귀 그물
        run: python3 scripts/test_review_record.py
```

- [ ] **Step 7: 배선 대조**

Run: `python3 scripts/verify_ci_check_coverage.py`
Expected: 종료코드 0

- [ ] **Step 8: 실환경 확인 — 봇 승인이 실제로 서는가**

**설계 문서의 미검증 위험 중 하나다.** 확인 없이 다음으로 가지 않는다.

1. 테스트 PR 을 하나 연다
2. 그 PR 에 마커가 든 코멘트를 손으로 단다:
   `<!-- cross-review v1 model=claude verdict=merge_ok sha=<그 PR 의 head> -->`
3. Run: `gh pr view <번호> --json reviews --jq '.reviews[] | {author: .author.login, state: .state}'`
   Expected: `{"author": "github-actions", "state": "APPROVED"}`
4. 낡은 sha 로도 해 보고 **아무 리뷰도 안 달리는지** 확인한다
5. 명령과 출력을 PR 본문에 그대로 싣는다

- [ ] **Step 9: 커밋**

```bash
git add scripts/review_record.py scripts/test_review_record.py .github/workflows/review-record.yml .github/workflows/repo-scans.yml
git commit -m "feat(ci): 판정 마커를 GitHub 리뷰로 옮겨 적는 기록기

판단은 Orca 리뷰어가 하고 이 워크플로는 읽어서 옮기기만 한다. 승인이
github-actions[bot] 명의여야 하는 이유는 GitHub 이 자기 PR 자기 승인을
막기 때문이다.

승인을 required 로 걸지 않으므로 stale 무효화를 GitHub 에 못 맡긴다 —
마커의 sha 를 head 와 직접 대조한다."
```

---

## Task 8: 흉내 내던 워크플로를 삭제하고 `plan-*` 을 통합한다

**Files:**
- Delete: `.github/workflows/merge-router.yml` · `review-gate.yml` · `board-status.yml`
- Delete: `.github/workflows/plan-check.yml` · `plan-label.yml` · `plan-label-issue.yml`
- Create: `.github/workflows/plan.yml` (위 셋의 잡을 이벤트로 갈라 담는다)
- Modify: 위 파일들을 참조하는 문서·스크립트 (Step 1 에서 전수 조사)

- [ ] **Step 1: 참조를 전수 조사한다**

**경로를 지우면 그 경로를 참조하는 것을 전부 찾는다.** 빨간불 난 것만 고치면 인스턴스만 고치고
클래스를 남긴 것이다.

Run:
```bash
grep -rn "merge-router\|review-gate\|board-status\|plan-check\|plan-label" \
  --include='*.md' --include='*.py' --include='*.yml' --include='*.mjs' . \
  | grep -v node_modules
```
조사한 목록과 처리 결과(갱신·삭제·해당 없음)를 **PR 본문에 담는다.**

- [ ] **Step 2: 삭제 전에 검증 스크립트를 돌리는지 확인한다**

Run:
```bash
for f in merge-router review-gate board-status plan-check plan-label plan-label-issue; do
  printf "%-18s %s건\n" "$f" "$(grep -cE 'python3? .*(verify|test)_.*\.(py|mjs)|node scripts/' .github/workflows/$f.yml)"
done
```
Expected: 전부 0건. **0이 아니면 그 스크립트가 고아가 되므로 먼저 다른 워크플로에 옮긴다.**

- [ ] **Step 3: `plan.yml` 을 만든다**

세 워크플로의 잡을 한 파일에 담고 이벤트로 가른다:

```yaml
name: plan
on:
  pull_request: {}
  issue_comment:
    types: [created]

permissions:
  issues: write
  pull-requests: write
  contents: read

jobs:
  plan-check:
    name: "chore: plan-check (비게이트)"
    if: ${{ github.event_name == 'pull_request' }}
    runs-on: ubuntu-latest
    steps: []   # plan-check.yml 의 스텝을 그대로 옮긴다

  plan-label:
    name: "chore: plan-reconcile (비게이트)"
    if: ${{ github.event_name == 'pull_request' }}
    runs-on: ubuntu-latest
    steps: []   # plan-label.yml 의 스텝을 그대로 옮긴다

  plan-label-issue:
    name: "chore: plan-label-issue (비게이트)"
    if: ${{ github.event_name == 'issue_comment' }}
    runs-on: ubuntu-latest
    steps: []   # plan-label-issue.yml 의 스텝을 그대로 옮긴다
```

**`steps: []` 를 그대로 두지 않는다** — 원본 파일의 스텝을 통째로 복사해 넣는다. 체크 이름은
`gh pr checks` 에서 확인한 기존 이름과 **byte-identical** 로 유지한다.

- [ ] **Step 4: 삭제한다**

```bash
git rm .github/workflows/merge-router.yml .github/workflows/review-gate.yml \
       .github/workflows/board-status.yml .github/workflows/plan-check.yml \
       .github/workflows/plan-label.yml .github/workflows/plan-label-issue.yml
```

- [ ] **Step 5: 배선 대조와 줄 수를 확인한다**

Run: `python3 scripts/verify_ci_check_coverage.py`
Expected: 종료코드 0

Run: `ls .github/workflows/*.yml | wc -l && cat .github/workflows/*.yml | wc -l`
Expected: 파일 **5개** · 총 줄 수 **1,100줄 이하**. 실제 숫자를 PR 본문에 적는다.

- [ ] **Step 6: 커밋**

```bash
git add -A .github/workflows/
git commit -m "refactor(ci): 흉내 내던 워크플로를 삭제하고 plan-* 을 통합한다

merge-router 와 review-gate 는 존재 이유가 'GitHub 이 안 막으니 우리가
흉내 낸다' 였다. 브랜치 보호와 네이티브 리뷰가 그 자리를 가져가면서
역할이 없어졌다.

board-status 는 fail-open 이라 초록이 '했다' 를 보장하지 못했다 (리드 결정).
plan-* 셋은 트리거만 다른 같은 관심사라 한 파일로 합친다."
```

---

## 자체 검토 결과

**설계 대비 커버리지**

| 설계 항목 | task |
| --- | --- |
| §1 경계 (결정론적인 것만 CI) | Task 3·8 |
| §2 네이티브 PR 리뷰 | Task 7 |
| §2-1 봇 PR 자동 머지 | Task 7 (케이스 9) |
| §3 라벨은 위험도만 | Task 7·8 |
| §4 머지 두 문장 + required 게이트 | Task 5·6 |
| §5 축 ① automation 3종 · 축 ② 정체 감지 | **이 계획에 없음 — 아래 참조** |
| §6 걷어내기 | Task 3·8 |
| §7 bash → scripts/ | Task 1·2·7 |

**의도적으로 뺀 것**: 설계 §5 의 두 축(Orca automation 3종 · 정체 감지)은 **CI 가 아니라 Orca
쪽 subsystem** 이고 도구(`orca-ide` CLI)도 다르다. 이 계획을 끝내면 CI 는 완결된 상태로 서고,
automation 은 그 위에 독립적으로 얹힌다. **별도 계획으로 세운다.**

**남은 미결** (설계 문서와 동일):

1. major 버전 봇 PR 을 사람 경로로 뺄 것인가 — 채택되면 Task 7 의 `decide_record` 에
   `update_type` 인자가 하나 는다
2. 워커 기동 automation 의 착수 표식 — automation 계획에서 정한다

## 이 계획이 못 닫는 것

- **Orca `UNKNOWN` 창의 머지 버튼 동작** — Task 6 Step 5 에서 재보지만 설계로는 못 닫는다.
  되돌리기가 토글 하나다.
- **`lastActivityAt` 이 안 움직이는 것** — Orca 가 주는 값이라 우리가 못 고친다. 이 계획은
  스윕 자체를 CI 에서 걷어내는 것으로 우회하지만, Orca automation 이 정리를 맡을 때 같은 함정을
  다시 밟지 않도록 automation 계획에 명시해야 한다.
