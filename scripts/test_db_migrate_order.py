#!/usr/bin/env python3
"""`db-migrate` 의 순서 판정이 fail-closed 인지 **실제로 돌려** 확인한다 (#359).

## 왜 필요한가

`process-compose.yaml` 의 `db-migrate` 는 「기존 DB 냐 신규 DB 냐」를 보고 `alembic` 을
`prisma db push` **앞**에 한 번 더 돌릴지 정한다. 그 판정이 틀리면 push 가 먼저 돌아
`frontend` 35컬럼을 `USING` 없이 SafeCast 로 바꾸고, 한 컬럼에 두 기원이 섞인 11개 테이블에서
**절반의 뜻이 사라진다** — 이 PR 이 막으려는 바로 그 사고다.

종전 형태는 그 자리에서 fail-open 이었다:

    if [ "$(… frontend_schema_present.py)" = "t" ]; then

명령치환은 stdout 만 가져오고 `set -e` 는 `if` 조건절 안에서 무효라, 두 가지가 조용히
「신규 DB」로 접혔다 —
  (A) DB 에 못 닿아 스크립트가 `exit 2` (stdout 은 빈 문자열)
  (B) stdout 에 잡음이 섞임 (종료코드는 0)

「모르는 상태」가 전부 파괴적인 쪽으로 흐르는 모양이다. 스크립트는 계약을 지키는데 호출부가
깼다.

## 무엇을 하나

**명령을 손으로 옮겨 적지 않는다** — `process-compose.yaml` 에서 뽑아 그대로 돌린다. 사본을
검사하면 「고친 그 명령」이 아니라 「내가 적어 둔 명령」을 확인하게 된다.

DB·네트워크는 쓰지 않는다. `PATH` 앞에 가짜 `uv`·`npm`·`python3` 를 놓아 판정 프로브의 출력과
종료코드만 갈아 끼우고, 뒤따르는 `alembic`·`prisma db push` 는 「돌았다」는 표식만 남긴다.
그래서 이 검사는 **호출부의 분기**만 본다.

    python3 scripts/test_db_migrate_order.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE = REPO_ROOT / "process-compose.yaml"

# (이름, 프로브 stdout, 프로브 종료코드, 기대 db-migrate 종료코드, push 가 돌아야 하나)
CASES: list[tuple[str, str, int, int, bool]] = [
    ("DB 도달 실패 (프로브 exit 2)", "", 2, 1, False),
    ("stdout 잡음 + 종료코드 0", "warning: 잡음\nt\n", 0, 1, False),
    ("빈 stdout + 종료코드 0", "", 0, 1, False),
    ("기존 DB (t)", "t\n", 0, 0, True),
    ("신규 DB (f)", "f\n", 0, 0, True),
]


def db_migrate_command() -> str:
    """`processes: db-migrate: command: |` 블록을 그대로 꺼낸다.

    **stdlib 만 쓴다** — 이 레포의 루트 `scripts/*.py` 는 의존성 없이 어디서든 돌아야 한다
    (러너의 맨 `python3` 에는 PyYAML 이 없다). 블록 스칼라 하나를 읽는 데 파서가 필요하지도
    않고, 파일 모양이 바뀌면 아래 가드가 시끄럽게 실패한다.
    """
    lines = COMPOSE.read_text(encoding="utf-8").splitlines()
    try:
        head = next(i for i, ln in enumerate(lines) if ln.rstrip() == "  db-migrate:")
    except StopIteration:
        raise SystemExit("::error::process-compose.yaml 에서 `db-migrate:` 를 못 찾았다(fail-closed)") from None

    body: list[str] | None = None
    for i in range(head + 1, len(lines)):
        line = lines[i]
        if line.strip() and not line.startswith("    "):
            break  # db-migrate 블록이 끝났다
        if line.rstrip() == "    command: |":
            block, indent = [], "      "
            for raw in lines[i + 1 :]:
                if raw.strip() and not raw.startswith(indent):
                    break
                block.append(raw[len(indent) :] if raw.startswith(indent) else "")
            body = block
            break
    if body is None:
        raise SystemExit("::error::db-migrate 의 `command: |` 블록을 못 찾았다(fail-closed)")

    command = "\n".join(body).rstrip("\n") + "\n"
    if "frontend_schema_present.py" not in command:
        raise SystemExit(
            "::error::db-migrate 명령에서 스키마 판정 프로브를 못 찾았다 — "
            "이 검사가 무엇을 보는지 모르는 상태다(fail-closed)"
        )
    return command


def _write_stubs(bindir: Path, probe_stdout: str, probe_rc: int, marker: Path, probe_out: Path) -> None:
    """가짜 `uv`·`npm`·`python3`. 프로브만 갈아 끼우고 나머지는 표식만 남긴다."""
    real_python = sys.executable

    # 프로브 stdout 은 파일로 준다 — 스텁 안에 문자열로 박으면 개행·따옴표가 셸에서 다시
    # 해석돼, 검사가 「무엇을 내보냈나」가 아니라 「어떻게 이스케이프했나」를 재게 된다.
    probe_out.write_text(probe_stdout, encoding="utf-8")
    (bindir / "uv").write_text(
        "#!/usr/bin/env bash\n"
        'case "$*" in\n'
        "  *frontend_schema_present.py*)\n"
        f"    cat {probe_out!s}\n"
        f"    exit {probe_rc} ;;\n"
        "  *alembic*)\n"
        f'    echo "alembic" >> {marker!s}; exit 0 ;;\n'
        "esac\n"
        'echo "예상 못 한 uv 호출: $*" >&2; exit 90\n',
        encoding="utf-8",
    )
    (bindir / "npm").write_text(f'#!/usr/bin/env bash\necho "push" >> {marker!s}\nexit 0\n', encoding="utf-8")
    # 프로브는 `uv run python` 으로 가므로, 직접 불리는 python3 는 head 신선도 검사뿐이다.
    (bindir / "python3").write_text(
        "#!/usr/bin/env bash\n"
        'case "$*" in\n'
        "  *verify_alembic_head_freshness.py*) exit 0 ;;\n"
        "esac\n"
        f'exec {real_python} "$@"\n',
        encoding="utf-8",
    )
    for name in ("uv", "npm", "python3"):
        (bindir / name).chmod(0o755)


def run_case(command: str, probe_stdout: str, probe_rc: int) -> tuple[int, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        bindir = tmpdir / "bin"
        bindir.mkdir()
        marker = tmpdir / "ran.txt"
        marker.touch()
        _write_stubs(bindir, probe_stdout, probe_rc, marker, tmpdir / "probe_out")

        env = dict(os.environ)
        env["PATH"] = f"{bindir}{os.pathsep}{env['PATH']}"
        proc = subprocess.run(
            ["bash", "-c", command],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc.returncode, marker.read_text(encoding="utf-8").split()


def main() -> int:
    command = db_migrate_command()
    print("db-migrate 순서 판정 검증 (process-compose.yaml 에서 뽑은 명령 그대로)")

    checked = 0
    problems: list[str] = []
    for name, probe_stdout, probe_rc, expected_rc, expect_push in CASES:
        checked += 1
        rc, ran = run_case(command, probe_stdout, probe_rc)
        pushed = "push" in ran
        if rc != expected_rc:
            problems.append(f"{name}: 종료코드 {rc} (기대 {expected_rc})")
        elif pushed != expect_push:
            problems.append(f"{name}: prisma db push 가 {'돌았다' if pushed else '안 돌았다'} (기대 반대)")
        else:
            verdict = "멈춘다" if expected_rc else ("alembic 먼저" if "alembic" in ran[:1] else "push 먼저")
            print(f"  ✓ {name} → 종료코드 {rc} · {verdict}")

    if checked < len(CASES):
        print(f"::error::케이스를 {checked}건만 돌았다 (기대 {len(CASES)}건) — fail-closed", file=sys.stderr)
        return 1
    print(f"케이스 {checked}건 검사")
    for line in problems:
        print(f"  ✗ {line}")
    if problems:
        print(
            "::error::db-migrate 의 순서 판정이 fail-closed 가 아니다 — "
            "모르는 상태가 파괴적인 쪽(push 먼저)으로 흐른다",
            file=sys.stderr,
        )
        return 1
    print("판정: 판정값이 t/f 가 아니거나 프로브가 죽으면 db-migrate 가 멈춘다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
