import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncssh
from core.config import settings
from core.exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    RequestEntityTooLargeError,
)
from core.logger import logger
from fastapi.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError
from repositories.file.file_repository import FileRepository
from repositories.file.sftp_file_repository import SftpFileRepository
from utils.common.file_utils import (
    DANGEROUS_EXTENSIONS,
    FileMetadataUtils,
    ImageTransformer,
    normalize_extension,
    resolve_upload_base,
)


class FileService:
    """파일 업로드/다운로드/삭제/이미지 처리를 담당하는 서비스"""

    def __init__(self, file_repository: FileRepository, file_store: SftpFileRepository):
        self.file_repository = file_repository
        self.file_store = file_store
        self.sftp_base_path = settings.SFTP_BASE_PATH
        self.max_upload_bytes = settings.max_upload_bytes
        self.max_upload_files = settings.MAX_UPLOAD_FILES

    def select_file_list(self, args: dict) -> tuple[list, int]:
        """파일 목록 조회"""
        return self.file_repository.select_file_list(args)

    def select_file(self, args: dict) -> dict:
        """파일 기본 정보 조회"""
        item = self.file_repository.select_file(args)
        if not item:
            raise NotFoundError("파일을 찾을 수 없습니다.")
        return item

    def select_file_detail_list(self, args: dict) -> tuple[list, int]:
        """파일 상세 목록 조회"""
        return self.file_repository.select_file_detail_list(args)

    def select_file_detail(self, args: dict) -> dict:
        """파일 상세 정보 조회"""
        item = self.file_repository.select_file_detail(args)
        if not item:
            raise NotFoundError("파일을 찾을 수 없습니다.")
        return item

    def get_last_file_sn(self, atch_file_id: str) -> int:
        """마지막 파일 순번 조회"""
        return self.file_repository.get_last_file_sn(atch_file_id)

    async def upload_files(self, args: dict) -> dict:
        """
        여러 파일을 동시에 업로드 처리
        - 신규 atch_file_id 생성
        - 병렬 업로드 (최대 4개 동시)
        """
        files = args["files"]
        atch_file_id = args.get("atch_file_id")
        user_id = args["user_id"]

        # 파일 개수 남용 차단선 (SFTP·파싱 이전에 조기 차단). 작은 파일 수천 개가 바디 상한 아래로
        # 통과해 개수만큼 비용을 무는 것을 막는다 (#144). 파일당 크기 검사와 독립적인 별개 축이다.
        if len(files) > self.max_upload_files:
            raise RequestEntityTooLargeError(
                f"한 번에 올릴 수 있는 파일 개수({self.max_upload_files}개)를 초과했습니다: {len(files)}개"
            )

        # 위험한 확장자 · 크기 검사 (SFTP 작업 이전에 차단)
        for file in files:
            if file.filename:
                ext = normalize_extension(file.filename)
                if ext in DANGEROUS_EXTENSIONS:
                    raise BadRequestError(f"위험한 파일 형식입니다: {ext}")
            if file.size is not None and file.size > self.max_upload_bytes:
                raise RequestEntityTooLargeError(
                    f"파일 크기가 허용 한도({settings.MAX_UPLOAD_SIZE_MB}MB)를 초과했습니다: {file.filename}"
                )

        # 파일 ID가 없으면 새로 생성
        if not atch_file_id:
            atch_file_id = FileMetadataUtils.generate_file_id()

        # 첨부파일 메인 레코드 없으면 새로 삽입
        existing = self.file_repository.select_file({"atch_file_id": atch_file_id})
        if not existing:
            self.file_repository.insert_file(
                {
                    "atch_file_id": atch_file_id,
                    "reg_id": user_id,
                    "mod_id": user_id,
                }
            )

        # 다음 파일 순번, 업로드 경로 지정 (base_path 는 SFTP_BASE_PATH 하위로 강제)
        next_sn = self.file_repository.get_next_file_sn(atch_file_id)
        try:
            upload_base = resolve_upload_base(args.get("base_path"), self.sftp_base_path)
        except ValueError as e:
            raise BadRequestError(str(e)) from e
        remote_path = FileMetadataUtils.get_upload_path(upload_base)

        # SFTP 세션 (한 연결로 디렉토리 생성 + 병렬 업로드)
        async with self.file_store.open_session() as session:
            await session.ensure_directory(remote_path)

            # 동시 업로드 제한 (최대 4개)
            semaphore = asyncio.Semaphore(4)

            async def limited_upload(file, i):
                async with semaphore:
                    return await self._upload_single(session, file, remote_path, atch_file_id, next_sn + i, user_id)

            # 비동기 업로드 병렬 실행
            tasks = [limited_upload(f, i) for i, f in enumerate(files)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            uploaded = [r for r in results if r and not isinstance(r, Exception)]

        return {
            "atch_file_id": atch_file_id,
            "uploaded_files": uploaded,
            "total_count": len(uploaded),
        }

    async def _upload_single(self, session, file, remote_path, atch_file_id, file_sn, user_id):
        """단일 파일 업로드 및 DB에 메타데이터 기록"""
        if not file.filename:
            return None

        file_ext = Path(file.filename).suffix
        stored_name = f"{FileMetadataUtils.generate_uuid()}{file_ext}"
        remote_file = f"{remote_path}/{stored_name}"

        try:
            # 파일 업로드 (Chunk 단위 + 권한 설정)
            await session.write(remote_file, file.file)

            # 파일 상세정보 DB 저장
            self.file_repository.insert_file_detail(
                {
                    "atch_file_id": atch_file_id,
                    "file_sn": file_sn,
                    "file_stre_cours": remote_file,
                    "stre_file_nm": stored_name,
                    "orignl_file_nm": file.filename,
                    "file_extsn": file_ext,
                    "file_mg": file.size or 0,
                    "file_ty": FileMetadataUtils.get_file_type(file.filename),
                    "reg_id": user_id,
                    "mod_id": user_id,
                }
            )

            return {
                "file_sn": file_sn,
                "orignl_file_nm": file.filename,
                "stre_file_nm": stored_name,
                "file_mg": file.size or 0,
                "file_ty": FileMetadataUtils.get_file_type(file.filename),
                "file_extsn": file_ext,
            }
        except Exception as e:
            logger.error(f"업로드 실패 ({file.filename}): {str(e)}")
            try:
                await session.delete(remote_file)
            except Exception:
                pass
            raise

    async def stream_file_download(self, args: dict) -> AsyncGenerator[bytes, None]:
        """파일 스트리밍 다운로드 (비동기 Generator 리턴)"""
        file_detail = self.file_repository.select_file_detail(args)
        if not file_detail:
            raise NotFoundError("파일을 찾을 수 없습니다.")

        remote_path = file_detail["file_stre_cours"]
        async with self.file_store.open_session() as session:
            async for chunk in session.read_stream(remote_path):
                yield chunk

    async def read_file_content(self, args: dict) -> tuple[bytes, str]:
        """파일 전체 내용을 메모리로 읽어 반환 (bytes, 원본파일명)"""
        file_detail = self.file_repository.select_file_detail(args)
        if not file_detail:
            raise NotFoundError("파일을 찾을 수 없습니다.")

        remote_path = file_detail["file_stre_cours"]
        content = await self.file_store.read_bytes(remote_path)
        return content, file_detail.get("orignl_file_nm", "unknown")

    async def select_file_detail_for_image_preview(self, args: dict) -> tuple[bytes, str]:
        """
        이미지 파일 미리보기 기능
        - SFTP에서 파일 다운로드
        - 크롭 / 축소 변환 수행 후 메모리로 반환
        """
        file_detail = self.file_repository.select_file_detail(args)
        if not file_detail:
            raise NotFoundError("파일을 찾을 수 없습니다.")
        if file_detail.get("file_ty") != "IMAGE":
            raise BadRequestError("이미지 파일이 아닙니다.")

        remote_path = file_detail["file_stre_cours"]

        # 이미지 로드
        content = await self.file_store.read_bytes(remote_path)

        transform = args.get("transform") or {}
        size = transform.get("size")
        crop = transform.get("crop") or {}

        # 크롭 또는 리사이즈 수행
        if size is not None or any(crop.get(k) is not None for k in ("x1", "y1", "x2", "y2")):
            if crop and any(crop.get(k) is not None for k in ("x1", "y1", "x2", "y2")):
                if not all(crop.get(k) is not None for k in ("x1", "y1", "x2", "y2")):
                    raise BadRequestError("crop은 x1,y1,x2,y2를 모두 제공해야 합니다.")

            try:
                content = await run_in_threadpool(
                    ImageTransformer.transform,
                    content=content,
                    filename=file_detail["orignl_file_nm"],
                    size=size,
                    crop=crop if crop else None,
                )
            except Image.DecompressionBombError as e:
                raise RequestEntityTooLargeError("이미지 크기가 허용 한도를 초과했습니다.") from e
            except UnidentifiedImageError as e:
                raise BadRequestError("이미지 형식을 인식할 수 없습니다.") from e

        # MIME 타입 결정
        media_type = FileMetadataUtils.get_media_type(file_detail["orignl_file_nm"])
        return content, media_type

    async def delete_file_detail(self, args: dict) -> None:
        """단일 파일 삭제 처리 (SFTP + DB)"""
        atch_file_id = args["atch_file_id"]
        file_sn = args["file_sn"]
        file_detail = self.file_repository.select_file_detail(args)
        if not file_detail:
            logger.warning(f"삭제할 파일 없음: {atch_file_id}/{file_sn}")
            return

        remote_path = file_detail["file_stre_cours"]
        if not remote_path:
            self.file_repository.delete_file_detail(args)
            return

        async with self.file_store.open_session() as session:
            try:
                await session.stat(remote_path)
                await session.delete(remote_path)
            except asyncssh.SFTPNoSuchFile:
                logger.warning(f"SFTP 파일 없음: {remote_path}")
            except asyncssh.SFTPPermissionDenied as e:
                raise ForbiddenError("파일 삭제 권한이 없습니다.") from e

            self.file_repository.delete_file_detail(args)

    async def delete_file(self, args: dict) -> None:
        """첨부파일 전체 묶음 삭제"""
        atch_file_id = args["atch_file_id"]
        file_details, _ = self.file_repository.select_file_detail_list({"atch_file_id": atch_file_id})
        if not file_details:
            raise NotFoundError("삭제할 파일을 찾을 수 없습니다.")

        async with self.file_store.open_session() as session:
            for detail in file_details:
                if detail.get("file_stre_cours"):
                    await session.delete(detail["file_stre_cours"])
            self.file_repository.delete_file(args)
