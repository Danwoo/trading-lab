"""`scan_push_for_secrets.sh` 가 **잡아야 할 것을 잡는지** (standalone, fail-closed).

## 왜 이 그물이 따로 필요한가

종전에는 gitleaks 의 공식 훅(`gitleaks protect --staged`)을 pre-push 단계에 그대로 걸었고,
「`pre-commit run --hook-stage pre-push` 가 Passed 였다」로 검증을 끝냈다. 그런데 `--staged` 는
**git 인덱스**를 보고 push 시점에는 인덱스가 비어 있는 것이 정상이라, 그 훅은 **아무것도 안
보고 늘 통과**한다 — 「통과했다」는 정상 동작과 회귀를 구분하지 못한다 (#488 리뷰 지적).

그래서 여기서는 **진짜 비밀을 커밋한 임시 레포**를 만들어 스크립트를 돌리고, 거부하는지를 본다.
잡는 것을 확인하지 않은 방어층은 있는 척만 하는 층이다.

    python3 scripts/test_scan_push_for_secrets.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "scan_push_for_secrets.sh"
#: 합성 카나리아 — 실제 자격증명이 아니다. gitleaks 의 AWS 키 규칙 모양만 빌린다.
CANARY = "AKIA" + "ABCDEFGHIJKLMNOP"  # gitleaks:allow — 합성 카나리아 (실 키 아님)

CHECKED = 0
FAILURES: list[str] = []


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def find_gitleaks() -> str | None:
    found = shutil.which("gitleaks")
    if found:
        return found
    # pre-commit 이 받아 둔 것을 쓴다 — 훅과 같은 판본이라 이 그물이 실제 경로를 잰다.
    cache = Path.home() / ".cache" / "pre-commit"
    if cache.is_dir():
        for path in cache.glob("repo*/golangenv-*/bin/gitleaks"):
            return str(path)
    return None


def run(tmp: Path, env_extra: dict[str, str], binary: str) -> int:
    env = {**os.environ, "GITLEAKS_BIN": binary, **env_extra}
    done = subprocess.run(["bash", str(SCRIPT)], cwd=tmp, capture_output=True, text=True, env=env)
    return done.returncode


def git(tmp: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=tmp, capture_output=True, text=True).stdout.strip()


def main() -> int:
    binary = find_gitleaks()
    if not binary:
        # 못 찾으면 **검사한 것이 0건**이다 — 통과로 끝내지 않는다.
        print("::error::gitleaks 바이너리를 못 찾았다 — 이 그물은 실제 실행으로만 성립한다 (fail-closed)")
        return 1

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        (tmp / "scripts").mkdir()
        subprocess.run(["git", "init", "-q", "."], cwd=tmp, check=True)
        git(tmp, "config", "user.email", "t@t.test")
        git(tmp, "config", "user.name", "t")
        (tmp / "ok.txt").write_text("hello\n")
        git(tmp, "add", "-A")
        git(tmp, "commit", "-q", "-m", "base")
        base = git(tmp, "rev-parse", "HEAD")

        (tmp / "secret.txt").write_text(CANARY + "\n")
        git(tmp, "add", "-A")
        git(tmp, "commit", "-q", "-m", "add secret")
        tip = git(tmp, "rev-parse", "HEAD")

        check(
            "커밋된 비밀을 잡는다 — push 를 거부한다",
            run(tmp, {"PRE_COMMIT_FROM_REF": base, "PRE_COMMIT_TO_REF": tip}, binary),
            1,
        )
        check(
            "범위를 못 받으면 거부한다 — 훑을 것을 모른다",
            run(tmp, {}, binary),
            1,
        )

        (tmp / "clean.txt").write_text("nothing here\n")
        git(tmp, "add", "-A")
        git(tmp, "commit", "-q", "-m", "clean")
        clean_tip = git(tmp, "rev-parse", "HEAD")
        check(
            "깨끗한 커밋만 밀면 통과한다 — 막는 범위가 넓어지지 않았다",
            run(tmp, {"PRE_COMMIT_FROM_REF": tip, "PRE_COMMIT_TO_REF": clean_tip}, binary),
            0,
        )
        check(
            "밀 커밋이 없으면 통과한다",
            run(tmp, {"PRE_COMMIT_FROM_REF": clean_tip, "PRE_COMMIT_TO_REF": clean_tip}, binary),
            0,
        )

        # **옛 방식은 같은 상황에서 통과한다** — 이 그물이 지키는 것이 그 차이다.
        old = subprocess.run(
            [binary, "protect", "--staged", "--redact", "--no-banner"],
            cwd=tmp,
            capture_output=True,
            text=True,
        )
        check("옛 방식(protect --staged)은 커밋된 비밀을 못 본다", old.returncode, 0)

    for line in FAILURES:
        print(f"FAIL {line}")
    print(f"\n검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if FAILURES:
        print("판정: push 시크릿 스캔이 기대와 다르게 동작한다 — 위 FAIL 을 보라")
        return 1
    print("판정: push 되는 커밋의 비밀을 실제로 잡고, 깨끗한 push 는 막지 않는다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
