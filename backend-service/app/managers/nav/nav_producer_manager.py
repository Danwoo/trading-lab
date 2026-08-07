# managers/nav/nav_producer_manager.py
import asyncio
import json
import random

from core.container import Container
from core.logger import logger
from dependency_injector.wiring import Provide, inject
from fastapi.concurrency import run_in_threadpool
from services.message_queue.message_queue_service import MessageQueueService

PRODUCE_INTERVAL = 10
ERROR_BACKOFF = 5  # 이터레이션 예외 후 재시도 전 대기(초) — 실패 지속 시 tight-loop/CPU 스핀 방지 (#68)
TOPIC = "nav.snapshot"
SEED_WORKSPACE_ID = 1  # 합성 NAV 시계열이 적재되는 시드 테넌트 (데모 데이터 — 실사용 시 테넌트별 producer 로 확장)

# key: (baseline, step, low, high) — 합성 random-walk 시세/체결 틱 (포트폴리오 NAV·벤치마크 시계열)
_SERIES = {
    "nav": (1000.0, 8.0, 800.0, 1300.0),
    "benchmark": (1000.0, 6.0, 850.0, 1250.0),
    "daily_return": (0.0, 0.6, -8.0, 8.0),
    "drawdown": (-2.0, 0.4, -25.0, 0.0),
}


class NavProducerManager:
    """합성 시세/체결 틱(포트폴리오 NAV 시계열)을 주기적으로 생성해 메시지 큐에 발행 (worker 프로세스 단일 인스턴스)"""

    def __init__(self):
        self.task: asyncio.Task | None = None
        self.should_stop = False
        self._values = {key: base for key, (base, *_rest) in _SERIES.items()}

    def _next_snapshot(self) -> dict:
        for key, (_base, step, low, high) in _SERIES.items():
            self._values[key] = max(low, min(high, self._values[key] + random.uniform(-step, step)))
        return {
            "workspace_id": SEED_WORKSPACE_ID,
            **{k: round(v, 4) for k, v in self._values.items()},
        }

    @inject
    async def start(
        self,
        message_queue_service: MessageQueueService = Provide[Container.message_queue_service],
    ) -> None:
        if self.task and not self.task.done():
            logger.warning("Nav producer already running")
            return

        self.should_stop = False
        logger.info("Starting nav producer...")

        async def loop():
            while not self.should_stop:
                try:
                    snapshot = self._next_snapshot()
                    await run_in_threadpool(
                        message_queue_service.publish,
                        {"topic": TOPIC, "payload": json.dumps(snapshot), "reg_id": "system"},
                    )
                    await asyncio.sleep(PRODUCE_INTERVAL)
                except asyncio.CancelledError:
                    raise  # 정상 종료(stop() 의 task.cancel) 신호 — 삼키지 않고 전파해 루프를 끝낸다
                except Exception:
                    # 개별 이터레이션 예외로 task 가 죽지 않게: 로깅 후 백오프하고 계속 발행 (#68)
                    logger.exception("NAV_PRODUCER_LOOP_ERROR — 이터레이션 실패, 백오프 후 재시도")
                    await asyncio.sleep(ERROR_BACKOFF)

        self.task = asyncio.create_task(loop())

    async def stop(self) -> None:
        logger.info("Stopping nav producer...")
        self.should_stop = True

        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("Nav producer stopped successfully")


nav_producer_manager = NavProducerManager()
