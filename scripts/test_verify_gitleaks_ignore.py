"""`verify_gitleaks_ignore.py` 가 **다른 줄의 유출을 덮는 지문**을 잡는지 (standalone, fail-closed).

예외 목록은 「진짜 유출을 덮는 한 줄」로 쓰이기 가장 쉬운 자리다. 종전 검사는 「파일 **어딘가에**
`gitleaks:allow` 가 있는가」만 봐서, 마커가 1번 줄에 있으면 2번 줄의 진짜 유출을 가리키는 지문도
통과했다 (#488 리뷰 지적). 그래서 여기서는 **그 공격을 그대로 구성해** 막히는지 본다.

    python3 scripts/test_verify_gitleaks_ignore.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify_gitleaks_ignore.py"
MARKER = "gitleaks:allow"
#: 합성 카나리아 두 줄 — 실제 자격증명이 아니다.
CANARY = "synthetic-value-for-redaction-test"
LEAK = "AKIA" + "ABCDEFGHIJKLMNOP"  # gitleaks:allow — 합성 카나리아 (실 키 아님)

CHECKED = 0
FAILURES: list[str] = []


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def run(tmp: Path, ignore_body: str) -> int:
    (tmp / ".gitleaksignore").write_text(ignore_body, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(tmp / "scripts" / "verify_gitleaks_ignore.py")], capture_output=True, text=True
    )
    return done.returncode


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        (tmp / "scripts").mkdir()
        (tmp / "scripts" / "verify_gitleaks_ignore.py").write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
        subprocess.run(["git", "init", "-q", "."], cwd=tmp, check=True)
        for key, value in (("user.email", "t@t.test"), ("user.name", "t")):
            subprocess.run(["git", "config", key, value], cwd=tmp, check=True)
        (tmp / "victim.py").write_text(
            f'CANARY = "{CANARY}"  # {MARKER} — 합성 카나리아 (실 키 아님)\nREAL = "{LEAK}"\n',
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=tmp, check=True)
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp, capture_output=True, text=True).stdout.strip()

        check(
            "마커가 다른 줄에 있으면 그 지문을 거부한다 — 진짜 유출을 덮지 못한다",
            run(tmp, f"{commit}:victim.py:generic-api-key:2\n"),
            1,
        )
        check(
            "지문이 마커 단 줄을 가리키면 통과한다",
            run(tmp, f"{commit}:victim.py:generic-api-key:1\n"),
            0,
        )
        check(
            "없는 커밋을 가리키면 거부한다 — 대조가 성립하지 않는다",
            run(tmp, f"{'1' * 40}:victim.py:generic-api-key:1\n"),
            1,
        )
        check(
            "지문 형식이 아니면 거부한다",
            run(tmp, "그냥-문자열\n"),
            1,
        )
        check(
            "파일은 있는데 항목이 0건이면 거부한다",
            run(tmp, "# 주석뿐\n"),
            1,
        )

    for line in FAILURES:
        print(f"FAIL {line}")
    print(f"\n검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if FAILURES:
        print("판정: 예외 검사가 기대와 다르게 동작한다 — 위 FAIL 을 보라")
        return 1
    print("판정: 지문이 가리키는 그 줄만 면제되고, 대조할 수 없으면 거부한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
