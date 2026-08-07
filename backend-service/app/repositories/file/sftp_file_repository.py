# repositories/file/sftp_file_repository.py
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncssh
from clients.file.sftp_client import SftpClient
from core.logger import logger
from fastapi.concurrency import run_in_threadpool


class SftpFileSession:
    """단일 SFTP 연결 위에서 파일 store CRUD 를 수행하는 세션 (한 연결로 여러 op)"""

    def __init__(self, sftp: asyncssh.SFTPClient, chunk_size: int):
        self._sftp = sftp
        self.chunk_size = chunk_size

    async def ensure_directory(self, remote_path: str) -> None:
        """경로의 중간 디렉토리까지 생성 (이미 존재하면 무시)"""
        parts = remote_path.strip("/").split("/")
        current_path = ""
        for part in parts:
            current_path += f"/{part}"
            try:
                await self._sftp.stat(current_path)
            except asyncssh.SFTPNoSuchFile:
                try:
                    await self._sftp.mkdir(current_path)
                except asyncssh.SFTPFailure:
                    # race condition: 다른 프로세스가 먼저 생성한 경우 등
                    logger.warning(f"디렉토리 생성 실패: {current_path}")

    async def write(self, remote_path: str, fileobj, *, mode: int = 0o644) -> None:
        """동기 file-like 객체를 청크 단위로 업로드 후 권한 설정"""
        fileobj.seek(0)
        async with self._sftp.open(remote_path, "wb") as rf:
            while chunk := await run_in_threadpool(fileobj.read, self.chunk_size):
                await rf.write(chunk)
        await self._sftp.chmod(remote_path, mode)

    async def read_stream(self, remote_path: str) -> AsyncGenerator[bytes, None]:
        """청크 단위 스트리밍 읽기"""
        async with self._sftp.open(remote_path, "rb") as rf:
            while chunk := await rf.read(self.chunk_size):
                yield chunk

    async def read_bytes(self, remote_path: str) -> bytes:
        """전체 내용을 메모리로 읽기"""
        content = b""
        async with self._sftp.open(remote_path, "rb") as rf:
            while chunk := await rf.read(self.chunk_size):
                content += chunk
        return content

    async def stat(self, remote_path: str):
        """파일 stat — 없으면 SFTPNoSuchFile, 권한없으면 SFTPPermissionDenied raise (호출측이 매핑)"""
        return await self._sftp.stat(remote_path)

    async def delete(self, remote_path: str) -> bool:
        """파일 삭제 (성공 True, 실패 False)"""
        try:
            await self._sftp.remove(remote_path)
            return True
        except (asyncssh.SFTPNoSuchFile, asyncssh.SFTPPermissionDenied, asyncssh.SFTPError):
            logger.error(f"SFTP 파일 삭제 실패: {remote_path}")
            return False


class SftpFileRepository:
    """SFTP 파일 store 접근 계층 — 연결(SftpClient)을 주입받아 세션 단위 store CRUD 제공"""

    def __init__(self, sftp_client: SftpClient):
        self.sftp_client = sftp_client
        self.chunk_size = sftp_client.chunk_size

    @asynccontextmanager
    async def open_session(self) -> AsyncGenerator[SftpFileSession, None]:
        """SFTP 연결을 열어 세션 제공 (배치 작업 — 한 연결로 여러 op)"""
        conn, sftp = await self.sftp_client.get_client()
        try:
            yield SftpFileSession(sftp, self.chunk_size)
        finally:
            await self.sftp_client.close_client(conn, sftp)

    async def read_bytes(self, remote_path: str) -> bytes:
        """단건 전체 읽기 (자체 연결 1회)"""
        async with self.open_session() as session:
            return await session.read_bytes(remote_path)
