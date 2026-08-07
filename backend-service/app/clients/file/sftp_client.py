import asyncssh
from core.exceptions import ServiceUnavailableError
from core.logger import logger
from utils.common.retry_utils import retry


def _is_sftp_retryable(exc: BaseException) -> bool:
    """일시적 SSH 연결 오류(연결 끊김·타임아웃·네트워크)만 재시도. 인증 실패 등 영구 오류는 제외."""
    return isinstance(exc, (asyncssh.ConnectionLost, asyncssh.DisconnectError, asyncssh.TimeoutError, OSError))


class SftpClient:
    """SFTP 서버 연결 및 파일 전송/삭제 유틸리티"""

    def __init__(self, config):
        self.host = config.SFTP_HOST
        self.port = config.SFTP_PORT
        self.username = config.SFTP_USERNAME
        self.password = config.SFTP_PASSWORD
        # 업로드/다운로드 시 기본 청크 크기 (4MB)
        self.chunk_size = 4 * 1024 * 1024

        # SSH 연결 시 사용할 암호화 옵션 설정
        self.ssh_opts = asyncssh.SSHClientConnectionOptions(
            encryption_algs=["aes128-gcm@openssh.com", "aes256-ctr"],
            compression_algs=None,
        )

    async def get_client(self) -> tuple[asyncssh.SSHClientConnection, asyncssh.SFTPClient]:
        """
        SFTP 클라이언트 연결 생성
        - SSH 연결 후 SFTP 세션 시작
        """

        async def _connect() -> tuple[asyncssh.SSHClientConnection, asyncssh.SFTPClient]:
            conn = await asyncssh.connect(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                options=self.ssh_opts,
                known_hosts=None,  # 호스트 키 검증 생략 (주의 요망)
            )
            sftp = await conn.start_sftp_client()
            return conn, sftp

        try:
            return await retry(_connect, base_delay=0.5, retryable=_is_sftp_retryable)
        except Exception as e:
            # 연결 실패 시 명확한 메시지로 래핑
            raise ServiceUnavailableError(f"SFTP 연결 실패: {str(e)}") from e

    async def close_client(self, conn, sftp):
        """
        SFTP 및 SSH 연결 안전 종료
        """
        try:
            if sftp:
                sftp.exit()  # SFTP 세션 종료
            if conn:
                conn.close()  # SSH 연결 종료
                await conn.wait_closed()
        except Exception as e:
            logger.error(f"SFTP 종료 오류: {str(e)}")
