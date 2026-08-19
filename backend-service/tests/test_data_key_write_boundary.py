"""#225 — **키 쓰기의 경계** (DB·네트워크 없음).

앱이 파일을 쓰는 것은 되돌리기 어렵고 다루는 값이 비밀이다. 그래서 이 그물이 경계를 잠근다:

  ① **요청이 파일 경로도 변수 이름도 정하지 못한다** — 소스 id 만 받고 서버가 표에서 꺼낸다.
     표에 없는 소스, 경로 조작 문자열, 임의 변수명이 전부 거부된다
  ② **로컬 개발에서만 열린다** — `APP_ENV` 가 development 가 아니면 저장·확인 둘 다 403.
     모르는 값도 막는다(fail-closed)
  ③ **거부·성공 어디에도 값이 안 나온다** — 응답과 예외 메시지가 API 로 나간다
  ④ 저장은 **재기동이 필요하다고 답한다** — 감수한 것을 감추지 않는다
  ⑤ 확인 호출이 없는 소스는 「실패」가 아니라 「확인 안 함」으로 답한다

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_data_key_write_boundary.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

# 설정을 세우고 나서 import 한다 — `test_data_source_key_leak.py` 와 같은 관용구다.
os.environ["APP_ENV"] = "data-key-write-test"
for _name, _value in {
    "BACKEND_SQL_DB_DRIVER": "postgresql+psycopg",
    "BACKEND_SQL_DB_HOST": "localhost",
    "BACKEND_SQL_DB_PORT": "5432",
    "BACKEND_SQL_DB_NAME": "test",
    "BACKEND_SQL_DB_USER": "test",
    "BACKEND_SQL_DB_PASSWORD": "test",
    "SFTP_HOST": "localhost",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "test",
    "SFTP_PASSWORD": "test",
    "JWT_SECRET": "test-secret",
}.items():
    os.environ.setdefault(_name, _value)

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.exceptions import BadRequestError, ForbiddenError, TooManyRequestsError  # noqa: E402
from services.data_key.data_key_service import SOURCE_KEY_SETTINGS, DataKeyService  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0

SECRET = "sk-live-WRITECANARY-0123456789"

# 변수 이름은 표에서 도출한다 — 리터럴로 적으면 단일 로더 그물에 걸리고, 표가 바뀌면 여기도 낡는다.
ALPACA_SETTING = SOURCE_KEY_SETTINGS["alpaca"]
ENV_BEFORE = f'# 주석\nOTHER="keep"\n{ALPACA_SETTING}="old"\n'


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


class Config:
    def __init__(self, app_env: str = "development") -> None:
        self.APP_ENV = app_env
        for setting in SOURCE_KEY_SETTINGS.values():
            setattr(self, setting, "")


def service_in(tmp: Path, app_env: str = "development") -> DataKeyService:
    """`.env.development` 가 있는 디렉터리를 cwd 로 둔 서비스 — 설정이 읽는 그 규칙과 같다."""
    (tmp / ".env.development").write_text(ENV_BEFORE, encoding="utf-8")
    os.chdir(tmp)
    return DataKeyService(Config(app_env))


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="keywrite."))
    origin = Path.cwd()

    try:
        # ── ① 요청이 이름·경로를 정하지 못한다 ────────────────────────────
        svc = service_in(root)
        for bad_source in (
            "../../../etc/passwd",
            "alpaca/../../secret",
            "JWT_SECRET",
            "sample",
            "",
            "ALPACA",
        ):
            try:
                svc.save_key(bad_source, SECRET)
                check(f"거부: {bad_source!r}", "저장됨", "거부")
            except BadRequestError as exc:
                check(f"거부: {bad_source!r}", True, True)
                check(f"사유에 값 없음: {bad_source!r}", SECRET in str(exc), False)

        after_bad = (root / ".env.development").read_text(encoding="utf-8")
        check("거부만 했으면 파일이 그대로다", after_bad, ENV_BEFORE)

        # ── 표에 있는 소스는 그 변수만 갈린다 ─────────────────────────────
        result = svc.save_key("alpaca", SECRET)
        after = (root / ".env.development").read_text(encoding="utf-8")

        check("표의 변수 이름을 쓴다", result["setting"], SOURCE_KEY_SETTINGS["alpaca"])
        check("갈아 끼웠다", result["action"], "replaced")
        check("④ 재기동이 필요하다고 답한다", result["restart_required"], True)
        check("③ 응답에 값이 없다", SECRET in repr(result), False)
        check("새 값이 들어갔다", SECRET in after, True)
        check("다른 변수가 그대로다", 'OTHER="keep"' in after, True)
        check("주석이 그대로다", "# 주석" in after, True)

        # 빈 값은 거부한다 — 지우는 것은 사용자가 파일에서 한다
        for blank in ("", "   ", "\t"):
            try:
                svc.save_key("alpaca", blank)
                check(f"빈 값 거부: {blank!r}", "저장됨", "거부")
            except BadRequestError:
                check(f"빈 값 거부: {blank!r}", True, True)

        # ── ② 로컬이 아니면 막힌다 (모르는 값도) ──────────────────────────
        for hostile_env in ("production", "staging", "", "Development", "unknown"):
            guarded = service_in(root, hostile_env)
            check(f"can_write_keys={hostile_env!r}", guarded.can_write_keys(), False)
            try:
                guarded.save_key("alpaca", SECRET)
                check(f"저장 403: {hostile_env!r}", "저장됨", "403")
            except ForbiddenError:
                check(f"저장 403: {hostile_env!r}", True, True)
            try:
                asyncio.run(guarded.probe_key("alpaca", SECRET))
                check(f"확인 403: {hostile_env!r}", "확인됨", "403")
            except ForbiddenError:
                check(f"확인 403: {hostile_env!r}", True, True)

        # ── ⑤ 확인 호출이 없는 소스 ──────────────────────────────────────
        svc = service_in(root)
        probed = asyncio.run(svc.probe_key("openfigi", SECRET))
        check("⑤ 확인 안 함으로 답한다", (probed["ok"], probed["checked"]), (False, False))
        check("③ 확인 응답에 값이 없다", SECRET in repr(probed), False)

        # 표에 없는 소스는 확인도 거부한다
        try:
            asyncio.run(svc.probe_key("../etc", SECRET))
            check("확인도 표를 본다", "확인됨", "거부")
        except BadRequestError:
            check("확인도 표를 본다", True, True)

        # 확인 호출은 소스당 쿨다운이 있다 — 밖으로 나가는 호출이라 연타가 외부 한도를 갉아먹는다.
        fresh = service_in(root)
        first = asyncio.run(fresh.probe_key("openfigi", SECRET))
        check("첫 확인은 답한다", first["checked"], False)
        try:
            asyncio.run(fresh.probe_key("openfigi", SECRET))
            check("연타는 막힌다", "답함", "429")
        except TooManyRequestsError as exc:
            check("연타는 막힌다", True, True)
            check("쿨다운 사유에 값이 없다", SECRET in str(exc), False)
    finally:
        os.chdir(origin)

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 40:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 요청이 경로·변수명을 정하지 못하고, 로컬 개발에서만 열리고, 값이 안 나온다 (#225)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
