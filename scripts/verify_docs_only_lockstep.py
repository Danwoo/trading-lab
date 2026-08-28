"""문서 전용 정의의 lockstep — cross-review 가 건너뛰는 PR 이 정확히 App 이 승인하는 PR 인가 (stdlib 전용, fail-closed).

## 왜 있나

문서 전용 PR 은 두 자리가 나눠 맡는다:
  · `cross-review.yml` `on.pull_request.paths-ignore` — 문서 전용 PR 에서 독립 리뷰를 **안 띄운다**
  · `ci.yml` `docs-notice` 잡 — `scripts/review_notice.py` 로 문서 전용을 판정해 「독립 리뷰 없음」을
    고지하고, App 명의로 **승인 + 자동 머지 arm** 을 건다 (2026-08-28 리드 결정)

불변식: **둘의 「문서 전용」 정의가 같아야 한다.** 어긋나면 한쪽엔 빈틈(리뷰도 승인도 안 받는
PR — 영구 차단)이, 다른 쪽엔 겹침(리뷰가 돌면서 App 도 승인하는 PR — 리뷰 판정과 무관한 승인)이
생긴다. 둘 다 조용하다 — paths-ignore 는 YAML 한 줄이고 판정부는 파이썬 상수라, 한쪽만 고쳐도
아무 검사도 빨개지지 않는다. 이 스크립트가 그 클래스를 닫는다.

## 무엇을 대조하나

1. `cross-review.yml` 의 `paths-ignore` 목록 == `review_notice.IGNORE_PATTERNS` (순서 무관, 완전 일치).
2. `paths-ignore` 가 레포 워크플로 전체에서 **cross-review.yml 한 곳**에만 있다 — 다른 워크플로가
   자기 정의를 두면 정의가 둘이 된다. 특히 `ci.yml` 은 트리거 레벨 경로 판정을 쓰지 않는다
   (필터 밖 PR 에서 체크런이 안 생겨 required 가 영영 pending — `ci.yml` 머리 주석).
3. `ci.yml` 의 `docs-notice` 잡 안에서 `review_notice.py` 를 부르는 `run:` 블록이 **둘 이상**이다
   (고지 스텝 + 승인 스텝) — 승인 스텝이 판정부를 안 거치고 자기 정의로 승인하면 1 이 무의미해진다.
4. 승인 스텝은 판정부를 **기본 브랜치에서 내려받아** 쓴다 (`?ref=` + `DEFAULT_BRANCH`) — PR 트리의
   판정부로 자기 승인을 판정하면 PR 이 그 판정을 고칠 수 있다.

## fail-closed

대조한 항목 수를 세고 **0 이면 실패**한다. paths-ignore 블록을 못 찾거나 패턴 0건이면 「일치」가
아니라 「대상 없음」이므로 실패다 — 워크플로 형식이 바뀌어 파서가 헛돌면 여기서 드러난다.

실행: `python3 scripts/verify_docs_only_lockstep.py`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
CROSS_REVIEW = WORKFLOW_DIR / "cross-review.yml"
CI = WORKFLOW_DIR / "ci.yml"
DOCS_JOB_ID = "docs-notice"
JUDGE_FILE = "review_notice.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_notice  # noqa: E402

_JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_][A-Za-z0-9_-]*):\s*$")


def parse_paths_ignore(text: str) -> list[str]:
    """`on.pull_request.paths-ignore:` 블록의 항목을 낸다. 블록이 없으면 빈 목록."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)paths-ignore:", line)
        if not m:
            continue
        indent = len(m.group(1))
        items: list[str] = []
        for nxt in lines[i + 1 :]:
            if not nxt.strip() or nxt.strip().startswith("#"):
                continue
            lead = len(nxt) - len(nxt.lstrip())
            if lead <= indent:
                break
            im = re.match(r"^\s*-\s*(.+?)\s*(#.*)?$", nxt)
            if not im:
                break
            raw = im.group(1).strip()
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
                raw = raw[1:-1]
            items.append(raw)
        return items
    return []


def job_block(text: str, job_id: str) -> str:
    """`jobs.<job_id>:` 부터 다음 잡 머리 전까지."""
    lines = text.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        m = _JOB_HEADER.match(line)
        if m:
            if inside:
                break
            inside = m.group(1) == job_id
            continue
        if inside:
            out.append(line)
    return "\n".join(out)


