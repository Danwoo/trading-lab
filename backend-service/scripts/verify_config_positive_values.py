"""무의미한 0·음수 설정값이 기동 validator 를 통과하지 못하는지 검증 (#271).

계약 (core/config.py `Settings`):
  (1) 크기·개수 상한류(MAX_UPLOAD_SIZE_MB·MAX_REQUEST_BODY_SIZE_MB·MAX_UPLOAD_FILES)는 0·음수면
      기동을 거부한다 — 0 이하는 "모든 요청을 무조건 거절"하는 무의미한 값이다.
  (2) 포트류(BACKEND_SQL_DB_PORT·SFTP_PORT·EMAIL_PORT)는 0·음수·65536 이상이면 기동을 거부한다
      — TCP 포트로 성립하지 않는 값이다.
  (3) 정상 값(기본값 근방의 양수)은 위 검사를 그대로 통과한다 — 방어가 정상 기동을 막지 않는다.

이 스크립트는 **행동** 검증(제약이 실제로 값을 거부하는가)이고 대상은 backend-service 하나다.
포트 제약이 **전 서비스에 선언돼 있는지**는 `scripts/verify_config_port_bounds.py` 가 글롭으로
전수 검사한다 — 같은 pydantic 메커니즘이라 행동 검증은 한 서비스가 대표한다 (#377).

core.config 는 모듈 최초 import 시 `Settings()` 를 즉시 인스턴스화하므로(`settings = Settings()`),
개별 케이스는 `Settings(**overrides)` 를 직접 호출해 검증한다(모듈 재로딩 불필요).
필수 env 를 더미로 주입한 뒤 로드한다.
`uv run python scripts/verify_config_positive_values.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

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

from core.config import Settings  # noqa: E402

# (필드명, 무의미한 값들, 정상 값) — 전수 검사 대상. 새 크기/개수/포트 설정을 추가하면 여기 등록한다.
_NONPOSITIVE_REJECT_CASES: list[tuple[str, tuple[int, ...], int]] = [
    ("MAX_UPLOAD_SIZE_MB", (0, -1), 20),
    ("MAX_REQUEST_BODY_SIZE_MB", (0, -1), 512),
    ("MAX_UPLOAD_FILES", (0, -1), 100),
    ("BACKEND_SQL_DB_PORT", (0, -1, 65536), 5432),
    ("SFTP_PORT", (0, -1, 65536), 22),
    ("EMAIL_PORT", (0, -1, 65536), 465),
]


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")
    raise SystemExit(1)


def check_nonpositive_values_rejected() -> int:
    """(1)(2) 각 필드의 무의미한 값이 기동 시 거부되는지."""
    checked = 0
    for field, bad_values, _ in _NONPOSITIVE_REJECT_CASES:
        for bad in bad_values:
            try:
                Settings(**{field: bad})
            except ValueError:
                pass  # 기대: fail-fast
            else:
                _fail(f"{field}={bad} 가 기동 시 거부되지 않음")
            checked += 1
    print(f"  ✓ 무의미 값 거부: {checked}건 (필드 {len(_NONPOSITIVE_REJECT_CASES)}개 × 값 2~3개)")
    return checked


def check_normal_values_pass() -> None:
    """(3) 정상 값은 그대로 통과."""
    for field, _, good in _NONPOSITIVE_REJECT_CASES:
        try:
            s = Settings(**{field: good})
        except ValueError as e:
            _fail(f"{field}={good}(정상값) 가 오탐 거절됨: {e}")
        if getattr(s, field) != good:
            _fail(f"{field} 정상값이 반영되지 않음")
    print(f"  ✓ 정상 값 통과: 필드 {len(_NONPOSITIVE_REJECT_CASES)}개 모두 기본값 근방 양수 허용")


def main() -> None:
    print("설정값 양수 검증 (0·음수·포트범위 밖 → 기동 거부)")
    checked = check_nonpositive_values_rejected()
    if checked == 0:
        _fail("검사 대상 0건 — 대상 필드 목록이 비었다")
    check_normal_values_pass()
    print("모든 검증 통과")


if __name__ == "__main__":
    main()
