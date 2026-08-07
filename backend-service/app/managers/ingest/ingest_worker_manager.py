"""적재 워커 — `tn_ingest_run` 을 폴링해 잡을 실행하는 앱 수명 백그라운드 루프.

anti-patterns 룰 13 의 패턴을 따른다: `lifespan` 에서 `asyncio.create_task` + instance attr 보관
+ shutdown 시 `cancel()` + `await`. 참조 없이 두면 GC 되어 조용히 죽는다.

루프 예외는 삼키지 않고 로그 + back-off + continue 다(룰 9 의 Daemon loop continuation 예외) —
잡 하나의 실패로 워커 전체가 멈추면 그 뒤 모든 적재가 조용히 사라진다.

DB 접근(폴링·상태 갱신)은 sync 라 `run_in_threadpool` 로 감싼다. 어댑터 호출은 `async` 라
그대로 await 한다 — 적재가 도는 동안 API 응답이 막히지 않는 이유가 이 구분이다.
"""

import asyncio

from core.container import Container
from core.logger import logger
from dependency_injector.wiring import Provide, inject
from fastapi.concurrency import run_in_threadpool
from services.ingest.ingest_service import IngestService

POLL_INTERVAL = 5  # 큐가 비었을 때 다음 폴링까지 대기(초)
ERROR_BACKOFF = 15  # 이터레이션 예외 후 재시도 전 대기(초) — 실패 지속 시 tight-loop 방지


class IngestWorkerManager:
    """적재 잡 폴링·실행 (worker 프로세스 단일 인스턴스 — `--workers=1`)."""

    def __init__(self):
        self.task: asyncio.Task | None = None
        self.should_stop = False

    @inject
    async def start(
        self,
        ingest_service: IngestService = Provide[Container.ingest_service],
    ) -> None:
        if self.task and not self.task.done():
            logger.warning("Ingest worker already running")
            return

        self.should_stop = False
        logger.info("Starting ingest worker...")

        async def loop():
            while not self.should_stop:
                try:
                    run = await run_in_threadpool(ingest_service.claim_next_queued_run)
                    if run is None:
                        await asyncio.sleep(POLL_INTERVAL)
                        continue
                    logger.info(f"적재 잡 {run['run_id']} 실행 — {run['source']}/{run['job_kind']} {run.get('scope')}")
                    await ingest_service.run_job(run)
                except asyncio.CancelledError:
                    raise  # 정상 종료 신호 — 삼키지 않고 전파해 루프를 끝낸다
                except Exception:
                    logger.exception("INGEST_WORKER_LOOP_ERROR — 이터레이션 실패, 백오프 후 재시도")
                    await asyncio.sleep(ERROR_BACKOFF)

        self.task = asyncio.create_task(loop())

    async def stop(self) -> None:
        """`start()` 가 던진 뒤에도 안전하다 — 자기가 무엇을 시작했는지 확인한 뒤 정리한다."""
        logger.info("Stopping ingest worker...")
        self.should_stop = True

        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None


ingest_worker_manager = IngestWorkerManager()
