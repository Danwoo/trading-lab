from clients.web.web_client import WebClient
from core.config import settings
from dependency_injector import containers, providers
from repositories.web.web_repository import WebRepository
from services.web.web_service import WebService


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Client (외부 연결 — Tavily Web Search API)
    web_client = providers.Singleton(WebClient, config)

    # Repository (web = 외부 검색 store, 연결 주입)
    web_repository = providers.Factory(WebRepository, web_client=web_client)

    # Service (repository 주입)
    web_service = providers.Factory(WebService, web_repository=web_repository)

    router_modules = ["routers.web.web_router"]
    wiring_config = containers.WiringConfiguration(modules=router_modules)
