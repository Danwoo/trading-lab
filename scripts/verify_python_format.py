"""파이썬 포맷·린트를 레포 전수로 본다 — pre-commit 과 같은 범위, fail-closed (stdlib 전용).

## 왜 있나

`.pre-commit-config.yaml` 은 `ruff-check`·`ruff-format` 을 **레포의 모든 파이썬 파일**에 건다.
그런데 CI 는 `ruff format` 을 한 번도 돌지 않았고, `ruff check` 도 두 서비스의 `app/` 만 봤다
(`ci.yml` 의 multi-agent·bot-agent 잡). 그래서 포맷 드리프트는 **로컬 훅을 거치는 사람에게만**
빨간불이었고, 그 훅을 안 거치는 경로(다른 워커·CI)는 통과시켰다.

실측(#331 이후 origin/main): `scripts/verify_stage_claims.py` 가 표준을 위반한 채 앉아 있는데
CI 는 초록이었다. 그 파일은 `ci.yml` 의 `FILTER_PATTERNS` 에도 없어, 그것만 고치는 PR 은
서비스 잡이 전부 `skipped` 로 끝난다 — 「검사가 존재하지 않는」 자리였다.

## 무엇을 보나

pre-commit 이 보는 것과 **같은 범위**다:

  · 대상 = git 이 추적하는 `*.py`·`*.pyi` 전수 (`ruff-*` 훅의 `types_or: [python, pyi]`).
  · `ruff format --check --force-exclude` — 포맷 드리프트.
  · `ruff check --force-exclude` — 린트. `--fix` 는 붙이지 않는다: CI 에서 고치면 위반이
    조용히 사라지고 초록이 된다 (frontend `npx eslint .` 가 `--fix` 를 뺀 것과 같은 이유, #265).

설정은 ruff 가 파일마다 가장 가까운 `pyproject.toml` 에서 찾는다 — 서비스별 설정과 루트
`pyproject.toml` 이 그대로 적용되므로 여기서 `--line-length` 류를 지정하지 않는다.

## 버전은 훅에서 읽는다 (lockstep)

ruff 버전을 이 파일에 박으면 `.pre-commit-config.yaml` 의 `rev` 와 조용히 갈린다 — 그러면
로컬은 초록인데 CI 가 빨갛거나(또는 그 반대) 그 이유가 아무 데도 안 적힌다. 그래서 rev 를
훅 설정에서 **읽어** `uvx ruff@<버전>` 으로 고정한다. 못 읽으면 실패한다.

## fail-closed

  · 대상 파일 0건이면 실패한다 (`git ls-files` 가 안 돌았거나 글롭이 현실과 어긋난 것이다).
  · `.pre-commit-config.yaml` 에서 ruff rev 를 못 읽으면 실패한다.
  · `uvx` 가 없으면 실패한다 — PATH 의 아무 ruff 로 대신 돌면 버전 고정이 사라진다.

검사한 파일 수를 출력에 남긴다 — 초록이 「위반 없음」인지 「아무것도 안 봤음」인지 읽는 사람이
구분할 수 있어야 한다.

실행: `python3 scripts/verify_python_format.py`
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRECOMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"

# `.pre-commit-config.yaml` 에서 ruff 훅의 rev 를 잡는 앵커. repo URL 다음 줄의 `rev:` 다.
RUFF_REPO = "https://github.com/astral-sh/ruff-pre-commit"

# pre-commit 의 `ruff-check`/`ruff-format` 훅은 `types_or: [python, pyi]` 로 대상을 고른다.
TARGET_GLOBS = ("*.py", "*.pyi")


def _fail(msg: str) -> None:
    print(f"::error::{msg}")


def read_ruff_rev(text: str) -> str | None:
    """`.pre-commit-config.yaml` 의 ruff-pre-commit rev 를 읽는다 (`v` 접두 제거)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if RUFF_REPO not in line:
            continue
        for follow in lines[i + 1 : i + 4]:
            m = re.match(r"\s*rev:\s*['\"]?v?([0-9][0-9A-Za-z.\-]*)['\"]?\s*$", follow)
            if m:
                return m.group(1)
    return None


def collect_targets() -> list[str]:
    """git 이 추적하는 파이썬 파일 전수 (REPO_ROOT 상대 posix 경로)."""
    proc = subprocess.run(
        ["git", "ls-files", "-z", *TARGET_GLOBS],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        _fail(f"git ls-files 가 실패했습니다 (rc={proc.returncode}): {proc.stderr.strip()}")
        return []
    return sorted(p for p in proc.stdout.split("\0") if p)


def run_ruff(runner: list[str], phase: list[str], targets: list[str]) -> bool:
    """ruff 한 단계를 돌린다. 통과면 True."""
    # ruff 출력이 이 스크립트의 안내보다 먼저 나오면 CI 로그에서 순서가 뒤집힌다.
    sys.stdout.flush()
    proc = subprocess.run([*runner, *phase, "--force-exclude", *targets], cwd=REPO_ROOT, check=False)
    return proc.returncode == 0


def main() -> int:
    if not PRECOMMIT_CONFIG.is_file():
        _fail(f"훅 설정이 없습니다: {PRECOMMIT_CONFIG} — ruff 버전을 고정할 근거가 사라졌습니다")
        return 1

    version = read_ruff_rev(PRECOMMIT_CONFIG.read_text(encoding="utf-8"))
    if not version:
        _fail(
            f"{PRECOMMIT_CONFIG.name} 에서 {RUFF_REPO} 의 rev 를 못 읽었습니다 — "
            "훅과 CI 가 같은 ruff 를 쓴다는 보장이 사라집니다"
        )
        return 1

    if shutil.which("uvx") is None:
        _fail("uvx 가 없습니다 — PATH 의 임의 ruff 로 대신 돌면 훅과의 버전 고정이 사라집니다")
        return 1
    runner = ["uvx", f"ruff@{version}"]

    targets = collect_targets()
    print(
        f"ruff {version} (.pre-commit-config.yaml 의 rev) · 대상 {len(targets)}건 ({' '.join(TARGET_GLOBS)}, git 추적분)"
    )
    if not targets:
        _fail("검사 대상을 0건 수집했습니다 — 통과가 아닙니다 (git 저장소 밖이거나 글롭이 어긋났습니다)")
        return 1

    ok = True
    print("── ruff format --check ──")
    if not run_ruff(runner, ["format", "--check"], targets):
        _fail(
            "포맷이 표준과 어긋난 파일이 있습니다 — `pre-commit run --all` 또는 "
            f"`uvx ruff@{version} format <파일>` 로 맞추세요"
        )
        ok = False

    print("── ruff check ──")
    if not run_ruff(runner, ["check"], targets):
        _fail("린트 위반이 있습니다 — `pre-commit run --all` 로 고치세요 (CI 는 --fix 를 쓰지 않습니다)")
        ok = False

    print(f"판정: 파이썬 {len(targets)}건 · 포맷·린트 {'통과' if ok else '실패'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
