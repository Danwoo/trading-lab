from contextlib import asynccontextmanager

import uvicorn
from core.container import Container
from core.exception_handler import get_exception_handlers
from core.logger import logger
from core.middlewares import get_middlewares
from core.schema_version import SchemaVersionError, ensure_schema_matches_code
from fastapi import FastAPI
from modules import BackgroundManager, load_managers, register_routers


async def _stop_managers(managers: list[BackgroundManager]) -> None:
    """역순으로 정리한다 — 개별 stop() 실패는 로깅만 하고 나머지 정리를 계속한다.

    한 매니저의 정리 실패가 나머지를 미정리로 남기거나, 기동 실패의 **원인 예외를 가려서는** 안
    된다 — 운영자가 보는 것이 "m2 stop 실패"인데 진짜 문제는 "m3 start 실패"인 상황이 그것이다.
    """
    for manager in reversed(managers):
        try:
            await manager.stop()
        except Exception as e:
            logger.error(f"Manager stop failed: {type(manager).__name__}: {e}", exc_info=True)


def _dispose_sql_client(backend_sql_client) -> None:
    """커넥션 풀 회수 — 기동 실패로 롤백하는 경로에서도 호출된다(안 하면 풀이 남는다)."""
    try:
        backend_sql_client.dispose()
        logger.info("SQL Database disconnect successful")
    except Exception as e:
        logger.error(f"SQL Database disconnect failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 백그라운드 매니저가 앱 안에서 실행 → 매니저 있는 서비스는 단일 프로세스(--workers=1)로 운영 (멀티워커 시 매니저 중복)
    backend_sql_client = app.container.backend_sql_client()
    # 매니저·요청보다 먼저 본다 — 판이 어긋난 채로 서면 최신 스키마를 읽는 경로만 500 으로 죽고
    # 그 사유가 어디에도 안 남는다 (#311). 여기서 멈추면 사유와 처방이 기동 로그에 남는다.
    try:
        ensure_schema_matches_code(backend_sql_client)
    except SchemaVersionError:
        _dispose_sql_client(backend_sql_client)
        raise
    managers = load_managers()
    # 시도된(= start() 를 호출한) 매니저는 성공·실패 무관하게 전부 stop 대상이다 — start() 가 일부
    # 부작용을 낸 뒤 던질 수 있어(예: 스케줄러 스레드를 띄운 뒤 DB 조회에서 실패) "실패했으니 아무
    # 부작용도 없다"고 가정할 수 없다. 매니저 자신의 stop() 이 시작 전 상태에서도 안전하도록
    # (idempotent/가드) 유지하는 것이 이 계약의 전제다 — 기존 3종 모두 그렇다.
    attempted: list[BackgroundManager] = []
    try:
        for manager in managers:
            attempted.append(manager)
            await manager.start()
    except Exception:
        await _stop_managers(attempted)
        _dispose_sql_client(backend_sql_client)
        raise

    yield

    await _stop_managers(managers)
    _dispose_sql_client(backend_sql_client)


app = FastAPI(
    title="Backend API",
    description="Backend API Server",
    version="1.0",
    lifespan=lifespan,
    middleware=get_middlewares(),
    exception_handlers=get_exception_handlers(),
)

app.container = Container()

register_routers(app)

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    except KeyboardInterrupt:
        pass
