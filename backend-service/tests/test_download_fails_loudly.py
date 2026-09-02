#!/usr/bin/env python3
"""다운로드가 실패를 **성공처럼 내지 않는다** (#433·B-7).

Cycle 7 발굴이 실측한 것: 파일 저장소가 완전히 끊긴 상태에서 다운로드를 요청하면
`HTTP:200 size:0` — 0바이트 파일이 성공처럼 저장되고 토스트도 오류도 없었다.
**업로드는 같은 고장에 정직하게 503 을 내는데 다운로드만 200 을 냈다.**

구조가 그렇게 만들었다: `StreamingResponse` 가 첫 조각을 당길 때 SFTP 세션이 열리는데,
그 시점엔 이미 200 헤더가 나가 되돌릴 수 없다.

이 파일이 보는 것: **세션 열기와 첫 조각 읽기가 응답을 만들기 전에 일어나는가** —
즉 저장소가 죽어 있으면 제너레이터를 얻는 단계에서 예외가 나는가.

    cd backend-service && APP_ENV=development uv run python tests/test_download_fails_loudly.py
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))

from core.exceptions import ServiceUnavailableError  # noqa: E402
from services.file.file_service import FileService  # noqa: E402

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  ok  {name}")
    else:
        FAILURES.append(f"{name} — {detail}")
        print(f"  FAIL {name} — {detail}")


class _Repo:
    def select_file_detail(self, _args):
        return {"file_stre_cours": "/upload/x.pdf", "orignl_file_nm": "보고서.pdf"}


class _DeadSession:
    async def read_stream(self, _path):
        raise ServiceUnavailableError()
        yield b""  # pragma: no cover


class _LiveSession:
    async def read_stream(self, _path):
        yield b"first-"
        yield b"second"


class _Store:
    def __init__(self, session, fail_on_open=False):
        self._session = session
        self._fail_on_open = fail_on_open

    @asynccontextmanager
    async def open_session(self):
        if self._fail_on_open:
            raise ServiceUnavailableError()
        yield self._session


def _service(store) -> FileService:
    svc = FileService.__new__(FileService)
    svc.file_repository = _Repo()
    svc.file_store = store
    return svc


def run() -> None:
    # 1) 저장소가 아예 안 열릴 때 — 응답을 만들기 전에 터진다
    async def _open_dead():
        return await _service(_Store(None, fail_on_open=True)).open_file_download({})

    try:
        asyncio.run(_open_dead())
        check("저장소가 안 열리면 스트림을 얻는 단계에서 실패한다", False, "예외 없이 제너레이터를 돌려줬다")
    except ServiceUnavailableError:
        check("저장소가 안 열리면 스트림을 얻는 단계에서 실패한다", True)
    except Exception as e:  # noqa: BLE001
        check("저장소가 안 열리면 스트림을 얻는 단계에서 실패한다", False, f"다른 예외: {type(e).__name__}")

    # 2) 열리지만 읽기가 죽을 때 — 이것도 응답 전에 터진다 (0바이트 200 의 실제 모양)
    async def _open_read_fails():
        return await _service(_Store(_DeadSession())).open_file_download({})

    try:
        asyncio.run(_open_read_fails())
        check("첫 조각 읽기가 실패하면 응답 전에 터진다", False, "예외 없이 제너레이터를 돌려줬다")
    except ServiceUnavailableError:
        check("첫 조각 읽기가 실패하면 응답 전에 터진다", True)
    except Exception as e:  # noqa: BLE001
        check("첫 조각 읽기가 실패하면 응답 전에 터진다", False, f"다른 예외: {type(e).__name__}")

    # 3) 정상일 때 — 첫 조각을 버리지 않는다
    async def _happy():
        gen = await _service(_Store(_LiveSession())).open_file_download({})
        return b"".join([chunk async for chunk in gen])

    try:
        body = asyncio.run(_happy())
        check("정상 경로는 첫 조각을 버리지 않는다", body == b"first-second", f"본문이 {body!r}")
    except Exception as e:  # noqa: BLE001
        check("정상 경로는 첫 조각을 버리지 않는다", False, f"예외: {type(e).__name__}: {e}")

    # 4) 옛 경로가 왜 위험했는지 — 부르는 것만으로는 아무 일도 안 난다(lazy).
    #    이 성질이 「200 이 먼저 나가고 본문만 0바이트」의 원인이다. 남아 있는 한 이 축을 고정한다.
    legacy = _service(_Store(_DeadSession())).stream_file_download({})
    check(
        "옛 stream_file_download 는 호출만으로 실패하지 않는다 (그래서 응답 전에 못 잡는다)",
        hasattr(legacy, "__anext__"),
        "제너레이터가 아니다",
    )


if __name__ == "__main__":
    print("다운로드 실패의 정직성 (#433·B-7)")
    run()
    print()
    if FAILURES:
        print(f"실패 {len(FAILURES)}건")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("전부 통과")
