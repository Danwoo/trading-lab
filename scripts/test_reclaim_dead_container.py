"""#452 A-1 — 죽은 컨테이너만 걷어내고 **돌고 있는 것은 건드리지 않는가** (standalone, fail-closed).

도커를 실제로 띄우지 않는다. `DOCKER_BIN` 으로 가짜 도커를 끼워 **판단**만 본다 — 결함이
사는 자리가 거기다(어느 상태에서 지우고 어느 상태에서 멈추는가). 실제 도커에서 도는지는
PR 본문의 실측이 받는다.

    uv run python scripts/test_reclaim_dead_container.py
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "reclaim_dead_container.sh"

#: 가짜 도커 — `inspect` 는 정해진 상태를 내고, `rm` 은 불린 사실을 파일에 남긴다.
FAKE_DOCKER = """#!/usr/bin/env bash
if [ "$1" = "inspect" ]; then
  if [ "$FAKE_STATE" = "missing" ]; then exit 1; fi
  echo "$FAKE_STATE"
  exit 0
fi
if [ "$1" = "rm" ]; then
  echo "$@" >> "$FAKE_RM_LOG"
  exit 0
fi
exit 0
"""


def run(state: str, name: str = "fintech-pg"):
    with tempfile.TemporaryDirectory() as tmp:
        docker = Path(tmp) / "docker"
        docker.write_text(FAKE_DOCKER, encoding="utf-8")
        docker.chmod(0o755)
        rm_log = Path(tmp) / "rm.log"
        env = {**os.environ, "DOCKER_BIN": str(docker), "FAKE_STATE": state, "FAKE_RM_LOG": str(rm_log)}
        proc = subprocess.run(["bash", str(SCRIPT), name], capture_output=True, text=True, env=env)
        removed = rm_log.read_text(encoding="utf-8") if rm_log.exists() else ""
        return proc.returncode, (proc.stdout + proc.stderr), removed


def main() -> int:
    if not SCRIPT.exists():
        print(f"::error::{SCRIPT} 가 없다 — 검사할 것이 없다 (fail-closed)")
        return 1

    failures: list[str] = []
    checked = 0

    def check(label: str, condition: bool) -> None:
        nonlocal checked
        checked += 1
        if not condition:
            failures.append(label)

    rc, out, removed = run("false")
    check("죽은 컨테이너는 걷어낸다", rc == 0 and "rm -f fintech-pg" in removed)
    check("무엇을 왜 지웠는지 말한다", "걷어냅니다" in out and "named volume" in out)

    rc, out, removed = run("true")
    check("돌고 있는 것은 지우지 않는다", removed == "")
    check("돌고 있으면 멈춘다 — 조용히 지나가지 않는다", rc != 0)
    check("돌고 있을 때 다음 걸음을 말한다", "process-compose down" in out)

    rc, out, removed = run("missing")
    check("그런 이름이 없으면 통과한다", rc == 0 and removed == "")
    check("없을 때는 말을 얹지 않는다", out.strip() == "")

    rc, out, removed = run("Error: No such object")
    check("상태를 못 읽으면 건드리지 않는다", removed == "" and rc != 0)

    bare = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True)
    check("이름 없이 부르면 사용법을 내고 실패한다", bare.returncode == 2 and "사용법" in bare.stderr)

    print(f"검사한 단언 {checked}건 중 {checked - len(failures)}건 통과")
    for line in failures:
        print(f"::error::{line}")
    if failures:
        return 1
    print("판정: 죽은 것만 걷어내고, 살아 있으면 사유를 말하고 멈춘다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
