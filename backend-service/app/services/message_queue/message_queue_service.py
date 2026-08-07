# services/message_queue/message_queue_service.py
import json

from core.logger import logger
from repositories.message_queue.message_queue_repository import MessageQueueRepository
from services.nav.nav_service import NavService

MAX_RETRIES = 5  # 일시 오류 재시도 상한 — 소진 시 터미널 'failed'(데드레터)


class MessageQueueService:
    def __init__(self, message_queue_repository: MessageQueueRepository, nav_service: NavService):
        self.message_queue_repository = message_queue_repository
        self.nav_service = nav_service

    def publish(self, args: dict) -> tuple:
        """메시지 발행 — producer 가 topic/payload 를 큐에 적재 (실사용 시 비즈니스 트랜잭션 내 호출 가능)"""
        return self.message_queue_repository.insert_message(args)

    def consume_pending(self, limit: int) -> int:
        """대기 메시지 배치 소비 → 성공 done / 실패 failed 마킹, 처리 건수 반환"""
        messages = self.message_queue_repository.select_pending({"limit": limit})

        processed = 0
        for message in messages:
            try:
                self._dispatch(message)
            except Exception as e:
                self.message_queue_repository.mark_failed(
                    {
                        "id": message["id"],
                        "error": str(e)[:500],
                        "max_retries": MAX_RETRIES,
                        "mod_id": "system",
                    }
                )
                continue

            # dispatch 성공 후에만 터미널 done — mark_done 이 실패해도 실패로 오분류하지 않는다.
            # 이때 메시지는 pending 으로 남아 다음 폴에서 멱등 재소비된다(_dispatch 가 멱등).
            try:
                self.message_queue_repository.mark_done({"id": message["id"], "mod_id": "system"})
                processed += 1
            except Exception:
                logger.exception(f"MQ_MARK_DONE_FAILED id={message['id']} — will re-consume idempotently")
        return processed

    def _dispatch(self, message: dict) -> None:
        """메시지 소비 — topic 별 핸들러 라우팅 (신규 topic 은 여기 분기 추가).

        핸들러는 message id 로 멱등해야 한다 — at-least-once 라 크래시/재기동 시 재호출될 수 있다.
        """
        topic = message["topic"]
        if topic == "nav.snapshot":
            self.nav_service.record_snapshot(json.loads(message["payload"]), message["id"])
        else:
            logger.info(f"MQ_CONSUME id={message['id']} topic={topic}")
