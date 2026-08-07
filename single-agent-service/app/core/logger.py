import logging
import os
import queue
from datetime import UTC, datetime
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path

import httpx
from core.config import settings


class _VictoriaLogsSink(logging.Handler):
    def __init__(self, url: str, service_name: str):
        super().__init__()
        self._url = url
        self._service_name = service_name
        self._client = httpx.Client(timeout=2.0)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._client.post(
                self._url,
                json={
                    "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
                    "service": self._service_name,
                    "level": record.levelname,
                    "message": record.getMessage(),
                },
            )
        except Exception:
            pass


class LoggerConfig:
    _instance = None
    _listener: QueueListener | None = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls._create_instance()
        return cls._instance

    @staticmethod
    def _create_instance():
        Path("logs").mkdir(exist_ok=True)

        logging.basicConfig(level=os.getenv("SERVICE_LOGGING_LEVEL", "INFO").upper(), force=True)

        external_loggers = {
            "httpx": logging.WARNING,
            "asyncssh": logging.WARNING,
            "asyncssh.sftp": logging.ERROR,
        }
        for name, level in external_loggers.items():
            logging.getLogger(name).setLevel(level)

        formatter = logging.Formatter(
            fmt="[%(asctime)s +0900] [%(process)d] [%(levelname)s] [%(filename)s] >> %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        logger = logging.getLogger(__name__)
        logger.propagate = False

        error_handler = logging.FileHandler(Path("logs") / "output_error.log")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)

        warning_handler = logging.FileHandler(Path("logs") / "output_warning.log")
        warning_handler.setLevel(logging.WARNING)
        warning_handler.addFilter(lambda record: record.levelno == logging.WARNING)
        warning_handler.setFormatter(formatter)

        info_handler = logging.StreamHandler()
        info_handler.setLevel(logging.INFO)
        info_handler.addFilter(lambda record: record.levelno >= logging.INFO)
        info_handler.setFormatter(formatter)

        logger.addHandler(error_handler)
        logger.addHandler(warning_handler)
        logger.addHandler(info_handler)

        victorialogs_base = settings.VICTORIALOGS_URL.rstrip("/")
        service_name = settings.SERVICE_NAME
        if victorialogs_base and service_name:
            push_url = (
                f"{victorialogs_base}/insert/jsonline"
                "?_msg_field=message&_time_field=timestamp&_stream_fields=service,level"
            )
            log_queue: queue.Queue = queue.Queue(maxsize=10000)
            queue_handler = QueueHandler(log_queue)
            queue_handler.setLevel(logging.WARNING)
            logger.addHandler(queue_handler)
            LoggerConfig._listener = QueueListener(log_queue, _VictoriaLogsSink(push_url, service_name))
            LoggerConfig._listener.start()

        return logger


logger = LoggerConfig.get_instance()
