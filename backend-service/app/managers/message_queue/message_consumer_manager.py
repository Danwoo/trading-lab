# managers/message_queue/message_consumer_manager.py
import asyncio

from core.container import Container
from core.logger import logger
from dependency_injector.wiring import Provide, inject
from fastapi.concurrency import run_in_threadpool
from services.message_queue.message_queue_service import MessageQueueService

POLL_INTERVAL = 5
BATCH_SIZE = 100
ERROR_BACKOFF = 5  # 이터레이션 예외 후 재시도 전 대기(초) — 실패 지속 시 tight-loop/CPU 스핀 방지 (#68)


class MessageConsumerManager:
    """메시지 큐 폴링 소비 및 lifecycle 관리 (worker 프로세스 단일 인스턴스 — web 과 분리되어 1개만 실행)"""

    def __init__(self):
        self.task: asyncio.Task | None = None
        self.should_stop = False

    @inject
    async def start(
        self,
        message_queue_service: MessageQueueService = Provide[Container.message_queue_service],
    ) -> None:
        if self.task and not self.task.done():
            logger.warning("Message consumer already running")
            return

        self.should_stop = False
        logger.info("Starting message consumer...")

        async def loop():
            while not self.should_stop:
                try:
                    processed = await run_in_threadpool(message_queue_service.consume_pending, BATCH_SIZE)
                    if processed:
                        logger.info(f"Message consumer processed {processed} messages")
                    await asyncio.sleep(POLL_INTERVAL)
                except asyncio.CancelledError:
                    raise  # 정상 종료(stop() 의 task.cancel) 신호 — 삼키지 않고 전파해 루프를 끝낸다
                except Exception:
                    # 개별 이터레이션 예외로 task 가 죽지 않게: 로깅 후 백오프하고 계속 폴링 (#68)
                    logger.exception("MSG_CONSUMER_LOOP_ERROR — 이터레이션 실패, 백오프 후 재시도")
                    await asyncio.sleep(ERROR_BACKOFF)

        self.task = asyncio.create_task(loop())

    async def stop(self) -> None:
        logger.info("Stopping message consumer...")
        self.should_stop = True

        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        logger.info("Message consumer stopped successfully")


message_consumer_manager = MessageConsumerManager()
