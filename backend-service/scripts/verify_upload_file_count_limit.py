"""업로드 파일 개수 상한 검증 — 작은 파일 대량이 바디 상한 아래로 통과하는 남용 차단 (#144).

계약 (core/config.py `MAX_UPLOAD_FILES` + services/file/file_service.py `upload_files` SoT):
  (1) 개수 상한(기본 100 = 프론트 UI 배치 상한 5·3 의 넉넉한 배수) 이하 요청은 개수 검사를
      통과한다 — 정상 다중파일 배치를 막지 않는다. 경계값(정확히 상한)도 통과.
  (2) 상한 초과 요청은 SFTP·파싱·DB 이전에 413(RequestEntityTooLargeError, "개수" 메시지)으로
      조기 거절된다.
  (3) 기존 크기 검사 무손상: 파일당 크기 초과는 여전히 413, 위험 확장자는 여전히 400 —
      개수 검사 추가가 두 검사를 대체하거나 가리지 않는다 (독립 축).
  (4) 설정 fail-fast: MAX_UPLOAD_FILES < 1 은 기동 시 거부된다.

file_service 는 core.config 를 import 하므로 필수 env 를 더미로 주입한 뒤 로드한다.
`uv run python scripts/verify_upload_file_count_limit.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

# --- 필수 env 더미 주입 (config 로드 전) ---------------------------------------
_DUMMY_ENV = {
    "APP_ENV": "production",
    "BACKEND_SQL_DB_DRIVER": "x",
    "BACKEND_SQL_DB_ODBC_DRIVER": "x",
    "BACKEND_SQL_DB_HOST": "x",
    "BACKEND_SQL_DB_PORT": "1433",
    "BACKEND_SQL_DB_NAME": "x",
    "BACKEND_SQL_DB_USER": "x",
    "BACKEND_SQL_DB_PASSWORD": "x",
    "SFTP_HOST": "x",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "x",
    "SFTP_PASSWORD": "x",
    "JWT_SECRET": "x",
}
for _k, _v in _DUMMY_ENV.items():
    os.environ.setdefault(_k, _v)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from core.config import Settings, settings  # noqa: E402
from core.exceptions import BadRequestError, RequestEntityTooLargeError  # noqa: E402
from services.file.file_service import FileService  # noqa: E402


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")
    raise SystemExit(1)


class _SentinelReached(Exception):
    """모든 조기 검사(개수·확장자·크기)를 통과해 저장 단계에 도달했음을 표시."""


class _StubRepo:
    """조기 검사 이후 첫 호출(select_file)에서 sentinel 을 던져, 검사 통과를 결정적으로 증명."""

    def select_file(self, args):
        raise _SentinelReached


def _make_service() -> FileService:
    return FileService(file_repository=_StubRepo(), file_store=object())


def _fake_file(name: str = "photo.png", size: int = 1024) -> SimpleNamespace:
    return SimpleNamespace(filename=name, size=size)


def _run_upload(files: list) -> None:
    service = _make_service()
    args = {"files": files, "atch_file_id": "AID", "user_id": "u@x", "base_path": None}
    asyncio.run(service.upload_files(args))


def check_normal_and_boundary_pass() -> None:
    """(1) 상한 이하(정상 5개·경계 100개)는 개수 검사를 통과 → 저장 단계 도달(sentinel)."""
    for count in (5, settings.MAX_UPLOAD_FILES):
        try:
            _run_upload([_fake_file() for _ in range(count)])
        except _SentinelReached:
            pass  # 기대: 개수 검사 통과 후 저장 단계 도달
        except RequestEntityTooLargeError as e:
            _fail(f"정상 개수 오탐 거절: {count}개 → {e}")
        else:
            _fail(f"{count}개에서 sentinel 미도달 (검사 흐름 이상)")
    print(f"  ✓ 정상 통과: 5개·경계 {settings.MAX_UPLOAD_FILES}개 모두 개수 검사 통과 (저장 단계 도달)")


def check_abuse_rejected() -> None:
    """(2) 상한 초과는 413 + '개수' 메시지로 조기 거절 (sentinel 미도달)."""
    over = settings.MAX_UPLOAD_FILES + 1
    try:
        _run_upload([_fake_file() for _ in range(over)])
    except RequestEntityTooLargeError as e:
        if "개수" not in str(e):
            _fail(f"개수 초과 메시지 부적합: {e!r}")
        if str(over) not in str(e):
            _fail(f"실제 개수 미포함 메시지: {e!r}")
    except _SentinelReached:
        _fail(f"{over}개가 개수 검사를 뚫고 저장 단계 도달 (남용 미차단)")
    else:
        _fail(f"{over}개가 거절되지 않음")
    print(f"  ✓ 남용 거절: {over}개 → 413 개수 초과 (SFTP·DB 이전 조기 차단)")


def check_existing_size_check_intact() -> None:
    """(3) 파일당 크기 초과는 여전히 413 (개수는 정상 1개 — 크기 축이 독립 작동)."""
    big = settings.max_upload_bytes + 1
    try:
        _run_upload([_fake_file(size=big)])
    except RequestEntityTooLargeError as e:
        if "개수" in str(e):
            _fail(f"크기 초과가 개수 메시지로 오분류: {e!r}")
        if "MB" not in str(e):
            _fail(f"크기 초과 메시지 부적합: {e!r}")
    except _SentinelReached:
        _fail("파일당 크기 초과가 검사를 뚫음 (기존 크기 검사 손상)")
    else:
        _fail("크기 초과가 거절되지 않음")
    print("  ✓ 기존 크기 검사 무손상: 파일당 초과 → 413 크기 메시지 (개수와 별개 축)")


def check_existing_ext_check_intact() -> None:
    """(3) 위험 확장자는 여전히 400 (개수 정상 1개)."""
    try:
        _run_upload([_fake_file(name="evil.svg")])
    except BadRequestError as e:
        if "위험한" not in str(e):
            _fail(f"위험 확장자 메시지 부적합: {e!r}")
    except _SentinelReached:
        _fail("위험 확장자가 검사를 뚫음 (기존 확장자 검사 손상)")
    else:
        _fail("위험 확장자가 거절되지 않음")
    print("  ✓ 기존 확장자 검사 무손상: 위험 확장자 → 400")


def check_config_fail_fast() -> None:
    """(4) MAX_UPLOAD_FILES < 1 은 기동 시 거부."""
    for bad in (0, -1):
        try:
            Settings(MAX_UPLOAD_FILES=bad)
        except ValueError:
            pass  # 기대: fail-fast
        else:
            _fail(f"MAX_UPLOAD_FILES={bad} 가 기동 시 거부되지 않음")
    print("  ✓ 설정 fail-fast: MAX_UPLOAD_FILES 0·음수 기동 거부")


def main() -> None:
    print(f"업로드 파일 개수 상한 검증 (MAX_UPLOAD_FILES={settings.MAX_UPLOAD_FILES})")
    check_normal_and_boundary_pass()
    check_abuse_rejected()
    check_existing_size_check_intact()
    check_existing_ext_check_intact()
    check_config_fail_fast()
    print("모든 검증 통과")


if __name__ == "__main__":
    main()
