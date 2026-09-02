#!/usr/bin/env python3
"""자리표시자 자격증명으로 기동하지 않는다 (#433).

Cycle 7 발굴(B-33): `.env.example` 의 `CHANGE_ME` 가 그대로 복사돼 왔는데
`SFTP_USERNAME: str` 은 **존재만** 요구해서 통과했다. 앱은 모든 화면이 뜨는 정상 상태로 보였고,
새로 받은 사람은 파일을 올릴 때가 되어서야 막혔다 — 진짜 원인은 두 계층 아래 503 본문에만 있었다.

이 레포의 원칙은 fail-closed 다(「검사 0건은 통과가 아니다」). 자격증명 자리표시자는 정확히
그 반대로 동작하던 자리다.

    cd backend-service && APP_ENV=development uv run python tests/test_placeholder_credentials.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))


def _seed_env_from_example() -> int:
    """`app/.env.example` 로 필수 환경변수를 채운다 — **import 전에** 불러야 한다.

    `core.config` 는 모듈을 읽는 순간 `settings = Settings()` 를 만들고, 그 값은 cwd 의
    `.env.{APP_ENV}` 에서 온다. 그 파일은 gitignore 라 **워크트리·CI 에는 없다** — 그대로 두면
    이 테스트는 자기 대상에 닿기도 전에 ValidationError 로 죽는다(실측: CI 에서만 빨갛고
    로컬에서만 초록이었다). 레포에 있는 `.env.example` 을 쓰면 어디서 돌든 같은 값이다.

    이미 있는 환경변수는 덮지 않는다 — 실제 설정으로 도는 자리를 이 파일이 흔들지 않게.
    """
    # 개발 모드로 읽는다 — production 에서는 `.env.example` 의 CHANGE_ME 가 기동을 막으므로
    # (이 PR 이 세운 규칙 그대로) import 자체가 실패한다. production 경로는 아래에서
    # `Settings(...)` 를 직접 만들어 확인한다.
    os.environ.setdefault("APP_ENV", "development")
    example = BACKEND / "app/.env.example"
    assert example.is_file(), f"{example} 가 없다 — 이 테스트의 전제가 사라졌다"
    seeded = 0
    for line in example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")
            seeded += 1
    assert seeded > 0, ".env.example 에서 채운 키가 0건이다 — 형식이 바뀌었다면 이 그물을 고쳐라"
    return seeded


_SEEDED = _seed_env_from_example()

from core.config import Settings  # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  ok  {name}")
    else:
        FAILURES.append(f"{name} — {detail}")
        print(f"  FAIL {name} — {detail}")


BASE = dict(
    APP_ENV="production",
    BACKEND_SQL_DB_HOST="h",
    BACKEND_SQL_DB_PORT=5432,
    BACKEND_SQL_DB_NAME="n",
    BACKEND_SQL_DB_USER="u",
    BACKEND_SQL_DB_PASSWORD="p",
    SFTP_HOST="h",
    SFTP_PORT=22,
    SFTP_USERNAME="real-user",
    SFTP_PASSWORD="real-pass",
    JWT_SECRET="s",
)


def build(**over):
    fields = set(Settings.model_fields)
    kwargs = {k: v for k, v in {**BASE, **over}.items() if k in fields}
    return Settings(**kwargs)


def run() -> None:
    # 1) 실제 값이면 종전대로 선다
    try:
        build()
        check("실제 자격증명이면 기동한다", True)
    except Exception as e:  # noqa: BLE001
        check("실제 자격증명이면 기동한다", False, f"예외: {e}")

    # 2) 운영에서 자리표시자면 거부한다
    for field in ("SFTP_USERNAME", "SFTP_PASSWORD"):
        try:
            build(**{field: "CHANGE_ME"})
            check(f"운영에서 {field}=CHANGE_ME 를 거부한다", False, "기동이 성공했다")
        except Exception as e:  # noqa: BLE001
            check(f"운영에서 {field}=CHANGE_ME 를 거부한다", "CHANGE_ME" in str(e), f"사유에 값이 없다: {e}")

    # 3) 개발에서는 막지 않는다 (경고만) — 파일 기능을 안 쓰는 사람의 길을 막지 않는다
    try:
        build(APP_ENV="development", SFTP_USERNAME="CHANGE_ME")
        check("개발에서는 기동은 시킨다", True)
    except Exception as e:  # noqa: BLE001
        check("개발에서는 기동은 시킨다", False, f"거부됐다: {e}")


if __name__ == "__main__":
    print("자리표시자 자격증명 기동 검사 (#433)")
    run()
    print()
    if FAILURES:
        print(f"실패 {len(FAILURES)}건")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("전부 통과")
