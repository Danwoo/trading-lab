"""요청 레이트 리밋 + 동시 SSE 스트림 제한 — 단일 uvicorn 프로세스 in-memory 구현.

멀티 워커 환경에서는 Redis 기반 확장 필요. --workers=1 운용 전제.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from core.logger import logger


class RateLimiter:
    """Sliding-window 기반 분당 요청 제한. per_minute=0 이면 비활성."""

    def __init__(self, config) -> None:
        self.per_minute = config.MA_RATE_LIMIT_PER_MINUTE
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """key 에 대해 허용 여부 반환. 허용 시 카운터 증가."""
        if self.per_minute <= 0:
            return True
        now = time.monotonic()
        threshold = now - 60.0
        with self._lock:
            q = self._hits[key]
            while q and q[0] < threshold:
                q.popleft()
            if len(q) >= self.per_minute:
                logger.warning("[RateLimit] quota 초과: key=%s, hits=%d/%d(min)", key, len(q), self.per_minute)
                return False
            q.append(now)
            return True


class StreamSemaphore:
    """동시 SSE 스트림 수 제한. limit=0 이면 비활성."""

    def __init__(self, config) -> None:
        self.limit = config.MA_MAX_CONCURRENT_STREAMS
        self._sem: asyncio.Semaphore | None = None

    def _ensure(self) -> asyncio.Semaphore | None:
        if self.limit <= 0:
            return None
        if self._sem is None:
            # 첫 사용 시 현재 이벤트루프에 바인딩
            self._sem = asyncio.Semaphore(self.limit)
        return self._sem

    @asynccontextmanager
    async def acquire(self):
        sem = self._ensure()
        if sem is None:
            yield
            return
        await sem.acquire()
        try:
            yield
        finally:
            sem.release()
