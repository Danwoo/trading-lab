#!/usr/bin/env python3
"""SFTP 연결 실패의 **응답 봉투에 서버 내부 정보가 실리지 않는다** (#433).

Cycle 7 발굴(B-6·F27)이 실측한 것: 업로드 503 본문이
`{"detail":"SFTP 연결 실패: Permission denied for user CHANGE_ME on host localhost"}` 였다 —
계정명과 호스트가 로그인한 누구에게나 개발자도구로 보였다.

**왜 기존 방어가 안 먹었나**: `core/exception_handler` 는 「한글이 없는 메시지는 기본 문구로
갈아친다」로 라이브러리 원문을 막는다. 그런데 `sftp_client` 가 한글 접두사(`SFTP 연결 실패: `)를
붙이는 순간 그 검사를 통과해 영어 원문이 함께 나갔다. 그래서 이 테스트는 **문구가 아니라
「원문이 봉투에 실리는가」**를 본다.

    cd backend-service && APP_ENV=development uv run python tests/test_sftp_error_envelope.py
"""

from __future__ import annotations

import asyncio
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

from clients.file.sftp_client import SftpClient  # noqa: E402
from core.exceptions import ServiceUnavailableError  # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  ok  {name}")
    else:
        FAILURES.append(f"{name} — {detail}")
        print(f"  FAIL {name} — {detail}")


# asyncssh 가 실제로 내는 모양 — 계정명·호스트가 들어 있다.
LEAKY = "Permission denied for user CHANGE_ME on host sftp.internal.example"


class _Boom(Exception):
    def __str__(self) -> str:
        return LEAKY


def _client() -> SftpClient:
    c = SftpClient.__new__(SftpClient)
    c.host = "sftp.internal.example"
    c.port = 22
    c.username = "CHANGE_ME"
    c.password = "s3cr3t"
    c.ssh_opts = None
    return c


def run() -> None:
    client = _client()

    async def _go():
        import clients.file.sftp_client as mod

        async def _always_fail(*_a, **_k):
            raise _Boom()

        original = mod.retry
        mod.retry = _always_fail  # type: ignore[assignment]
        try:
            await client.get_client()
        except ServiceUnavailableError as exc:
            return str(exc)
        finally:
            mod.retry = original  # type: ignore[assignment]
        return None

    message = asyncio.run(_go())

    check("실패가 ServiceUnavailableError 로 올라온다", message is not None, "예외가 안 났거나 다른 타입")
    if message is None:
        return

    # 카나리 — 봉투에 실리면 안 되는 것들
    for canary, what in (
        ("CHANGE_ME", "계정명"),
        ("sftp.internal.example", "호스트명"),
        ("Permission denied", "라이브러리 원문"),
        ("s3cr3t", "비밀번호"),
    ):
        check(f"봉투에 {what} 이 없다", canary not in message, f"메시지에 {canary!r} 이 들어 있다: {message!r}")

    check(
        "우리가 쓴 기본 문구를 낸다",
        message == ServiceUnavailableError.default_message,
        f"기대 {ServiceUnavailableError.default_message!r} · 실제 {message!r}",
    )


if __name__ == "__main__":
    print("SFTP 실패 봉투 카나리 (#433)")
    run()
    print()
    if FAILURES:
        print(f"실패 {len(FAILURES)}건")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("전부 통과")
