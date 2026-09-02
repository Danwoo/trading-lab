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

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

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