def run_blocks(block: str) -> list[str]:
    """스텝의 `run:` 블록 본문들 (블록 스칼라만 — 이 잡은 전부 그 형식이다)."""
    lines = block.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)run:\s*(\|-?|>-?)?\s*$", lines[i])
        if m:
            indent = len(m.group(1))
            body: list[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= indent:
                    break
                body.append(nxt)
                j += 1
            out.append("\n".join(body))
            i = j
            continue
        i += 1
    return out


def main() -> int:
    checked = 0
    problems: list[str] = []

    # ① 패턴 목록 일치
    cross_text = CROSS_REVIEW.read_text(encoding="utf-8")
    declared = parse_paths_ignore(cross_text)
    judged = list(review_notice.IGNORE_PATTERNS)
    if not declared:
        problems.append(f"{CROSS_REVIEW.name}: `paths-ignore` 블록을 못 찾았거나 패턴 0건 — 대조 대상이 없다")
    if not judged:
        problems.append("review_notice.IGNORE_PATTERNS 가 비었다 — 모든 PR 이 문서 전용이 아니게 되어 승인이 죽는다")
    if declared and judged:
        checked += len(declared)
        if sorted(declared) != sorted(judged):
            problems.append(
                "문서 전용 정의 불일치 — "
                f"cross-review paths-ignore={sorted(declared)} vs review_notice.IGNORE_PATTERNS={sorted(judged)}. "
                "한쪽만 고치면 빈틈(리뷰도 승인도 없음) 또는 겹침(리뷰 중인 PR 을 App 이 승인)이 생긴다"
            )

    # ② 정의는 한 곳 — paths-ignore 는 cross-review.yml 에만
    for wf in sorted(WORKFLOW_DIR.glob("*.yml")):
        checked += 1
        has = bool(re.search(r"^\s*paths-ignore:", wf.read_text(encoding="utf-8"), re.M))
        if wf == CROSS_REVIEW and not has:
            problems.append(f"{wf.name}: `paths-ignore` 가 없다 — 정의의 정본이 사라졌다")
        if wf != CROSS_REVIEW and has:
            problems.append(
                f"{wf.name}: `paths-ignore` 를 따로 둔다 — 문서 전용 정의는 cross-review.yml + "
                "review_notice.py 한 벌뿐이어야 한다 (ci.yml 은 트리거 레벨 경로 판정 금지)"
            )

    # ③④ docs-notice 잡 — 판정부를 부르는 스텝이 둘 이상, 승인 스텝은 기본 브랜치 판본
    ci_text = CI.read_text(encoding="utf-8")
    docs_job = job_block(ci_text, DOCS_JOB_ID)
    if not docs_job:
        problems.append(f"{CI.name}: `{DOCS_JOB_ID}` 잡이 없다")
    else:
        blocks = run_blocks(docs_job)
        callers = [b for b in blocks if JUDGE_FILE in b]
        checked += 1
        if len(callers) < 2:
            problems.append(
                f"{CI.name} `{DOCS_JOB_ID}`: `{JUDGE_FILE}` 를 부르는 run 블록이 {len(callers)}개 — "
                "고지 스텝과 승인 스텝 둘 다 같은 판정부를 거쳐야 한다"
            )
        approvers = [b for b in blocks if 'event: "APPROVE"' in b and "pulls/$PR/reviews" in b]
        checked += 1
        if not approvers:
            problems.append(
                f"{CI.name} `{DOCS_JOB_ID}`: APPROVE 리뷰를 게시하는 run 블록이 없다 — 승인 스텝이 사라졌다"
            )
        for b in approvers:
            fetched = re.search(rf"contents/scripts/{re.escape(JUDGE_FILE)}\?ref=\$\{{?DEFAULT_BRANCH", b) or re.search(
                r"contents/scripts/\$\w+\?ref=\$\{?DEFAULT_BRANCH", b
            )
            if JUDGE_FILE in b and not fetched:
                problems.append(
                    f"{CI.name} `{DOCS_JOB_ID}`: 승인 스텝이 `{JUDGE_FILE}` 를 기본 브랜치에서 내려받지 않는다 — "
                    "PR 트리의 판정부로 자기 승인을 판정하면 PR 이 그 판정을 고칠 수 있다"
                )

    print(
        f"문서 전용 lockstep {checked}건 대조 · paths-ignore {sorted(declared)} · "
        f"IGNORE_PATTERNS {sorted(judged)} · 위반 {len(problems)}건"
    )
    if checked == 0:
        print("::error::대조 대상 0건 — 통과가 아니라 검사가 죽은 것이다 (fail-closed)")
        return 1
    for p in problems:
        print(f"::error::{p}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
