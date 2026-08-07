"""
파일 처리 유틸리티
- 파일 메타데이터 생성
- 이미지 변환
"""

import io
import posixpath
import uuid
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

# 프리뷰 디코드 시 decompression bomb 상한 (픽셀 수). PIL 은 2×MAX 초과에서만
# DecompressionBombError 를 던지므로 transform 에서 이 값으로 명시 검사도 한다.
MAX_IMAGE_PIXELS = 50_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

# 업로드 차단할 위험한 파일 확장자 (.svg/.svgz 는 인라인 스크립트 실행 위험 — 저장형 XSS)
DANGEROUS_EXTENSIONS = {
    ".exe",
    ".bat",
    ".cmd",
    ".com",
    ".pif",
    ".scr",
    ".vbs",
    ".js",
    ".jar",
    ".sh",
    ".ps1",
    ".svg",
    ".svgz",
}

# 프리뷰를 인라인(브라우저 렌더)으로 서빙해도 안전한 래스터 MIME 화이트리스트.
# 이 목록 밖(octet-stream 등)은 프리뷰에서 attachment 로 강제 다운로드한다.
SAFE_INLINE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/bmp", "image/webp"})


def resolve_upload_base(base_path: str | None, sftp_base_path: str) -> str:
    """업로드 base_path 를 SFTP_BASE_PATH 하위로 강제 정규화.

    클라이언트가 준 base_path 를 posix 정규화한 뒤 containment 를 검사한다 —
    절대경로 탈출·`..` 상위탐색·형제 prefix(`/upload-evil`) 를 모두 거부.
    base_path 가 비면 SFTP_BASE_PATH 자체를 쓴다.

    Args:
        base_path: 클라이언트 제공 경로 (신뢰 불가)
        sftp_base_path: 허용 루트 (SFTP_BASE_PATH)

    Returns:
        str: SFTP_BASE_PATH 하위로 확정된 절대경로

    Raises:
        ValueError: 정규화 결과가 허용 루트를 벗어날 때
    """
    root = posixpath.normpath("/" + sftp_base_path.strip().lstrip("/"))
    raw = (base_path or "").strip()
    if not raw:
        return root

    if posixpath.isabs(raw):
        candidate = posixpath.normpath(raw)
    else:
        candidate = posixpath.normpath(posixpath.join(root, raw))

    if candidate != root and not candidate.startswith(root + "/"):
        raise ValueError(f"업로드 경로가 허용 범위를 벗어났습니다: {base_path!r}")
    return candidate


def strip_extension(file_nm: str) -> str:
    """파일명에서 확장자를 제거 (context_label 등에 활용)"""
    if not file_nm:
        return ""
    if "." in file_nm:
        return file_nm.rsplit(".", 1)[0]
    return file_nm


def normalize_extension(file_nm: str) -> str:
    """파일명에서 확장자를 정규화해 추출 — trim 후 소문자 suffix.

    확장자 판정(위험 확장자 차단·타입·MIME·포맷)의 단일 정규화 지점.
    앞/끝 공백·탭·개행을 제거해 `evil.svg ` 같은 trailing-space 우회를 막는다.
    이름 전체가 `.svg` 류 dotfile 이면 Path.suffix 는 빈 문자열이라 차단이 새므로,
    이름 자체를 확장자로 본다 (fail-closed).
    """
    name = Path((file_nm or "").strip()).name
    suffix = Path(name).suffix
    if not suffix and name.startswith("."):
        suffix = name
    return suffix.lower()


