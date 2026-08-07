"""SMTP 메일 발송 (SSL). 백그라운드 매니저에서 호출 → run_in_threadpool 로 블로킹 회피."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.logger import logger
from fastapi.concurrency import run_in_threadpool
from utils.common.retry_utils import retry


def _is_smtp_retryable(exc: BaseException) -> bool:
    """일시적 SMTP 오류(연결·소켓·서버 끊김)만 재시도. 인증 실패·수신 거부 등 영구 오류는 제외."""
    return isinstance(exc, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError))


class MailClient:
    def __init__(self, config):
        self.host = config.EMAIL_HOST
        self.port = config.EMAIL_PORT
        self.user = config.EMAIL_USER
        self.password = config.EMAIL_PASSWORD

    async def send_html(self, to: str, subject: str, html: str) -> None:
        await run_in_threadpool(self._send_sync, to, subject, html)

    def _send_sync(self, to: str, subject: str, html: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.user
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))

        def _op() -> None:
            with smtplib.SMTP_SSL(self.host, self.port) as server:
                server.login(self.user, self.password)
                server.sendmail(self.user, [to], msg.as_string())

        retry(_op, base_delay=0.5, label="SMTP", retryable=_is_smtp_retryable)
        logger.info(f"메일 발송: {to} / {subject}")
