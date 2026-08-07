from clients.fx.fx_rate_client import FxRateClient
from clients.portfolio.portfolio_client import PortfolioClient
from core.config import settings
from dependency_injector import containers, providers
from repositories.portfolio.portfolio_repository import PortfolioRepository
from services.portfolio.portfolio_service import PortfolioService


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Client (데이터 소스 — 기본 in-memory MOCK, USE_REAL_API=true 면 브로커리지 REST API)
    portfolio_client = providers.Singleton(PortfolioClient, config)

    # Client (환율 소스 — market-data-mcp /market/fx REST, 기준통화 환산 시에만 호출)
    fx_rate_client = providers.Singleton(FxRateClient, config)

    # Repository (브로커리지/포트폴리오 store, 연결 주입)
    portfolio_repository = providers.Factory(PortfolioRepository, portfolio_client=portfolio_client)

    # Service (repository·환율 클라이언트 주입)
    portfolio_service = providers.Factory(
        PortfolioService,
        portfolio_repository=portfolio_repository,
        fx_rate_client=fx_rate_client,
    )

    router_modules = ["routers.portfolio.portfolio_router"]
    wiring_config = containers.WiringConfiguration(modules=router_modules)