class FileMetadataUtils:
    """파일 메타데이터 생성 유틸리티"""

    # 이미지 확장자 목록 (.svg 제외 — 인라인 렌더 시 스크립트 실행 위험)
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}

    # MIME 타입 매핑
    MEDIA_TYPES = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
    }

    @staticmethod
    def generate_file_id() -> str:
        """파일 ID (UUID 기반) 자동 생성"""
        return str(uuid.uuid4()).replace("-", "")[:20]

    @staticmethod
    def generate_uuid() -> str:
        """저장 파일명용 UUID 생성"""
        return str(uuid.uuid4())

    @staticmethod
    def get_upload_path(base_path: str) -> str:
        """
        SFTP 업로드 경로 (KST 기준 날짜별 디렉토리)

        Args:
            base_path: SFTP 기본 경로

        Returns:
            str: {base_path}/YYYYMMDD/HH/MM
        """
        now_utc = datetime.now(UTC)
        now_kst = now_utc.astimezone(ZoneInfo("Asia/Seoul"))
        return f"{base_path}/{now_kst.year:04d}{now_kst.month:02d}{now_kst.day:02d}/{now_kst.hour:02d}/{now_kst.minute:02d}"

    @staticmethod
    def get_file_type(filename: str) -> str:
        """
        파일 확장자 기반으로 IMAGE / DOCUMENT 구분

        Args:
            filename: 파일명

        Returns:
            str: "IMAGE" 또는 "DOCUMENT"
        """
        ext = normalize_extension(filename)
        return "IMAGE" if ext in FileMetadataUtils.IMAGE_EXTENSIONS else "DOCUMENT"

    @staticmethod
    def get_media_type(filename: str) -> str:
        """
        MIME 타입 결정

        Args:
            filename: 파일명

        Returns:
            str: MIME 타입 (기본값: "application/octet-stream")
        """
        ext = normalize_extension(filename)
        return FileMetadataUtils.MEDIA_TYPES.get(ext, "application/octet-stream")


class ImageTransformer:
    """이미지 변환 유틸리티 (크롭, 리사이즈, 포맷 변환)"""

    @staticmethod
    def transform(content: bytes, filename: str, size: int = None, crop: dict = None) -> bytes:
        """
        이미지 크롭 → 리사이즈 → 포맷 변환

        Args:
            content: 원본 이미지 bytes
            filename: 원본 파일명 (확장자 추출용)
            size: 최대 크기 (thumbnail, 비율 유지)
            crop: {"x1", "y1", "x2", "y2"} 크롭 좌표

        Returns:
            bytes: 변환된 이미지 bytes
        """
        im = Image.open(io.BytesIO(content))

        # decompression bomb 방어 — 디코드(crop/thumbnail/save) 전 헤더 선언 픽셀 수로 차단.
        # PIL 은 2×MAX 초과에서만 자동 raise 하므로 MAX~2×MAX 구간을 여기서 결정론적으로 막는다.
        width, height = im.size
        if width * height > MAX_IMAGE_PIXELS:
            raise Image.DecompressionBombError(f"이미지 픽셀 수가 허용 한도를 초과했습니다: {width}x{height}")

        # 1. 크롭 적용
        if crop and any(crop.get(k) is not None for k in ("x1", "y1", "x2", "y2")):
            x1 = int(crop.get("x1", 0))
            y1 = int(crop.get("y1", 0))
            x2 = int(crop.get("x2", 0))
            y2 = int(crop.get("y2", 0))

            # 좌표 정규화 (x1 < x2, y1 < y2)
            if x2 < x1:
                x1, x2 = x2, x1
            if y2 < y1:
                y1, y2 = y2, y1

            im = im.crop((x1, y1, x2, y2))

        # 2. 리사이즈 (비율 유지)
        if size is not None:
            im.thumbnail((int(size), int(size)))

        # 3. 포맷 변환
        ext = normalize_extension(filename)
        fmt = "JPEG" if ext in (".jpg", ".jpeg") else ext.replace(".", "").upper() or "PNG"

        # JPEG 포맷 변환 시 알파 채널 제거
        if fmt == "JPEG" and im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGB")

        # 4. bytes 저장
        out = io.BytesIO()
        im.save(out, format=fmt)
        return out.getvalue()
