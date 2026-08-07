"""확장자 정규화 검증 — trailing-space 위험 확장자 차단 우회 폐쇄 (#108).

계약 (utils/common/file_utils.py `normalize_extension` SoT):
  (1) 파일명 앞/끝 공백·탭·개행이 있어도 위험 확장자(DANGEROUS_EXTENSIONS) 차단이
      뚫리지 않는다 — `evil.svg ` → `.svg` 로 정규화돼 file_service.py 의 차단 조건
      (`normalize_extension(x) in DANGEROUS_EXTENSIONS`) 과 동치로 매칭.
  (2) 타입 분류(get_file_type)·MIME(get_media_type)·transform 포맷 판정이 같은
      정규화를 탄다 — classification 정규화가 깨우는 transform 경로(`fmt="PNG "`
      크래시)까지 함께 닫힘 (연쇄 in-scope).
  (3) 회귀 감지: 공백 없는 정상 파일명의 차단·분류·MIME·transform 동작은 불변.

file_utils.py 는 core.config 를 import 하지 않으므로 env 세팅 불필요 (결정론적).
`uv run python scripts/verify_extension_normalization.py` (cwd=서비스 루트).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from PIL import Image  # noqa: E402
from utils.common.file_utils import (  # noqa: E402
    DANGEROUS_EXTENSIONS,
    FileMetadataUtils,
    ImageTransformer,
    normalize_extension,
)


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")
    raise SystemExit(1)


def check_dangerous_bypass_closed() -> None:
    """(1) 공백류 붙은 위험 확장자가 차단 조건에 매칭되는지 (핵심)."""
    for name in ["evil.svg ", "evil.svg\t", "evil.svg\n", "evil.exe ", ".svg  ", ".svg"]:
        ext = normalize_extension(name)
        if ext not in DANGEROUS_EXTENSIONS:
            _fail(f"우회 잔존: {name!r} → {ext!r} 가 DANGEROUS_EXTENSIONS 미매칭")
    print("  ✓ 우회 폐쇄: 공백/탭/개행·dotfile 위험 확장자 6종 모두 차단 조건 매칭")


def check_normalize_regression() -> None:
    """(3) 정상 파일명의 확장자 추출 불변."""
    cases = {"evil.svg": ".svg", "photo.png": ".png", "report.pdf": ".pdf", "README": "", "": ""}
    for name, expected in cases.items():
        got = normalize_extension(name)
        if got != expected:
            _fail(f"정상 입력 회귀: {name!r} → {got!r} (기대 {expected!r})")
    if FileMetadataUtils.get_file_type(".gitignore") != "DOCUMENT":
        _fail("get_file_type('.gitignore') 이 DOCUMENT 가 아님 (dotfile 오분류)")
    print("  ✓ 회귀 없음: 정상 파일명·무확장자·일반 dotfile 판정 불변")


def check_file_type() -> None:
    """(2)(3) 타입 분류 — trailing-space 정규화 + 정상 경로 불변."""
    if FileMetadataUtils.get_file_type("photo.png ") != "IMAGE":
        _fail("get_file_type('photo.png ') 이 IMAGE 가 아님 (정규화 미적용)")
    if FileMetadataUtils.get_file_type("report.pdf") != "DOCUMENT":
        _fail("get_file_type('report.pdf') 이 DOCUMENT 가 아님 (회귀)")
    print("  ✓ 타입 분류: 'photo.png ' → IMAGE, 'report.pdf' → DOCUMENT")


def check_media_type() -> None:
    """(2)(3) MIME — trailing-space 정규화 + 미등록 확장자 기본값 불변."""
    if FileMetadataUtils.get_media_type("photo.png ") != "image/png":
        _fail("get_media_type('photo.png ') 이 image/png 가 아님 (정규화 미적용)")
    if FileMetadataUtils.get_media_type("x.bin") != "application/octet-stream":
        _fail("get_media_type('x.bin') 이 octet-stream 이 아님 (회귀)")
    print("  ✓ MIME: 'photo.png ' → image/png, 'x.bin' → octet-stream")


def check_transform_chain() -> None:
    """(2)(3) transform 연쇄 — 정규화 없으면 `format='PNG '` 로 PIL 크래시."""
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(buf, format="PNG")
    content = buf.getvalue()

    try:
        out = ImageTransformer.transform(content, "photo.png ", size=1)
    except Exception as e:
        _fail(f"transform('photo.png ') 크래시 (연쇄 미방어): {type(e).__name__}: {e}")
    if not isinstance(out, bytes) or not out:
        _fail(f"transform('photo.png ') 결과가 비정상: {type(out).__name__}")

    out_normal = ImageTransformer.transform(content, "photo.png", size=1)
    if not isinstance(out_normal, bytes) or not out_normal:
        _fail("transform('photo.png') 정상 경로 회귀")
    print("  ✓ transform: 'photo.png ' 예외 없이 변환, 정상 경로 불변")


def main() -> None:
    print("확장자 정규화 검증 (#108)")
    check_dangerous_bypass_closed()
    check_normalize_regression()
    check_file_type()
    check_media_type()
    check_transform_chain()
    print("전체 통과")


if __name__ == "__main__":
    main()
