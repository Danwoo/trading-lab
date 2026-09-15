"""리뷰어 한도 판별 문구가 **지금 벤더가 쓰는 말**을 잡는가 (standalone, fail-closed).

## 왜 있나

`cross-review.yml` 의 사전 프로브는 후보마다 2.5초에 한도를 걸러, 소진된 리뷰어에 리뷰 상한
(수십 분)을 태우지 않게 한다. 그 판별은 **문구 하나**에 걸려 있는데, 벤더는 문구를 바꾼다.

실측 (2026-09-15, PR #501 리뷰 run 34925746697): kimi 가 0.30.0 → 0.36.1 로 가면서
`You've reached your usage limit for this billing cycle` 이
`You've reached your weekly (7-day) usage limit` 로 바뀌었다. 종전 패턴은 `your` 와
`usage limit` 사이에 낀 `weekly (7-day) ` 때문에 **미매치**였고, 그래서:

  04:19:44  kimi 시작        (사전 프로브가 한도를 못 잡아 그대로 디스패치)
  04:29:39  터미널에 한도 정황 — 확증 프로브도 같은 패턴이라 못 잡음 → 폴링 계속
  04:51:48  타임아웃 1884s 로 포기 → codex(76s 기동 실패) → claude
  04:59:33  claude 판정 산출 — **6분 29초**

40분 중 33분이 버려졌다. 판별이 조용히 낡으면 폴백은 「돌긴 도는데 늦는」 상태가 된다.

## 무엇을 보나

패턴을 **워크플로에서 읽어** 기록된 원문에 대 본다 — 여기 사본을 두면 둘이 갈린다. 판정은
`grep -qiE` 로 실제 엔진에서 한다 (파이썬 `re` 로 옮기면 ERE 와 미묘하게 다르다).

    uv run python scripts/test_rate_limit_phrases.py
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/cross-review.yml"

#: 한도로 **잡혀야** 하는 원문 — 전부 CLI stderr 실측이다 (워크플로 주석의 기록과 같은 출처).
LIMIT_SAMPLES: dict[str, str] = {
    "kimi 0.30.0": (
        "error: failed to run prompt: provider.api_error: 403 You've reached your usage limit "
        "for this billing cycle. Your quota will be refreshed in the next cycle."
    ),
    "kimi 0.36.1 (2026-09-15 — 주간 한도로 문구가 바뀌었다)": (
        "error: failed to run prompt: provider.auth_error: 403 You've reached your weekly (7-day) "
        "usage limit. Your quota will reset when the current 7-day window ends. To continue now, "
        "purchase extra usage or upgrade your plan: https://www.kimi.com/membership/subscription"
    ),
    "codex-cli 0.144.6": (
        "ERROR: You've hit your usage limit. Upgrade to Plus to continue using Codex, "
        "or try again at Aug 8th, 2026 3:06 PM."
    ),
}

#: 한도가 **아닌** 것 — 여기 걸리면 멀쩡한 리뷰어를 소진됐다고 버린다.
CONTROL_SAMPLES: dict[str, str] = {
    "신뢰 디렉터리 아님": "ERROR: Not inside a trusted directory. Run codex in a trusted workspace.",
    "네트워크 끊김": "error: failed to run prompt: ECONNRESET socket hang up",
    "리뷰 본문이 한도를 인용": ("이 PR 은 사용량 한도(usage limit)를 다루지 않는다 — diff 에 그 낱말이 있을 뿐이다."),
    "빈 stderr": "",
}


def workflow_pattern() -> str | None:
    """`is_rate_limited` 가 실제로 쓰는 패턴을 워크플로에서 꺼낸다."""
    text = WORKFLOW.read_text(encoding="utf-8")
    body = text[text.index("is_rate_limited() {") :]
    match = re.search(r'grep -qiE "([^"]+)"', body)
    return match.group(1) if match else None


def matches(pattern: str, sample: str) -> bool:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write(sample + "\n")
        path = handle.name
    try:
        return subprocess.run(["grep", "-qiE", pattern, path], check=False).returncode == 0
    finally:
        Path(path).unlink(missing_ok=True)


def main() -> int:
    pattern = workflow_pattern()
    if not pattern:
        print("::error::cross-review.yml 에서 `is_rate_limited` 의 패턴을 못 읽었다 — 대조할 것이 없다 (fail-closed)")
        return 1
    if not LIMIT_SAMPLES or not CONTROL_SAMPLES:
        print("::error::표본이 0건이다 — 통과가 아니다 (fail-closed)")
        return 1

    print(f"패턴: {pattern}")
    failures: list[str] = []

    for name, sample in LIMIT_SAMPLES.items():
        if not matches(pattern, sample):
            failures.append(f"한도인데 못 잡는다: {name}")
    for name, sample in CONTROL_SAMPLES.items():
        if matches(pattern, sample):
            failures.append(f"한도가 아닌데 잡는다: {name}")

    print(f"검사한 원문 {len(LIMIT_SAMPLES)}건(한도) + {len(CONTROL_SAMPLES)}건(대조)")
    for line in failures:
        print(f"::error::{line}")
    if failures:
        print("  → 벤더가 문구를 바꿨으면 워크플로의 패턴과 이 파일의 원문을 함께 고치세요.")
        return 1
    print("판정: 기록된 한도 문구를 전부 잡고, 한도가 아닌 것은 하나도 안 잡는다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
