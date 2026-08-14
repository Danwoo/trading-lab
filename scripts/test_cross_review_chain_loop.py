"""cross-review.yml 의 **체인 루프 자체**를 파일에서 뽑아 돌리는 회귀 그물.

## 왜 순수 함수 테스트만으로는 부족한가

`scripts/test_review_chain.py` 는 분류·집계가 옳은지를 본다. 그런데 이번 결함은 **판정이
틀린 것이 아니라 워크플로가 판정을 안 부른 것**이었다 — YAML 안 bash `case` 가 rc 10·20 만
폴백으로 인정해, 기동 실패에서 체인이 첫 후보에 멈췄다 (실측 run 31815113895). 분류부가
아무리 옳아도 호출부가 어긋나면 초록이 거짓말이 되는 자리다.

같은 함정을 이 파일 헤더가 이미 이름 붙여 뒀다 (「셸 플래그 함정」, 2026-07-29): Actions 기본
셸은 `bash -e {0}` 라 `set -uo pipefail` 이 `-e` 를 끄지 않고, 그 때문에 후보가 죽자 `rc=$?`
에 닿기도 전에 셸이 끝나 **폴백이 통째로 실행되지 않았다**. 그때 로컬 56케이스가 통과했던
이유는 추출한 스텝을 `bash -e` 로 안 돌렸기 때문이다.

그래서 이 그물은 두 가지를 지킨다:
  ① 루프 텍스트를 **워크플로 파일에서 그대로 뽑는다** (복제본을 검사하면 드리프트가 숨는다)
  ② **`bash -e` 로 실행한다** (Actions 기본 셸과 같은 자세)

후보 실행(`try_candidate`)만 스텁으로 갈아 rc 를 각본대로 돌려준다 — Orca·self-hosted 러너
없이 검증할 수 있는 것은 딱 그 경계까지다.

케이스를 0건 모으거나 루프 추출에 실패하면 실패한다 (fail-closed).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cross-review.yml"
JUDGE = REPO_ROOT / "scripts" / "review_chain.py"

START_ANCHOR = "── 체인 루프 (리뷰어가 바깥)"
END_ANCHOR = '} >> "$GITHUB_OUTPUT"'
YAML_INDENT = 10

# 후보 실행 스텁 — 실제 `run_orca`·`try_candidate` 와 같은 계약을 흉내 낸다:
# rc 를 돌려주고 실패 사유를 err.txt 에 남긴다. 사유 문구는 워크플로의 실제 문자열이다.
PREAMBLE = r"""
set -uo pipefail
set +e
CHAIN_STATE="$PWD/ctx/review_chain.py"
PR=999
FALLBACK_TIER=sonnet
ORCA_OK=yes
ORCA_WHY=런타임-ok+ready
GITHUB_OUTPUT="$PWD/gh_output"; : > "$GITHUB_OUTPUT"
GITHUB_STEP_SUMMARY="$PWD/gh_summary"; : > "$GITHUB_STEP_SUMMARY"
: > reviewer_tier.txt
IDX=0
try_candidate() {
  IDX=$(( IDX + 1 ))
  local rc; rc=$(printf '%s' "$SCRIPTED" | cut -d' ' -f"$IDX")
  : > err.txt
  echo "리뷰 후보 실행: $1"
  case "$rc" in
    21) echo "에이전트 TUI 준비 실패(60s — 입력 상자가 화면에 나타나지 않았다)" > err.txt ;;
    20) echo "Orca 리뷰 워커 타임아웃(2400s) — 마커 미검출" > err.txt ;;
    10) echo "You've reached your usage limit for this billing cycle" > err.txt ;;
    1)  echo "Orca 경로 불가용(런타임-불가용) — 리뷰 워커를 세울 수 없다 (후보를 갈아도 같다)" > err.txt ;;
    30) echo "체인 예산(5400s) 소진" > err.txt ;;
  esac
  return "$rc"
}
"""

TUI_FAIL = "에이전트 TUI 준비 실패(60s — 입력 상자가 화면에 나타나지 않았다)"

# (이름, 체인, rc 각본, 있어야 하는 조각들, 없어야 하는 조각들)
CASES: list[tuple[str, str, str, list[str], list[str]]] = [
    (
        "기동 실패(TUI) → 다음 후보로 넘어간다  ← 이 개정의 계기",
        "kimi claude",
        "21 0",
        [
            "리뷰 후보 실행: kimi",
            "리뷰 후보 실행: claude",
            "effective=claude",
            "fallback=yes",
            "startup_failed=kimi",
            "failure_kind=\n",
            TUI_FAIL,
        ],
        [],
    ),
    (
        "체인의 모든 후보가 실패하면 여전히 unable",
        "kimi claude",
        "21 21",
        [
            "리뷰 후보 실행: kimi",
            "리뷰 후보 실행: claude",
            "effective=\n",
            "failure_kind=chain-exhausted",
            "startup_failed=kimi·claude",
            "fail-closed(리뷰 불가)",
            "CI 교차 리뷰 실패 — 판정 없음",
        ],
        [],
    ),
    (
        "폴백이 성공해도 첫 후보의 실패 사유가 기록에 남는다",
        "kimi claude",
        "21 0",
        [
            f"리뷰어 시도 이력: kimi: 기동 실패 — {TUI_FAIL}",
            f"fallback_cause=kimi 기동 실패({TUI_FAIL})",
            "::warning::리뷰어 폴백",
            "### 리뷰어 폴백 — 실효 리뷰어",
        ],
        [],
    ),
    (
        "확정 실패(Orca 불가용)는 다음 후보를 시도하지 않는다",
        "kimi claude",
        "1 0",
        [
            "리뷰 후보 실행: kimi",
            "failure_kind=confirmed",
            "effective=\n",
            "startup_failed=\n",
        ],
        ["리뷰 후보 실행: claude"],
    ),
    (
        "예산 소진은 다음 후보를 시도하지 않는다 (남은 시간이 없다)",
        "kimi claude",
        "30 0",
        ["failure_kind=budget", "effective=\n"],
        ["리뷰 후보 실행: claude"],
    ),
    (
        "한도 → 다음 후보 (종전 동작 유지)",
        "kimi claude",
        "10 0",
        ["effective=claude", "exhausted=kimi", "fallback_cause=kimi 한도 소진"],
        [],
    ),
    (
        "타임아웃 → 다음 후보 (종전 동작 유지)",
        "kimi claude",
        "20 0",
        ["effective=claude", "degraded=kimi", "일시 장애"],
        [],
    ),
    (
        "1순위가 성공하면 폴백 표기가 붙지 않는다",
        "kimi claude",
        "0",
        ["effective=kimi", "fallback=no", "attempts_note=kimi: 판정 산출"],
        ["리뷰 후보 실행: claude", "::warning::리뷰어 폴백"],
    ),
]


def extract_loop() -> str:
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if START_ANCHOR in line), -1)
    if start < 0:
        raise SystemExit(f"::error::체인 루프 시작 앵커를 못 찾았다: {START_ANCHOR!r}")
    end = next(
        (
            i
            for i, line in enumerate(lines[start:], start)
            if line.strip() == END_ANCHOR
        ),
        -1,
    )
    if end < 0:
        raise SystemExit(f"::error::체인 루프 끝 앵커를 못 찾았다: {END_ANCHOR!r}")
    body = "\n".join(
        line[YAML_INDENT:] if line.startswith(" " * YAML_INDENT) else line.strip()
        for line in lines[start : end + 1]
    )
    # 뽑은 것이 정말 체인 루프인지 — 앵커만 맞고 내용이 딴 것이면 이 그물은 아무것도 안 본다
    for token in ("try_candidate", "chain_continue", "summarize", "attempts.tsv"):
        if token not in body:
            raise SystemExit(
                f"::error::추출한 블록에 {token!r} 가 없다 — 앵커가 밀렸다"
            )
    return body


def run_case(loop: str, chain: str, scripted: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "ctx").mkdir()
        (work / "ctx" / "review_chain.py").write_text(
            JUDGE.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (work / "driver.sh").write_text(PREAMBLE + loop, encoding="utf-8")
        # **`bash -e`** — Actions 기본 셸과 같은 자세 (헤더 「셸 플래그 함정」)
        proc = subprocess.run(
            ["bash", "-e", "driver.sh"],
            cwd=work,
            env={
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "SCRIPTED": scripted,
                "CHAIN": chain,
                "ROUTED": chain.split()[0],
                "LANG": "C.UTF-8",
            },
            capture_output=True,
            text=True,
        )
        out = work / "gh_output"
        summary = work / "gh_summary"
        return "\n".join(
            [
                proc.stdout,
                proc.stderr,
                "--- GITHUB_OUTPUT ---",
                out.read_text(encoding="utf-8") if out.exists() else "",
                "--- STEP_SUMMARY ---",
                summary.read_text(encoding="utf-8") if summary.exists() else "",
            ]
        )


def main() -> int:
    loop = extract_loop()
    print(f"cross-review.yml 에서 뽑은 체인 루프: {len(loop.splitlines())}줄")

    failures: list[str] = []
    for name, chain, scripted, expect, forbid in CASES:
        combined = run_case(loop, chain, scripted)
        missing = [e for e in expect if e not in combined]
        present = [f for f in forbid if f in combined]
        if missing or present:
            detail = "".join(f"\n    없음: {m!r}" for m in missing)
            detail += "".join(f"\n    있으면 안 됨: {p!r}" for p in present)
            failures.append(f"{name}{detail}\n    ── 실제 출력 ──\n{combined}")
        else:
            print(f"  통과  {name}")

    print(f"\n검사한 케이스 {len(CASES)}건 · 실패 {len(failures)}건")
    if not CASES:
        print("::error::케이스를 0건 모았습니다 — fail-closed 종료")
        return 1
    if failures:
        for f in failures:
            print(f"::error::{f}")
        return 1
    print("체인 루프 회귀 그물 통과 (bash -e · 워크플로에서 추출한 원문)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
