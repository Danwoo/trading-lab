"""통합 앱의 모듈 등록부 — 라우터·매니저를 한 목록에서 선언한다.

모듈은 폴더 이름(도메인 세그먼트)으로만 존재하고 레이어 우선 폴더 구조는 그대로다.
여기의 목록이 세 곳을 동시에 먹인다: `main.py` 의 라우터 등록, `main.py` lifespan 의 매니저
기동/종료, `core/container.py` 의 DI wiring 대상.

목록이 모듈 경로 문자열인 이유: `core/container.py` 가 이 파일을 import 하는데, 라우터 객체를
여기서 import 하면 `container → modules → routers → container` 순환이 된다.
"""

from importlib import import_module
from typing import Protocol, runtime_checkable

from fastapi import APIRouter, FastAPI


@runtime_checkable
class BackgroundManager(Protocol):
    """앱 수명 동안 도는 백그라운드 매니저 — lifespan 이 기동/종료를 책임진다.

    **`stop()` 은 `start()` 가 던진 뒤에도 안전해야 한다** — `main.py` lifespan 은 다른 매니저의
    기동 실패 시 자신을 포함해 이미 시도된 매니저 전부의 stop() 을 호출한다(#270). `start()` 가
    일부 부작용(예: 내부 스케줄러 기동)을 낸 뒤 예외를 던질 수 있으므로 "시작에 실패했으니 아무
    것도 정리할 게 없다"고 가정하지 않는다 — `stop()` 은 자신이 실제로 무엇을 시작했는지 스스로
    확인(idempotent 가드)한 뒤 정리한다.
    """

    async def start(self) -> None: ...

    async def stop(self) -> None: ...


# 등록 순서가 곧 OpenAPI 문서의 태그·경로 순서
ROUTER_MODULES: list[str] = [
    "routers.portfolio.portfolio_router",
    "routers.watchlist.watchlist_router",
    "routers.nav.nav_router",
    "routers.research_document.research_document_router",
    "routers.file.file_router",
    "routers.chat.chat_router",
    "routers.scheduler.scheduler_router",
    "routers.bar.bar_router",
    "routers.instrument.instrument_router",
    "routers.quote.quote_router",
    "routers.ingest.ingest_router",
    "routers.capability.capability_router",
    "routers.bot.bot_router",
    "routers.backtest.backtest_router",
    "routers.data_key.data_key_router",
]

# (모듈 경로, 매니저 인스턴스 이름) — 기동은 목록 순서, 종료는 역순
MANAGER_MODULES: list[tuple[str, str]] = [
    ("managers.message_queue.message_consumer_manager", "message_consumer_manager"),
    ("managers.nav.nav_producer_manager", "nav_producer_manager"),
    ("managers.scheduler_manager", "scheduler_manager"),
    ("managers.ingest.ingest_worker_manager", "ingest_worker_manager"),
]

# dependency-injector 가 @inject 를 꽂을 대상
WIRING_MODULES: list[str] = [*ROUTER_MODULES, *(path for path, _ in MANAGER_MODULES)]


def load_routers() -> list[APIRouter]:
    """ROUTER_MODULES 선언 순서대로 라우터 객체를 모은다."""
    return [import_module(path).router for path in ROUTER_MODULES]


def load_managers() -> list[BackgroundManager]:
    """MANAGER_MODULES 선언 순서대로 매니저 인스턴스를 모은다."""
    return [getattr(import_module(path), name) for path, name in MANAGER_MODULES]


def register_routers(app: FastAPI) -> None:
    """라우터를 등록한다. prefix 가 겹치면 기동을 거부한다.

    같은 prefix 를 두 번 include 하면 뒤에 온 라우터의 겹치는 경로가 앞의 것에 가려지는데,
    런타임에는 "어떤 라우터가 가려졌는지"가 드러나지 않는다. 합쳐진 앱에서는 실제 위험이라
    등록 시점에 막는다.
    """
    owner_by_prefix: dict[str, str] = {}
    for path, router in zip(ROUTER_MODULES, load_routers(), strict=True):
        if (owner := owner_by_prefix.get(router.prefix)) is not None:
            raise RuntimeError(f"라우터 prefix 중복: '{router.prefix}' 를 {owner} 와 {path} 가 함께 씁니다.")
        owner_by_prefix[router.prefix] = path
        app.include_router(router)
