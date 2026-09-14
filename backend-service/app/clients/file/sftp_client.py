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
            # **원문을 봉투에 싣지 않는다.** asyncssh 의 실패 문구에는 계정명·호스트가 그대로 들어
            # 있고(`Permission denied for user … on host …`), 그것이 503 본문으로 나가 로그인한
            # 누구에게나 개발자도구로 보였다 (#433).
            #
            # `exception_handler` 는 「한글이 없는 메시지는 기본 문구로 갈아친다」로 라이브러리
            # 원문을 막는데, 여기서 한글 접두사를 붙이는 순간 그 검사를 통과해 원문이 함께 나갔다.
            # 사유는 서버 로그에만 남기고, 봉투에는 우리가 쓴 기본 문구만 보낸다.
            logger.error(f"SFTP 연결 실패: {e}", exc_info=True)
            raise ServiceUnavailableError() from e

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
