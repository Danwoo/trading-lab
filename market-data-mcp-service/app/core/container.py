from clients.market.market_client import MarketClient
from core.config import settings
from dependency_injector import containers, providers
from repositories.market.market_repository import MarketRepository
from services.market.market_service import MarketService


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Client (외부 연결 — 시세 벤더 / 기본 MOCK 인메모리 픽스처)
    market_client = providers.Singleton(MarketClient, config)

    # Repository (market = 외부 시장 데이터 store, 연결 주입)
    market_repository = providers.Factory(MarketRepository, market_client=market_client)

    # Service (repository 주입)
    market_service = providers.Factory(MarketService, market_repository=market_repository)

    wiring_config = containers.WiringConfiguration(modules=["routers.market.market_router"])
